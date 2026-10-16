"""A colour gallery, or a general gallery when color is None."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Gallery:
    color: str | None
    images: tuple[str, ...]

    def __post_init__(self):
        if self.color is not None and (not isinstance(self.color, str) or not self.color.strip()):
            raise ValueError("Gallery color must be non-empty or None")
        if not isinstance(self.images, tuple) or any(not isinstance(image, str) or not image for image in self.images):
            raise ValueError("Gallery images must be an immutable tuple of non-empty references")
