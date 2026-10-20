import hashlib
import json

from django.db import transaction
from django.utils.crypto import salted_hmac
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware

from .models import DeletionReceipt
from .rejected import NotificationRejected


class ReceiptService:
    def receive(self, body):
        try:
            payload = json.loads(body)
            metadata, notification = payload["metadata"], payload["notification"]
            topic, schema = metadata["topic"], metadata["schemaVersion"]
            notification_id = notification["notificationId"]
            data = notification["data"]
            user_id = data["userId"]
            event_date = parse_datetime(notification["eventDate"])
            if (
                topic != "MARKETPLACE_ACCOUNT_DELETION" or schema != "1.0"
                or not isinstance(notification_id, str) or not 1 <= len(notification_id) <= 200
                or not isinstance(user_id, str) or not 1 <= len(user_id) <= 2000
                or event_date is None or not is_aware(event_date)
                or not isinstance(data, dict)
            ):
                raise ValueError
            # publishDate / publishAttemptCount change on legitimate delivery retries.
            stable_event = {"topic": topic, "schema": schema,
                            "eventDate": notification["eventDate"], "data": data}
            fingerprint = hashlib.sha256(
                json.dumps(stable_event, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            user_fingerprint = salted_hmac("ebay-deletion-user-v1", user_id, algorithm="sha256").hexdigest()
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise NotificationRejected("ebay.invalid_notification", 400) from None
        with transaction.atomic():
            receipt, _ = DeletionReceipt.objects.get_or_create(
                notification_id=notification_id,
                defaults={"topic": topic, "schema_version": schema, "event_date": event_date,
                          "payload_fingerprint": fingerprint, "user_fingerprint": user_fingerprint},
            )
            if receipt.payload_fingerprint != fingerprint:
                raise NotificationRejected("ebay.conflicting_notification", 409)
        return receipt
