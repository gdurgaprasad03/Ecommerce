from django.urls import path
from .views import (
    DashboardAPIView, SalesAnalyticsAPIView, CustomerAnalyticsAPIView,
    ReviewAnalyticsAPIView, WishlistAnalyticsAPIView, InventoryAnalyticsAPIView,
    ComprehensiveAnalyticsAPIView
)

urlpatterns = [
    path("dashboard/", DashboardAPIView.as_view(), name="dashboard"),
    path("analytics/sales/", SalesAnalyticsAPIView.as_view(), name="analytics-sales"),
    path("analytics/customers/", CustomerAnalyticsAPIView.as_view(), name="analytics-customers"),
    path("analytics/reviews/", ReviewAnalyticsAPIView.as_view(), name="analytics-reviews"),
    path("analytics/wishlists/", WishlistAnalyticsAPIView.as_view(), name="analytics-wishlists"),
    path("analytics/inventory/", InventoryAnalyticsAPIView.as_view(), name="analytics-inventory"),
    path("analytics/comprehensive/", ComprehensiveAnalyticsAPIView.as_view(), name="analytics-comprehensive"),
]
