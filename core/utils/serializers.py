import bleach
from django.conf import settings
from rest_framework import serializers

class SanitizedModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that automatically strips HTML tags and whitespace
    from all CharField and TextField inputs to prevent XSS.
    """
    def to_internal_value(self, data):
        ret = super().to_internal_value(data)
        for field_name, value in ret.items():
            if isinstance(value, str):
                # Strip HTML tags and whitespace
                ret[field_name] = bleach.clean(value, tags=[], attributes={}, strip=True).strip()
        return ret

def validate_image_file(value):
    """
    Reusable image validator for size and type.
    """
    max_size = 5 * 1024 * 1024  # 5MB
    content_type = getattr(value, "content_type", "")
    
    if content_type and not content_type.startswith("image/"):
        raise serializers.ValidationError("Only image uploads are allowed.")
    
    if value.size > max_size:
        raise serializers.ValidationError("Image size must be 5MB or less.")
    
    return value
