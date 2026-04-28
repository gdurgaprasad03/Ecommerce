from django_elasticsearch_dsl import Document, Text, Integer, Keyword, Completion, Float
from django_elasticsearch_dsl.registries import registry
from products.models import Product
import logging

logger = logging.getLogger(__name__)


@registry.register_document
class ProductDocument(Document):
    name = Text(
        analyzer='standard',
        fields={
            'raw': Keyword(),
            'suggest': Completion(),
        }
    )
    description = Text(analyzer='standard')
    highlights = Text(analyzer='standard')
    
    category_name = Keyword()
    brand_name = Keyword()
    
    rating = Float()
    price_min = Float()
    price_max = Float()
    
    featured = Keyword()
    top_selling = Keyword()
    new_arrival = Keyword()
    
    in_stock = Keyword()
    
    class Index:
        name = 'products'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0,
            'analysis': {
                'analyzer': {
                    'standard': {
                        'type': 'standard',
                        'stopwords': '_english_',
                    }
                },
                'normalizer': {
                    'lowercase': {
                        'type': 'custom',
                        'char_filter': [],
                        'filter': ['lowercase'],
                    }
                }
            }
        }
    
    class Django:
        model = Product
        fields = [
            'id',
            'created_at',
            'updated_at',
        ]
    
    def prepare_category_name(self, instance):
        return instance.category.name if instance.category else ""
    
    def prepare_brand_name(self, instance):
        return instance.brand.name if instance.brand else ""
    
    def prepare_featured(self, instance):
        return "yes" if instance.featured else "no"
    
    def prepare_top_selling(self, instance):
        return "yes" if instance.top_selling else "no"
    
    def prepare_new_arrival(self, instance):
        return "yes" if instance.new_arrival else "no"
    
    def prepare_in_stock(self, instance):
        try:
            stock = instance.inventory.stock
            return "yes" if stock > 0 else "no"
        except:
            return "unknown"


class ElasticsearchSearchManager:
    @staticmethod
    def search(query_string, **kwargs):
        from elasticsearch_dsl import Q, Search
        try:
            s = Search(index='products')
            q = Q('multi_match', query=query_string, fields=[
                'name^3',
                'description',
                'highlights',
            ], fuzziness='AUTO', prefix_length=1)
            
            s = s.query(q)
            
            if kwargs.get('category'):
                s = s.filter('term', category_name=kwargs['category'])
            if kwargs.get('brand'):
                s = s.filter('term', brand_name=kwargs['brand'])
            if kwargs.get('in_stock'):
                s = s.filter('term', in_stock='yes')
            if kwargs.get('min_rating'):
                s = s.filter('range', rating={'gte': kwargs['min_rating']})
            if kwargs.get('featured'):
                s = s.filter('term', featured='yes')
            
            response = s.execute()
            
            results = []
            for hit in response:
                results.append({
                    'id': hit.meta.id,
                    'name': hit.name,
                    'description': hit.description[:200] if hit.description else '',
                    'rating': hit.rating,
                    'score': hit.meta.score,
                    'category': hit.category_name,
                    'brand': hit.brand_name,
                })
            return results
        except Exception as e:
            logger.warning(f"Elasticsearch search failed, falling back to database: {str(e)}")
            from products.models import Product
            from django.db.models import Q as DjangoQ
            
            queryset = Product.objects.filter(is_active=True)
            queryset = queryset.filter(
                DjangoQ(name__icontains=query_string) |
                DjangoQ(description__icontains=query_string)
            )
            
            if kwargs.get('category'):
                queryset = queryset.filter(category_id=kwargs['category'])
            if kwargs.get('brand'):
                queryset = queryset.filter(brand_id=kwargs['brand'])
            if kwargs.get('featured'):
                queryset = queryset.filter(featured=True)
            if kwargs.get('min_rating'):
                queryset = queryset.filter(rating__gte=kwargs['min_rating'])
            
            results = []
            for p in queryset[:20]:
                results.append({
                    'id': p.id,
                    'name': p.name,
                    'description': p.description[:200] if p.description else '',
                    'rating': p.rating,
                    'score': 1.0,
                    'category': p.category.name if p.category else None,
                    'brand': p.brand.name if p.brand else None,
                })
            return results
    
    @staticmethod
    def autocomplete(prefix, limit=10):
        from elasticsearch_dsl import Search
        try:
            s = Search(index='products')
            s.suggest('product_suggest', prefix, completion={
                'field': 'name.suggest',
                'size': limit,
                'skip_duplicates': True,
            })
            
            response = s.execute()
            suggestions = []
            if 'product_suggest' in response.suggest:
                for suggestion_set in response.suggest.product_suggest:
                    for suggestion in suggestion_set.options:
                        suggestions.append({
                            'text': suggestion.text,
                            'score': suggestion._score,
                        })
            return suggestions[:limit]
        except Exception as e:
            from products.models import Product
            suggestions = Product.objects.filter(
                name__istartswith=prefix, 
                is_active=True
            ).values_list('name', flat=True)[:limit]
            return [{'text': s, 'score': 1.0} for s in suggestions]
    
    @staticmethod
    def get_facets():
        from elasticsearch_dsl import Search, A
        try:
            s = Search(index='products')
            s.aggs.bucket('categories', A('terms', field='category_name', size=100))
            s.aggs.bucket('brands', A('terms', field='brand_name', size=100))
            s.aggs.bucket('ratings', A('terms', field='rating'))
            s.aggs.bucket('features', A('terms', field='featured'))
            
            response = s.execute()
            facets = {
                'categories': [{'name': cat.key, 'count': cat.doc_count} for cat in response.aggregations.categories.buckets],
                'brands': [{'name': brand.key, 'count': brand.doc_count} for brand in response.aggregations.brands.buckets],
                'ratings': [{'rating': rating.key, 'count': rating.doc_count} for rating in response.aggregations.ratings.buckets],
                'features': [{'type': feature.key, 'count': feature.doc_count} for feature in response.aggregations.features.buckets],
            }
            return facets
        except Exception as e:
            return {}
    
    @staticmethod
    def index_product(product):
        try:
            doc = ProductDocument()
            doc.meta.id = product.id
            doc.save()
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def delete_product_index(product_id):
        try:
            doc = ProductDocument()
            doc.meta.id = product_id
            doc.delete()
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def reindex_all():
        try:
            from products.models import Product
            ProductDocument._index.delete(ignore=404)
            ProductDocument._index.create()
            products = Product.objects.filter(is_active=True)
            for product in products:
                ElasticsearchSearchManager.index_product(product)
            return True
        except Exception as e:
            return False
