from django.urls import path
from .views import ProductReviewAPIView, ReviewDetailAPIView

urlpatterns = [
    path("reviews/", ProductReviewAPIView.as_view(), name="review-list-create"),
    path("reviews/<int:product_id>/", ProductReviewAPIView.as_view(), name="product-reviews"),
    path("reviews/detail/<int:review_id>/", ReviewDetailAPIView.as_view(), name="review-detail"),
]
