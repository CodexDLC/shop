from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LegalSection:
    """Plain localization keys only; no provider HTML is renderable."""

    slug: str
    title_key: str
    paragraph_keys: tuple[str, ...]
    cards: tuple[tuple[str, str], ...] = ()
    rows: tuple[tuple[str, str, str], ...] = ()
    form_keys: tuple[str, ...] = ()
