# DTOs and PII

`BaseDTO` is a frozen Pydantic model. Its `str` and `repr` mask fields selected by `codex_core.core.pii.mask_value`; `model_dump()` and ordinary field access retain the original values. Keep sensitive values out of arbitrary serialization and logging paths.

```python
from codex_core.core import BaseDTO

class Contact(BaseDTO):
    email: str
    ticket_id: int

contact = Contact(email="person@example.org", ticket_id=7)
assert "person@example.org" not in repr(contact)
assert contact.model_dump()["email"] == "person@example.org"
```

Without a registry, field names containing keywords such as `email`, `phone`, `name`, `address`, `note`, or `comment` are masked. Defining a `PIIRegistry` subclass globally switches detection to exact field-name matches accumulated across registry subclasses. Declare every sensitive field name before logging DTOs; a partial registry can expose fields that the heuristic mode would have masked. Nested dict and list values are traversed by `mask_value`, but arbitrary nested objects are not. See `codex_core.core.pii` for the current keyword set and detection behavior.
