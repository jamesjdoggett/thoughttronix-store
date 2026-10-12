from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import User


class SecurityPasswordChangeForm(PasswordChangeForm):
    """Use Django's current-password check and configured password policy."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class SignupForm(UserCreationForm):
    """Username signup using Django password validation and a recovery address."""

    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is unavailable")
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class SignInForm(AuthenticationForm):
    """The stock authentication form, dressed in DaisyUI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"


class EmailCorrectionForm(forms.Form):
    """Validate an unverified account's address and current password."""

    email = forms.EmailField(label="Email address")
    current_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"
        self.fields["current_password"].widget.attrs["autocomplete"] = (
            "current-password"
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.exclude(pk=self.user.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is unavailable")
        return email

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Your current password is incorrect.")
        return password

    def clean(self):
        cleaned = super().clean()
        if self.user.email_verified:
            raise forms.ValidationError("Your email is already verified.")
        return cleaned


class EmailReplacementForm(EmailCorrectionForm):
    """Confirm ownership credentials before staging a new recovery address."""

    def clean(self):
        cleaned = forms.Form.clean(self)
        if not self.user.email_verified:
            raise forms.ValidationError(
                "Verify your current email before replacing it."
            )
        if cleaned.get("email") == self.user.email:
            self.add_error("email", "Choose a different email address.")
        return cleaned


class RecoveryRequestForm(forms.Form):
    """Accept even malformed destinations without disclosing eligibility."""

    email = forms.CharField(
        label="Email address",
        required=False,
        widget=forms.EmailInput(
            attrs={"class": "input w-full", "autocomplete": "email"}
        ),
    )


class RecoveryPasswordForm(SetPasswordForm):
    """Apply the existing password policy to recovered accounts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input w-full"
