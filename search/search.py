from django_elasticsearch_dsl import Document, fields, Text, Integer, Keyword, Completion, Float
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
    sku = Keyword()
    mpn = Keyword()

    category = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(),
    })
    subcategory = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(),
    })
    brand = fields.ObjectField(properties={
        'id': fields.IntegerField(),
        'name': fields.TextField(),
    })

    rating = Float()
    featured = Keyword()
    top_selling = Keyword()
    new_arrival = Keyword()
    is_active = Keyword()

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

    def prepare_category(self, instance):
        return {'id': instance.category.id, 'name': instance.category.name} if instance.category else None

    def prepare_subcategory(self, instance):
        return {'id': instance.subcategory.id, 'name': instance.subcategory.name} if instance.subcategory else None

    def prepare_brand(self, instance):
        return {'id': instance.brand.id, 'name': instance.brand.name} if instance.brand else None

    def prepare_featured(self, instance):
        return "yes" if instance.featured else "no"

    def prepare_top_selling(self, instance):
        return "yes" if instance.top_selling else "no"

    def prepare_new_arrival(self, instance):
        return "yes" if instance.new_arrival else "no"

    def prepare_is_active(self, instance):
        return "yes" if instance.is_active else "no"

class ElasticsearchSearchManager:
    @staticmethod
    def search(query_string='', **kwargs):
        from elasticsearch_dsl import Q, Search
        try:
            s = Search(index='products')

            if query_string:
                q = Q('multi_match', query=query_string, fields=[
                    'name^3',
                    'description',
                    'highlights',
                    'sku',
                    'mpn',
                ], fuzziness='AUTO', prefix_length=1)
                s = s.query(q)
            else:
                s = s.query('match_all')

            if kwargs.get('category_id'):
                s = s.filter('term', category__id=kwargs['category_id'])
            if kwargs.get('subcategory_id'):
                s = s.filter('term', subcategory__id=kwargs['subcategory_id'])
            if kwargs.get('brand_id'):
                s = s.filter('term', brand__id=kwargs['brand_id'])
            if kwargs.get('featured'):
                s = s.filter('term', featured='yes')
            if kwargs.get('top_selling'):
                s = s.filter('term', top_selling='yes')
            if kwargs.get('new_arrival'):
                s = s.filter('term', new_arrival='yes')
            if kwargs.get('is_active') is not None:
                val = "yes" if kwargs['is_active'] else "no"
                s = s.filter('term', is_active=val)
            else:
                s = s.filter('term', is_active='yes')

            if kwargs.get('min_rating'):
                s = s.filter('range', rating={'gte': kwargs['min_rating']})

            sort_by = kwargs.get('sort', '-created_at')
            if sort_by == 'price_low':
                s = s.sort('price')
            elif sort_by == 'price_high':
                s = s.sort('-price')
            elif sort_by == 'rating':
                s = s.sort('-rating')
            elif sort_by == 'newest':
                s = s.sort('-created_at')
            else:
                s = s.sort('-created_at')

            page = int(kwargs.get('page', 1))
            page_size = int(kwargs.get('page_size', 20))
            start = (page - 1) * page_size
            s = s[start:start + page_size]

            response = s.execute()

            product_ids = [hit.meta.id for hit in response]
            logger.debug(f"Elasticsearch search completed: query='{query_string}', results={len(product_ids)}")
            return {
                'ids': product_ids,
                'total': response.hits.total.value,
                'took': response.took,
            }
        except Exception as e:
            logger.error(f"Elasticsearch search failed for query '{query_string}': {str(e)}", exc_info=True)
            return None

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
            logger.warning(f"Elasticsearch autocomplete failed: {str(e)}, falling back to database")
            try:
                from products.models import Product
                suggestions = Product.objects.filter(
                    name__istartswith=prefix,
                    is_active=True
                ).values_list('name', flat=True)[:limit]
                return [{'text': s, 'score': 1.0} for s in suggestions]
            except Exception as db_error:
                logger.error(f"Autocomplete database fallback failed: {str(db_error)}")
                return []

    @staticmethod
    def get_facets():
        from elasticsearch_dsl import Search, A
        try:
            s = Search(index='products').filter('term', is_active='yes')
            s.aggs.bucket('categories', A('terms', field='category.name.raw', size=100))
            s.aggs.bucket('brands', A('terms', field='brand.name.raw', size=100))
            s.aggs.bucket('ratings', A('terms', field='rating'))

            response = s.execute()
            facets = {
                'categories': [{'name': cat.key, 'count': cat.doc_count} for cat in response.aggregations.categories.buckets],
                'brands': [{'name': brand.key, 'count': brand.doc_count} for brand in response.aggregations.brands.buckets],
                'ratings': [{'rating': rating.key, 'count': rating.doc_count} for rating in response.aggregations.ratings.buckets],
            }
            logger.debug(f"Retrieved facets successfully")
            return facets
        except Exception as e:
            logger.error(f"Error fetching facets: {str(e)}", exc_info=True)
            return {}

    @staticmethod
    def index_product(product):
        try:
            doc = ProductDocument()
            doc.meta.id = product.id
            doc.save()
            logger.debug(f"Product {product.id} indexed successfully")
            return True
        except Exception as e:
            logger.error(f"Error indexing product {product.id}: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def delete_product_index(product_id):
        try:
            doc = ProductDocument()
            doc.meta.id = product_id
            doc.delete()
            logger.debug(f"Product {product_id} deleted from index")
            return True
        except Exception as e:
            logger.warning(f"Error deleting product {product_id} from index: {str(e)}")
            return False

    @staticmethod
    def reindex_all():
        try:
            from products.models import Product
            ProductDocument._index.delete(ignore=404)
            ProductDocument._index.create()
            products = Product.objects.filter(is_active=True)
            indexed_count = 0
            for product in products:
                if ElasticsearchSearchManager.index_product(product):
                    indexed_count += 1
            logger.info(f"Reindexed {indexed_count} products in Elasticsearch")
            return True
        except Exception as e:
            logger.error(f"Error during full reindex: {str(e)}", exc_info=True)
            return False
