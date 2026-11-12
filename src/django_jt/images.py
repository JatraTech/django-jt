"""Image optimization helpers for product/media uploads."""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

DEFAULT_MAX_EDGE = 1280
DEFAULT_WEBP_QUALITY = 75

FileSource = Path | str | BinaryIO


def slugify_filename(name: str) -> str:
    slug = name.lower().strip()
    for char in " _/\\":
        slug = slug.replace(char, "-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _source_stem(source: FileSource, original_name: str | None) -> str:
    if original_name:
        return Path(original_name).stem
    if isinstance(source, (str, Path)):
        return Path(source).stem
    name = getattr(source, "name", None) or "image"
    return Path(str(name)).stem


def _normalize_mode(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA"):
        return img.convert("RGBA")
    if img.mode == "P":
        return img.convert("RGBA") if "transparency" in img.info else img.convert("RGB")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def optimize_image_to_webp(
    source: FileSource,
    *,
    original_name: str | None = None,
    max_edge: int = DEFAULT_MAX_EDGE,
    quality: int = DEFAULT_WEBP_QUALITY,
) -> tuple[bytes, str]:
    if hasattr(source, "seek"):
        try:
            source.seek(0)
        except (OSError, io.UnsupportedOperation):
            pass

    stem = _source_stem(source, original_name)
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        img = _normalize_mode(img)
        img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="WEBP", quality=quality, method=6)
        filename = f"{slugify_filename(stem)}.webp"
        return buffer.getvalue(), filename


def optimize_image_content(
    file: FileSource,
    original_name: str,
    *,
    max_edge: int = DEFAULT_MAX_EDGE,
    quality: int = DEFAULT_WEBP_QUALITY,
) -> tuple[ContentFile, str]:
    webp_bytes, webp_name = optimize_image_to_webp(
        file,
        original_name=original_name,
        max_edge=max_edge,
        quality=quality,
    )
    return ContentFile(webp_bytes), webp_name
