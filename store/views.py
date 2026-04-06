import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    Category,
    Brand,
    CustomerRequest,
    Inventory,
    OTPVerification,
    Product,
    ProductImage,
    ProductSpecification,
)
from .serializers import (
    CategoryReadSerializer,
    BrandSerializer,
    CategorySerializer,
    CategoryWriteSerializer,
    CustomerRegistrationSerializer,
    CustomerRequestSerializer,
    CustomerRequestStatusSerializer,
    InventorySerializer,
    LoginSerializer,
    OTPResendSerializer,
    OTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProductImageSerializer,
    ProductSerializer,
    ProductSpecificationSerializer,
)

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = getattr(settings, "OTP_EXPIRY_MINUTES", 10)
OTP_MAX_ATTEMPTS = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
OTP_RESEND_COOLDOWN_SECONDS = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)

REGISTRATION_CACHE_PREFIX = "pending_registration"
REGISTRATION_CACHE_TIMEOUT = OTP_EXPIRY_MINUTES * 60


def registration_cache_key(email):
    return f"{REGISTRATION_CACHE_PREFIX}:{email.lower()}"


def get_pending_registration(email):
    return cache.get(registration_cache_key(email))


def set_pending_registration(email, data):
    cache.set(registration_cache_key(email), data, timeout=REGISTRATION_CACHE_TIMEOUT)


def delete_pending_registration(email):
    cache.delete(registration_cache_key(email))


def generate_otp():
    return f"{secrets.randbelow(900000) + 100000:06d}"


def build_reset_link(uid, token):
    base_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:5173").rstrip("/")
    return f"{base_url}/reset-password?uid={uid}&token={token}"


def safe_send_mail(subject, message, recipient_list):
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")

    if not from_email:
        logger.warning("Email skipped because DEFAULT_FROM_EMAIL is empty")
        return

    if not recipient_list or not all(recipient_list):
        logger.warning("Email skipped because recipient list is invalid")
        return

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Email sending failed", extra={"recipients": recipient_list, "subject": subject})


class StandardPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100


