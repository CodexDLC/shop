"""Bind saved seller details to drafts without changing their policy clauses."""

from dataclasses import replace

from web.localization import translate_text


def bind_legal_identity(document):
    parts = {
        ("impressum", "anbieter"): "address",
        ("impressum", "kontakt"): "contact_address",
        ("widerruf", "erklaerung"): "recipient",
        ("widerruf", "formular"): "recipient",
        ("agb", "geltung"): "address",
        ("impressum", "register"): "register",
        ("datenschutz", "verantwortlicher"): "full",
    }
    sections = []
    for section in document.sections:
        part = parts.get((document.slug, section.slug), "")
        if part:
            # Replace only the identity placeholder; retain the existing draft policy.
            placeholder = f"legal.{document.slug}.{section.slug}.p1"
            paragraphs = tuple(key for key in section.paragraph_keys if key != placeholder)
            form_keys = section.form_keys
            if (document.slug, section.slug) == ("impressum", "kontakt"):
                paragraphs = tuple("store_identity.legal_returns_notice" if key == "legal.impressum.kontakt.p2"
                                   else key for key in paragraphs)
            elif (document.slug, section.slug) == ("widerruf", "erklaerung"):
                paragraphs = ("store_identity.withdrawal_declaration", *paragraphs)
            elif (document.slug, section.slug) == ("widerruf", "formular"):
                # The first form line identifies the seller; customer blanks stay unchanged.
                form_keys = tuple(key for key in form_keys if key != "legal.widerruf.formular.line1")
                paragraphs = section.paragraph_keys
            elif (document.slug, section.slug) == ("agb", "geltung"):
                paragraphs = ("store_identity.agb_scope", *paragraphs)
            section = replace(section, identity_part=part, paragraph_keys=paragraphs, form_keys=form_keys)
        sections.append(section)
    return replace(document, sections=tuple(sections))


def identity_text_lines(identity, part):
    lines = [translate_text("store_identity.legal_recipient")] if part == "recipient" else []
    if part not in {"contacts", "register"}:
        lines.append(identity["legal_name"] or translate_text("store_identity.unconfigured"))
        if identity["representative"]:
            lines.append(f'{translate_text("store_identity.representative")}: {identity["representative"]}')
        if identity["street_address"]:
            lines.extend((identity["street_address"],
                          f'{identity["postal_code"]} {identity["city"]}'.strip(), identity["country"]))
    if part not in {"register", "address"}:
        lines.extend(identity[field] for field in ("contact_email", "contact_phone") if identity[field])
        if not identity["contact_email"] and not identity["contact_phone"]:
            lines.append(translate_text("store_identity.contacts_unconfigured"))
    if part in {"register", "full"}:
        for field in ("vat_id", "register_court", "register_number"):
            if identity[field]:
                lines.append(f'{translate_text("store_identity." + field)}: {identity[field]}')
    return lines
