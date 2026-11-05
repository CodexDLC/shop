from dataclasses import dataclass

from .validation import identifier, nonnegative_int


@dataclass(frozen=True, slots=True)
class OperationContext:
    """Future metadata; no deduplication or authorization is performed.

    Identity is (source, owner, operation_key). Kind, target, quantities and
    revision are payload: a different payload under that identity conflicts.
    Source and owner are opaque identifiers, never customer details or secrets.
    """

    operation_key: str
    source: str
    owner: str
    reason: str
    expected_revision: int

    def __post_init__(self):
        for value in (self.operation_key, self.source, self.owner, self.reason):
            identifier(value)
        nonnegative_int(self.expected_revision)
