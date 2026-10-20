from dataclasses import dataclass

from web.support.legal_section import LegalSection


@dataclass(frozen=True, slots=True)
class LegalDocument:
    slug: str
    url_name: str
    title_key: str
    summary_key: str
    sections: tuple[LegalSection, ...]
    version: str = "2026-10-20-draft-1"
    language: str = "de"
    source: str = "local-draft"
