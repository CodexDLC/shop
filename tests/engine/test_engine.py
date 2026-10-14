import pytest
from pydantic import ValidationError

from codex_ecommerce import Engine, EngineStatus


def test_status_is_immutable_and_external_writes_cannot_be_enabled():
    status = Engine().status()
    assert isinstance(status, EngineStatus)
    assert status.model_dump(mode="json") == {
        "phase": "foundation",
        "payments_enabled": False,
        "ebay_write_enabled": False,
    }
    with pytest.raises(ValidationError):
        status.payments_enabled = True
    with pytest.raises(ValidationError):
        EngineStatus(ebay_write_enabled=True)
