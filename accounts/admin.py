from django.contrib import admin
from .models import OTPVerification

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "otp", "is_verified", "verified_at", "attempts", "expires_at", "last_sent_at", "created_at")
    search_fields = ("user__username", "user__email")
    list_filter = ("expires_at", "created_at")
