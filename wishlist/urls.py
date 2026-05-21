from django.urls import path
from .views import WishlistAPIView

urlpatterns = [
    path("wishlist/", WishlistAPIView.as_view(), name="wishlist"),
    path("wishlist/<int:product_id>/", WishlistAPIView.as_view(), name="wishlist-remove-product"),
]