"""
Celery tasks for Phase 2 - Email Notifications, Analytics & Background Jobs
Handles asynchronous email sending, stock alerts, analytics generation
"""

from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models import Count, Q, Avg
from datetime import timedelta, datetime
import logging

logger = logging.getLogger(__name__)


# ==================== Email Tasks ====================

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    """Send welcome email to new user"""
    try:
        user = User.objects.get(id=user_id)
        
        subject = "Welcome to E-Commerce Platform!"
        context = {
            "user_name": user.first_name or user.username,
            "email": user.email,
            "frontend_url": settings.FRONTEND_BASE_URL,
            "verification_link": f"{settings.FRONTEND_BASE_URL}/verify-email",
        }
        
        html_message = render_to_string("emails/welcome.html", context)
        text_message = render_to_string("emails/welcome.txt", context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        
        logger.info(f"Welcome email sent to {user.email}")
        return f"Welcome email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return f"User {user_id} not found"
    except Exception as exc:
        logger.error(f"Error sending welcome email: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_stock_alert_email(self, product_id, user_emails):
    """Send stock alert email to interested users"""
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
        
        logger.info(f"Stock alert sent for {product.name} to {len(user_emails)} users")
        return f"Stock alert sent for {product.name}"
        
    except Exception as exc:
        logger.error(f"Error sending stock alert email: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_price_drop_email(self, product_id, user_emails, old_price, new_price):
    """Send price drop notification email"""
    try:
        from products.models import Product
        
        product = Product.objects.get(id=product_id)
        discount_percent = ((old_price - new_price) / old_price) * 100
        
        subject = f"Price Drop Alert: {product.name} is now ${new_price}!"
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
        
        logger.info(f"Price drop alert sent for {product.name} to {len(user_emails)} users")
        return f"Price drop alert sent"
        
    except Exception as exc:
        logger.error(f"Error sending price drop email: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_review_notification_email(self, review_id, product_id):
    """Send notification email to product watchers when new review is posted"""
    try:
        from products.models import Product
        from reviews.models import ProductReview
        
        product = Product.objects.get(id=product_id)
        review = ProductReview.objects.get(id=review_id)
        
        subject = f"New Review: {product.name} - {review.rating}★"
        context = {
            "product_name": product.name,
            "reviewer_name": review.user.first_name or review.user.username,
            "rating": review.rating,
            "title": review.title,
            "comment": review.comment[:200] + "..." if len(review.comment) > 200 else review.comment,
            "product_url": f"{settings.FRONTEND_BASE_URL}/product/{product.id}",
            "frontend_url": settings.FRONTEND_BASE_URL,
        }
        
        html_message = render_to_string("emails/review_notification.html", context)
        text_message = render_to_string("emails/review_notification.txt", context)
        
        # Get all users who have this product in wishlist
        from wishlist.models import Wishlist
        wishlisted_users = Wishlist.objects.filter(products=product).values_list("user__email", flat=True)
        
        if wishlisted_users:
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=list(wishlisted_users),
            )
            email.attach_alternative(html_message, "text/html")
            email.send()
            
            logger.info(f"Review notification sent for {product.name} to {len(wishlisted_users)} users")
        
        return "Review notification sent"
        
    except Exception as exc:
        logger.error(f"Error sending review notification: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_wishlist_reminder_email(self, user_id):
    """Send wishlist reminder email"""
    try:
        from wishlist.models import Wishlist
        from products.models import Product
        
        user = User.objects.get(id=user_id)
        wishlist = Wishlist.objects.get(user=user)
        
        products = wishlist.products.filter(is_active=True)[:5]
        
        if not products:
            return "No products in wishlist"
        
        subject = "Your Wishlist Items - Check Out Now!"
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
        logger.error(f"Error sending wishlist reminder: {str(exc)}")
        raise self.retry(exc=exc, countdown=60)


# ==================== Stock Alert Tasks ====================

@shared_task(bind=True, max_retries=2)
def notify_stock_low(self, product_id):
    """Notify admin when product stock is low"""
    try:
        from products.models import Product
        
        product = Product.objects.get(id=product_id)
        admin_email = settings.SALES_NOTIFICATION_EMAIL
        
        subject = f"Low Stock Alert: {product.name}"
        context = {
            "product_name": product.name,
            "product_id": product.id,
            "stock": product.inventory.stock,
            "threshold": 10,
        }
        
        html_message = render_to_string("emails/admin_low_stock.html", context)
        text_message = render_to_string("emails/admin_low_stock.txt", context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[admin_email],
        )
        email.attach_alternative(html_message, "text/html")
        email.send()
        
        logger.warning(f"Low stock notification sent for {product.name}")
        return f"Low stock notification sent"
        
    except Exception as exc:
        logger.error(f"Error sending low stock notification: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=2)
def check_stock_alerts(self):
    """Periodic task to check and notify about back-in-stock items"""
    try:
        from products.models import Product
        from wishlist.models import Wishlist
        
        # Find products that were out of stock but now have stock
        low_stock_products = Product.objects.filter(
            inventory__stock__gt=0,
            inventory__stock__lte=5
        )
        
        for product in low_stock_products:
            # Find users interested in this product
            wishlisted_users = Wishlist.objects.filter(
                products=product
            ).values_list("user__email", flat=True)
            
            if wishlisted_users:
                send_stock_alert_email.delay(product.id, list(wishlisted_users))
        
        logger.info(f"Stock alert check completed. {len(low_stock_products)} products checked")
        return f"Stock alert check completed"
        
    except Exception as exc:
        logger.error(f"Error in stock alert check: {str(exc)}")
        raise self.retry(exc=exc, countdown=300)


# ==================== Analytics Tasks ====================

@shared_task
def generate_analytics_snapshot():
    """Generate and cache analytics snapshots"""
    try:
        from products.models import Product
        from reviews.models import ProductReview
        from wishlist.models import Wishlist
        from django.contrib.auth.models import User as UserModel
        from core.cache_utils import CacheManager, LONG_CACHE_TIMEOUT
        
        # Sales Metrics
        total_product_views = Product.objects.count()
        most_viewed = Product.objects.order_by('-rating').first()
        least_viewed = Product.objects.order_by('rating').first()
        
        # Customer Metrics
        total_users = UserModel.objects.count()
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        active_today = UserModel.objects.filter(last_login__gte=today_start).count()
        
        # Review Metrics
        avg_rating = ProductReview.objects.aggregate(Avg('rating'))['rating__avg'] or 0
        most_reviewed = Product.objects.annotate(
            review_count=Count('reviews')
        ).order_by('-review_count').first()
        
        # Wishlist Metrics
        most_wishlisted = Product.objects.annotate(
            wishlist_count=Count('in_wishlists')
        ).order_by('-wishlist_count').first()
        
        analytics_data = {
            "timestamp": timezone.now().isoformat(),
            "sales_metrics": {
                "total_products": total_product_views,
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
        
        CacheManager.set_cache(
            "analytics_snapshot",
            analytics_data,
            timeout=LONG_CACHE_TIMEOUT
        )
        
        logger.info("Analytics snapshot generated successfully")
        return "Analytics snapshot generated"
        
    except Exception as exc:
        logger.error(f"Error generating analytics snapshot: {str(exc)}")
        return f"Error: {str(exc)}"


@shared_task
def clean_expired_otps():
    """Clean up expired OTP records"""
    try:
        from accounts.models import OTPVerification
        
        expired = OTPVerification.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        
        logger.info(f"Cleaned up {expired[0]} expired OTP records")
        return f"Cleaned {expired[0]} expired OTP records"
        
    except Exception as exc:
        logger.error(f"Error cleaning expired OTPs: {str(exc)}")
        return f"Error: {str(exc)}"


# ==================== Customer Request & Enquiry Email Tasks ====================

@shared_task(bind=True, max_retries=3)
def send_customer_request_email(self, request_id):
    """Send customer request notification emails"""
    try:
        from orders.models import CustomerRequest
        
        customer_request = CustomerRequest.objects.select_related('product').get(id=request_id)
        product_name = customer_request.product.name if customer_request.product else "N/A"
        
        # Send notification to admin
        admin_message = (
            f"New customer inquiry received.\n\n"
            f"Customer Name: {customer_request.name}\n"
            f"Email: {customer_request.email}\n"
            f"Phone: {customer_request.phone}\n"
            f"Product: {product_name}\n"
            f"Quantity: {customer_request.quantity}\n"
            f"Description:\n{customer_request.description}"
        )
        
        admin_email = getattr(settings, "SALES_NOTIFICATION_EMAIL", "")
        if admin_email:
            try:
                from django.core.mail import send_mail
                send_mail(
                    f"New Product Request - {product_name}",
                    admin_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [admin_email],
                    fail_silently=False,
                )
                logger.info(f"Admin notification sent for customer request {request_id}")
            except Exception as e:
                logger.error(f"Failed to send admin notification: {str(e)}", exc_info=True)
        
        # Send confirmation to customer
        customer_message = (
            f"Dear {customer_request.name},\n\n"
            f"Thank you for reaching out to us.\n"
            f"We have successfully received your quote request for {product_name}.\n\n"
            f"Our team will contact you soon with the pricing and further details.\n\n"
            f"Best regards,\n"
            f"Your Company Team"
        )
        
        try:
            from django.core.mail import send_mail
            send_mail(
                "We received your quote request",
                customer_message,
                settings.DEFAULT_FROM_EMAIL,
                [customer_request.email],
                fail_silently=False,
            )
            logger.info(f"Customer confirmation sent for request {request_id}")
        except Exception as e:
            logger.error(f"Failed to send customer confirmation: {str(e)}", exc_info=True)
        
        return f"Emails sent for customer request {request_id}"
        
    except CustomerRequest.DoesNotExist:
        logger.error(f"Customer request {request_id} not found")
        return f"Customer request {request_id} not found"
    except Exception as exc:
        logger.error(f"Error sending customer request emails: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_enquiry_email(self, enquiry_id):
    """Send enquiry notification emails"""
    try:
        from orders.models import Enquiry
        
        enquiry = Enquiry.objects.select_related('product').get(id=enquiry_id)
        product_name = enquiry.product.name if enquiry.product else "General Enquiry"
        
        # Send notification to admin
        admin_message = (
            f"New enquiry received.\n\n"
            f"Name: {enquiry.name}\n"
            f"Company Name: {enquiry.company_name}\n"
            f"Company Address: {enquiry.company_address}\n"
            f"Email: {enquiry.email}\n"
            f"Phone: {enquiry.phone}\n"
            f"Product: {product_name}\n"
            f"Quantity: {enquiry.quantity}\n"
            f"Description:\n{enquiry.description}"
        )
        
        admin_email = getattr(settings, "SALES_NOTIFICATION_EMAIL", "")
        if admin_email:
            try:
                from django.core.mail import send_mail
                send_mail(
                    f"New Enquiry - {product_name}",
                    admin_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [admin_email],
                    fail_silently=False,
                )
                logger.info(f"Admin notification sent for enquiry {enquiry_id}")
            except Exception as e:
                logger.error(f"Failed to send admin notification: {str(e)}", exc_info=True)
        
        # Send confirmation to customer
        customer_message = (
            f"Dear {enquiry.name},\n\n"
            f"Thank you for contacting us.\n"
            f"We have received your enquiry and our team will get in touch with you shortly.\n\n"
            f"Product: {product_name}\n"
            f"Quantity: {enquiry.quantity}\n\n"
            f"Best regards,\n"
            f"Your Company Team"
        )
        
        try:
            from django.core.mail import send_mail
            send_mail(
                "Thank you for your enquiry",
                customer_message,
                settings.DEFAULT_FROM_EMAIL,
                [enquiry.email],
                fail_silently=False,
            )
            logger.info(f"Customer confirmation sent for enquiry {enquiry_id}")
        except Exception as e:
            logger.error(f"Failed to send customer confirmation: {str(e)}", exc_info=True)
        
        return f"Emails sent for enquiry {enquiry_id}"
        
    except Enquiry.DoesNotExist:
        logger.error(f"Enquiry {enquiry_id} not found")
        return f"Enquiry {enquiry_id} not found"
    except Exception as exc:
        logger.error(f"Error sending enquiry emails: {str(exc)}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)
