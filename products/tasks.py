import logging
from celery import shared_task
from .models import Product, ProductImage
from .services import BulkProductUploadService

logger = logging.getLogger(__name__)

@shared_task
def download_product_images_task(product_id, image_urls):
    try:
        product = Product.objects.get(id=product_id)
        for url in image_urls:
            image_file = BulkProductUploadService.download_image_from_url(url)
            if image_file:
                ProductImage.objects.create(
                    product=product,
                    image=image_file
                )
    except Product.DoesNotExist:
        logger.warning(f"Product {product_id} not found for image downloading.")
    except Exception as e:
        logger.error(f"Error in download_product_images_task: {str(e)}")
