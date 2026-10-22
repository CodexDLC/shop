from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from codex_ecommerce.cart import CartError, DiscountRule, discount_amount


class PromoCode(models.Model):
    code = models.CharField(max_length=32, unique=True, validators=[
        RegexValidator(r'\A[A-Z0-9][A-Z0-9_-]{0,31}\Z', 'commerce.error.coupon_invalid'),
    ])
    kind = models.CharField(max_length=7, choices=[('percent', 'percent'), ('fixed', 'fixed')])
    value = models.DecimalField(max_digits=12, decimal_places=2)
    min_subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='EUR')
    is_active = models.BooleanField(default=False)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        try:
            discount_amount(self.min_subtotal, DiscountRule(self.kind, self.value, self.min_subtotal, self.currency))
        except CartError:
            raise ValidationError('commerce.error.coupon_invalid') from None
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'commerce.error.coupon_invalid'})

    def __str__(self):
        return self.code

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(value__gt=0), name='promo_value_positive'),
            models.CheckConstraint(condition=models.Q(min_subtotal__gte=0), name='promo_minimum_nonnegative'),
            models.CheckConstraint(condition=models.Q(currency='EUR'), name='promo_currency_eur'),
            models.CheckConstraint(condition=(models.Q(kind='fixed') | models.Q(kind='percent', value__lte=100)),
                                   name='promo_kind_value_valid'),
            models.CheckConstraint(condition=(models.Q(starts_at__isnull=True) | models.Q(ends_at__isnull=True)
                                             | models.Q(ends_at__gt=models.F('starts_at'))),
                                   name='promo_dates_ordered'),
            models.CheckConstraint(condition=(models.Q(code__regex=r'^[A-Z0-9][A-Z0-9_-]{0,31}$')
                                             & ~models.Q(code__contains='\n')),
                                   name='promo_code_ascii_upper'),
        ]
