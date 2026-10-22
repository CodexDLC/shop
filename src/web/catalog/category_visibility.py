"""Recursive category constraints stay inside SQL: no per-product ancestor lookups.

The CTE uses SQL supported by PostgreSQL and SQLite; values always use parameters.
Only trees rooted in a visible root are visible, so corrupt cycles fail closed.
"""
from django.db.models.expressions import RawSQL


def visible_category_ids():
    return RawSQL("""
        WITH RECURSIVE visible(id) AS (
          SELECT id FROM catalog_category WHERE parent_id IS NULL AND is_visible
          UNION
          SELECT child.id FROM catalog_category child JOIN visible ON child.parent_id = visible.id
          WHERE child.is_visible
        ) SELECT id FROM visible
    """, [])


def descendant_category_ids(slugs):
    placeholders = ", ".join(["%s"] * len(slugs))
    return RawSQL(f"""
        WITH RECURSIVE descendants(id) AS (
          SELECT id FROM catalog_category WHERE slug IN ({placeholders})
          UNION
          SELECT child.id FROM catalog_category child JOIN descendants ON child.parent_id = descendants.id
        ) SELECT id FROM descendants
    """, list(slugs))
