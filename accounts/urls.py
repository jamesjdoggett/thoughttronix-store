from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
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
