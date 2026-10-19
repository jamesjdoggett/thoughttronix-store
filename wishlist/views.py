from urllib.parse import parse_qs, urlsplit

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from orders.models import Cart
from products.models import Product

from .models import Wishlist, WishlistEntry


class WishlistView(LoginRequiredMixin, ListView):
    template_name = "wishlist/detail.html"
    context_object_name = "entries"
    paginate_by = 20

    def paginate_queryset(self, queryset, page_size):
        paginator = self.get_paginator(queryset, page_size)
        page = paginator.get_page(self.request.GET.get(self.page_kwarg, 1))
        return paginator, page, page.object_list, page.has_other_pages()

    def get_queryset(self):
        return WishlistEntry.objects.filter(
            wishlist__user=self.request.user
        ).select_related("product__category")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wishlist = Wishlist.objects.filter(user=self.request.user).first()
        if wishlist and wishlist.share_token:
            context["sharing_url"] = self.request.build_absolute_uri(
                reverse("wishlist:shared", args=[wishlist.share_token])
            )
        return context


class WishlistMutationView(LoginRequiredMixin, View):
    http_method_names = ["post", "options"]

    def get_return_url(self):
        destination = self.request.POST.get("next", "")
        if destination.startswith("/") and url_has_allowed_host_and_scheme(
            destination, allowed_hosts=set(), require_https=self.request.is_secure()
        ):
            return destination
        return reverse("wishlist:detail")

    def handle_no_permission(self):
        response = redirect_to_login(self.get_return_url())
        if self.request.headers.get("HX-Request") == "true":
            return HttpResponse(headers={"HX-Redirect": response.url})
        return response


class EnableSharingView(WishlistMutationView):
    def post(self, request):
        Wishlist.for_user(request.user).enable_sharing()
        return redirect("wishlist:detail")


class DisableSharingView(WishlistMutationView):
    def post(self, request):
        wishlist = Wishlist.objects.filter(user=request.user).first()
        if wishlist:
            wishlist.disable_sharing()
        return redirect("wishlist:detail")


class SharedWishlistView(ListView):
    template_name = "wishlist/shared.html"
    context_object_name = "entries"
    paginate_by = 20

    def get(self, request, *args, **kwargs):
        self.wishlist = Wishlist.objects.filter(share_token=kwargs["token"]).first()
        if self.wishlist is None:
            return render(request, "wishlist/unavailable.html", status=404)
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return self.wishlist.entries.select_related("product__category")


class AddSavedProductToCartView(WishlistMutationView):
    def post(self, request, pk):
        entry = get_object_or_404(
            WishlistEntry.objects.select_related("product"),
            wishlist__user=request.user,
            product_id=pk,
        )
        product = entry.product
        error = ""
        if product.is_available:
            item = Cart.for_user(request.user).add(product)
            feedback = f"{product.name} added to cart. Quantity: {item.quantity}."
        else:
            error = "This product is no longer available and could not be added to your cart."
            feedback = error
        if request.headers.get("HX-Request") == "true":
            return render(
                request,
                "wishlist/partials/_cart_control.html",
                {
                    "product": product,
                    "return_url": self.get_return_url(),
                    "cart_feedback": feedback,
                    "cart_error": error,
                    "oob_badge": True,
                },
            )
        if error:
            messages.error(request, feedback)
        else:
            messages.success(request, feedback)
        return redirect(self.get_return_url())


class SaveProductView(WishlistMutationView):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            Wishlist.for_user(request.user).add(product)
        except Product.DoesNotExist:
            # The product may have been deleted after the initial lookup.
            messages.error(
                request, "This product no longer exists and could not be saved."
            )
        except ValueError as error:
            if request.headers.get("HX-Request") == "true":
                product.refresh_from_db()
                return render(
                    request,
                    "wishlist/partials/_save_control.html",
                    {
                        "product": product,
                        "is_saved": False,
                        "return_url": self.get_return_url(),
                        "save_error": str(error),
                        "oob_count": True,
                    },
                )
            messages.error(request, str(error))
        else:
            if request.headers.get("HX-Request") == "true":
                return render(
                    request,
                    "wishlist/partials/_save_control.html",
                    {
                        "product": product,
                        "is_saved": True,
                        "return_url": self.get_return_url(),
                        "oob_count": True,
                    },
                )
        return redirect(self.get_return_url())


class RemoveProductView(WishlistMutationView):
    def post(self, request, pk):
        WishlistEntry.objects.filter(
            wishlist__user=request.user, product_id=pk
        ).delete()
        destination = self.get_return_url()
        if request.headers.get("HX-Request") == "true" and urlsplit(
            destination
        ).path == reverse("wishlist:detail"):
            entries = WishlistEntry.objects.filter(
                wishlist__user=request.user
            ).select_related("product__category")
            page_number = parse_qs(urlsplit(destination).query).get("page", ["1"])[0]
            page = Paginator(entries, WishlistView.paginate_by).get_page(page_number)
            return render(
                request,
                "wishlist/partials/_contents.html",
                {
                    "entries": page.object_list,
                    "page_obj": page,
                    "is_paginated": page.has_other_pages(),
                    "return_url": destination,
                    "oob_count": True,
                },
            )
        if request.headers.get("HX-Request") == "true":
            product = get_object_or_404(Product, pk=pk)
            return render(
                request,
                "wishlist/partials/_save_control.html",
                {
                    "product": product,
                    "is_saved": False,
                    "return_url": destination,
                    "oob_count": True,
                },
            )
        return redirect(self.get_return_url())
