from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    CustomerRegistrationAPIView, VerifyOTPAPIView, ResendOTPAPIView,
    LoginAPIView, LogoutAPIView, PasswordResetRequestAPIView,
    PasswordResetVerifyOTPAPIView, PasswordResetConfirmAPIView,
    ResetPasswordAPIView, ProfileAPIView,
)

urlpatterns = [
    path("register/", CustomerRegistrationAPIView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPAPIView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOTPAPIView.as_view(), name="resend-otp"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("reset-password/", ResetPasswordAPIView.as_view(), name="reset-password"),
    path("forgot-password/", PasswordResetRequestAPIView.as_view(), name="forgot-password"),
    path("verify-reset-otp/", PasswordResetVerifyOTPAPIView.as_view(), name="verify-reset-otp"),
    path("confirm-password/", PasswordResetConfirmAPIView.as_view(), name="confirm-password"),
    path("profile/", ProfileAPIView.as_view(), name="profile"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]