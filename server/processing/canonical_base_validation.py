"""Canonical Berwynn south-base checks. Isolated from production validate_sprite gating."""

from __future__ import annotations

from PIL import Image

from models.character import QualityValidation, QualityWarning
from processing.validation import _metrics, _warn, validate_sprite

LEGS_CODE = "legs_visible"
ARMOR_CODE = "armor_visible"
BUSY_BG_CODE = "busy_background"
MULTI_CODE = "extra_characters"
CROP_CODES = {
    "likely_cropped",
    "touches_top",
    "touches_bottom",
    "touches_left",
    "touches_right",
    "touches_edges",
    "silhouette_incomplete",
}
FULL_BODY_CODES = {
    "likely_portrait",
    "likely_closeup",
    "likely_non_full_body",
    "missing_lower_body",
    "lower_spirit_body_missing",
    "missing_spirit_tail",
    "silhouette_incomplete",
}

REJECT_MESSAGES = {
    LEGS_CODE: "Rejected: legs are visible; Berwynn needs a spectral ghost tail",
    ARMOR_CODE: "Rejected: armor or shoulder pieces are visible",
    BUSY_BG_CODE: "Rejected: background is busy",
    MULTI_CODE: "Rejected: more than one character appears",
    "possible_duplicate_figure": "Rejected: more than one character appears",
    "extra_artifact": "Rejected: more than one character appears",
    "likely_cropped": "Rejected: body is cropped",
    "touches_top": "Rejected: body is cropped",
    "touches_bottom": "Rejected: body is cropped",
    "touches_left": "Rejected: body is cropped",
    "touches_right": "Rejected: body is cropped",
    "touches_edges": "Rejected: body is cropped",
    "silhouette_incomplete": "Rejected: silhouette is not full body",
    "likely_portrait": "Rejected: silhouette is not full body",
    "likely_closeup": "Rejected: silhouette is not full body",
    "likely_non_full_body": "Rejected: silhouette is not full body",
    "missing_lower_body": "Rejected: silhouette is not full body",
    "lower_spirit_body_missing": "Rejected: silhouette is not full body",
    "missing_spirit_tail": "Rejected: silhouette is not full body",
}


