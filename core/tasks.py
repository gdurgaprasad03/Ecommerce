from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models import Count, Avg
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Welcome Email
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    """Send branded HTML welcome email to a newly registered user."""
    try:
        user = User.objects.get(id=user_id)
        subject = "Welcome to NxSys Digital — Your Account is Ready!"
        context = {
            "user_name": user.first_name or user.username,
            "email": user.email,
            "frontend_url": getattr(settings, "FRONTEND_BASE_URL", ""),
        }
        html_message = render_to_string("emails/welcome.html", context)
        plain_message = (
            f"Welcome {context['user_name']}!\n\n"
            f"Your NxSys Digital account is now active.\n"
            f"Browse products: {context['frontend_url']}/products\n\n"
            f"Need help? Contact us at sales@sriainfotech.com"
        )
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send()
        logger.info(f"Welcome email sent to {user.email}")
        return f"Welcome email sent to {user.email}"
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found — cannot send welcome email")
        return f"User {user_id} not found"
    except Exception as exc:
        logger.error(f"Error sending welcome email to user {user_id}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


# ─────────────────────────────────────────────────────────────────────────────
# Stock & Price Alerts
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def send_stock_alert_email(self, product_id, user_emails):
    """Notify interested users when a product comes back into stock."""
    try:
        from products.models import Product
        product = Product.objects.get(id=product_id)
        subject = f"Good news! {product.name} is back in stock!"
        context = {
            "product_name": product.name,
            "product_id": product.id,
            "product_url": f"{settings.FRONTEND_BASE_URL}/product/{product.id}",
            "frontend_url": settings.FRONTEND_BASE_URL,
        }
        html_message = render_to_string("emails/stock_alert.html", context)
        text_message = render_to_string("emails/stock_alert.txt", context)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=user_emails,
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        logger.info(f"Stock alert sent for '{product.name}' to {len(user_emails)} users")
        return f"Stock alert sent for {product.name}"
    except Exception as exc:
        logger.error(f"Error sending stock alert for product {product_id}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_price_drop_email(self, product_id, user_emails, old_price, new_price):
    """Notify users who wishlisted a product when its price drops."""
    try:
        from products.models import Product
        product = Product.objects.get(id=product_id)
        discount_percent = ((old_price - new_price) / old_price) * 100
        subject = f"Price Drop Alert: {product.name} is now ₹{new_price}!"
        context = {
            "product_name": product.name,
            "old_price": old_price,
            "new_price": new_price,
            "discount_percent": round(discount_percent, 1),
            "product_url": f"{settings.FRONTEND_BASE_URL}/product/{product.id}",
            "frontend_url": settings.FRONTEND_BASE_URL,
        }
        html_message = render_to_string("emails/price_drop.html", context)
        text_message = render_to_string("emails/price_drop.txt", context)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=user_emails,
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        logger.info(f"Price drop alert sent for '{product.name}' to {len(user_emails)} users")
        return f"Price drop alert sent for {product.name}"
    except Exception as exc:
        logger.error(f"Error sending price drop email for product {product_id}: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_review_notification_email(self, review_id, product_id):
    """Notify users who wishlisted a product when a new review is posted."""
    try:
        from products.models import Product
        from reviews.models import ProductReview
        product = Product.objects.get(id=product_id)
        review = ProductReview.objects.get(id=review_id)
        subject = f"New Review: {product.name} — {review.rating}★"
        context = {
            "product_name": product.name,
            "reviewer_name": review.user.first_name or review.user.username,
            "rating": review.rating,
            "title": review.title,
            "comment": (
                review.comment[:200] + "..."
                if len(review.comment) > 200
                else review.comment
            ),
            "product_url": f"{settings.FRONTEND_BASE_URL}/product/{product.id}",
            "frontend_url": settings.FRONTEND_BASE_URL,
        }
        html_message = render_to_string("emails/review_notification.html", context)
        text_message = render_to_string("emails/review_notification.txt", context)
        from wishlist.models import Wishlist
        wishlisted_users = Wishlist.objects.filter(
            products=product
        ).values_list("user__email", flat=True)
        if wishlisted_users:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=list(wishlisted_users),
            )
            email.attach_alternative(html_message, "text/html")
            email.send()
            logger.info(
                f"Review notification sent for '{product.name}' "
                f"to {len(wishlisted_users)} users"
            )
        return "Review notification sent"
    except Exception as exc:
        logger.error(f"Error sending review notification: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_wishlist_reminder_email(self, user_id):
    """Send a wishlist reminder email to a user."""
    try:
        from wishlist.models import Wishlist
        user = User.objects.get(id=user_id)
        wishlist = Wishlist.objects.get(user=user)
        products = wishlist.products.filter(is_active=True)[:5]
        if not products:
            return "No active products in wishlist — skipped"
        subject = "Your Wishlist Items — Don't Miss Out!"
        context = {
            "user_name": user.first_name or user.username,
            "products": products,
            "product_count": wishlist.products.count(),
            "frontend_url": settings.FRONTEND_BASE_URL,
            "wishlist_url": f"{settings.FRONTEND_BASE_URL}/wishlist",
        }
        html_message = render_to_string("emails/wishlist_reminder.html", context)
        text_message = render_to_string("emails/wishlist_reminder.txt", context)
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        logger.info(f"Wishlist reminder sent to {user.email}")
        return f"Wishlist reminder sent to {user.email}"
    except Exception as exc:
        logger.error(f"Error sending wishlist reminder: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


# ─────────────────────────────────────────────────────────────────────────────
# Low Stock Alerts
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2)
def notify_stock_low(self, product_id):
    """
    Notify the admin team when a product's stock falls below the threshold.
    Includes direct links to the admin panel for quick action.
    """
    try:
        from products.models import Product
        product = Product.objects.get(id=product_id)
        admin_email = getattr(settings, "SALES_NOTIFICATION_EMAIL", "")
        if not admin_email:
            logger.warning("SALES_NOTIFICATION_EMAIL not set — skipping low stock alert")
            return "Skipped: no admin email configured"
        frontend_url = getattr(settings, "FRONTEND_BASE_URL", "")
        context = {
            "product_name": product.name,
            "product_id": product.id,
            "stock": product.inventory.stock,
            "threshold": 10,
            "detected_at": timezone.now().strftime("%d %b %Y, %I:%M %p"),
            "admin_product_url": f"{frontend_url}/admin/products/{product.id}",
            "admin_inventory_url": f"{frontend_url}/admin/inventory",
        }
        html_message = render_to_string("emails/admin_low_stock.html", context)
        plain_message = (
            f"LOW STOCK ALERT\n\n"
            f"Product  : {product.name} (ID: {product.id})\n"
            f"Stock    : {product.inventory.stock} units remaining\n"
            f"Threshold: 10 units\n"
            f"Detected : {context['detected_at']}\n\n"
            f"Admin link: {context['admin_product_url']}"
        )
        msg = EmailMultiAlternatives(
            subject=f"⚠️ Low Stock: {product.name} ({product.inventory.stock} units left)",
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[admin_email],
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send()
        logger.warning(f"Low stock notification sent for '{product.name}'")
        return f"Low stock notification sent for {product.name}"
    except Exception as exc:
        logger.error(f"Error sending low stock notification: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=2)
def check_stock_alerts(self):
    """
    Periodic task — scans all products for low stock and dispatches
    alert emails to users who wishlisted those products.
    Uses a single grouped query instead of one query per product (avoids N+1).
    """
    try:
        from collections import defaultdict
        from products.models import Product
        from wishlist.models import Wishlist

        low_stock_products = list(
            Product.objects.filter(
                inventory__stock__gt=0,
                inventory__stock__lte=5,
            ).only("id", "name")
        )

        if not low_stock_products:
            logger.info("Stock alert check: no low-stock products found")
            return "Stock alert check completed (no low stock)"

        product_ids = [p.id for p in low_stock_products]

        # Single grouped query instead of N queries
        rows = Wishlist.objects.filter(
            products__id__in=product_ids
        ).values_list("products__id", "user__email")

        emails_by_product = defaultdict(set)
        for product_id, email in rows:
            if email:
                emails_by_product[product_id].add(email)

        dispatched = 0
        for product in low_stock_products:
            recipients = emails_by_product.get(product.id)
            if recipients:
                send_stock_alert_email.delay(product.id, list(recipients))
                dispatched += 1

        logger.info(
            f"Stock alert check: {len(low_stock_products)} products checked, "
            f"{dispatched} alert batches dispatched"
        )
        return "Stock alert check completed"
    except Exception as exc:
        logger.error(f"Error in stock alert check: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=300)


# ─────────────────────────────────────────────────────────────────────────────
# OTP Email
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_otp_email_task(self, subject, message, recipient_list):
    """
    Send OTP and password reset emails asynchronously.
    Used for resend OTP flow — registration OTP is sent synchronously
    in the view since it is on the critical registration path.
    """
    from core.utils.helpers import safe_send_mail
    try:
        sent = safe_send_mail(subject, message, recipient_list)
        if not sent:
            raise RuntimeError("safe_send_mail returned False — email not delivered")
        logger.info(f"OTP email sent to {recipient_list}")
        return f"OTP email sent to {recipient_list}"
    except Exception as exc:
        logger.error(f"OTP email failed for {recipient_list}: {exc}", exc_info=True)
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# Analytics
# ─────────────────────────────────────────────────────────────────────────────

@shared_task
def generate_analytics_snapshot():
    """
    Generate a cached analytics snapshot for the admin dashboard.
    Runs every hour via Celery beat. Result stored in Redis for 1 hour.
    """
    try:
        from products.models import Product
        from reviews.models import ProductReview
        from django.contrib.auth.models import User as UserModel
        from core.cache_utils import CacheManager, LONG_CACHE_TIMEOUT

        total_products = Product.objects.count()
        most_viewed = Product.objects.order_by("-rating").first()
        least_viewed = Product.objects.order_by("rating").first()

        total_users = UserModel.objects.count()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = UserModel.objects.filter(last_login__gte=today_start).count()

        avg_rating = ProductReview.objects.aggregate(Avg("rating"))["rating__avg"] or 0
        most_reviewed = Product.objects.annotate(
            review_count=Count("reviews")
        ).order_by("-review_count").first()

        most_wishlisted = Product.objects.annotate(
            wishlist_count=Count("in_wishlists")
        ).order_by("-wishlist_count").first()

        analytics_data = {
            "timestamp": timezone.now().isoformat(),
            "sales_metrics": {
                "total_products": total_products,
                "most_viewed": most_viewed.name if most_viewed else None,
                "least_viewed": least_viewed.name if least_viewed else None,
            },
            "customer_metrics": {
                "total_users": total_users,
                "active_today": active_today,
            },
            "review_metrics": {
                "average_rating": round(avg_rating, 2),
                "most_reviewed": most_reviewed.name if most_reviewed else None,
            },
            "wishlist_metrics": {
                "most_wishlisted": most_wishlisted.name if most_wishlisted else None,
            },
        }

        CacheManager.set_cache("analytics_snapshot", analytics_data, timeout=LONG_CACHE_TIMEOUT)
        logger.info("Analytics snapshot generated and cached successfully")
        return "Analytics snapshot generated"
    except Exception as exc:
        logger.error(f"Error generating analytics snapshot: {str(exc)}", exc_info=True)
        return f"Error: {str(exc)}"


@shared_task
def clean_expired_otps():
    """
    Remove expired OTP verification records from the database.
    Runs every 10 minutes via Celery beat to keep the table clean.
    """
    try:
        from accounts.models import OTPVerification
        deleted_count, _ = OTPVerification.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        logger.info(f"Cleaned up {deleted_count} expired OTP records")
        return f"Cleaned {deleted_count} expired OTP records"
    except Exception as exc:
        logger.error(f"Error cleaning expired OTPs: {str(exc)}", exc_info=True)
        return f"Error: {str(exc)}"


# ─────────────────────────────────────────────────────────────────────────────
# DB Keep-Alive
# ─────────────────────────────────────────────────────────────────────────────

@shared_task
def ping_database():
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        logger.debug("DB ping OK — Neon connection alive")
        return "DB ping OK"
    except Exception as exc:
        logger.warning(f"DB ping failed: {exc}")
        return f"DB ping failed: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Quote Request Emails
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def send_customer_request_email(self, request_id):

    try:
        from orders.models import CustomerRequest
        customer_request = CustomerRequest.objects.select_related("product").get(id=request_id)
        product_name = customer_request.product.name if customer_request.product else "N/A"
        submitted_at = customer_request.created_at.strftime("%d %b %Y, %I:%M %p")

        context = {
            "customer_name": customer_request.name,
            "customer_email": customer_request.email,
            "customer_phone": customer_request.phone,
            "product_name": product_name,
            "quantity": customer_request.quantity,
            "description": customer_request.description or "",
            "submitted_at": submitted_at,
            "frontend_url": settings.FRONTEND_BASE_URL,
        }

        # ── Admin notification ──────────────────────────────────────────────
        admin_email = getattr(settings, "SALES_NOTIFICATION_EMAIL", "")
        if admin_email:
            try:
                html_body = render_to_string("emails/customer_request_admin.html", context)
                plain_body = (
                    f"New Quote Request\n\n"
                    f"Customer : {customer_request.name}\n"
                    f"Email    : {customer_request.email}\n"
                    f"Phone    : {customer_request.phone}\n"
                    f"Product  : {product_name}\n"
                    f"Quantity : {customer_request.quantity}\n"
                    f"Notes    : {customer_request.description or 'N/A'}\n"
                    f"Submitted: {submitted_at}"
                )
                msg = EmailMultiAlternatives(
                    subject=f"New Quote Request — {product_name}",
                    body=plain_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[admin_email],
                )
                msg.attach_alternative(html_body, "text/html")
                msg.send()
                logger.info(f"Admin notified for quote request {request_id}")
            except Exception as e:
                logger.error(
                    f"Failed to send admin notification for request {request_id}: {str(e)}",
                    exc_info=True,
                )

        # ── Customer confirmation ───────────────────────────────────────────
        try:
            html_body = render_to_string("emails/customer_request_user.html", context)
            plain_body = (
                f"Dear {customer_request.name},\n\n"
                f"Thank you for your quote request for {product_name}.\n"
                f"Our team will contact you soon with pricing and further details.\n\n"
                f"Your Request Summary\n"
                f"────────────────────\n"
                f"Product  : {product_name}\n"
                f"Quantity : {customer_request.quantity}\n"
                f"Date     : {submitted_at}\n\n"
                f"Best regards,\n"
                f"NxSys Digital Sales Team\n"
                f"sales@sriainfotech.com"
            )
            msg = EmailMultiAlternatives(
                subject="We received your quote request — NxSys Digital",
                body=plain_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[customer_request.email],
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send()
            logger.info(f"Customer confirmation sent for request {request_id}")
        except Exception as e:
            logger.error(
                f"Failed to send customer confirmation for request {request_id}: {str(e)}",
                exc_info=True,
            )

        return f"Emails sent for customer request {request_id}"

    except CustomerRequest.DoesNotExist:
        logger.error(f"CustomerRequest {request_id} not found")
        return f"CustomerRequest {request_id} not found"
    except Exception as exc:
        logger.error(
            f"Unexpected error sending emails for request {request_id}: {str(exc)}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60)


# ─────────────────────────────────────────────────────────────────────────────
# Enquiry Emails
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def send_enquiry_email(self, enquiry_id):
    try:
        from orders.models import Enquiry
        enquiry = Enquiry.objects.select_related("product").get(id=enquiry_id)
        product_name = enquiry.product.name if enquiry.product else "General Enquiry"
        submitted_at = enquiry.created_at.strftime("%d %b %Y, %I:%M %p")

        context = {
            "customer_name": enquiry.name,
            "customer_email": enquiry.email,
            "customer_phone": enquiry.phone,
            "company_name": enquiry.company_name,
            "company_address": enquiry.company_address,
            "product_name": product_name,
            "quantity": enquiry.quantity,
            "description": enquiry.description or "",
            "submitted_at": submitted_at,
            "frontend_url": settings.FRONTEND_BASE_URL,
        }

        # ── Admin notification ──────────────────────────────────────────────
        admin_email = getattr(settings, "SALES_NOTIFICATION_EMAIL", "")
        if admin_email:
            try:
                html_body = render_to_string("emails/enquiry_admin.html", context)
                plain_body = (
                    f"New Business Enquiry\n\n"
                    f"Name     : {enquiry.name}\n"
                    f"Company  : {enquiry.company_name}\n"
                    f"Address  : {enquiry.company_address}\n"
                    f"Email    : {enquiry.email}\n"
                    f"Phone    : {enquiry.phone}\n"
                    f"Product  : {product_name}\n"
                    f"Quantity : {enquiry.quantity}\n"
                    f"Message  : {enquiry.description or 'N/A'}\n"
                    f"Submitted: {submitted_at}"
                )
                msg = EmailMultiAlternatives(
                    subject=f"New Enquiry — {product_name} | {enquiry.company_name}",
                    body=plain_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[admin_email],
                )
                msg.attach_alternative(html_body, "text/html")
                msg.send()
                logger.info(f"Admin notified for enquiry {enquiry_id}")
            except Exception as e:
                logger.error(
                    f"Failed to send admin notification for enquiry {enquiry_id}: {str(e)}",
                    exc_info=True,
                )

        # ── Customer confirmation ───────────────────────────────────────────
        try:
            html_body = render_to_string("emails/enquiry_user.html", context)
            plain_body = (
                f"Dear {enquiry.name},\n\n"
                f"Thank you for contacting NxSys Digital.\n"
                f"We have received your enquiry and our sales team will get in touch shortly.\n\n"
                f"Your Enquiry Summary\n"
                f"────────────────────\n"
                f"Company  : {enquiry.company_name}\n"
                f"Product  : {product_name}\n"
                f"Quantity : {enquiry.quantity}\n"
                f"Date     : {submitted_at}\n\n"
                f"Best regards,\n"
                f"NxSys Digital Sales Team\n"
                f"sales@sriainfotech.com"
            )
            msg = EmailMultiAlternatives(
                subject="Thank you for your enquiry — NxSys Digital",
                body=plain_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[enquiry.email],
            )
            msg.attach_alternative(html_body, "text/html")
            msg.send()
            logger.info(f"Customer confirmation sent for enquiry {enquiry_id}")
        except Exception as e:
            logger.error(
                f"Failed to send customer confirmation for enquiry {enquiry_id}: {str(e)}",
                exc_info=True,
            )

        return f"Emails sent for enquiry {enquiry_id}"

    except Enquiry.DoesNotExist:
        logger.error(f"Enquiry {enquiry_id} not found")
        return f"Enquiry {enquiry_id} not found"
    except Exception as exc:
        logger.error(
            f"Unexpected error sending emails for enquiry {enquiry_id}: {str(exc)}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60)


# ─────────────────────────────────────────────────────────────────────────────
# Quote Status Update Email
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3)
def send_quote_status_email(self, request_id, new_status):
    try:
        from orders.models import CustomerRequest

        req = CustomerRequest.objects.select_related("product").get(id=request_id)
        product_name = req.product.name if req.product else "N/A"
        updated_at = req.updated_at.strftime("%d %b %Y, %I:%M %p")

        STATUS_MAP = {
            CustomerRequest.STATUS_PENDING: {
                "title": "Your Request is Pending",
                "label": "Pending",
                "icon": "⏳",
                "bg_color": "#fff8e1",
                "border_color": "#fbc61d",
                "message": (
                    f"Your quote request for {product_name} has been received and is currently "
                    f"under review. Our team will prepare a personalised quote for you shortly."
                ),
            },
            CustomerRequest.STATUS_QUOTE_SENT: {
                "title": "Your Quote is Ready!",
                "label": "Quote Sent",
                "icon": "📄",
                "bg_color": "#f0fdf4",
                "border_color": "#4ade80",
                "message": (
                    f"Great news! We have prepared a quote for {product_name} and our sales team "
                    f"will be in touch with you shortly with pricing and availability details. "
                    f"Please check your inbox or contact us at sales@sriainfotech.com."
                ),
            },
            CustomerRequest.STATUS_CLOSED: {
                "title": "Request Closed",
                "label": "Closed",
                "icon": "✅",
                "bg_color": "#f0f4ff",
                "border_color": "#818cf8",
                "message": (
                    f"Your request for {product_name} has been closed. "
                    f"If you have any further questions or need assistance, "
                    f"please do not hesitate to reach out at sales@sriainfotech.com."
                ),
            },
        }

        status_info = STATUS_MAP.get(new_status, STATUS_MAP[CustomerRequest.STATUS_PENDING])

        context = {
            "customer_name": req.name,
            "product_name": product_name,
            "quantity": req.quantity,
            "updated_at": updated_at,
            "status_title": status_info["title"],
            "status_label": status_info["label"],
            "status_icon": status_info["icon"],
            "status_bg_color": status_info["bg_color"],
            "status_border_color": status_info["border_color"],
            "status_message": status_info["message"],
            "frontend_url": getattr(settings, "FRONTEND_BASE_URL", ""),
        }

        html_body = render_to_string("emails/quote_status_update.html", context)
        plain_body = (
            f"Dear {req.name},\n\n"
            f"Your quote request status has been updated.\n\n"
            f"Update Details\n"
            f"──────────────\n"
            f"Product  : {product_name}\n"
            f"Quantity : {req.quantity}\n"
            f"Status   : {status_info['label']}\n"
            f"Updated  : {updated_at}\n\n"
            f"{status_info['message']}\n\n"
            f"Best regards,\n"
            f"NxSys Digital Sales Team\n"
            f"sales@sriainfotech.com"
        )
        msg = EmailMultiAlternatives(
            subject=f"Quote Update: {status_info['title']} — {product_name}",
            body=plain_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[req.email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send()
        logger.info(
            f"Quote status email sent to {req.email} "
            f"for request {request_id} — status: {new_status}"
        )
        return f"Quote status email sent for request {request_id}"

    except CustomerRequest.DoesNotExist:
        logger.error(f"CustomerRequest {request_id} not found — cannot send status email")
        return f"CustomerRequest {request_id} not found"
    except Exception as exc:
        logger.error(
            f"Error sending quote status email for request {request_id}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60)