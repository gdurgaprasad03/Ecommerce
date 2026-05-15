import html
import bleach
from django.conf import settings
from rest_framework import serializers

class SanitizedModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that strips HTML tags and whitespace from string
    inputs to prevent XSS.

    `bleach.clean()` strips tags and ALSO HTML-escapes characters like
    `&`, `<`, `>` — which is correct when the stored value will be rendered
    as raw HTML, but wrong for an API whose JSON consumers (React, Vue, etc.)
    escape at render time. So we run `html.unescape()` after cleaning to
    keep `Tom & Jerry` as `Tom & Jerry`, not `Tom &amp; Jerry`. Any actual
    HTML tags are already gone by then, so XSS safety is preserved.
    """
    def to_internal_value(self, data):
        ret = super().to_internal_value(data)
        for field_name, value in ret.items():
            if isinstance(value, str):
                stripped = bleach.clean(value, tags=[], attributes={}, strip=True).strip()
                ret[field_name] = html.unescape(stripped)
        return ret

def validate_image_file(value):
    """
    Reusable image validator for size and type.
    """
    max_size = 5 * 1024 * 1024
    content_type = getattr(value, "content_type", "")

    if content_type and not content_type.startswith("image/"):
        raise serializers.ValidationError("Only image uploads are allowed.")

    if value.size > max_size:
        raise serializers.ValidationError("Image size must be 5MB or less.")

    return value
