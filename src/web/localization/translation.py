"""Stable UI keys, Django gettext translations and a German source fallback."""

import json
from functools import lru_cache
from pathlib import Path

from django.utils.translation import gettext


@lru_cache(maxsize=1)
def source_messages() -> dict[str, str]:
    with (Path(__file__).parent / "messages" / "de.json").open(encoding="utf-8") as stream:
        return json.load(stream)


def translate_text(key: str, **params: object) -> str:
    """Translate a key, interpolating plain text without granting HTML safety.

    Catalog strings use Python named placeholders: ``Hallo {name}``.
    Missing keys remain visible as ``[key]``; missing parameters deliberately
    raise KeyError so broken text contracts cannot silently ship.
    """
    translated = gettext(key)
    if translated == key:
        translated = source_messages().get(key, f"[{key}]")
    return str(translated).format_map(params) if params else str(translated)
