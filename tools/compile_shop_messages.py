"""Compile stable-key JSON catalogs to Django PO/MO files without GNU tools.

Run after adding texts/translations: python tools/compile_shop_messages.py
German is the source catalog; other languages may contain a translated subset.
Missing translations are resolved by the runtime German fallback.
"""

import argparse
import json
import struct
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "src/web/localization"


def compile_mo(messages: dict[str, str]) -> bytes:
    entries = sorted(messages.items())
    count = len(entries)
    offset = 28 + count * 16
    originals = bytearray()
    translations = bytearray()
    original_table = []
    translated_table = []
    for key, _ in entries:
        data = key.encode("utf-8")
        original_table.append((len(data), offset + len(originals)))
        originals.extend(data + b"\0")
    translated_offset = offset + len(originals)
    for _, value in entries:
        data = value.encode("utf-8")
        translated_table.append((len(data), translated_offset + len(translations)))
        translations.extend(data + b"\0")
    header = struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + count * 8, 0, 0)
    tables = b"".join(struct.pack("<2I", *entry) for entry in original_table + translated_table)
    return header + tables + originals + translations


def compile_catalogs(root: Path) -> list[Path]:
    written = []
    for source in sorted((root / "messages").glob("*.json")):
        language = source.stem
        messages = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(messages, dict) or not all(
            isinstance(key, str) and key and isinstance(value, str) for key, value in messages.items()
        ):
            raise ValueError(f"Expected nonempty string keys and string translations in {source}")
        header = (
            "Content-Type: text/plain; charset=UTF-8\n"
            "MIME-Version: 1.0\n"
            f"Language: {language}\n"
        )
        catalog = {"": header, **messages}
        destination = root / "locale" / language / "LC_MESSAGES"
        destination.mkdir(parents=True, exist_ok=True)
        def quote(value: str) -> str:
            return json.dumps(value, ensure_ascii=False)

        po = "\n\n".join(
            f"msgid {quote(key)}\nmsgstr {quote(value)}" for key, value in sorted(catalog.items())
        ) + "\n"
        (destination / "django.po").write_text(po, encoding="utf-8")
        mo = destination / "django.mo"
        mo.write_bytes(compile_mo(catalog))
        written.append(mo)
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    for path in compile_catalogs(parser.parse_args().root):
        print(path)
