from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User

from orders.models import CustomerRequest
from inventory.models import Inventory
from products.models import Product, Category, Brand, ProductImage
from reviews.models import ProductReview
from wishlist.models import Wishlist
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inventory side-effect on closed customer requests
# ---------------------------------------------------------------------------

@receiver(post_save, sender=CustomerRequest)
def update_inventory_on_closed_request(sender, instance, **kwargs):
    """
    Automatically decrements product stock when a customer request is marked as 'closed'.
    """
    if instance.status == CustomerRequest.STATUS_CLOSED and not instance.stock_deducted:
        try:
            with transaction.atomic():
                inventory = Inventory.objects.select_for_update().get(product=instance.product)

                if inventory.stock >= instance.quantity:
                    inventory.stock -= instance.quantity
                    inventory.save(update_fields=["stock"])
                    CustomerRequest.objects.filter(pk=instance.pk).update(stock_deducted=True)
                    logger.info(f"Inventory updated for {instance.product.name}: -{instance.quantity} units.")
                else:
                    logger.warning(
                        f"Insufficient stock for {instance.product.name}. "
                        f"Available: {inventory.stock}, Requested: {instance.quantity}"
                    )

        except Inventory.DoesNotExist:
            logger.error(f"Inventory record missing for product: {instance.product.name}")
        except Exception as e:
            logger.exception(f"Failed to update inventory for request {instance.id}: {str(e)}")


# ---------------------------------------------------------------------------
# Product save -> cache invalidation
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Product)
def invalidate_product_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate caches that depend on this product when it's saved."""
    from core.cache_utils import CacheManager

    try:
        CacheManager.clear_product_cache(instance.id)
        CacheManager.clear_product_list_cache()
        CacheManager.clear_analytics_cache()
        logger.debug(f"Cache invalidated for product save: {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for product save {instance.id}: {str(e)}")


# ---------------------------------------------------------------------------
# Product DELETE -> cache invalidation + Elasticsearch cleanup
# THIS IS THE FIX for ghost products appearing after delete.
# ---------------------------------------------------------------------------

@receiver(post_delete, sender=Product)
def on_product_deleted(sender, instance, **kwargs):
    """
    Runs when a Product row is removed. Two responsibilities:
      1. Wipe every cache key that could still hold this product.
      2. Drop it from the Elasticsearch index.

    Cache failures are logged at ERROR level (not warning, not swallowed)
    because a silent failure here is exactly the "deleted product still
    shows up on refresh" bug that prompted this fix.
    """
    from core.cache_utils import CacheManager
    from search.search import ElasticsearchSearchManager

    product_id = instance.id

    # 1. Cache invalidation
    try:
        CacheManager.clear_product_cache(product_id)          # product:<id>* + product_images:<id>
        CacheManager.clear_product_list_cache()               # product_list:*
        CacheManager.clear_analytics_cache()                  # analytics:*
        CacheManager.delete_cache(f"product_specs:{product_id}")
        CacheManager.delete_cache(f"product_reviews:{product_id}")
        CacheManager.delete_cache(f"product_inventory:{product_id}")
        logger.info(f"Cache cleared for deleted product {product_id}")
    except Exception as e:
        logger.error(
            f"FAILED to invalidate cache for deleted product {product_id}: {e}",
            exc_info=True,
        )

    # 2. Elasticsearch cleanup
    try:
        ElasticsearchSearchManager.delete_product_index(product_id)
        logger.debug(f"Product {product_id} removed from Elasticsearch")
    except Exception as e:
        logger.warning(
            f"Error removing product {product_id} from Elasticsearch: {e}"
        )


# ---------------------------------------------------------------------------
# Category / Brand cache invalidation
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Category)
def invalidate_category_cache(sender, instance, created, **kwargs):
    from core.cache_utils import CacheManager
    try:
        CacheManager.clear_category_cache(instance.id)
        CacheManager.clear_product_list_cache()
        logger.debug(f"Cache invalidated for category: {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for category {instance.id}: {str(e)}")


@receiver(post_delete, sender=Category)
def invalidate_category_cache_on_delete(sender, instance, **kwargs):
    from core.cache_utils import CacheManager
    try:
        CacheManager.clear_category_cache(instance.id)
        CacheManager.clear_product_list_cache()
        logger.info(f"Cache cleared for deleted category: {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for deleted category {instance.id}: {str(e)}")


