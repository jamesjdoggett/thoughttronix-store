"""Customer review endpoints scoped to the public product page."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views import View

from .forms import ReviewEditForm, ReviewForm
from .models import Product, Review
from .review_services import can_review, publish_review, review_context


class ReviewCsrfView(View):
    """Refresh a drafting form's token without replacing its inputs."""

    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        """Return current CSRF state even when the session has expired."""
        product = get_object_or_404(Product, slug=slug)
        response = render(
            request,
            "products/partials/_review_csrf.html",
            {
                "product": product,
                "refreshed": True,
                "save_failed": request.GET.get("failed") == "1",
            },
        )
        response["Cache-Control"] = "no-store"
        return response


class ReviewView(LoginRequiredMixin, View):
    """Shared product scoping, author access, and enhanced responses."""

    def handle_no_permission(self) -> HttpResponse:
        """Retain enhanced save drafts when their authentication has expired."""
        if (
            self.request.headers.get("HX-Request") == "true"
            and self.request.method == "POST"
            and self.request.resolver_match.url_name in {"review_create", "review_edit"}
        ):
            product = get_object_or_404(Product, slug=self.kwargs["slug"])
            editing = self.request.resolver_match.url_name == "review_edit"
            form_class = ReviewEditForm if editing else ReviewForm
            form = form_class(
                self.request.POST,
                auto_id=f"id_{self.get_location()}_%s" if editing else "id_create_%s",
            )
            form.is_valid()
            form.add_error(
                None,
                "Your session has expired. Sign in in another tab, then return "
                "here to retry. Your draft has been kept.",
            )
            review = Review(pk=self.kwargs["pk"], product=product) if editing else None
            response = self.render_form(product, review=review, form=form)
            response["Cache-Control"] = "no-store"
            return response
        return super().handle_no_permission()

    def get_review(self, product, pk):
        """Resolve a review within its product for its author or staff."""
        review = get_object_or_404(
            Review.objects.select_related("author"), product=product, pk=pk
        )
        if review.author_id != self.request.user.pk and not self.request.user.is_staff:
            raise PermissionDenied
        return review

    def get_location(self):
        """Use only the two supported representations for DOM targets."""
        value = self.request.POST.get("location", self.request.GET.get("location"))
        return "public" if value == "public" else "own"

    def render_form(
        self,
        product,
        *,
        review=None,
        form=None,
        deleting=False,
        conflict=False,
        deleted=False,
    ):
        """Keep invalid fields in the originating inline form or a full page."""
        context = {
            "product": product,
            "review": review,
            "form": form,
            "location": self.get_location(),
            "deleting": deleting,
            "conflict": conflict,
            "deleted": deleted,
            "enhanced": self.request.headers.get("HX-Request") == "true",
        }
        if conflict or deleted:
            context.update(review_context(product, self.request.user))
        template = "products/review_form.html"
        if self.request.headers.get("HX-Request") == "true":
            template = (
                "products/partials/_review_confirmation.html"
                if deleting
                else "products/partials/_review_form.html"
            )
        return render(self.request, template, context)

    def success(
        self, product, *, mutation, review=None, deleted_pk=None, deleted_author_id=None
    ):
        """Synchronize affected copies without replacing the review list."""
        if self.request.headers.get("HX-Request") != "true":
            return HttpResponseRedirect(product.get_absolute_url() + "#reviews")
        context = review_context(product, self.request.user)
        context.update(
            mutation=mutation,
            review=review,
            deleted_pk=deleted_pk,
            update_own=(review.author_id if review is not None else deleted_author_id)
            == self.request.user.pk,
            review_form=ReviewForm(auto_id="id_create_%s"),
        )
        response = render(
            self.request, "products/partials/_review_updates.html", context
        )
        response["HX-Reswap"] = "none"
        return response


class ReviewEditView(ReviewView):
    """Display and submit a purchaser's inline edit form."""

    def deleted_response(self, product, pk):
        """Retain a pending draft without providing a way to recreate its row."""
        review = Review(pk=pk, product=product)
        form = ReviewEditForm(
            self.request.POST,
            auto_id=f"id_{self.get_location()}_%s",
        )
        form.is_valid()
        form.add_error(
            None,
            "This review was deleted while you were editing. Your draft is kept "
            "below for copying, but it cannot be saved to the deleted review. "
            "Return to the product to check whether you can publish a new review.",
        )
        return self.render_form(product, review=review, form=form, deleted=True)

    def get(self, request, slug, pk):
        product = get_object_or_404(Product, slug=slug)
        review = self.get_review(product, pk)
        if "cancel" in request.GET:
            if request.headers.get("HX-Request") != "true":
                return HttpResponseRedirect(product.get_absolute_url() + "#reviews")
            return render(
                request,
                "products/partials/_review_card.html",
                {
                    "product": product,
                    "review": review,
                    "location": self.get_location(),
                },
            )
        return self.render_form(
            product,
            review=review,
            form=ReviewEditForm(
                instance=review, auto_id=f"id_{self.get_location()}_%s"
            ),
        )

    def post(self, request, slug, pk):
        product = get_object_or_404(Product, slug=slug)
        try:
            review = self.get_review(product, pk)
        except Http404:
            if Review.objects.filter(pk=pk).exists():
                raise
            return self.deleted_response(product, pk)
        form = ReviewEditForm(request.POST, auto_id=f"id_{self.get_location()}_%s")
        if not form.is_valid():
            return self.render_form(product, review=review, form=form)
        if not review.edit(**form.cleaned_data, editor=request.user):
            try:
                review.refresh_from_db()
            except Review.DoesNotExist:
                return self.deleted_response(product, pk)
            data = request.POST.copy()
            data["revision"] = review.revision
            form = ReviewEditForm(data, auto_id=f"id_{self.get_location()}_%s")
            form.is_valid()
            form.add_error(
                None,
                "This review changed while you were editing. Your draft has been "
                "kept. Compare the latest saved version below, then Save to retry.",
            )
            return self.render_form(product, review=review, form=form, conflict=True)
        try:
            review.refresh_from_db()
        except Review.DoesNotExist:
            return self.deleted_response(product, pk)
        return self.success(product, mutation="edit", review=review)


class ReviewCreateView(ReviewView):
    """Submit a new review from a product's dedicated author area."""

    def post(self, request, slug):
        product = get_object_or_404(Product, slug=slug)
        if not can_review(request.user, product):
            raise PermissionDenied("A qualifying purchase is required.")
        form = ReviewForm(request.POST, auto_id="id_create_%s")
        if form.is_valid():
            try:
                review = publish_review(request.user, product, **form.cleaned_data)
            except ValueError as error:
                review = Review.objects.filter(
                    author=request.user, product=product, **form.cleaned_data
                ).first()
                if review is not None:
                    return self.success(
                        product, mutation="recover_create", review=review
                    )
                form.add_error(None, str(error))
            else:
                return self.success(product, mutation="create", review=review)
        return self.render_form(product, form=form)


class ReviewDeleteView(ReviewView):
    """Confirm removal before accepting the author's deletion POST."""

    def get(self, request, slug, pk):
        product = get_object_or_404(Product, slug=slug)
        review = self.get_review(product, pk)
        return self.render_form(product, review=review, deleting=True)

    def post(self, request, slug, pk):
        product = get_object_or_404(Product, slug=slug)
        review = self.get_review(product, pk)
        author_id = review.author_id
        review.delete()
        return self.success(
            product, mutation="delete", deleted_pk=pk, deleted_author_id=author_id
        )
