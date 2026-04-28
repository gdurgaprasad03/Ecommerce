from django.db import models
from django.core.validators import MinValueValidator
from products.models import Product

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
