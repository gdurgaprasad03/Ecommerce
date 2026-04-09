from datetime import timedelta

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subcategories",
    )
    navbar_group = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name", "parent"], name="uniq_category_name_parent")
        ]
        ordering = ["name"]

    def __str__(self):
        return self.name


class Brand(models.Model):
    name = models.CharField(max_length=200, unique=True)
    logo = models.ImageField(upload_to="brands/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products", null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    subcategory = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategory_products",
    )
    name = models.CharField(max_length=255, db_index=True)
    mpn = models.CharField(max_length=100, null=True, blank=True)
    sku = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField()
    highlights = models.TextField(null=True, blank=True)
    rating = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    featured = models.BooleanField(default=False)
    top_selling = models.BooleanField(default=False)
    new_arrival = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} Image"


class ProductSpecification(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="specifications"
    )
    section = models.CharField(max_length=100, default="General")
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "section", "key"],
                name="uniq_product_spec_section_key"
            )
        ]
        ordering = ["section", "key"]

    def __str__(self):
        return f"{self.product.name} - {self.section} - {self.key}"


class Inventory(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="inventory")
    stock = models.PositiveIntegerField(validators=[MinValueValidator(0)])
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["product__name"]

    def __str__(self):
        return f"{self.product.name} - {self.stock}"


class CustomerRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_QUOTE_SENT = "quote_sent"
    STATUS_CLOSED = "closed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_QUOTE_SENT, "Quote Sent"),
        (STATUS_CLOSED, "Closed"),
    ]

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="customer_requests")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    stock_deducted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.product.name}"


class OTPVerification(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="otp_verification")
    otp = models.CharField(max_length=6)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField(default=timezone.now)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ["-created_at"]

    def is_expired(self):
        return timezone.now() >= self.expires_at

    @classmethod
    def default_expiry(cls):
        return timezone.now() + timedelta(minutes=10)

    def __str__(self):
        return f"{self.user.username} - {self.otp}"


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    company_name = models.CharField(max_length=255)
    company_address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.company_name}"

class Enquiry(models.Model):
    name = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    company_address = models.TextField()
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enquiries",
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        product_name = self.product.name if self.product else "General Enquiry"
        return f"{self.name} - {product_name}"
