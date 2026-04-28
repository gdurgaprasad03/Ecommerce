from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Wishlist
from .serializers import WishlistSerializer
from products.models import Product

class WishlistAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try: wishlist = Wishlist.objects.get(user=request.user)
        except Wishlist.DoesNotExist: wishlist = Wishlist.objects.create(user=request.user)
        serializer = WishlistSerializer(wishlist)
        return Response(serializer.data)
    
    def post(self, request):
        try: wishlist = Wishlist.objects.get(user=request.user)
        except Wishlist.DoesNotExist: wishlist = Wishlist.objects.create(user=request.user)
        
        product_id = request.data.get("product_id")
        action = request.data.get("action", "add")
        
        if not product_id:
            return Response({"error": "product_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try: product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)
        
        if action == "add":
            wishlist.products.add(product)
            message = "Product added to wishlist."
        elif action == "remove":
            wishlist.products.remove(product)
            message = "Product removed from wishlist."
        else:
            return Response({"error": "Invalid action. Use 'add' or 'remove'."}, status=status.HTTP_400_BAD_REQUEST)
        
        
        
         
        serializer = WishlistSerializer(wishlist)
        return Response({"message": message, "wishlist": serializer.data}, status=status.HTTP_200_OK)

    def delete(self, request):
        try: wishlist = Wishlist.objects.get(user=request.user)
        except Wishlist.DoesNotExist:
            return Response({"error": "Wishlist not found."}, status=status.HTTP_404_NOT_FOUND)
        
        wishlist.delete()
        return Response({"message": "Wishlist cleared."}, status=status.HTTP_200_OK)