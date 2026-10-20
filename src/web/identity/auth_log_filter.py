import logging
import re


class AuthLogFilter(logging.Filter):
    """Keep verification/reset tokens out of Django development access logs."""

    def filter(self, record):
        def clean(value):
            if isinstance(value, str):
                value = re.sub(r"(/(?:[a-z]{2}/)?accounts/)[^\s]*", r"\1[redacted]", value)
                return re.sub(r"(/integrations/ebay/oauth/)[^\s]*", r"\1[redacted]", value)
            return value

        record.msg = clean(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(clean(value) for value in record.args)
        return True
