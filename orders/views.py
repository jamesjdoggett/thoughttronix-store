"""Cart and checkout views — thin per the architecture convention.

The three HTMX interactions of the core live here: add-to-cart, quantity
change, and line removal. Each renders a partial (never ``base.html``);
the responses carry the navbar badge as an out-of-band swap via the
``oob_badge`` context flag. Checkout is conventional full-page work:
validate the form, hand everything to ``place_order``.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from accounts.mixins import StaffRequiredMixin
from products.models import Product

from .forms import CheckoutForm, CouponCodeForm, CouponForm, OrderStatusForm
from .models import Cart, CartItem, Coupon, Order
from .services import place_order, quote_order


class CartView(LoginRequiredMixin, TemplateView):
    """The customer's cart page."""

    template_name = "orders/cart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart"] = Cart.for_user(self.request.user)
        return context


class AddToCartView(LoginRequiredMixin, View):
    """HTMX: add a product; the button swaps and the badge updates OOB.

    Looks the product up through ``available()``, so adding an
    unavailable product 404s — the same not-for-sale semantics as the
    public catalog.
    """

    def post(self, request, pk):
        product = get_object_or_404(Product.objects.available(), pk=pk)
        item = Cart.for_user(request.user).add(product)
        return render(
            request,
            "orders/partials/_add_button.html",
            {"product": product, "in_cart": item.quantity, "oob_badge": True},
        )


class CartItemActionView(LoginRequiredMixin, View):
    """Base for HTMX line mutations: act, then re-render the cart contents.

    Items are always fetched through the owner's cart — never by bare pk.
    """

    def post(self, request, pk):
        item = get_object_or_404(CartItem, pk=pk, cart__user=request.user)
        self.act(item)
        return render(
            request,
            "orders/partials/_cart_contents.html",
            {"cart": item.cart, "oob_badge": True},
        )

    def act(self, item):
        raise NotImplementedError


class IncrementCartItemView(CartItemActionView):
    def act(self, item):
        item.increment()


class DecrementCartItemView(CartItemActionView):
    def act(self, item):
        item.decrement()


class RemoveCartItemView(CartItemActionView):
    def act(self, item):
        item.delete()


class CheckoutView(LoginRequiredMixin, FormView):
    """The single checkout page: validate the form, hand off to the service.

    A cart that can't check out (empty, or holding a product that has
    since become unavailable) is sent back to the cart page to be fixed —
    ``place_order`` enforces the same rules transactionally as the
    backstop.
    """

    template_name = "orders/checkout.html"
    form_class = CheckoutForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        cart = Cart.for_user(request.user)
        if not cart.items.exists():
            messages.info(request, "Your cart is empty — add something first.")
            return redirect("orders:cart")
        unavailable = [
            line.product.name for line in cart.lines() if not line.product.is_available
        ]
        if unavailable:
            messages.warning(
                request,
                f"No longer available: {', '.join(unavailable)}. "
                "Remove them from the cart to check out.",
            )
            return redirect("orders:cart")
        try:
            return super().dispatch(request, *args, **kwargs)
        except ValueError as error:
            # A cart may change after the initial availability check.
            messages.warning(request, str(error))
            return redirect("orders:cart")

    def load_preview(self):
        self.cart = Cart.for_user(self.request.user)
        self.coupon_error = ""
        try:
            self.quote = quote_order(self.cart, coupon_code=self.cart.coupon_code)
        except ValueError as error:
            self.coupon_error = str(error)
            self.quote = quote_order(self.cart)

    def checkout_response(self, *, form=None, error="", code=None):
        if form is None:
            form = CheckoutForm(
                initial=self.request.POST if self.request.method == "POST" else None,
                payment_required=bool(self.quote.total),
            )
        template = self.template_name
        if self.request.headers.get("HX-Request") == "true":
            template = "orders/partials/_checkout.html"
        return render(
            self.request,
            template,
            {
                "form": form,
                "cart": self.cart,
                "quote": self.quote,
                "pricing_snapshot": self.quote.signed_snapshot(),
                "coupon_error": self.coupon_error,
                "checkout_error": error,
                "coupon_input": self.cart.coupon_code if code is None else code,
            },
        )

    def get(self, request, *args, **kwargs):
        self.load_preview()
        return self.checkout_response()

    def post(self, request, *args, **kwargs):
        cart = Cart.for_user(request.user)
        action = request.POST.get("action", "place")
        code = request.POST.get("coupon_code", "")
        if action in {"apply", "remove"}:
            code_form = CouponCodeForm({"code": code})
            if action == "apply" and not code_form.is_valid():
                self.load_preview()
                return self.checkout_response(
                    error=" ".join(code_form.errors["code"]), code=code
                )
            cart.coupon_code = (
                code_form.cleaned_data["code"] if action == "apply" else ""
            )
            cart.save(update_fields=["coupon_code"])
            self.load_preview()
            return self.checkout_response()

        self.load_preview()
        if Coupon.normalize_code(code) != self.cart.coupon_code:
            return self.checkout_response(
                error="Apply your entered coupon code, or remove it, before placing the order.",
                code=code,
            )
        if self.coupon_error:
            return self.checkout_response()
        try:
            self.quote.check_snapshot(request.POST.get("pricing_snapshot", ""))
        except ValueError as error:
            return self.checkout_response(error=str(error))
        form = CheckoutForm(request.POST, payment_required=bool(self.quote.total))
        if not form.is_valid():
            return self.checkout_response(form=form)
        try:
            order = place_order(
                self.cart,
                request.user,
                form.cleaned_data,
                coupon_code=self.cart.coupon_code,
                expected_snapshot=request.POST.get("pricing_snapshot", ""),
            )
        except ValueError as error:
            # Refresh both payment requirements and the displayed quote.
            if not self.cart.items.exists():
                messages.info(request, str(error))
                return redirect("orders:cart")
            try:
                self.load_preview()
            except ValueError:
                messages.warning(request, str(error))
                return redirect("orders:cart")
            return self.checkout_response(error=str(error))
        except OperationalError as error:
            if "locked" not in str(error).lower():
                raise
            return self.checkout_response(
                error="Checkout is busy. Please review your order and try again."
            )
        messages.success(request, f"Order {order.number} placed. Thank you!")
        return redirect(reverse("orders:confirmation", kwargs={"pk": order.pk}))


