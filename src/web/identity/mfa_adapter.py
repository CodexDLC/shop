from allauth.mfa.adapter import DefaultMFAAdapter
from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ShopMFAAdapter(DefaultMFAAdapter):
    def cipher(self):
        keys = settings.SHOP_MFA_ENCRYPTION_KEYS
        if not keys:
            raise ImproperlyConfigured("Dedicated MFA encryption keys are required")
        return MultiFernet([Fernet(key.encode("ascii")) for key in keys])

    def encrypt(self, text):
        return self.cipher().encrypt(text.encode("utf-8")).decode("ascii")

    def decrypt(self, encrypted_text):
        return self.cipher().decrypt(encrypted_text.encode("ascii")).decode("utf-8")

