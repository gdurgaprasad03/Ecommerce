from django.urls import path
from .views import WishlistAPIView

urlpatterns = [
    path("wishlist/", WishlistAPIView.as_view(), name="wishlist"),
]
