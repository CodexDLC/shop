from enum import StrEnum


class OperationKind(StrEnum):
    """Stable movement names; enum membership alone never proves execution.

    All target a stock key and include OperationContext. Initialize sets a
    nonnegative on-hand count; receive and checked_return add a positive
    quantity; adjust sets an absolute nonnegative count at expected revision.
    Reserve includes reservation ID, positive quantity and explicit expiry.
    Commit identifies a reservation; release and fulfill identify a reservation
    and positive quantity. Expire identifies a due reservation and releases
    its entire remaining quantity. Fulfillment consumes only committed quantity.
    Checked returns require a received and inspected item, never merely a refund.
    The synthetic external snapshot name belongs to a local test adapter;
    it does not authorize a real provider or turn this enum into an API.
    """
    INITIALIZE = "initialize"
    RECEIVE = "receive"
    ADJUST = "adjust"
    RESERVE = "reserve"
    COMMIT = "commit"
    RELEASE = "release"
    EXPIRE = "expire"
    FULFILL = "fulfill"
    CHECKED_RETURN = "checked_return"
    EXTERNAL_SNAPSHOT = "external_snapshot"
