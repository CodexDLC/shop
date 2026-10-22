from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class ListingRequest:
    """Bounded, canonical GET input. No request body or raw SQL reaches selectors."""

    query: str = ""
    filters: dict = field(default_factory=dict)
    sort: str = "name"
    page: int = 1
    errors: tuple = ()

    @classmethod
    def from_query(cls, params):
        errors = []
        filters = {}
        query = params.get("q", "").strip()
        if len(query) > 160:
            errors.append("catalog.listing.error.invalid_filter")
            query = query[:160]
        for key, length in (
            ("brand", 120), ("category", 120), ("tag", 120), ("material", 120), ("property", 120),
            ("color", 40), ("size", 20),
        ):
            raw = params.getlist(key)
            values = list(dict.fromkeys(value.strip() for value in raw if value.strip()))
            if len(values) > 20 or any(len(value) > length for value in values):
                errors.append("catalog.listing.error.invalid_filter")
            values = [value for value in values[:20] if len(value) <= length]
            if values:
                filters[key] = values
        for key in ("min_price", "max_price"):
            value = params.get(key, "").strip()
            if not value:
                continue
            try:
                if len(value) > 12:
                    raise ValueError
                price = Decimal(value)
                if not price.is_finite() or price < 0 or price > Decimal("99999999.99"):
                    raise ValueError
                if price != price.quantize(Decimal("0.01")):
                    raise ValueError
                filters[key] = format(price, ".2f")
            except (ValueError, InvalidOperation):
                errors.append("catalog.listing.error.invalid_price")
        if ("min_price" in filters and "max_price" in filters
                and Decimal(filters["min_price"]) > Decimal(filters["max_price"])):
            filters.pop("min_price")
            filters.pop("max_price")
            errors.append("catalog.listing.error.invalid_range")
        stock = params.get("in_stock", "")
        if stock in ("1", "true", "on"):
            filters["in_stock"] = "1"
        elif stock not in ("", "0", "false", "off"):
            errors.append("catalog.listing.error.invalid_filter")
        section = params.get("section", "").strip()
        if section in ("underwear", "swimwear", "other") and len(params.getlist("section")) == 1:
            filters["section"] = section
        elif section or len(params.getlist("section")) > 1:
            errors.append("catalog.listing.error.invalid_filter")
        for name in ("new", "sale"):
            flag = params.get(name, "")
            if len(params.getlist(name)) > 1:
                errors.append("catalog.listing.error.invalid_filter")
            elif flag in ("1", "true", "on"):
                filters[name] = "1"
            elif flag not in ("", "0", "false", "off"):
                errors.append("catalog.listing.error.invalid_filter")
        sort = params.get("sort", "name")
        if sort not in ("name", "price_asc", "price_desc", "newest", "rating"):
            sort = "name"
            errors.append("catalog.listing.error.invalid_sort")
        raw_page = params.get("page", "1")
        if not raw_page.isascii() or not raw_page.isdigit() or len(raw_page) > 8 or int(raw_page) < 1:
            page = 1
            errors.append("catalog.listing.error.invalid_page")
        else:
            page = int(raw_page)
        return cls(query=query, filters=filters, sort=sort, page=page, errors=tuple(dict.fromkeys(errors)))
