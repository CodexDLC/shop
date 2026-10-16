from email.message import MIMEPart

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.urls import reverse


class ShopAccountAdapter(DefaultAccountAdapter):
    """Shop role policy; framework workflow remains allauth-owned."""

    def get_login_redirect_url(self, request):
        user = request.user
        return reverse("staff:home" if user.is_staff or user.is_superuser else "customer:overview")

    def render_mail(self, template_prefix, email, context, headers=None):
        message = super().render_mail(template_prefix, email, context, headers=headers)
        if template_prefix in {
            "account/email/email_confirmation", "account/email/email_confirmation_signup",
            "account/email/password_reset_key",
        }:
            # Embedded PNG: no remote image requests or external font tracking.
            logo = settings.BASE_DIR / "src/web/static/storefront/brand/logo-horizontal-light.png"
            image = MIMEPart()
            image.set_content(logo.read_bytes(), maintype="image", subtype="png",
                              cid="<maennermasche-logo>", disposition="inline", filename="maennermasche.png")
            message.attach(image)
        return message
