from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import SignInForm, SignupForm
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


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        # Flash after super() has flushed the session, or the message
        # would be wiped along with it.
        response = super().post(request, *args, **kwargs)
        messages.info(request, "You have signed out.")
        return response