def _color_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _corner_stats(image: Image.Image) -> dict:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    inset_w = max(4, width // 8)
    inset_h = max(4, height // 8)
    patches = [
        (0, 0, inset_w, inset_h),
        (width - inset_w, 0, width, inset_h),
        (0, height - inset_h, inset_w, height),
        (width - inset_w, height - inset_h, width, height),
    ]
    medians: list[tuple[int, int, int]] = []
    unique: set[tuple[int, int, int]] = set()
    for x0, y0, x1, y1 in patches:
        colors: list[tuple[int, int, int]] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                r, g, b, a = pixels[x, y]
                if a < 16:
                    continue
                color = (r, g, b)
                colors.append(color)
                unique.add(color)
        if not colors:
            continue
        colors.sort()
        medians.append(colors[len(colors) // 2])
    spread = 0.0
    if len(medians) >= 2:
        spread = max(_color_dist(a, b) for i, a in enumerate(medians) for b in medians[i + 1 :])
    bg = medians[0] if medians else (128, 128, 128)
    return {"bg": bg, "spread": spread, "unique": len(unique), "medians": medians}


def knockout_plain_background(image: Image.Image) -> tuple[Image.Image, bool]:
    """Treat a consistent corner color as background. Returns (masked, busy)."""
    stats = _corner_stats(image)
    rgba = image.convert("RGBA")
    corners_disagree = stats["spread"] > 55
    if corners_disagree or not stats["medians"]:
        return rgba, True
    bg = stats["bg"]
    pixels = rgba.load()
    width, height = rgba.size
    removed = 0
    kept = 0
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            if _color_dist((r, g, b), bg) <= 46:
                pixels[x, y] = (r, g, b, 0)
                removed += 1
            else:
                kept += 1
    if kept == 0 or removed / max(1, removed + kept) < 0.20:
        return image.convert("RGBA"), True
    occupancy = kept / max(1, width * height)
    busy = occupancy > 0.62
    return rgba, busy


def _legs_visible(metrics: dict, image: Image.Image) -> bool:
    bbox = metrics.get("bbox") or (0, 0, 0, 0)
    min_x, min_y, max_x, max_y = bbox
    if max_x <= min_x or max_y <= min_y:
        return False
    pixels = image.convert("RGBA").load()
    bbox_w = max(1, max_x - min_x)
    bbox_h = max(1, max_y - min_y)
    y0 = min_y + int(bbox_h * 0.76)
    left = mid = right = 0
    for y in range(y0, max_y):
        for x in range(min_x, max_x):
            if pixels[x, y][3] < 16:
                continue
            rel = (x - min_x) / bbox_w
            if rel < 0.33:
                left += 1
            elif rel > 0.67:
                right += 1
            else:
                mid += 1
    side = max(left, right)
    if left > 18 and right > 18 and mid < max(12, side * 0.42):
        return True
    # Two foot-like contacts at the very bottom.
    y1 = min_y + int(bbox_h * 0.90)
    columns = [0] * max(1, bbox_w)
    for y in range(y1, max_y):
        for x in range(min_x, max_x):
            if pixels[x, y][3] >= 16:
                columns[x - min_x] += 1
    clusters = 0
    inside = False
    for count in columns:
        on = count >= 2
        if on and not inside:
            clusters += 1
            inside = True
        elif not on:
            inside = False
    return clusters >= 2 and left > 10 and right > 10


def _armor_visible(metrics: dict, image: Image.Image) -> bool:
    bbox = metrics.get("bbox") or (0, 0, 0, 0)
    min_x, min_y, max_x, max_y = bbox
    if max_x <= min_x or max_y <= min_y:
        return False
    pixels = image.convert("RGBA").load()
    bbox_w = max(1, max_x - min_x)
    bbox_h = max(1, max_y - min_y)

    def band_width(start: float, end: float) -> tuple[int, int]:
        y0 = min_y + int(bbox_h * start)
        y1 = min_y + int(bbox_h * end)
        left = max_x
        right = min_x
        count = 0
        for y in range(y0, max(y0 + 1, y1)):
            for x in range(min_x, max_x):
                r, g, b, a = pixels[x, y]
                if a < 16:
                    continue
                count += 1
                left = min(left, x)
                right = max(right, x)
        return (max(0, right - left + 1) if count else 0, count)

    shoulder_w, shoulder_n = band_width(0.16, 0.36)
    waist_w, waist_n = band_width(0.48, 0.64)
    if waist_w and shoulder_w / waist_w >= 1.48 and shoulder_n > 40:
        return True

    metal = 0
    y0 = min_y + int(bbox_h * 0.12)
    y1 = min_y + int(bbox_h * 0.38)
    edge = max(4, int(bbox_w * 0.16))
    for y in range(y0, max(y0 + 1, y1)):
        for x in range(min_x, max_x):
            if x > min_x + edge and x < max_x - edge:
                continue
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            mx = max(r, g, b)
            mn = min(r, g, b)
            sat = mx - mn
            if mx >= 190 and sat <= 28:
                metal += 1
            if r >= 165 and g >= 130 and b <= 80 and sat >= 50:
                metal += 1
    return metal >= max(40, int(bbox_w * bbox_h * 0.018))


def reject_reasons(validation: QualityValidation, extra: list[QualityWarning]) -> list[str]:
    reasons: list[str] = []
    for warning in [*validation.warnings, *extra]:
        message = REJECT_MESSAGES.get(warning.code)
        if message and message not in reasons:
            reasons.append(message)
    return reasons


def validate_canonical_base(image: Image.Image) -> tuple[QualityValidation, list[str], bool]:
    masked, busy = knockout_plain_background(image)
    validation = validate_sprite(
        masked,
        expected_size=image.size[0],
        palette_limit=512,
        spirit_form=True,
        for_base=True,
        one_character=True,
        source=masked,
    )
    extra: list[QualityWarning] = []
    metrics = _metrics(masked)
    if busy:
        extra.append(_warn(BUSY_BG_CODE, "Background is busy", "error"))
    if _legs_visible(metrics, masked):
        extra.append(_warn(LEGS_CODE, "Legs are visible instead of a spectral tail", "error"))
    if _armor_visible(metrics, masked):
        extra.append(_warn(ARMOR_CODE, "Armor or shoulder pieces are visible", "error"))

    seen = {warning.code for warning in validation.warnings}
    merged = list(validation.warnings)
    for warning in extra:
        if warning.code not in seen:
            merged.append(warning)
            seen.add(warning.code)
    validation.warnings = merged
    reasons = reject_reasons(validation, extra)
    valid = not reasons
    validation.validForBase = valid
    validation.ok = valid
    return validation, reasons, busy
