from allauth.mfa.totp.forms import ActivateTOTPForm
from django.core.exceptions import ValidationError

from web.identity.policy import has_verified_email
from web.localization import translate_text


class VerifiedTOTPActivationForm(ActivateTOTPForm):
    def clean_code(self):
        if not has_verified_email(self.user):
            raise ValidationError(translate_text("auth.verified_email_required"), code="unverified_email")
        return super().clean_code()