class OwnOrdersMixin(LoginRequiredMixin):
    """Orders are always fetched through the owner — never by bare pk."""

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)


class OrderConfirmationView(OwnOrdersMixin, DetailView):
    template_name = "orders/confirmation.html"
    context_object_name = "order"


class OrderHistoryView(OwnOrdersMixin, ListView):
    """The customer's orders, most recent first per the model ordering."""

    template_name = "orders/order_history.html"
    context_object_name = "orders"


class OrderDetailView(OwnOrdersMixin, DetailView):
    template_name = "orders/order_detail.html"
    context_object_name = "order"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("items")


# --- The back office --------------------------------------------------------
#
# Staff-only order oversight: every customer's orders, filterable by
# status, with the status dropdown on the detail page. The ``section``
# context entry drives the active tab in the staff shell.


class ManageOrderListView(StaffRequiredMixin, ListView):
    """All orders, most recent first, filterable via ``?status=``."""

    template_name = "orders/manage_orders.html"
    context_object_name = "orders"
    paginate_by = 20
    extra_context = {"section": "orders"}

    def get_queryset(self):
        orders = Order.objects.select_related("user")
        status = self.request.GET.get("status", "")
        if status in Order.Status.values:
            orders = orders.filter(status=status)
        return orders

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["statuses"] = Order.Status.choices
        context["active_status"] = self.request.GET.get("status", "")
        return context


class ManageOrderDetailView(StaffRequiredMixin, DetailView):
    """Any order's detail, with the status form alongside."""

    template_name = "orders/manage_order_detail.html"
    context_object_name = "order"
    queryset = Order.objects.select_related("user").prefetch_related("items")
    extra_context = {"section": "orders"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_form"] = OrderStatusForm(instance=self.object)
        return context


class UpdateOrderStatusView(StaffRequiredMixin, View):
    """POST-only: set an order's status from the back-office dropdown."""

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"{order.number} is now {order.get_status_display().lower()}.",
            )
        else:
            messages.error(request, "That isn't a status an order can have.")
        return redirect("orders:manage_order_detail", pk=order.pk)


class ManageCouponListView(StaffRequiredMixin, ListView):
    model = Coupon
    template_name = "orders/manage_coupons.html"
    context_object_name = "coupons"
    extra_context = {"section": "coupons"}


class ManageCouponCreateView(StaffRequiredMixin, SuccessMessageMixin, CreateView):
    model = Coupon
    form_class = CouponForm
    template_name = "orders/manage_coupon_form.html"
    success_url = reverse_lazy("orders:manage_coupons")
    success_message = "Coupon created."
    extra_context = {"section": "coupons"}


class ManageCouponUpdateView(StaffRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Coupon
    form_class = CouponForm
    template_name = "orders/manage_coupon_form.html"
    success_url = reverse_lazy("orders:manage_coupons")
    success_message = "Coupon updated. Existing orders are unchanged."
    extra_context = {"section": "coupons"}
