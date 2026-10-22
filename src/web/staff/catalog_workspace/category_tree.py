"""One category query, with direct product counts; assemble the hierarchy in memory."""
import hashlib
import json
from collections import defaultdict

from django.core import signing
from django.db.models import Count, Q

from web.catalog.models import Category


def category_rows():
    return list(Category.objects.annotate(
        product_count=Count("products"),
        published_count=Count("products", filter=Q(products__is_active=True)),
    ).order_by("position", "pk"))


def tree_rows(categories):
    children = defaultdict(list)
    for category in categories:
        children[category.parent_id].append(category)
    result, seen = [], set()
    stack = [(category, 0, True, []) for category in reversed(children[None])]
    while stack:
        category, depth, visible, ancestors = stack.pop()
        if category.pk in seen:
            continue
        seen.add(category.pk)
        visible = visible and category.is_visible
        result.append({"object": category, "depth": depth, "visible": visible,
                       "path": " / ".join([*ancestors, category.name]), "indent": min(depth, 10) * 18})
        stack.extend((child, depth + 1, visible, [*ancestors, category.name])
                     for child in reversed(children[category.pk]))
    return result


def branch_ids(categories, pk):
    children = defaultdict(list)
    for category in categories:
        children[category.parent_id].append(category.pk)
    found, pending = set(), [pk]
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(children[current])
    return found


def tree_digest(categories):
    state = [{field.attname: str(getattr(category, field.attname))
              for field in Category._meta.concrete_fields} for category in sorted(categories, key=lambda c: c.pk)]
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def issue_category_state(categories, pk):
    return signing.dumps([pk, tree_digest(categories)], salt="staff-category-tree")


def check_category_state(token, categories, pk):
    try:
        return signing.loads(token, salt="staff-category-tree", max_age=7200) == [pk, tree_digest(categories)]
    except signing.BadSignature:
        return False
