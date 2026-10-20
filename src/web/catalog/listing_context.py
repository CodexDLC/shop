import re

from django.core.paginator import Paginator
from django.http import QueryDict
from django.urls import reverse

from web.localization import translate_text

from .presentation import product_presentation
from .selectors import listing_facets, listing_products


class ListingContext:
    """Compose one bounded page and canonical links without changing business state."""

    page_size = 12

    def __init__(self, criteria):
        self.criteria = criteria
        self.action = reverse("catalog:list")
        self.params = QueryDict(mutable=True)
        if criteria.query:
            self.params["q"] = criteria.query
        for name, value in criteria.filters.items():
            if isinstance(value, list):
                self.params.setlist(name, value)
            else:
                self.params[name] = value
        if criteria.sort != "name":
            self.params["sort"] = criteria.sort

    def url(self, *, page=None, remove=None):
        params = self.params.copy()
        if remove:
            name, value = remove
            remaining = [item for item in params.getlist(name) if item != value]
            if remaining:
                params.setlist(name, remaining)
            else:
                params.pop(name, None)
        if page is not None and page != 1:
            params["page"] = str(page)
        encoded = params.urlencode()
        return self.action + ("?" + encoded if encoded else "")

    def build(self):
        paginator = Paginator(listing_products(self.criteria), self.page_size)
        page = paginator.get_page(self.criteria.page)
        cards = [product_presentation(
            product, code=f"listing-{product.pk}", selected_sku=product.listing_sku, currency="EUR",
        ) for product in page.object_list]
        facets = self.facets()
        labels = {
            (name, item["value"]): item["label"]
            for name, entries in facets.items() for item in entries
        }
        plural = {"brand": "brands", "category": "categories", "tag": "tags",
                  "color": "colors", "size": "sizes"}
        active = []
        if self.criteria.query:
            active.append({"label": self.criteria.query, "value": self.criteria.query,
                           "remove_url": self.url(remove=("q", self.criteria.query))})
        for name, selected in self.criteria.filters.items():
            for value in selected if isinstance(selected, list) else [selected]:
                label = labels.get((plural.get(name), value), value)
                if name in ("min_price", "max_price", "in_stock"):
                    prefix = translate_text(f"catalog.listing.filter.{name}")
                    label = prefix if name == "in_stock" else f"{prefix}: {value} €"
                if name in ("new", "sale"):
                    label = translate_text(f"catalog.listing.filter.{name}")
                elif name == "section":
                    label = translate_text(f"catalog.section.{value}")
                active.append({"label": label, "value": value,
                               "remove_url": self.url(remove=(name, value))})
        # Bounded navigation even for a large number of products.
        numbers = sorted({1, paginator.num_pages, *range(max(1, page.number - 2),
                                                       min(paginator.num_pages, page.number + 2) + 1)})
        return {
            "products": cards, "total": paginator.count, "page": page.number,
            "num_pages": paginator.num_pages, "page_start": page.start_index(), "page_end": page.end_index(),
            "previous_url": self.url(page=page.previous_page_number()) if page.has_previous() else "",
            "next_url": self.url(page=page.next_page_number()) if page.has_next() else "",
            "page_links": [{"number": number, "url": self.url(page=number), "current": number == page.number}
                           for number in numbers],
            "query": self.criteria.query, "filters": self.criteria.filters, "facets": facets,
            "active_filters": active, "clear_url": self.action, "form_action": self.action,
            "sort": self.criteria.sort, "errors": list(self.criteria.errors),
        }

    def facets(self):
        raw = listing_facets()
        result = {}
        singular = {"brands": "brand", "categories": "category", "tags": "tag",
                    "colors": "color", "sizes": "size"}
        for name, rows in raw.items():
            entries = {}
            selected = self.criteria.filters.get(singular[name], [])
            for row in rows:
                value, label = (row, row) if name == "sizes" else row[:2]
                if name not in ("brands", "sizes"):
                    label = translate_text(label)
                entry = {"value": value, "label": label, "selected": value in selected}
                if name == "colors" and re.fullmatch(r"#[0-9a-fA-F]{6}", row[2]):
                    entry["hex"] = row[2]
                entries.setdefault(value, entry)
            # Preserve selected URL constraints even if unknown or beyond the facet cap.
            # Otherwise the next form submission silently broadens the result set.
            for value in selected:
                entries.setdefault(value, {"value": value, "label": value, "selected": True})
            result[name] = list(entries.values())
        return result
