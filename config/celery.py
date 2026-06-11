import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.task_routes = {
    # ── Email tasks (emails queue) ──────────────────────────────────────────
    "core.tasks.send_otp_email_task":            {"queue": "emails"},
    "core.tasks.send_welcome_email":             {"queue": "emails"},
    "core.tasks.send_stock_alert_email":         {"queue": "emails"},
    "core.tasks.send_price_drop_email":          {"queue": "emails"},
    "core.tasks.send_review_notification_email": {"queue": "emails"},
    "core.tasks.send_wishlist_reminder_email":   {"queue": "emails"},
    "core.tasks.send_customer_request_email":    {"queue": "emails"},
    "core.tasks.send_enquiry_email":             {"queue": "emails"},
    "core.tasks.send_quote_status_email":        {"queue": "emails"},

    # ── Alert tasks (alerts queue) ──────────────────────────────────────────
    "core.tasks.notify_stock_low":               {"queue": "alerts"},
    "core.tasks.check_stock_alerts":             {"queue": "alerts"},

    # ── Analytics & maintenance tasks (analytics queue) ─────────────────────
    "core.tasks.generate_analytics_snapshot":    {"queue": "analytics"},
    "core.tasks.clean_expired_otps":             {"queue": "analytics"},
    "core.tasks.ping_database":                  {"queue": "analytics"},
}


@app.task(bind=True)
def debug_task(self):
    """Debug task — use to verify Celery worker is alive and routing correctly."""
    print(f"Request: {self.request!r}")