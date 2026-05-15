import html
import logging
import bleach
from django.conf import settings
from rest_framework import serializers

logger = logging.getLogger(__name__)

class SanitizedModelSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        try:
            ret = super().to_internal_value(data)
            for field_name, value in ret.items():
                if isinstance(value, str):
                    stripped = bleach.clean(value, tags=[], attributes={}, strip=True).strip()
                    ret[field_name] = html.unescape(stripped)
            return ret
        except Exception as e:
            logger.error(f"Error sanitizing input data: {str(e)}")
            raise

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
}
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

def validate_image_file(value):
    try:
        max_size = 5 * 1024 * 1024
        content_type = (getattr(value, "content_type", "") or "").lower()
        name = (getattr(value, "name", "") or "").lower()
        ext = name.rsplit(".", 1)[-1] if "." in name else ""

        if content_type and not content_type.startswith("image/"):
            raise serializers.ValidationError("Only image uploads are allowed.")

        if (content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES) or (
            ext not in ALLOWED_IMAGE_EXTENSIONS
        ):
            raise serializers.ValidationError(
                "Unsupported image format. Allowed formats: JPG, JPEG, PNG, GIF, WEBP."
            )

        if value.size > max_size:
            raise serializers.ValidationError("Image size must be 5MB or less.")

        return value
    except serializers.ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error validating image file: {str(e)}")
        raise serializers.ValidationError("Image validation failed.")
