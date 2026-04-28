from django.urls import path
from .views import ElasticsearchSearchAPIView, AutocompleteAPIView, SearchFacetsAPIView

urlpatterns = [
    path("search/", ElasticsearchSearchAPIView.as_view(), name="elasticsearch-search"),
    path("search/autocomplete/", AutocompleteAPIView.as_view(), name="autocomplete"),
    path("search/facets/", SearchFacetsAPIView.as_view(), name="search-facets"),
]
