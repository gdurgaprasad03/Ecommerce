"""
Celery configuration for the ecommerce project
"""

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.task_routes = {
    'core.tasks.send_otp_email_task': {'queue': 'emails'},
    'core.tasks.send_welcome_email': {'queue': 'emails'},
    'core.tasks.send_stock_alert_email': {'queue': 'emails'},
    'core.tasks.send_price_drop_email': {'queue': 'emails'},
    'core.tasks.send_review_notification_email': {'queue': 'emails'},
    'core.tasks.send_wishlist_reminder_email': {'queue': 'emails'},
    'core.tasks.notify_stock_low': {'queue': 'alerts'},
    'core.tasks.generate_analytics_snapshot': {'queue': 'analytics'},
}

@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f'Request: {self.request!r}')
