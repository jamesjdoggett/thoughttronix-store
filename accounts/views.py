from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, TemplateView

from .forms import EmailCorrectionForm, SignInForm, SignupForm
from .verification import reserve_request, send_verification, verify_token


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


class VerificationRequestView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/verification_request.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            can_verify_email=self.request.user.can_verify_email(), **kwargs
        )

    def post(self, request, *args, **kwargs):
        messages.info(request, send_verification(request, request.user))
        return HttpResponseRedirect(reverse_lazy("accounts:verification_request"))


class VerifyEmailView(TemplateView):
    template_name = "accounts/verification_result.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = verify_token(kwargs["token"])
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


class SecurityOverviewView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/security.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            can_verify_email=self.request.user.can_verify_email(), **kwargs
        )


class EmailCorrectionView(LoginRequiredMixin, FormView):
    template_name = "accounts/email_correction.html"
    form_class = EmailCorrectionForm
    success_url = reverse_lazy("accounts:security")

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "user": self.request.user}

    def post(self, request, *args, **kwargs):
        # Count invalid forms and suppressed sends as network requests as well.
        self.send_allowed = reserve_request(
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
        if self.send_allowed:
            messages.info(
                self.request,
                send_verification(self.request, self.request.user, count_network=False),
            )
        else:
            messages.info(
                self.request,
                "Please wait before retrying; network email request limits apply.",
            )
        return super().form_valid(form)


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        # Flash after super() has flushed the session, or the message
        # would be wiped along with it.
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have signed out.")
        return response
