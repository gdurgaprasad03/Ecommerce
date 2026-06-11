from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 20

class PaginatedAPIView(APIView):
    pagination_class = StandardPagination

    def paginate(self, request, queryset, serializer_class):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)

        if page is not None:
            serializer = serializer_class(page, many=True, context={"request": request})
            return paginator.get_paginated_response(serializer.data)

        serializer = serializer_class(queryset, many=True, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
