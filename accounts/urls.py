from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    CustomerRegistrationAPIView, VerifyOTPAPIView, ResendOTPAPIView,
    LoginAPIView, LogoutAPIView, PasswordResetRequestAPIView, PasswordResetConfirmAPIView
)

urlpatterns = [
    path("register/", CustomerRegistrationAPIView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPAPIView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOTPAPIView.as_view(), name="resend-otp"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("reset-password/", PasswordResetRequestAPIView.as_view(), name="reset-password"),
    path("confirm-password/", PasswordResetConfirmAPIView.as_view(), name="confirm-password"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
