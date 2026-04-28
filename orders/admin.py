from django.contrib import admin
from .models import CustomerRequest

@admin.register(CustomerRequest)
class CustomerRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id", "name", "email", "phone", "product",
        "quantity", "status", "stock_deducted", "created_at",
    )
    search_fields = ("name", "email", "phone", "product__name")
    list_filter = ("status", "stock_deducted", "created_at")
    readonly_fields = ("stock_deducted", "created_at", "updated_at")
