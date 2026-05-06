import logging

from celery import shared_task
from django.db import transaction

from .models import Product, ProductImage
from .services import BulkProductUploadService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def download_single_image_task(self, product_id, image_url):
    """Download one image and attach it to a product."""
    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        logger.warning(f"Product {product_id} not found; skipping {image_url}")
        return {"status": "product_not_found", "url": image_url}

    image_file = BulkProductUploadService.download_image_from_url(image_url)
    if not image_file:
        logger.error(
            f"Image download FAILED: product_id={product_id} url={image_url}"
        )
        return {
            "status": "download_failed",
            "url": image_url,
            "product_id": product_id,
        }

    with transaction.atomic():
        ProductImage.objects.create(product=product, image=image_file)
        product.refresh_from_db(fields=["product_image"])
        if not product.product_image:
            fresh_file = BulkProductUploadService.download_image_from_url(image_url)
            if fresh_file:
                product.product_image = fresh_file
                product.save(update_fields=["product_image"])

    logger.info(
        f"Image downloaded OK: product_id={product_id} url={image_url}"
    )
    return {"status": "success", "url": image_url, "product_id": product_id}


@shared_task
def download_product_images_task(product_id, image_urls):
    """Fan out individual download tasks so they run in parallel."""
    if not Product.objects.filter(id=product_id).exists():
        logger.warning(
            f"Product {product_id} not found; skipping bulk image download"
        )
        return

    for url in image_urls:
        download_single_image_task.delay(product_id, url)