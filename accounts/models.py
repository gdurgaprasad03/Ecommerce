from datetime import timedelta
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

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
