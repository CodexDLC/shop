"""SEO workspace boundary: scoped permissions, optimistic locking and text-free audit."""
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .display import display_metadata
from .models import SeoAudit, SeoPage, SeoRule
from .targets import search_pages, target_data, validate_identity
from .templates import render_template, validate_template

PAGE_FIELDS = ("title", "description", "body")
RULE_FIELDS = ("title_template", "description_template")


def require(user, *permissions):
    if not user.has_perms(["seo.view_seopage", *("seo." + item for item in permissions)]):
        raise PermissionDenied


def _stale():
    raise ValidationError("SEO draft changed. Reload before saving.", code="stale")


def _clean(values, *, rule=False):
    allowed = RULE_FIELDS if rule else PAGE_FIELDS
    if not isinstance(values, dict) or set(values) - set(allowed):
        raise ValidationError("Unsupported SEO field.")
    cleaned = {}
    for field, value in values.items():
        if not isinstance(value, str):
            raise ValidationError({field: "Use text only."})
        value = value.strip()
        limit = 10000 if field == "body" else 320 if "description" in field else 160
        if len(value) > limit or any(ord(char) < 32 and char not in "\n\r\t" for char in value):
            raise ValidationError({field: "SEO text is too long or contains invalid characters."})
        if field != "body" and any(char in value for char in "\n\r\t"):
            raise ValidationError({field: "Use one line of text."})
        if rule:
            validate_template(value)
        cleaned[field] = value
    return cleaned


def _permissions(user, fields, *, rule=False):
    if rule:
        require(user, "manage_rules")
    else:
        permissions = {"change_text" if field == "body" else "change_metadata" for field in fields}
        require(user, *permissions)


def _write(user, model, identity, expected_version, values=None, *, action="save", rule=False):
    require(user)
    if action != "save":
        require(user, "publish_seo")
    if rule:
        require(user, "manage_rules")
    if not isinstance(expected_version, int) or expected_version < 0:
        _stale()
    with transaction.atomic():
        row = model.objects.filter(**identity).first()
        if row is None:
            if expected_version != 0:
                _stale()
            if action != "save":
                raise ValidationError("Save a draft before publishing.")
            # Validate authorization before the first persisted row.
            _permissions(user, values, rule=rule)
            try:
                with transaction.atomic():
                    row = model.objects.create(**identity, version=0)
            except IntegrityError:
                _stale()
        if row.version != expected_version:
            _stale()
        changes = {}
        if action == "save":
            fields = list(values)
            _permissions(user, fields, rule=rule)
            changes["draft"] = {**row.draft, **values}
        else:
            destination = row.previous if action == "restore" else row.draft
            if destination is None:
                raise ValidationError("No previous published version.")
            fields = [field for field in (RULE_FIELDS if rule else PAGE_FIELDS)
                      if destination.get(field, "") != row.published.get(field, "")]
            _permissions(user, fields, rule=rule)
            changes.update(previous=row.published, published=destination, draft=destination)
        updated = model.objects.filter(pk=row.pk, version=expected_version).update(
            **changes, version=expected_version + 1, updated_at=timezone.now())
        if updated != 1:
            _stale()
        SeoAudit.objects.create(actor=user, target=("rule:" if rule else "page:") + ":".join(str(value) for key, value in identity.items() if key != "language"),
                                language=identity["language"], action=action, fields=fields, version=expected_version + 1)
        from web.staff.audit import record_staff_action

        record_staff_action(SimpleNamespace(user=user), f"seo.{'rule' if rule else 'page'}.{action}", row)
        row.refresh_from_db()
        return row


def _identity(kind, key, language):
    target = target_data(kind, key, language)
    return {"kind": kind, "key": key, "language": language}, target


def save_draft(user, kind, key, language, *, expected_version, values):
    require(user)
    identity, target = _identity(kind, key, language)
    values = _clean(values)
    if values.get("body") and not target["body_allowed"]:
        raise ValidationError({"body": "Legal page content is managed in legal documents."})
    return _write(user, SeoPage, identity, expected_version, values)


def publish_page(user, kind, key, language, *, expected_version):
    require(user, "publish_seo")
    identity, _ = _identity(kind, key, language)
    return _write(user, SeoPage, identity, expected_version, action="publish")


def restore_previous(user, kind, key, language, *, expected_version):
    require(user, "publish_seo")
    identity, _ = _identity(kind, key, language)
    return _write(user, SeoPage, identity, expected_version, action="restore")


def apply_rule(automatic, variables, published):
    result = automatic.copy()
    for field in ("title", "description"):
        template = published.get(field + "_template", "")
        if template:
            result[field] = render_template(template, variables)
    return result


def get_page(kind, key, language="de"):
    _, target = _identity(kind, key, language)
    row = SeoPage.objects.filter(kind=kind, key=key, language=language).first()
    rule = SeoRule.objects.filter(kind=kind, language=language).first()
    automatic = apply_rule(target["automatic"], target["variables"], rule.published if rule else {})
    draft = row.draft if row else {}
    published = row.published if row else {}
    def resolve_values(values):
        result = {field: values.get(field) or automatic[field] for field in PAGE_FIELDS}
        if (target["body_supplies_description"] and values.get("body") and not values.get("description")
                and not (rule and rule.published.get("description_template"))):
            result["description"] = values["body"]
        return display_metadata(result)

    effective = resolve_values(published)
    preview = resolve_values(draft)
    checks = []
    if not preview["title"].strip():
        checks.append("empty_title")
    if not preview["description"].strip():
        checks.append("empty_description")
    if len(preview["title"]) > 70:
        checks.append("long_title")
    if len(preview["description"]) > 160:
        checks.append("long_description")
    return {**target, **{field: draft.get(field, "") for field in PAGE_FIELDS},
            "version": row.version if row else 0, "published": published,
            "previous": row.previous if row else None, "automatic": automatic, "effective": effective,
            "preview": preview, "checks": checks, "has_draft": draft != published,
            "audit": list(SeoAudit.objects.filter(target="page:" + kind + ":" + key, language=language).values("action", "fields", "version", "created_at")[:20])}


def get_rule(kind, language="de"):
    validate_identity(kind, language)
    row = SeoRule.objects.filter(kind=kind, language=language).first()
    draft = row.draft if row else {}
    return {"kind": kind, "language": language, "version": row.version if row else 0,
            **{field: draft.get(field, "") for field in RULE_FIELDS},
            "published": row.published if row else {}, "previous": row.previous if row else None,
            "has_draft": draft != (row.published if row else {})}


def save_rule_draft(user, kind, language, *, expected_version, values):
    validate_identity(kind, language)
    return _write(user, SeoRule, {"kind": kind, "language": language}, expected_version, _clean(values, rule=True), rule=True)


def publish_rule(user, kind, language, *, expected_version):
    validate_identity(kind, language)
    return _write(user, SeoRule, {"kind": kind, "language": language}, expected_version, action="publish", rule=True)


def restore_previous_rule(user, kind, language, *, expected_version):
    validate_identity(kind, language)
    return _write(user, SeoRule, {"kind": kind, "language": language}, expected_version, action="restore", rule=True)


def preview_rule(kind, language, values, limit=3):
    validate_identity(kind, language)
    values = _clean(values, rule=True)
    pages = search_pages(kind=kind, language=language)
    examples = []
    for page in list(pages)[:min(max(limit, 1), 3)]:
        target = target_data(kind, page["key"], language)
        examples.append({**page, **display_metadata(apply_rule(target["automatic"], target["variables"], values))})
    return examples
