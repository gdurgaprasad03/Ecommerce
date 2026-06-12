import logging

from django.db import IntegrityError
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Wishlist
from .serializers import WishlistSerializer
from products.models import Product

logger = logging.getLogger(__name__)


class WishlistAPIView(APIView):
    """
    GET  /wishlist/             -> Return current user's wishlist (creates one if missing).
    POST /wishlist/             -> Add a product  (body: { "product_id": 5 })
    PUT  /wishlist/             -> Bulk-replace wishlist (body: { "products": [1, 2, 3] }).
    DELETE /wishlist/           -> Clear the entire wishlist.
    """
    permission_classes = [IsAuthenticated]

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #
    def _get_or_create_wishlist(self, user):
        """Return (wishlist, created). Never raises."""
        return Wishlist.objects.get_or_create(user=user)

    def _get_product(self, product_id):
        """
        Validate and fetch a product by PK.
        Returns (product, error_response).  One of them will always be None.
        """
        if not product_id:
            return None, Response(
                {"error": "product_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not str(product_id).isdigit():
            return None, Response(
                {"error": "product_id must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            return Product.objects.get(pk=product_id, is_active=True), None
        except Product.DoesNotExist:
            return None, Response(
                {"error": f"Product with id {product_id} does not exist or is no longer available."},
                status=status.HTTP_404_NOT_FOUND,
            )

    # ------------------------------------------------------------------ #
    # GET  /wishlist/                                                       #
    # ------------------------------------------------------------------ #
    def get(self, request):
        try:
            wishlist, _ = self._get_or_create_wishlist(request.user)
            serializer = WishlistSerializer(wishlist, context={"request": request})
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Unexpected error fetching wishlist for user {request.user.id}: {e}", exc_info=True)
            return Response(
                {"error": "Unable to load your wishlist right now. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------------------------------------ #
    # PUT  /wishlist/   (bulk-replace — merge guest wishlist on login)     #
    # ------------------------------------------------------------------ #
    def put(self, request):
        """
        PUT /wishlist/wishlist/
        Body: { "products": [1, 2, 3] }
        Bulk-replaces the wishlist — used to merge guest wishlist on login.
        """
        product_ids = request.data.get("products", [])
        if not isinstance(product_ids, list):
            return Response(
                {"error": "products must be a list of product IDs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        wishlist, _ = self._get_or_create_wishlist(request.user)

        valid_ids = list(
            Product.objects.filter(
                pk__in=product_ids, is_active=True
            ).values_list("pk", flat=True)
        )

        wishlist.products.set(valid_ids)   # replaces existing M2M items atomically
        serializer = WishlistSerializer(wishlist, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ------------------------------------------------------------------ #
    # POST /wishlist/   (add a product)                                    #
    # ------------------------------------------------------------------ #
    def post(self, request):
        product_id = request.data.get("product_id")
        product, err = self._get_product(product_id)
        if err:
            return err

        try:
            wishlist, _ = self._get_or_create_wishlist(request.user)

            if wishlist.products.filter(pk=product.pk).exists():
                return Response(
                    {"message": "This product is already in your wishlist."},
                    status=status.HTTP_200_OK,
                )

            wishlist.products.add(product)
            serializer = WishlistSerializer(wishlist, context={"request": request})
            return Response(
                {"message": f'"{product.name}" has been added to your wishlist.', "wishlist": serializer.data},
                status=status.HTTP_200_OK,
            )
        except IntegrityError as e:
            logger.error(f"DB integrity error adding product {product_id} to wishlist: {e}", exc_info=True)
            return Response(
                {"error": "Could not add the product to your wishlist due to a data conflict. Please try again."},
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as e:
            logger.error(f"Unexpected error adding product {product_id} to wishlist: {e}", exc_info=True)
            return Response(
                {"error": "Something went wrong while adding the product. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------------------------------------ #
    # DELETE /wishlist/{product_id}/   (remove ONE product)               #
    # ------------------------------------------------------------------ #
    def delete(self, request, product_id=None):
        """
        If a product_id is provided in the URL → remove that single product.
        If no product_id → clear the entire wishlist.
        """
        try:
            wishlist = Wishlist.objects.get(user=request.user)
        except Wishlist.DoesNotExist:
            return Response(
                {"error": "You don't have a wishlist yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ---- Remove a single product ----
        if product_id is not None:
            product, err = self._get_product(product_id)
            if err:
                return err

            if not wishlist.products.filter(pk=product.pk).exists():
                return Response(
                    {"error": f'"{product.name}" is not in your wishlist.'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            try:
                wishlist.products.remove(product)
                serializer = WishlistSerializer(wishlist, context={"request": request})
                return Response(
                    {"message": f'"{product.name}" has been removed from your wishlist.', "wishlist": serializer.data},
                    status=status.HTTP_200_OK,
                )
            except Exception as e:
                logger.error(f"Error removing product {product_id} from wishlist: {e}", exc_info=True)
                return Response(
                    {"error": "Could not remove the product from your wishlist. Please try again."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # ---- Clear entire wishlist ----
        try:
            wishlist.products.clear()          # clears M2M items, doesn't delete the wishlist row
            return Response(
                {"message": "Your wishlist has been cleared."},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Error clearing wishlist for user {request.user.id}: {e}", exc_info=True)
            return Response(
                {"error": "Could not clear your wishlist. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )