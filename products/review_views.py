"""Customer review endpoints scoped to the public product page."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View

from .forms import ReviewForm
from .models import Product, Review
from .review_services import can_review, publish_review, review_context


class ReviewView(LoginRequiredMixin, View):
    """Shared product scoping, author access, and enhanced responses."""

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

    def render_form(self, product, *, review=None, form=None, deleting=False):
        """Keep invalid fields in the originating inline form or a full page."""
        context = {
            "product": product,
            "review": review,
            "form": form,
            "location": self.get_location(),
            "deleting": deleting,
        }
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
            form=ReviewForm(instance=review, auto_id=f"id_{self.get_location()}_%s"),
        )

    def post(self, request, slug, pk):
        product = get_object_or_404(Product, slug=slug)
        review = self.get_review(product, pk)
        form = ReviewForm(
            request.POST, instance=review, auto_id=f"id_{self.get_location()}_%s"
        )
        if not form.is_valid():
            return self.render_form(product, review=review, form=form)
        attribution = {}
        if request.user.is_staff and review.author_id != request.user.pk:
            attribution = {
                "staff_editor": request.user,
                "staff_edited_at": timezone.now(),
            }
        # Posting time and author survive moderation; author edits retain attribution.
        Review.objects.filter(pk=review.pk).update(
            **form.cleaned_data, **attribution, revision=F("revision") + 1
        )
        review.refresh_from_db()
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
