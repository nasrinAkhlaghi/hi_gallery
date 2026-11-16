"""Development-only local image storage with bounded decoding and generated names."""

from io import BytesIO
from pathlib import Path
import re
import warnings
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MEDIA_PREFIX = "/media/products/"
FORMATS = {"JPEG": (".jpg", "image/jpeg"), "PNG": (".png", "image/png"), "WEBP": (".webp", "image/webp")}


class InvalidImage(Exception):
    pass


def image_path(filename: str) -> Path | None:
    if not re.fullmatch(r"[0-9a-f]{32}\.(jpg|png|webp)", filename):
        return None
    return get_settings().product_upload_dir / filename


def store_image(data: bytes, content_type: str) -> str:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise InvalidImage
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as original:
                image_format = original.format
                if image_format not in FORMATS or FORMATS[image_format][1] != content_type:
                    raise InvalidImage
                if original.width * original.height > MAX_IMAGE_PIXELS or getattr(original, "n_frames", 1) != 1:
                    raise InvalidImage
                original.load()
                # Re-encode pixels rather than persisting the untrusted original or its metadata.
                clean = Image.new("RGB" if image_format == "JPEG" else "RGBA", original.size)
                clean.paste(original.convert(clean.mode))
                output = BytesIO()
                clean.save(output, format=image_format)
                encoded = output.getvalue()
                if len(encoded) > MAX_IMAGE_BYTES:
                    raise InvalidImage
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage from exc
    filename = uuid4().hex + FORMATS[image_format][0]
    path = image_path(filename)
    assert path is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        try:
            target.write(encoded)
        except Exception:
            target.close()
            path.unlink(missing_ok=True)
            raise
    return MEDIA_PREFIX + filename


def remove_image(url: str) -> None:
    if url.startswith(MEDIA_PREFIX):
        path = image_path(url.removeprefix(MEDIA_PREFIX))
        if path is not None:
            path.unlink(missing_ok=True)
