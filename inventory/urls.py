from django.urls import path
from .views import InventoryAPIView, InventoryDetailAPIView

urlpatterns = [
    path("inventory/", InventoryAPIView.as_view(), name="inventory-list-create"),
    path("inventory/<int:pk>/", InventoryDetailAPIView.as_view(), name="inventory-detail"),
]
