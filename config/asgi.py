import os
import logging

from django.asgi import get_asgi_application

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    application = get_asgi_application()
except Exception as e:
    logger.error(f"Failed to initialize ASGI application: {str(e)}")
    raise
