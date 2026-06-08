import logging
from datetime import timedelta, datetime
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User, update_last_login
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
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
    ChangePasswordSerializer, CustomerProfileSerializer,
    CustomerRegistrationSerializer, EnquiryHistorySerializer, LoginSerializer,
    OTPResendSerializer, OTPVerifySerializer, PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer, ProfileUpdateSerializer,
    QuoteRequestHistorySerializer,
)
from core.utils.helpers import generate_otp, safe_send_mail
from core.tasks import send_otp_email_task

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = getattr(settings, "OTP_EXPIRY_MINUTES", 10)
OTP_MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_COOLDOWN_SECONDS = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)


def _send_otp_html_email(subject, email, otp, expiry_minutes, template_name, extra_context=None):
    """
    Send an OTP email with HTML template + plain text fallback.
    Returns True on success, False on failure.
    """
    try:
        context = {
            "user_name": email.split("@")[0],
            "email": email,
            "otp": otp,
            "expiry_minutes": expiry_minutes,
            "frontend_url": getattr(settings, "FRONTEND_BASE_URL", ""),
            **(extra_context or {}),
        }
        html_body = render_to_string(template_name, context)
        plain_body = f"Your OTP is {otp}. It expires in {expiry_minutes} minutes."

        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        return True
    except Exception as exc:
        logger.error(f"HTML OTP email failed for {email}: {exc}", exc_info=True)
        # Fallback to plain text
        return safe_send_mail(
            subject,
            f"Your OTP is {otp}. It expires in {expiry_minutes} minutes.",
            [email],
        )


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
        password = validated_data["password"]
        first_name = validated_data.get("first_name", "").strip()
        last_name = validated_data.get("last_name", "").strip()
        company_name = validated_data["company_name"].strip()
        company_address = validated_data["company_address"].strip()
        phone = validated_data.get("phone", "").strip()

        existing_active_user = User.objects.filter(email__iexact=email, is_active=True).first()
        if existing_active_user:
            return Response(
                {"error": "User with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"pending_registration:{email}"
        otp = generate_otp()
        cache.set(
            cache_key,
            {
                "username": username,
                "password": password,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "company_name": company_name,
                "company_address": company_address,
                "phone": phone,
                "otp": otp,
                "attempts": 0,
                "expires_at": (timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat(),
            },
            timeout=OTP_EXPIRY_MINUTES * 60,
        )

        # Send HTML OTP email (synchronous — critical path)
        sent = _send_otp_html_email(
            subject="Your OTP for Registration — NxSys Digital",
            email=email,
            otp=otp,
            expiry_minutes=OTP_EXPIRY_MINUTES,
            template_name="emails/otp_registration.html",
            extra_context={"user_name": first_name or username},
        )
        if not sent:
            cache.delete(cache_key)
            return Response(
                {"error": "Failed to send OTP email. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "message": "Registration successful. Please verify the OTP sent to your email.",
                "email": email,
            },
            status=status.HTTP_201_CREATED,
        )


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

        cache_key = f"pending_registration:{email}"
        registration_data = cache.get(cache_key)

        if not registration_data:
            return Response(
                {"error": "No pending registration found for this email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expires_at = datetime.fromisoformat(registration_data["expires_at"])
        if timezone.now() >= expires_at:
            cache.delete(cache_key)
            return Response(
                {"error": "OTP has expired. Please register again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if registration_data.get("attempts", 0) >= OTP_MAX_ATTEMPTS:
            cache.delete(cache_key)
            return Response(
                {"error": "Maximum OTP attempts exceeded. Please register again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if registration_data["otp"] != otp:
            registration_data["attempts"] = registration_data.get("attempts", 0) + 1
            cache.set(cache_key, registration_data, timeout=OTP_EXPIRY_MINUTES * 60)
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user, created = User.objects.get_or_create(
                email__iexact=email,
                defaults={
                    "username": registration_data["username"],
                    "email": email,
                    "first_name": registration_data["first_name"],
                    "last_name": registration_data["last_name"],
                    "is_active": True,
                },
            )

            if not created:
                if not user.is_active:
                    user.is_active = True
                    user.save(update_fields=["is_active"])
            else:
                user.set_password(registration_data["password"])
                user.save(update_fields=["password"])

            CustomerProfile.objects.get_or_create(
                user=user,
                defaults={
                    "company_name": registration_data["company_name"],
                    "company_address": registration_data["company_address"],
                    "phone": registration_data.get("phone", ""),
                },
            )

            OTPVerification.objects.update_or_create(
                user=user,
                defaults={
                    "otp": otp,
                    "is_verified": True,
                    "verified_at": timezone.now(),
                    "attempts": registration_data.get("attempts", 0),
                    "expires_at": expires_at,
                },
            )

        cache.delete(cache_key)

        return Response(
            {"message": "OTP verified successfully. Your account is now active. You can now log in."},
            status=status.HTTP_200_OK,
        )


class ResendOTPAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()

        cache_key = f"pending_registration:{email}"
        registration_data = cache.get(cache_key)

        if not registration_data:
            return Response(
                {"error": "No pending registration found for this email."},
                status=status.HTTP_404_NOT_FOUND,
            )

        now = timezone.now()
        expires_at = datetime.fromisoformat(registration_data["expires_at"])

        if now >= expires_at:
            cache.delete(cache_key)
            return Response(
                {"error": "OTP has expired. Please register again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        last_sent = registration_data.get("last_sent_at")
        if last_sent:
            last_sent_time = datetime.fromisoformat(last_sent)
            if (now - last_sent_time).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
                return Response(
                    {"error": f"Please wait {OTP_RESEND_COOLDOWN_SECONDS} seconds before requesting another OTP."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

        new_otp = generate_otp()
        registration_data["otp"] = new_otp
        registration_data["attempts"] = 0
        registration_data["last_sent_at"] = now.isoformat()
        registration_data["expires_at"] = (now + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()
        cache.set(cache_key, registration_data, timeout=OTP_EXPIRY_MINUTES * 60)

        send_otp_email_task.delay(
            "Your New OTP for Registration — NxSys Digital",
            f"Your OTP is {new_otp}. It expires in {OTP_EXPIRY_MINUTES} minutes.",
            [email],
        )
        return Response(
            {"message": "A new OTP has been sent to your email."},
            status=status.HTTP_200_OK,
        )


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        login_id = serializer.validated_data["login_id"]
        password = serializer.validated_data["password"]

        if "@" in login_id:
            user_obj = User.objects.filter(email__iexact=login_id).only("username").first()
            username_for_auth = user_obj.username if user_obj else login_id
        else:
            username_for_auth = login_id

        user = authenticate(request, username=username_for_auth, password=password)

        if user is None:
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({"error": "Account is not active."}, status=status.HTTP_403_FORBIDDEN)

        # last_login is None until the first successful login — use it to send
        # the welcome email exactly once, on the user's first login.
        is_first_login = user.last_login is None

        update_last_login(None, user)

        if is_first_login:
            from core.tasks import send_welcome_email
            try:
                send_welcome_email.delay(user.id)
                logger.info(f"Welcome email task queued on first login for user: {user.email}")
            except Exception as e:
                logger.error(f"Error queuing welcome email for user {user.id}: {str(e)}", exc_info=True)

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
            otp_verification, _ = OTPVerification.objects.get_or_create(
                user=user,
                defaults={"expires_at": timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)},
            )
            otp_verification.otp = generate_otp()
            otp_verification.attempts = 0
            otp_verification.expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
            otp_verification.last_sent_at = timezone.now()
            otp_verification.is_verified = False
            otp_verification.verified_at = None
            otp_verification.save()

            # Send HTML password reset email (synchronous — critical path,
            # same pattern as registration OTP so the template is always rendered).
            _send_otp_html_email(
                subject="Password Reset OTP — NxSys Digital",
                email=email,
                otp=otp_verification.otp,
                expiry_minutes=OTP_EXPIRY_MINUTES,
                template_name="emails/password_reset.html",
            )

        return Response(
            {"message": "If an account with that email exists, password reset details have been sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetVerifyOTPAPIView(APIView):
    """
    Verify the OTP sent by PasswordResetRequestAPIView (forgot-password flow).

    This is the reset-flow counterpart to VerifyOTPAPIView. It does NOT touch
    the registration cache, so it never returns "No pending registration".
    On success the OTP is marked verified and the frontend can proceed to
    POST the new password to PasswordResetConfirmAPIView.

    POST /accounts/verify-reset-otp/
    Body: { "email": "...", "otp": "123456" }   ("code" is also accepted
    """
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].strip().lower()
        otp = serializer.validated_data["otp"]

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response({"error": "Invalid email or OTP."}, status=status.HTTP_400_BAD_REQUEST)

        otp_verification = OTPVerification.objects.filter(user=user).first()
        if not otp_verification or otp_verification.is_expired():
            return Response(
                {"error": "OTP has expired. Please request a new password reset."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_verification.attempts >= OTP_MAX_ATTEMPTS:
            return Response(
                {"error": "Maximum OTP attempts exceeded. Please request a new password reset."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if otp_verification.otp != otp:
            otp_verification.attempts += 1
            otp_verification.save(update_fields=["attempts"])
            return Response({"error": "Invalid email or OTP."}, status=status.HTTP_400_BAD_REQUEST)

        otp_verification.is_verified = True
        otp_verification.verified_at = timezone.now()
        otp_verification.save(update_fields=["is_verified", "verified_at"])

        return Response(
            {"message": "OTP verified. You can now set a new password.", "email": email},
            status=status.HTTP_200_OK,
        )


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
            return Response(
                {"error": "OTP has expired. Please request a new password reset."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_verification.attempts >= OTP_MAX_ATTEMPTS:
            return Response(
                {"error": "Maximum OTP attempts exceeded. Please request a new password reset."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

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


class ResetPasswordAPIView(APIView):
    """
    Authenticated 'reset password' flow for a logged-in user.
    Requires the current password and a new password.
    No OTP/email involved — that's the separate forgot-password flow.

    POST /accounts/reset-password/
    Body: { "old_password": "...", "new_password": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        old_password = serializer.validated_data["old_password"]
        new_password = serializer.validated_data["new_password"]

        if not user.check_password(old_password):
            return Response(
                {"error": "Old password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return Response(
                {"error": "refresh_token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {"error": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"message": "Logout successful."}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Profile API
# ─────────────────────────────────────────────────────────────────────────────

class ProfileAPIView(APIView):
    """
    GET  /accounts/profile/  → return user info + profile + enquiry/request history
    PUT  /accounts/profile/  → update name, company, address, phone
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get or create profile
        profile, _ = CustomerProfile.objects.get_or_create(
            user=user,
            defaults={"company_name": "", "company_address": "", "phone": ""},
        )

        # Fetch enquiry history by email
        from orders.models import Enquiry, CustomerRequest
        enquiries = Enquiry.objects.select_related("product").filter(
            email__iexact=user.email
        ).order_by("-created_at")[:20]

        # Fetch quote request history by email
        quote_requests = CustomerRequest.objects.select_related("product").filter(
            email__iexact=user.email
        ).order_by("-created_at")[:20]

        return Response({
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": f"{user.first_name} {user.last_name}".strip() or user.username,
                "date_joined": user.date_joined,
                "last_login": user.last_login,
                "is_staff": user.is_staff,
            },
            "profile": CustomerProfileSerializer(profile).data,
            "enquiries": {
                "count": enquiries.count(),
                "results": EnquiryHistorySerializer(enquiries, many=True).data,
            },
            "quote_requests": {
                "count": quote_requests.count(),
                "results": QuoteRequestHistorySerializer(quote_requests, many=True).data,
            },
        })

    def put(self, request):
        user = request.user
        serializer = ProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Update User fields
        user_fields_changed = False
        if "first_name" in data:
            user.first_name = data["first_name"]
            user_fields_changed = True
        if "last_name" in data:
            user.last_name = data["last_name"]
            user_fields_changed = True
        if user_fields_changed:
            user.save(update_fields=[f for f in ["first_name", "last_name"] if f in data])

        # Update CustomerProfile fields
        profile, _ = CustomerProfile.objects.get_or_create(
            user=user,
            defaults={"company_name": "", "company_address": "", "phone": ""},
        )
        profile_fields_changed = False
        if "company_name" in data:
            profile.company_name = data["company_name"]
            profile_fields_changed = True
        if "company_address" in data:
            profile.company_address = data["company_address"]
            profile_fields_changed = True
        if "phone" in data:
            profile.phone = data["phone"]
            profile_fields_changed = True
        if profile_fields_changed:
            profile.save()

        return Response({
            "message": "Profile updated successfully.",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": f"{user.first_name} {user.last_name}".strip() or user.username,
            },
            "profile": CustomerProfileSerializer(profile).data,
        })