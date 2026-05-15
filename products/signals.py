"""
Product-specific signal handlers.

Cache invalidation for Product save/delete lives in core/signals.py
to keep a single source of truth. This module only handles side effects
that are PRODUCT-app specific:
  - Gallery image cache busts on ProductImage add/remove
  - Spec cache busts on ProductSpecification add/remove
  - Optional secondary Elasticsearch sync (gated by USE_ELASTICSEARCH)
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
import logging

from .models import Product, ProductImage, ProductSpecification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def sync_product_to_elasticsearch_on_save(sender, instance, **kwargs):
    """Push product to ES index on save (only if USE_ELASTICSEARCH=True)."""
    if not getattr(settings, "USE_ELASTICSEARCH", False):
        return
    try:
        from search.search import ElasticsearchSearchManager
        ElasticsearchSearchManager.index_product(instance)
        logger.debug(f"Synced product {instance.id} to Elasticsearch (post_save)")
    except Exception as e:
        logger.error(f"Elasticsearch sync failed on save for product {instance.id}: {e}")


@receiver(post_delete, sender=Product)
def sync_product_to_elasticsearch_on_delete(sender, instance, **kwargs):
    """Drop product from ES index on delete (only if USE_ELASTICSEARCH=True)."""
    if not getattr(settings, "USE_ELASTICSEARCH", False):
        return
    try:
        from search.search import ElasticsearchSearchManager
        ElasticsearchSearchManager.delete_product_index(instance.id)
        logger.debug(f"Removed product {instance.id} from Elasticsearch (post_delete)")
    except Exception as e:
        logger.error(f"Elasticsearch sync failed on delete for product {instance.id}: {e}")


@receiver(post_save, sender=ProductImage)
@receiver(post_delete, sender=ProductImage)
def invalidate_image_caches_on_gallery_change(sender, instance, **kwargs):
    """
    When a ProductImage row is added/removed, bust:
      - the per-product gallery cache (product_images:<id>)
      - the product detail cache (product:<id>*)
      - the product list cache (product_list:*)
    because all three can embed image URLs.
    """
    from core.cache_utils import CacheManager
    try:
        CacheManager.delete_cache(f"product_images:{instance.product_id}")
        CacheManager.clear_product_cache(instance.product_id)
        CacheManager.clear_product_list_cache()
        logger.debug(
            f"Image caches cleared (product_id={instance.product_id})"
        )
    except Exception as e:
        logger.error(
            f"Failed to clear image cache for product {instance.product_id}: {e}"
        )


@receiver(post_save, sender=ProductSpecification)
@receiver(post_delete, sender=ProductSpecification)
def invalidate_spec_cache_on_change(sender, instance, **kwargs):
    """Bust the specifications sub-cache when specs change."""
    from core.cache_utils import CacheManager
    try:
        CacheManager.delete_cache(f"product_specs:{instance.product_id}")
        CacheManager.clear_product_cache(instance.product_id)
    except Exception as e:
        logger.error(
            f"Failed to clear spec cache for product {instance.product_id}: {e}"
        )