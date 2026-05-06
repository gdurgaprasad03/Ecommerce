from django.db.models import Avg
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ProductReview
from .serializers import ProductReviewSerializer
from products.models import Product

class ProductReviewAPIView(APIView):
    def get(self, request, product_id=None):
        if product_id:
            try: product = Product.objects.get(pk=product_id)
            except Product.DoesNotExist: return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
            reviews = ProductReview.objects.filter(product=product).select_related("user")
            serializer = ProductReviewSerializer(reviews, many=True)
            avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
            return Response({
                "product_id": product_id, "average_rating": avg_rating or 0,
                "total_reviews": reviews.count(), "reviews": serializer.data
            })
        reviews = ProductReview.objects.select_related("user", "product").all()
        serializer = ProductReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        product_id = request.data.get("product")
        if not product_id:
            return Response({"error": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        existing_review = ProductReview.objects.filter(product=product, user=request.user).first()

        if existing_review:

            serializer = ProductReviewSerializer(existing_review, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Review updated successfully.", "review": serializer.data}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = ProductReviewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReviewDetailAPIView(APIView):
    def put(self, request, review_id):
        try: review = ProductReview.objects.get(pk=review_id)
        except ProductReview.DoesNotExist: return Response({"error": "Review not found."}, status=status.HTTP_404_NOT_FOUND)
        if review.user != request.user and not request.user.is_staff:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ProductReviewSerializer(review, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, review_id):
        try: review = ProductReview.objects.get(pk=review_id)
        except ProductReview.DoesNotExist: return Response({"error": "Review not found."}, status=status.HTTP_404_NOT_FOUND)
        if review.user != request.user and not request.user.is_staff:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        review.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
