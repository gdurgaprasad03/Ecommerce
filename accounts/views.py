import logging
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomerProfile, OTPVerification
from .serializers import (
    CustomerRegistrationSerializer, LoginSerializer, OTPResendSerializer,
    OTPVerifySerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer
)
from core.utils.helpers import safe_send_mail, build_reset_text, generate_otp

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = getattr(settings, "OTP_EXPIRY_MINUTES", 10)
OTP_MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_COOLDOWN_SECONDS = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)

class CustomerRegistrationAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        email = validated_data["email"].strip().lower()
        username = validated_data.get("username", "").strip() or email
        company_name = validated_data["company_name"].strip()
        company_address = validated_data["company_address"].strip()

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()

            if user:
                if user.is_active:
                    return Response({"error": "User with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

                user.username = username
                user.password = make_password(validated_data["password"])
                user.first_name = validated_data.get("first_name", "").strip()
                user.last_name = validated_data.get("last_name", "").strip()
                user.save()

                profile, _ = CustomerProfile.objects.get_or_create(user=user)
                profile.company_name = company_name
                profile.company_address = company_address
                profile.save()

            else:
                user = User.objects.create(
                    email=email, username=username, password=make_password(validated_data["password"]),
                    first_name=validated_data.get("first_name", "").strip(),
                    last_name=validated_data.get("last_name", "").strip(),
                    is_active=False,
                )

                CustomerProfile.objects.create(user=user, company_name=company_name, company_address=company_address)

            otp_verification, created_ov = OTPVerification.objects.get_or_create(
                user=user, defaults={"otp": generate_otp(), "expires_at": timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)}
            )

            now = timezone.now()
            if not created_ov:
                if (now - otp_verification.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
                    return Response({"error": f"Please wait {OTP_RESEND_COOLDOWN_SECONDS} seconds before requesting another OTP."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
                otp_verification.otp = generate_otp()
                otp_verification.attempts = 0
                otp_verification.expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
                otp_verification.last_sent_at = now
                otp_verification.is_verified = False
                otp_verification.verified_at = None
                otp_verification.save()

            otp = otp_verification.otp
            safe_send_mail("Your OTP for Registration", f"Your OTP is {otp}. It expires in {OTP_EXPIRY_MINUTES} minutes.", [email])

        return Response({"message": "Registration successful. Please verify the OTP sent to your email."}, status=status.HTTP_201_CREATED)

class VerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        otp = serializer.validated_data["otp"]

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"error": "No pending registration found for this email."}, status=status.HTTP_400_BAD_REQUEST)

        otp_verification = OTPVerification.objects.filter(user=user).first()
        if not otp_verification or otp_verification.is_verified:
            return Response({"error": "No pending registration found or account already verified."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_verification.is_expired():
            return Response({"error": "OTP has expired. Please register again."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_verification.attempts >= OTP_MAX_ATTEMPTS:
            return Response({"error": "Maximum OTP attempts exceeded. Please register again."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        if otp_verification.otp != otp:
            otp_verification.attempts += 1
            otp_verification.save(update_fields=["attempts"])
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user.is_active = True
            user.save(update_fields=["is_active"])
            otp_verification.is_verified = True
            otp_verification.verified_at = timezone.now()
            otp_verification.save()

        return Response({"message": "OTP verified successfully. You can now log in."}, status=status.HTTP_200_OK)

class ResendOTPAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if not user or user.is_active:
            return Response({"error": "No pending registration found for this email."}, status=status.HTTP_404_NOT_FOUND)

        otp_verification = OTPVerification.objects.filter(user=user).first()
        if not otp_verification:
             otp_verification = OTPVerification.objects.create(user=user, otp=generate_otp(), expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES))

        now = timezone.now()
        if (now - otp_verification.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
            return Response({"error": f"Please wait {OTP_RESEND_COOLDOWN_SECONDS} seconds before requesting another OTP."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp = generate_otp()
        otp_verification.otp = otp
        otp_verification.attempts = 0
        otp_verification.expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
        otp_verification.last_sent_at = now
        otp_verification.is_verified = False
        otp_verification.save()

        safe_send_mail("Your New OTP for Registration", f"Your OTP is {otp}. It expires in {OTP_EXPIRY_MINUTES} minutes.", [email])
        return Response({"message": "A new OTP has been sent to your email."}, status=status.HTTP_200_OK)

class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        login_id = serializer.validated_data["login_id"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=login_id, password=password)
        if user is None:
            user_obj = User.objects.filter(email__iexact=login_id).first()
            if user_obj:
                user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({"error": "Account is not active."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Login successful.",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "username": user.username,
            "is_staff": user.is_staff,
        }, status=status.HTTP_200_OK)

class PasswordResetRequestAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user:
            otp_verification, _ = OTPVerification.objects.get_or_create(user=user)
            otp_verification.otp = generate_otp()
            otp_verification.attempts = 0
            otp_verification.expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
            otp_verification.last_sent_at = timezone.now()
            otp_verification.is_verified = False
            otp_verification.verified_at = None
            otp_verification.save()

            safe_send_mail("Password Reset OTP", build_reset_text(otp_verification.otp), [email])

        return Response({"message": "If an account with that email exists, password reset details have been sent."}, status=status.HTTP_200_OK)

class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"error": "Invalid email or OTP."}, status=status.HTTP_400_BAD_REQUEST)

        otp_verification = OTPVerification.objects.filter(user=user).first()
        if not otp_verification or otp_verification.is_expired():
            return Response({"error": "OTP has expired. Please request a new password reset."}, status=status.HTTP_400_BAD_REQUEST)

        if otp_verification.attempts >= OTP_MAX_ATTEMPTS:
            return Response({"error": "Maximum OTP attempts exceeded. Please request a new password reset."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        if otp_verification.otp != otp:
            otp_verification.attempts += 1
            otp_verification.save(update_fields=["attempts"])
            return Response({"error": "Invalid email or OTP."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=["password"])
        otp_verification.is_verified = True
        otp_verification.verified_at = timezone.now()
        otp_verification.save(update_fields=["is_verified", "verified_at"])

        return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return Response({"error": "refresh_token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response({"error": "Invalid or expired refresh token."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Logout successful."}, status=status.HTTP_200_OK)
