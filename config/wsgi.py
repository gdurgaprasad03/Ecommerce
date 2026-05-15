import os
import logging

from django.core.wsgi import get_wsgi_application

logger = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    application = get_wsgi_application()
except Exception as e:
    logger.error(f"Failed to initialize WSGI application: {str(e)}")
    raise
