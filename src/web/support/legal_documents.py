"""Fixed read-only drafts. This boundary can later load validated provider versions.

No remote calls, database writes, raw HTML or publication mechanism exist here.
"""

from web.support.legal_document import LegalDocument
from web.support.legal_section import LegalSection


def _section(document, slug, paragraphs=2, *, cards=(), rows=(), form=0):
    prefix = f"legal.{document}.{slug}"
    return LegalSection(
        slug=slug,
        title_key=f"{prefix}.title",
        paragraph_keys=tuple(f"{prefix}.p{i}" for i in range(1, paragraphs + 1)),
        cards=tuple((f"{prefix}.{card}.title", f"{prefix}.{card}.body") for card in cards),
        rows=tuple(tuple(f"{prefix}.{row}.{column}" for column in ("name", "data", "status"))
                   for row in rows),
        form_keys=tuple(f"{prefix}.line{i}" for i in range(1, form + 1)),
    )


_DOCUMENTS = (
    LegalDocument("datenschutz", "datenschutz", "legal.datenschutz.title", "legal.datenschutz.summary", (
        _section("datenschutz", "verantwortlicher"),
        _section("datenschutz", "konto", cards=("identity", "addresses", "orders")),
        _section("datenschutz", "betrieb", rows=("hosting", "fonts", "images")),
        _section("datenschutz", "cookies"),
        _section("datenschutz", "empfaenger"),
        _section("datenschutz", "speicherung"),
        _section("datenschutz", "rechte", cards=("access", "erasure", "objection", "complaint")),
        _section("datenschutz", "planung"),
    )),
    LegalDocument("impressum", "impressum", "legal.impressum.title", "legal.impressum.summary", (
        _section("impressum", "anbieter"),
        _section("impressum", "kontakt"),
        _section("impressum", "register"),
        _section("impressum", "streitbeilegung"),
    )),
    LegalDocument("agb", "agb", "legal.agb.title", "legal.agb.summary", (
        _section("agb", "geltung"),
        _section("agb", "vertrag"),
        _section("agb", "preise"),
        _section("agb", "lieferung"),
        _section("agb", "maengel"),
        _section("agb", "abschluss"),
    )),
    LegalDocument("widerruf", "widerruf", "legal.widerruf.title", "legal.widerruf.summary", (
        _section("widerruf", "recht"),
        _section("widerruf", "erklaerung"),
        _section("widerruf", "folgen"),
        _section("widerruf", "ausnahmen"),
        _section("widerruf", "formular", form=9),
        _section("widerruf", "online"),
    )),
    LegalDocument("versand-zahlung", "versand_zahlung", "legal.versand.title", "legal.versand.summary", (
        _section("versand", "betrieb"),
        _section("versand", "liefergebiet"),
        _section("versand", "kosten"),
        _section("versand", "zahlung"),
    )),
)


def legal_documents() -> tuple[LegalDocument, ...]:
    return _DOCUMENTS


def get_legal_document(slug: str) -> LegalDocument:
    for document in legal_documents():
        if document.slug == slug:
            return document
    raise KeyError(slug)
