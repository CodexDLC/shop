"""Safe, read-only public projection. Empty settings never create database rows."""
import re
from urllib.parse import quote

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from web.shop.models import StoreIdentity

PUBLIC_FIELDS = (
    "legal_name", "representative", "street_address", "postal_code", "city", "country",
    "contact_email", "contact_phone", "vat_id", "register_court", "register_number",
)


def get_store_identity(request=None):
    if request is not None and hasattr(request, "_shop_public_identity"):
        return request._shop_public_identity.copy()
    result = StoreIdentity.objects.filter(pk=1).values(*PUBLIC_FIELDS).first()
    if result is None:
        result = dict.fromkeys(PUBLIC_FIELDS, "")
        result["country"] = "DE"
    phone = result["contact_phone"]
    normalized = re.sub(r"[ ()/.-]", "", phone)
    result["phone_href"] = f"tel:{normalized}" if re.fullmatch(r"\+?[0-9]{3,20}", normalized) else ""
    result["email_href"] = ""
    if result["contact_email"]:
        try:
            validate_email(result["contact_email"])
        except ValidationError:
            pass
        else:
            result["email_href"] = "mailto:" + quote(result["contact_email"], safe="@.+-")
    if request is not None:
        request._shop_public_identity = result.copy()
    return result
