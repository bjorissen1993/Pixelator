"""Global validators: integrity, dimensions, corruption, requested subject count."""

from __future__ import annotations

from PIL import Image

from models.catalog import AssetProfile
from models.character import QualityWarning
from processing.validation import _warn
from processing.validators.heuristics import knockout_plain_background

BUSY_BG_CODE = "busy_background"
MULTI_CODE = "extra_subjects"
INTEGRITY_CODE = "image_integrity"
DIMENSION_CODE = "expected_dimensions"
CORRUPT_CODE = "image_corrupt"


def global_warnings(image: Image.Image, asset: AssetProfile) -> tuple[Image.Image, list[QualityWarning]]:
    extra: list[QualityWarning] = []
    try:
        image.load()
    except Exception:
        extra.append(_warn(CORRUPT_CODE, "Image could not be decoded", "error"))
        return image.convert("RGBA"), extra

    width, height = image.size
    if width <= 0 or height <= 0:
        extra.append(_warn(INTEGRITY_CODE, "Image has no pixels", "error"))
        return image.convert("RGBA"), extra

    expected_w = asset.generation.width or width
    expected_h = asset.generation.height or height
    if asset.generation.enabled and (width != expected_w or height != expected_h):
        extra.append(
            _warn(
                DIMENSION_CODE,
                f"Expected {expected_w}×{expected_h}, got {width}×{height}",
                "error",
            )
        )

    extrema = image.convert("RGBA").getextrema()
    if extrema and all(channel[0] == channel[1] for channel in extrema):
        extra.append(_warn(CORRUPT_CODE, "Image is a single flat color", "error"))

    masked, busy = knockout_plain_background(image)
    if asset.flags.plainBackground and busy:
        extra.append(_warn(BUSY_BG_CODE, "Background is busy", "error"))
    return masked, extra
