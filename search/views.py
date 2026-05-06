from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
import logging

logger = logging.getLogger(__name__)

class ElasticsearchSearchAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from .search import ElasticsearchSearchManager
        query = request.query_params.get('q', '')
        if not query or len(query) < 2:
            return Response({"error": "Search query must be at least 2 characters"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            filters = {
                'category': request.query_params.get('category'),
                'brand': request.query_params.get('brand'),
                'in_stock': request.query_params.get('in_stock', '').lower() == 'true',
                'min_rating': float(request.query_params.get('min_rating', 0)),
                'featured': request.query_params.get('featured', '').lower() == 'true',
            }
            filters = {k: v for k, v in filters.items() if v is not None}
            results = ElasticsearchSearchManager.search(query, **filters)

            return Response({'query': query, 'count': len(results), 'results': results}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Elasticsearch search error: {str(e)}")
            return Response({"error": "Search failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AutocompleteAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from .search import ElasticsearchSearchManager
        prefix = request.query_params.get('prefix', '')
        if not prefix or len(prefix) < 2:
            return Response({"suggestions": []}, status=status.HTTP_200_OK)

        try:
            suggestions = ElasticsearchSearchManager.autocomplete(prefix)
            return Response({'prefix': prefix, 'suggestions': suggestions}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Autocomplete error: {str(e)}")
            return Response({'suggestions': []}, status=status.HTTP_200_OK)

class SearchFacetsAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from .search import ElasticsearchSearchManager
        try:
            facets = ElasticsearchSearchManager.get_facets()
            return Response(facets, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching facets: {str(e)}")
            return Response({"error": "Failed to fetch search facets"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
