"""Safe catalogue failure contract, independent of transport and UI language."""


class CatalogSelectionError(Exception):
    def __init__(self, code: str, action: str):
        self.code = code
        self.action = action
        super().__init__(code)