class PaginatedAPIView(APIView):
    pagination_class = StandardPagination

    def paginate(self, request, queryset, serializer_class):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = serializer_class(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class BrandAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = Brand.objects.filter(is_active=True)
        return self.paginate(request, queryset, BrandSerializer)

    def post(self, request):
        serializer = BrandSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BrandDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        brand = get_object_or_404(Brand.objects.filter(is_active=True), pk=pk)
        serializer = BrandSerializer(brand, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        brand = get_object_or_404(Brand, pk=pk)
        serializer = BrandSerializer(brand, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        brand = get_object_or_404(Brand, pk=pk)
        try:
            brand.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this brand because it is linked to existing products."},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.exception("Brand delete failed", extra={"brand_id": pk})
            return Response(
                {"error": "Failed to delete brand."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
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

        with transaction.atomic():
            user = User.objects.filter(email__iexact=email).first()
            
            if user:
                if user.is_active:
                    return Response(
                        {"error": "User with this email already exists."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Update info if re-registering
                user.username = username
                user.password = make_password(validated_data["password"])
                user.first_name = validated_data.get("first_name", "").strip()
                user.last_name = validated_data.get("last_name", "").strip()
                user.save()
            else:
                user = User.objects.create(
                    email=email,
                    username=username,
                    password=make_password(validated_data["password"]),
                    first_name=validated_data.get("first_name", "").strip(),
                    last_name=validated_data.get("last_name", "").strip(),
                    is_active=False,
                )


            # Check resend cooldown
            otp_verification, created_ov = OTPVerification.objects.get_or_create(user=user, defaults={
                "otp": generate_otp(),
                "expires_at": timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
            })

            now = timezone.now()
            if not created_ov:
                if (now - otp_verification.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
                    return Response(
                        {"error": f"Please wait {OTP_RESEND_COOLDOWN_SECONDS} seconds before requesting another OTP."},
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                
                # Update OTP
                otp_verification.otp = generate_otp()
                otp_verification.attempts = 0
                otp_verification.expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
                otp_verification.last_sent_at = now
                otp_verification.is_verified = False
                otp_verification.save()

            otp = otp_verification.otp

            safe_send_mail(
                "Your OTP for Registration",
                f"Your OTP is {otp}. It expires in {OTP_EXPIRY_MINUTES} minutes.",
                [email],
            )

        return Response(
            {"message": "Registration successful. Please verify the OTP sent to your email."},
            status=status.HTTP_201_CREATED,
        )



class VerifyOTPAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "otp"

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        otp = serializer.validated_data["otp"]

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(
                {"error": "No pending registration found for this email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp_verification = OTPVerification.objects.filter(user=user).first()
        if not otp_verification or otp_verification.is_verified:
            return Response(
                {"error": "No pending registration found or account already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_verification.is_expired():
            return Response(
                {"error": "OTP has expired. Please register again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if otp_verification.attempts >= OTP_MAX_ATTEMPTS:
            return Response(
                {"error": "Maximum OTP attempts exceeded. Please register again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if otp_verification.otp != otp:
            otp_verification.attempts += 1
            otp_verification.save(update_fields=["attempts"])
            return Response(
                {"error": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user.is_active = True
            user.save(update_fields=["is_active"])
            
            otp_verification.is_verified = True
            otp_verification.verified_at = timezone.now()
            otp_verification.save()

        # Clean up old pending registration from cache if it exists (legacy)
        delete_pending_registration(email)

        return Response(
            {"message": "OTP verified successfully. You can now log in."},
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
        user = User.objects.filter(email__iexact=email).first()

        if not user or user.is_active:
            return Response(
                {"error": "No pending registration found for this email."},
                status=status.HTTP_404_NOT_FOUND,
            )

        otp_verification = OTPVerification.objects.filter(user=user).first()
        if not otp_verification:
             # Create one if missing for some reason
             otp_verification = OTPVerification.objects.create(
                 user=user, 
                 otp=generate_otp(), 
                 expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
             )
        
        now = timezone.now()
        if (now - otp_verification.last_sent_at).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
            return Response(
                {"error": f"Please wait {OTP_RESEND_COOLDOWN_SECONDS} seconds before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        otp = generate_otp()
        otp_verification.otp = otp
        otp_verification.attempts = 0
        otp_verification.expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
        otp_verification.last_sent_at = now
        otp_verification.is_verified = False
        otp_verification.save()

        safe_send_mail(
            "Your New OTP for Registration",
            f"Your OTP is {otp}. It expires in {OTP_EXPIRY_MINUTES} minutes.",
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
        return Response(
            {
                "message": "Login successful.",
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "username": user.username,
                "is_staff": user.is_staff,
            },
            status=status.HTTP_200_OK,
        )


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
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_link = build_reset_link(uid, token)

            safe_send_mail(
                "Password Reset Request",
                f"Click the link below to reset your password:\n{reset_link}",
                [email],
            )

        return Response(
            {"message": "If an account with that email exists, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uidb64 = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Invalid token or user."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"error": "Invalid token or user."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=["password"])

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


class CategoryAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        is_tree = request.query_params.get("tree", "true").lower() == "true"
        base_queryset = Category.objects.filter(is_active=True)
        queryset = base_queryset.filter(parent__isnull=True) if is_tree else base_queryset
        queryset = queryset.prefetch_related("subcategories")
        return self.paginate(request, queryset, CategorySerializer)

    def post(self, request):
        serializer = CategoryWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        category = get_object_or_404(
            Category.objects.prefetch_related("subcategories").filter(is_active=True),
            pk=pk
        )
        serializer = CategorySerializer(category)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        serializer = CategoryWriteSerializer(category, data=request.data, partial=True)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        category = get_object_or_404(Category, pk=pk)
        try:
            category.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {
                    "error": "Cannot delete this category because it is linked to existing products or subcategories."
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.exception("Category delete failed", extra={"category_id": pk})
            return Response(
                {"error": "Failed to delete category."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SubCategoryAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        category = get_object_or_404(
            Category.objects.prefetch_related("subcategories").filter(is_active=True),
            pk=pk
        )
        serializer = CategoryReadSerializer(
            category.subcategories.filter(is_active=True),
            many=True,
            context={"depth": 0}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        parent_category = get_object_or_404(Category, pk=pk)
        data = request.data.copy()
        data["parent"] = parent_category.id
        serializer = CategoryWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = Product.objects.select_related("category", "subcategory").filter(is_active=True)

        top_selling = request.query_params.get("top_selling")
        featured = request.query_params.get("featured")
        new_arrival = request.query_params.get("new_arrival")
        category_id = request.query_params.get("category")
        subcategory_id = request.query_params.get("subcategory")

        if top_selling and top_selling.lower() == "true":
            queryset = queryset.filter(top_selling=True)

        if featured and featured.lower() == "true":
            queryset = queryset.filter(featured=True)

        if new_arrival and new_arrival.lower() == "true":
            queryset = queryset.filter(new_arrival=True)

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if subcategory_id:
            queryset = queryset.filter(subcategory_id=subcategory_id)

        return self.paginate(request, queryset, ProductSerializer)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        product = get_object_or_404(
            Product.objects.select_related("category", "subcategory").filter(is_active=True),
            pk=pk
        )
        serializer = ProductSerializer(product)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        serializer = ProductSerializer(product, data=request.data, partial=True)

        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        try:
            product.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {
                    "error": "Cannot delete this product because it is linked to existing customer requests or other protected records."
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception:
            logger.exception("Product delete failed", extra={"product_id": pk})
            return Response(
                {"error": "Failed to delete product."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProductImageAPIView(PaginatedAPIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk=None):
        if pk:
            image = get_object_or_404(ProductImage.objects.select_related("product"), pk=pk)
            serializer = ProductImageSerializer(image, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        queryset = ProductImage.objects.select_related("product").all()
        product_id = request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return self.paginate(request, queryset, ProductImageSerializer)

    def post(self, request):
        serializer = ProductImageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        image_obj = get_object_or_404(ProductImage, pk=pk)
        serializer = ProductImageSerializer(image_obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        image_obj = get_object_or_404(ProductImage, pk=pk)
        try:
            image_obj.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            logger.exception("Product image delete failed", extra={"image_id": pk})
            return Response(
                {"error": "Failed to delete image."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProductSpecificationAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk=None):
        if pk:
            spec = get_object_or_404(ProductSpecification.objects.select_related("product"), pk=pk)
            serializer = ProductSpecificationSerializer(spec)
            return Response(serializer.data, status=status.HTTP_200_OK)

        queryset = ProductSpecification.objects.select_related("product").all()
        product_id = request.query_params.get("product")
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return self.paginate(request, queryset, ProductSpecificationSerializer)

    def post(self, request):
        serializer = ProductSpecificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        spec = get_object_or_404(ProductSpecification, pk=pk)
        serializer = ProductSpecificationSerializer(spec, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        spec = get_object_or_404(ProductSpecification, pk=pk)
        try:
            spec.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            logger.exception("Product specification delete failed", extra={"spec_id": pk})
            return Response(
                {"error": "Failed to delete specification."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class InventoryAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = Inventory.objects.select_related("product").all()
        return self.paginate(request, queryset, InventorySerializer)

    def post(self, request):
        product_id = request.data.get("product")
        stock = request.data.get("stock")

        if product_id is None or stock is None:
            return Response(
                {"error": "product and stock are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        inventory, created = Inventory.objects.update_or_create(
            product=product,
            defaults={"stock": stock},
        )

        serializer = InventorySerializer(inventory)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class InventoryDetailAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request, pk):
        inventory = get_object_or_404(Inventory.objects.select_related("product"), pk=pk)
        serializer = InventorySerializer(inventory)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        inventory = get_object_or_404(Inventory, pk=pk)
        serializer = InventorySerializer(inventory, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class CustomerRequestAPIView(PaginatedAPIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        queryset = CustomerRequest.objects.select_related("product").all()
        return self.paginate(request, queryset, CustomerRequestSerializer)

    def post(self, request):
        serializer = CustomerRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_obj = serializer.save()

        transaction.on_commit(
            lambda: safe_send_mail(
                f"New Product Request - {request_obj.product.name}",
                (
                    f"New customer inquiry received.\n\n"
                    f"Customer Name: {request_obj.name}\n"
                    f"Email: {request_obj.email}\n"
                    f"Phone: {request_obj.phone}\n"
                    f"Product: {request_obj.product.name}\n"
                    f"Quantity: {request_obj.quantity}\n"
                    f"Description:\n{request_obj.description}"
                ),
                [settings.SALES_NOTIFICATION_EMAIL],
            )
        )

        return Response(
            {"status": True, "message": "Request submitted successfully."},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, pk):
        req = get_object_or_404(CustomerRequest, pk=pk)
        serializer = CustomerRequestStatusSerializer(req, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Status updated successfully.", "status": req.status},
            status=status.HTTP_200_OK,
        )


class DashboardAPIView(APIView):
    permission_classes = [IsAdminUser]
    

    def get(self, request):
        low_stock_threshold = 5

        total_categories = Category.objects.filter(is_active=True).count()
        total_products = Product.objects.filter(is_active=True).count()
        total_inventory_items = Inventory.objects.count()
        total_requests = CustomerRequest.objects.count()

        pending_requests = CustomerRequest.objects.filter(status=CustomerRequest.STATUS_PENDING).count()
        quote_sent_requests = CustomerRequest.objects.filter(status=CustomerRequest.STATUS_QUOTE_SENT).count()
        closed_requests = CustomerRequest.objects.filter(status=CustomerRequest.STATUS_CLOSED).count()

        low_stock_products = Inventory.objects.select_related("product").filter(stock__lte=low_stock_threshold)
        top_selling_products = Product.objects.filter(is_active=True, top_selling=True)[:10]
        recent_requests = CustomerRequest.objects.select_related("product").order_by("-created_at")[:10]

        return Response(
            {
                "summary": {
                    "total_categories": total_categories,
                    "total_products": total_products,
                    "total_inventory_items": total_inventory_items,
                    "total_requests": total_requests,
                    "pending_requests": pending_requests,
                    "quote_sent_requests": quote_sent_requests,
                    "closed_requests": closed_requests,
                },
                "low_stock_products": [
                    {
                        "id": item.product.id,
                        "name": item.product.name,
                        "brand": item.product.brand.name if item.product.brand else None,
                        "stock": item.stock,
                    }
                    for item in low_stock_products
                ],
                "top_selling_products": [
                    {
                        "id": product.id,
                        "name": product.name,
                        "brand": product.brand.name if product.brand else None,
                        "category": product.category.name if product.category else None,
                    }
                    for product in top_selling_products
                ],
                "recent_requests": [
                    {
                        "id": req.id,
                        "name": req.name,
                        "email": req.email,
                        "product": req.product.name if req.product else None,
                        "quantity": req.quantity,
                        "status": req.status,
                        "created_at": req.created_at,
                    }
                    for req in recent_requests
                ],
            },
            status=status.HTTP_200_OK,
        )


def home(request):
    return HttpResponse("Backend is running 🚀")