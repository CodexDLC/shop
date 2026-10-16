from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from web.localization import translate_text


class StaffAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not (user.is_staff or user.is_superuser):
            raise ValidationError(translate_text("staff.login.denied"), code="staff_required")
