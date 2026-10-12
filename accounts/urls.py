from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("password/reset/", views.RecoveryRequestView.as_view(), name="password_reset"),
    path(
        "password/reset/sent/",
        views.TemplateView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password/reset/<str:uidb64>/<str:token>/",
        views.RecoveryConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/<str:token>/",
        views.TemplateView.as_view(
            template_name="accounts/password_reset_confirm.html",
            extra_context={"validlink": False},
        ),
        name="password_reset_legacy",
    ),
    path(
        "security/password/",
        views.SecurityPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "security/email/replace/",
        views.EmailReplacementView.as_view(),
        name="email_replacement",
    ),
    path(
        "security/email/cancel/",
        views.CancelEmailReplacementView.as_view(),
        name="email_replacement_cancel",
    ),
    path("security/", views.SecurityOverviewView.as_view(), name="security"),
    path(
        "security/email/", views.EmailCorrectionView.as_view(), name="email_correction"
    ),
    path(
        "security/verify/",
        views.VerificationRequestView.as_view(),
        name="verification_request",
    ),
    path("verify/<str:token>/", views.VerifyEmailView.as_view(), name="verify_email"),
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.SignInView.as_view(), name="login"),
    path("logout/", views.SignOutView.as_view(), name="logout"),
]
