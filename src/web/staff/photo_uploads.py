import io
import uuid
import warnings

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from web.localization.translation import translate_text

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_DIMENSION = 8000


def sanitize_photo(upload):
    """Decode actual pixels and save a metadata-free PNG/JPEG with a generated name."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(translate_text("staff.photos.invalid_upload"))
    data = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(translate_text("staff.photos.invalid_upload"))
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("format")
                if (original.width * original.height > MAX_PIXELS
                        or max(original.size) > MAX_DIMENSION or getattr(original, "n_frames", 1) != 1):
                    raise ValueError("dimensions or frames")
                original.load()
                oriented = ImageOps.exif_transpose(original)
                alpha = "A" in oriented.getbands() or "transparency" in oriented.info
                mode = "RGBA" if alpha else "RGB"
                pixels = oriented.convert(mode)
                clean = Image.new(mode, pixels.size)
                clean.paste(pixels)
                output = io.BytesIO()
                clean.save(output, format="PNG" if alpha else "JPEG", **({} if alpha else {"quality": 90}))
                if output.tell() > MAX_UPLOAD_BYTES:
                    raise ValueError("encoded size")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ValidationError(translate_text("staff.photos.invalid_upload")) from None
    return ContentFile(output.getvalue(), name=f"{uuid.uuid4().hex}.{'png' if alpha else 'jpg'}")
