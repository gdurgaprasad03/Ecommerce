import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class PasswordValidator:
    def __init__(self, min_length=8):
        self.min_length = min_length

    def validate(self, password, user=None):
        errors = []
        if len(password) < self.min_length:
            errors.append(_(f"Password must be at least {self.min_length} characters long."))

        if not re.search(r'[A-Z]', password):
            errors.append(_("Password must contain at least one uppercase letter."))

        if not re.search(r'[a-z]', password):
            errors.append(_("Password must contain at least one lowercase letter."))

        if not re.search(r'[0-9]', password):
            errors.append(_("Password must contain at least one digit."))

        if not re.search(r'[!@#$%^&*(),.?":{}|<>_+-]', password):
            errors.append(_("Password must contain at least one special character."))

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            f"Your password must contain at least {self.min_length} characters, "
            "including uppercase, lowercase, numbers, and special characters."
        )

def validate_password_complexity(value):
    """
    Function-based validator for use in serializers or models.
    """
    validator = PasswordValidator()
    validator.validate(value)
    return value
