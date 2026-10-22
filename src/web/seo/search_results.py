class SearchResults:
    """A small static allowlist followed by SQL-sliced catalog identities."""

    ordered = True

    def __init__(self, static, queryset):
        self.static = static
        self.queryset = queryset

    def count(self):
        return len(self.static) + self.queryset.count()

    def __getitem__(self, bounds):
        start, stop = bounds.start or 0, bounds.stop
        static = self.static[start:stop]
        offset = len(self.static)
        rows = self.queryset[max(start - offset, 0):max(stop - offset, 0)]
        return [*static, *rows]
