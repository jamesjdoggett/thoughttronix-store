from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, FormView, TemplateView

from .forms import (
    EmailCorrectionForm,
    EmailReplacementForm,
    SecurityPasswordChangeForm,
    SignInForm,
    SignupForm,
)
from .models import SecurityRequest
from .passwords import send_password_change_alert
from .verification import reserve_request, send_verification, verify_email_link


class SignupView(CreateView):
    """Create an unverified customer with Django's built-in password handling."""

    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")

    def post(self, request, *args, **kwargs):
        if not reserve_request(request.META.get("REMOTE_ADDR", "unknown"), signup=True):
            self.object = None
            form = self.form_class()
            messages.error(
                request, "Too many signup attempts. Please try again in an hour."
            )
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save()
        except IntegrityError:
            form.add_error(
                None,
                "Username or email is unavailable. This email is unavailable if already assigned.",
            )
            return self.form_invalid(form)
        messages.success(self.request, "Account created - you can now sign in.")
        messages.info(
            self.request,
            send_verification(self.request, self.object, count_network=False),
        )
        return HttpResponseRedirect(self.get_success_url())


class CheckoutContinuationMixin:
    """Carry only the named checkout destination through signed-in controls."""

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            checkout_next=self.request.GET.get("next") == reverse("orders:checkout"),
            **kwargs,
        )

    def get_success_url(self):
        destination = str(self.success_url)
        if self.request.GET.get("next") == reverse("orders:checkout"):
            destination += "?next=" + reverse("orders:checkout")
        return destination


class VerificationRequestView(
    CheckoutContinuationMixin, LoginRequiredMixin, TemplateView
):
    template_name = "accounts/verification_request.html"
    success_url = reverse_lazy("accounts:verification_request")

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            can_verify_email=self.request.user.can_verify_email(), **kwargs
        )

    def post(self, request, *args, **kwargs):
        messages.info(request, send_verification(request, request.user))
        return HttpResponseRedirect(self.get_success_url())


class VerifyEmailView(TemplateView):
    template_name = "accounts/verification_result.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = verify_email_link(kwargs["token"])
        user = result.user
        context["verification_message"] = result.message
        context["verification_status"] = result.status
        context["verified"] = user is not None
        context["matching_account"] = (
            user is not None and self.request.user.pk == user.pk
        )
        return context


class SignInView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = SignInForm

    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.user.email_verified:
            messages.info(
                self.request,
                "Add or verify your email in Account security to prepare your recovery address.",
            )
        return response


class SecurityOverviewView(CheckoutContinuationMixin, LoginRequiredMixin, TemplateView):
    template_name = "accounts/security.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            can_verify_email=self.request.user.can_verify_email(), **kwargs
        )


class SecurityPasswordChangeView(PasswordChangeView):
    """Change credentials while retaining only the submitting session."""

    template_name = "accounts/password_change.html"
    form_class = SecurityPasswordChangeForm
    success_url = reverse_lazy("accounts:security")

    def form_valid(self, form):
        response = super().form_valid(form)
        send_password_change_alert(self.request.user)
        messages.success(
            self.request, "Password changed. Other sessions have been signed out."
        )
        return response


class EmailCorrectionView(CheckoutContinuationMixin, LoginRequiredMixin, FormView):
    template_name = "accounts/email_correction.html"
    form_class = EmailCorrectionForm
    success_url = reverse_lazy("accounts:security")

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}

    def post(self, request, *args, **kwargs):
        # Count invalid forms and suppressed sends as network requests as well.
        self.send_decision = SecurityRequest.objects.reserve_result(
            request.META.get("REMOTE_ADDR", "unknown"), network_only=True
        )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                corrected = self.request.user.correct_unverified_email(
                    form.cleaned_data["email"]
                )
        except IntegrityError:
            form.add_error("email", "This email is unavailable")
            return self.form_invalid(form)
        if not corrected:
            form.add_error(None, "Your account changed. Reload and try again.")
            return self.form_invalid(form)
        messages.success(
            self.request, "Email address saved. Verify it using the emailed link."
        )
        if self.send_decision:
            messages.info(
                self.request,
                send_verification(self.request, self.request.user, count_network=False),
            )
        else:
            messages.info(
                self.request,
                self.send_decision.message,
            )
        return super().form_valid(form)


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        # Flash after super() has flushed the session, or the message
        # would be wiped along with it.
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have signed out.")
        return response


class EmailReplacementView(EmailCorrectionView):
    """Stage a replacement while preserving the verified current address."""

    template_name = "accounts/email_replacement.html"
    form_class = EmailReplacementForm

    def form_valid(self, form):
        if not self.request.user.stage_email_replacement(form.cleaned_data["email"]):
            form.add_error(None, "Your account changed. Reload and try again.")
            return self.form_invalid(form)
        messages.success(
            self.request,
            "Replacement saved. Your current verified email stays active until verification.",
        )
        messages.info(
            self.request,
            send_verification(self.request, self.request.user, count_network=False)
            if self.send_decision
            else self.send_decision.message,
        )
        return HttpResponseRedirect(self.get_success_url())


class CancelEmailReplacementView(
    CheckoutContinuationMixin, LoginRequiredMixin, TemplateView
):
    """Cancel only the signed-in account's pending replacement."""

    success_url = reverse_lazy("accounts:security")
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        if request.user.stage_email_replacement(""):
            messages.success(
                request, "Pending email change cancelled. Its links no longer work."
            )
        else:
            messages.info(request, "Your account changed. Reload and try again.")
        return HttpResponseRedirect(self.get_success_url())
