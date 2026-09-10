from PIL import Image

from models.character import QualityValidation, QualityWarning
from models.enums import Direction, WarningSeverity

ALPHA = 16

INVALID_BASE_MESSAGES = {
    "likely_portrait": "Invalid base: likely portrait composition",
    "likely_closeup": "Invalid base: likely portrait composition",
    "likely_non_full_body": "Invalid base: likely portrait composition",
    "likely_cropped": "Invalid base: likely cropped",
    "touches_top": "Invalid base: likely cropped",
    "touches_bottom": "Invalid base: likely cropped",
    "touches_left": "Invalid base: likely cropped",
    "touches_right": "Invalid base: likely cropped",
    "touches_edges": "Invalid base: likely cropped",
    "silhouette_incomplete": "Invalid base: likely cropped",
    "missing_lower_body": "Invalid base: missing lower body / spirit tail",
    "lower_spirit_body_missing": "Invalid base: missing lower body / spirit tail",
    "missing_spirit_tail": "Invalid base: missing lower body / spirit tail",
}

CROP_CODES = {
    "likely_cropped",
    "touches_edges",
    "touches_top",
    "touches_bottom",
    "touches_left",
    "touches_right",
    "silhouette_incomplete",
}

PORTRAIT_CODES = {"likely_portrait", "likely_closeup", "likely_non_full_body"}
FULL_BODY_CODES = {
    "likely_non_full_body",
    "missing_lower_body",
    "lower_spirit_body_missing",
    "missing_spirit_tail",
    "silhouette_incomplete",
}


def invalid_base_reasons(validation: QualityValidation | None) -> list[str]:
    if validation is None:
        return ["Invalid base: likely non-full-body output"]
    reasons: list[str] = []
    for warning in validation.warnings:
        message = INVALID_BASE_MESSAGES.get(warning.code)
        if message and message not in reasons:
            reasons.append(message)
    if not validation.validForBase and not reasons:
        reasons.append("Invalid base: likely non-full-body output")
    return reasons


def is_valid_base(validation: QualityValidation | None) -> bool:
    return not invalid_base_reasons(validation)


