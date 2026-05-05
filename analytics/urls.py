from django.urls import path
from .views import (
    DashboardAPIView, SalesAnalyticsAPIView, CustomerAnalyticsAPIView,
    ReviewAnalyticsAPIView, WishlistAnalyticsAPIView, InventoryAnalyticsAPIView,
    ComprehensiveAnalyticsAPIView
)

urlpatterns = [
    path("dashboard/", DashboardAPIView.as_view(), name="unified-dashboard"),
    path('sales/', SalesAnalyticsAPIView.as_view(), name="sales-analytics"),
    path('customers/', CustomerAnalyticsAPIView.as_view(), name="customers-analytics"),
    path('reviews/', ReviewAnalyticsAPIView.as_view(), name="reviews-analytics"),
    path('wishlists/', WishlistAnalyticsAPIView.as_view(), name="wishlists-analytics"),
    path('inventory/', InventoryAnalyticsAPIView.as_view(), name="inventory-analytics"),
    path('comprehensive/', ComprehensiveAnalyticsAPIView.as_view(), name="comprehensive-analytics"),
]