@receiver(post_save, sender=Brand)
def invalidate_brand_cache(sender, instance, created, **kwargs):
    from core.cache_utils import CacheManager
    try:
        CacheManager.clear_brand_cache(instance.id)
        CacheManager.clear_product_list_cache()
        logger.debug(f"Cache invalidated for brand: {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for brand {instance.id}: {str(e)}")


@receiver(post_delete, sender=Brand)
def invalidate_brand_cache_on_delete(sender, instance, **kwargs):
    from core.cache_utils import CacheManager
    try:
        CacheManager.clear_brand_cache(instance.id)
        CacheManager.clear_product_list_cache()
        logger.info(f"Cache cleared for deleted brand: {instance.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for deleted brand {instance.id}: {str(e)}")


# ---------------------------------------------------------------------------
# ProductImage gallery caches
# ---------------------------------------------------------------------------

@receiver(post_save, sender=ProductImage)
def invalidate_product_images_cache_on_save(sender, instance, **kwargs):
    """Drop the cached gallery list so a newly uploaded image appears
    immediately on the next product detail fetch."""
    from core.cache_utils import CacheManager
    try:
        CacheManager.delete_cache(f"product_images:{instance.product_id}")
        CacheManager.clear_product_cache(instance.product_id)
        CacheManager.clear_product_list_cache()
    except Exception as e:
        logger.error(f"Error invalidating product image cache: {str(e)}")


@receiver(post_delete, sender=ProductImage)
def invalidate_product_images_cache_on_delete(sender, instance, **kwargs):
    """Same as above but for image deletion."""
    from core.cache_utils import CacheManager
    try:
        CacheManager.delete_cache(f"product_images:{instance.product_id}")
        CacheManager.clear_product_cache(instance.product_id)
        CacheManager.clear_product_list_cache()
    except Exception as e:
        logger.error(f"Error invalidating product image cache: {str(e)}")


# ---------------------------------------------------------------------------
# Inventory cache + low-stock alerts
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Inventory)
def invalidate_inventory_cache(sender, instance, created, **kwargs):
    from core.cache_utils import CacheManager
    try:
        CacheManager.delete_cache(f"product_inventory:{instance.product.id}")
        CacheManager.clear_product_cache(instance.product.id)

        if instance.stock < 10:
            from core.tasks import notify_stock_low
            notify_stock_low.delay(instance.product.id)

        logger.debug(f"Cache invalidated for inventory: {instance.product.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for inventory: {str(e)}")


# ---------------------------------------------------------------------------
# Reviews cache
# ---------------------------------------------------------------------------

@receiver(post_save, sender=ProductReview)
def invalidate_product_review_cache(sender, instance, created, **kwargs):
    from core.cache_utils import CacheManager
    try:
        CacheManager.delete_cache(f"product_reviews:{instance.product.id}")
        CacheManager.clear_product_cache(instance.product.id)
        CacheManager.clear_analytics_cache("reviews")
        logger.debug(f"Cache invalidated for product reviews: {instance.product.id}")
    except Exception as e:
        logger.error(f"Error invalidating cache for product reviews: {str(e)}")


# ---------------------------------------------------------------------------
# Welcome email on user creation
# ---------------------------------------------------------------------------

@receiver(post_save, sender=User)
def send_welcome_email_on_user_creation(sender, instance, created, **kwargs):
    """Send welcome email when new user registers"""
    if created:
        from core.tasks import send_welcome_email
        try:
            send_welcome_email.apply_async(args=[instance.id], countdown=5)
            logger.info(f"Welcome email task queued for user: {instance.email}")
        except Exception as e:
            logger.error(f"Error queuing welcome email for user {instance.id}: {str(e)}")


# ---------------------------------------------------------------------------
# Elasticsearch indexing for Product (save side; delete handled above)
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Product)
def index_product_in_elasticsearch(sender, instance, created, **kwargs):
    """Index product in Elasticsearch when created/updated."""
    if instance.is_active:
        from search.search import ElasticsearchSearchManager
        try:
            ElasticsearchSearchManager.index_product(instance)
            logger.debug(f"Product {instance.id} indexed in Elasticsearch")
        except Exception as e:
            logger.warning(f"Error indexing product {instance.id} in Elasticsearch: {str(e)}")