def _count_blobs(pixels, width: int, height: int) -> tuple[int, int]:
    scale = max(1, max(width, height) // 80)
    sw = max(1, width // scale)
    sh = max(1, height // scale)
    grid = [[False] * sw for _ in range(sh)]
    for y in range(sh):
        sy = min(height - 1, y * scale)
        for x in range(sw):
            sx = min(width - 1, x * scale)
            grid[y][x] = pixels[sx, sy][3] >= ALPHA
    seen = [[False] * sw for _ in range(sh)]
    sizes: list[int] = []
    for y in range(sh):
        for x in range(sw):
            if not grid[y][x] or seen[y][x]:
                continue
            size = 0
            stack = [(x, y)]
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                size += 1
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if nx < 0 or ny < 0 or nx >= sw or ny >= sh or seen[ny][nx] or not grid[ny][nx]:
                        continue
                    seen[ny][nx] = True
                    stack.append((nx, ny))
            sizes.append(size)
    opaque = sum(sizes) or 1
    significant = sum(1 for size in sizes if size >= max(4, int(opaque * 0.05)))
    return len(sizes), significant


def _metrics(image: Image.Image) -> dict:
    width, height = image.size
    pixels = image.convert("RGBA").load()
    opaque = 0
    unique: set[tuple[int, int, int]] = set()
    touches_left = touches_right = touches_top = touches_bottom = False
    mass_x = 0.0
    mass_y = 0.0
    left_mass = 0
    min_x, min_y, max_x, max_y = width, height, -1, -1
    top_band = 0
    bottom_band = 0
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < ALPHA:
                continue
            opaque += 1
            unique.add((r, g, b))
            mass_x += x
            mass_y += y
            min_x, min_y = min(min_x, x), min(min_y, y)
            max_x, max_y = max(max_x, x), max(max_y, y)
            if x == 0:
                touches_left = True
            if x == width - 1:
                touches_right = True
            if y == 0:
                touches_top = True
            if y == height - 1:
                touches_bottom = True
            if x < width // 2:
                left_mass += 1
            if y < height * 0.45:
                top_band += 1
            if y >= height * 0.70:
                bottom_band += 1
    total = max(1, width * height)
    occupancy = opaque / total
    if opaque and max_y >= min_y:
        bbox_w = max(1, max_x - min_x + 1)
        bbox_h = max(1, max_y - min_y + 1)
        center_x = (mass_x / opaque) / max(1, width - 1)
        center_y = (mass_y / opaque) / max(1, height - 1)
        upper_bbox = 0
        lower_bbox = 0
        lower_quarter = 0
        for y in range(min_y, max_y + 1):
            rel = (y - min_y) / max(1, bbox_h)
            for x in range(min_x, max_x + 1):
                if pixels[x, y][3] < ALPHA:
                    continue
                if rel < 0.45:
                    upper_bbox += 1
                if rel >= 0.60:
                    lower_bbox += 1
                if rel >= 0.75:
                    lower_quarter += 1
        upper_in_bbox = upper_bbox / opaque
        lower_in_bbox = lower_bbox / opaque
        lower_quarter_in_bbox = lower_quarter / opaque
        blobs, significant = _count_blobs(pixels, width, height)
    else:
        bbox_w = bbox_h = 0
        center_x = center_y = 0.5
        upper_in_bbox = lower_in_bbox = lower_quarter_in_bbox = 0.0
        min_x = min_y = 0
        max_x = max_y = 0
        blobs = significant = 0
    return {
        "opaque": opaque,
        "occupancy": occupancy,
        "unique": unique,
        "touches_edge": touches_left or touches_right or touches_top or touches_bottom,
        "touches_left": touches_left,
        "touches_right": touches_right,
        "touches_top": touches_top,
        "touches_bottom": touches_bottom,
        "height_ratio": bbox_h / height,
        "width_ratio": bbox_w / width,
        "aspect": bbox_w / max(1, bbox_h),
        "center_x": center_x,
        "center_y": center_y,
        "blobs": blobs,
        "significant_blobs": significant,
        "left_mass": left_mass,
        "right_mass": opaque - left_mass,
        "top_band": top_band,
        "bottom_band": bottom_band,
        "upper_in_bbox": upper_in_bbox,
        "lower_in_bbox": lower_in_bbox,
        "lower_quarter_in_bbox": lower_quarter_in_bbox,
        "bbox": (min_x, min_y, max_x + 1 if opaque else 0, max_y + 1 if opaque else 0),
    }


def _palette_mismatch(colors: set[tuple[int, int, int]], palette: list[tuple[int, int, int]] | None) -> float:
    if not palette or not colors:
        return 0.0
    total = 0.0
    for color in colors:
        nearest = min(((c[0] - color[0]) ** 2 + (c[1] - color[1]) ** 2 + (c[2] - color[2]) ** 2) for c in palette)
        total += nearest ** 0.5
    return total / max(1, len(colors))


def _direction_warning(direction: Direction | None, metrics: dict) -> QualityWarning | None:
    if not direction or metrics["opaque"] == 0:
        return None
    left = metrics["left_mass"]
    right = metrics["right_mass"]
    total = max(1, left + right)
    bias = (right - left) / total
    if direction == "E" and bias < -0.22:
        return _warn("direction_likely_incorrect", "Facing looks left-heavy for an east view")
    if direction == "W" and bias > 0.22:
        return _warn("direction_likely_incorrect", "Facing looks right-heavy for a west view")
    if direction in ("N", "S") and abs(bias) > 0.38:
        return _warn("direction_likely_incorrect", "Front/back facing looks strongly side-biased")
    return None


def _warn(code: str, message: str, severity: WarningSeverity = "warning") -> QualityWarning:
    return QualityWarning(code=code, message=message, severity=severity)


def _add_composition_failures(
    warnings: list[QualityWarning],
    metrics: dict,
    source: dict | None,
    spirit_form: bool,
    for_base: bool,
    one_character: bool,
) -> None:
    severity: WarningSeverity = "error" if for_base else "warning"
    data = source or metrics
    aspect = data.get("aspect") or 0
    lower = data.get("lower_in_bbox") or 0
    lower_q = data.get("lower_quarter_in_bbox") or 0
    height_ratio = data.get("height_ratio") or 0
    width_ratio = data.get("width_ratio") or 0
    occupancy = data.get("occupancy") or 0

    if data.get("touches_top"):
        warnings.append(_warn("touches_top", "Sprite touches top edge", severity))
    if data.get("touches_bottom"):
        warnings.append(_warn("touches_bottom", "Sprite touches bottom edge", severity))
    if data.get("touches_left"):
        warnings.append(_warn("touches_left", "Sprite touches left edge", severity))
    if data.get("touches_right"):
        warnings.append(_warn("touches_right", "Sprite touches right edge", severity))

    cropped = bool(data.get("touches_edge")) or height_ratio > 0.90 or width_ratio > 0.90
    if cropped:
        warnings.append(_warn("likely_cropped", "Likely cropped sprite", severity))
        warnings.append(_warn("silhouette_incomplete", "Likely incomplete silhouette", severity))

    portrait = aspect >= 0.82
    closeup = (aspect >= 0.78 and occupancy >= 0.14 and height_ratio >= 0.55) or (
        aspect >= 0.90 and occupancy >= 0.12
    )
    if portrait:
        warnings.append(_warn("likely_portrait", "Likely portrait composition", severity))
    if closeup:
        warnings.append(_warn("likely_closeup", "Likely close-up / bust composition", severity))
    if portrait or closeup:
        warnings.append(_warn("likely_non_full_body", "Likely non-full-body output", severity))

    if lower_q < 0.08 or lower < 0.12:
        warnings.append(_warn("missing_lower_body", "Missing lower body", severity))
        if spirit_form:
            warnings.append(_warn("lower_spirit_body_missing", "Lower spirit body missing", severity))
            warnings.append(_warn("missing_spirit_tail", "Missing spirit tail", severity))
    elif spirit_form and (lower < 0.18 or lower_q < 0.10):
        warnings.append(_warn("missing_spirit_tail", "Missing spirit tail", severity))
        warnings.append(_warn("lower_spirit_body_missing", "Lower spirit body missing", severity))

    blobs = data.get("significant_blobs") or metrics.get("significant_blobs") or 0
    if one_character and blobs >= 3:
        warnings.append(_warn("extra_characters", "More than one character-sized blob"))


def validate_sprite(
    image: Image.Image,
    expected_size: int,
    palette_limit: int,
    source_size: int | None = None,
    reference: Image.Image | None = None,
    palette: list[tuple[int, int, int]] | None = None,
    direction: Direction | None = None,
    spirit_form: bool = False,
    source: Image.Image | None = None,
    for_base: bool = False,
    one_character: bool = True,
) -> QualityValidation:
    warnings: list[QualityWarning] = []
    width, height = image.size
    if width != expected_size or height != expected_size:
        warnings.append(_warn("wrong_dimensions", f"Sprite is {width}x{height}, expected {expected_size}x{expected_size}", "error"))

    metrics = _metrics(image)
    source_metrics = _metrics(source) if source is not None else None
    occupancy = metrics["occupancy"]
    if metrics["opaque"] == 0:
        warnings.append(_warn("empty_sprite", "Sprite has no opaque pixels", "error"))
    elif occupancy < 0.04:
        warnings.append(_warn("too_much_transparency", "Sprite is almost empty"))
    elif occupancy < 0.08:
        warnings.append(_warn("sprite_too_small", "Sprite occupies too little of the canvas"))
    if occupancy > 0.72 or metrics["height_ratio"] > 0.92 or metrics["width_ratio"] > 0.92:
        warnings.append(_warn("too_large_for_canvas", f"Character too large for {expected_size}x{expected_size}"))
    if len(metrics["unique"]) > palette_limit:
        warnings.append(_warn("palette_exceeds", f"Sprite uses {len(metrics['unique'])} colors, limit is {palette_limit}"))

    _add_composition_failures(warnings, metrics, source_metrics, spirit_form, for_base, one_character)

    if source_size and source_size >= expected_size * 4:
        warnings.append(
            _warn(
                "downscaled_source",
                f"Source was {source_size}px then reduced to {expected_size}px with pixel-aware downsample.",
            )
        )
    if width != height:
        warnings.append(_warn("inconsistent_canvas", "Canvas is not square"))

    mismatch = _palette_mismatch(metrics["unique"], palette)
    if palette and mismatch > 28:
        warnings.append(_warn("palette_mismatch", f"Colors drift from the accepted character palette (mean distance {mismatch:.0f})"))

    ref_metrics = _metrics(reference) if reference is not None else None
    if ref_metrics and ref_metrics["opaque"] and not for_base:
        dx = abs(metrics["center_x"] - ref_metrics["center_x"])
        dy = abs(metrics["center_y"] - ref_metrics["center_y"])
        if dx > 0.12 or dy > 0.14:
            warnings.append(_warn("center_of_mass_shift", "Center of mass shifted too far from the accepted base"))
        if ref_metrics["height_ratio"] and abs(metrics["height_ratio"] - ref_metrics["height_ratio"]) > 0.16:
            warnings.append(_warn("height_inconsistent", "Character height is inconsistent with the accepted base"))
        if ref_metrics["width_ratio"] and abs(metrics["width_ratio"] - ref_metrics["width_ratio"]) > 0.18:
            warnings.append(_warn("silhouette_width_inconsistent", "Silhouette width is inconsistent with the accepted base"))
        if metrics["blobs"] >= max(4, ref_metrics["blobs"] + 2):
            warnings.append(_warn("probable_extra_limbs", "Too many separate opaque blobs; possible extra limbs or debris"))
    elif metrics["blobs"] >= 5:
        warnings.append(_warn("probable_extra_limbs", "Too many separate opaque blobs; possible extra limbs or debris"))

    facing = _direction_warning(direction, metrics)
    if facing:
        warnings.append(facing)

    seen: set[str] = set()
    unique_warnings: list[QualityWarning] = []
    for warning in warnings:
        if warning.code in seen:
            continue
        seen.add(warning.code)
        unique_warnings.append(warning)
    warnings = unique_warnings

    portrait_failed = any(w.code in PORTRAIT_CODES for w in warnings)
    crop_failed = any(w.code in CROP_CODES for w in warnings)
    full_body_failed = any(w.code in FULL_BODY_CODES for w in warnings)
    valid_for_base = not any(w.code in INVALID_BASE_MESSAGES for w in warnings)
    if for_base and metrics["opaque"] == 0:
        valid_for_base = False

    score = 100
    composition_score = 100
    for warning in warnings:
        penalty = 18 if warning.severity == "error" else 8
        score -= penalty
        if warning.code in INVALID_BASE_MESSAGES:
            composition_score -= 22 if warning.severity == "error" else 14
    score = max(0, min(100, score))
    composition_score = max(0, min(100, composition_score))
    bbox = metrics["bbox"]
    edge_source = source_metrics or metrics

    return QualityValidation(
        ok=not any(w.severity == "error" for w in warnings) and (valid_for_base if for_base else True),
        score=score,
        compositionScore=composition_score,
        validForBase=valid_for_base,
        warnings=warnings,
        futureChecks=[],
        occupancy=round(occupancy, 4),
        heightRatio=round(metrics["height_ratio"], 4),
        widthRatio=round(metrics["width_ratio"], 4),
        centerX=round(metrics["center_x"], 4),
        centerY=round(metrics["center_y"], 4),
        bboxLeft=int(bbox[0]),
        bboxTop=int(bbox[1]),
        bboxRight=int(bbox[2]),
        bboxBottom=int(bbox[3]),
        touchesTop=bool(edge_source["touches_top"]),
        touchesBottom=bool(edge_source["touches_bottom"]),
        touchesLeft=bool(edge_source["touches_left"]),
        touchesRight=bool(edge_source["touches_right"]),
        portraitFailed=portrait_failed,
        cropFailed=crop_failed,
        fullBodyFailed=full_body_failed,
    )
