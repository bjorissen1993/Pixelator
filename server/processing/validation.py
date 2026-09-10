from PIL import Image

from models.character import QualityValidation, QualityWarning
from models.enums import Direction

ALPHA = 16


def _metrics(image: Image.Image) -> dict:
    width, height = image.size
    pixels = image.convert("RGBA").load()
    opaque = 0
    unique: set[tuple[int, int, int]] = set()
    touches_edge = False
    mass_x = 0.0
    mass_y = 0.0
    min_x, min_y, max_x, max_y = width, height, -1, -1
    labels = [[0] * width for _ in range(height)]
    blob_id = 0
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
            if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                touches_edge = True
            if labels[y][x] == 0:
                blob_id += 1
                stack = [(x, y)]
                labels[y][x] = blob_id
                while stack:
                    cx, cy = stack.pop()
                    for nx in range(max(0, cx - 1), min(width, cx + 2)):
                        for ny in range(max(0, cy - 1), min(height, cy + 2)):
                            if labels[ny][nx] or pixels[nx, ny][3] < ALPHA:
                                continue
                            labels[ny][nx] = blob_id
                            stack.append((nx, ny))
    total = max(1, width * height)
    occupancy = opaque / total
    if opaque:
        bbox_w = max(1, max_x - min_x + 1)
        bbox_h = max(1, max_y - min_y + 1)
        center_x = (mass_x / opaque) / max(1, width - 1)
        center_y = (mass_y / opaque) / max(1, height - 1)
        left_mass = sum(1 for y in range(height) for x in range(width // 2) if pixels[x, y][3] >= ALPHA)
        right_mass = opaque - left_mass
    else:
        bbox_w = bbox_h = 0
        center_x = center_y = 0.5
        left_mass = right_mass = 0
    return {
        "opaque": opaque,
        "occupancy": occupancy,
        "unique": unique,
        "touches_edge": touches_edge,
        "height_ratio": bbox_h / height,
        "width_ratio": bbox_w / width,
        "center_x": center_x,
        "center_y": center_y,
        "blobs": blob_id,
        "left_mass": left_mass,
        "right_mass": right_mass,
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
        return QualityWarning(code="direction_likely_incorrect", message="Facing looks left-heavy for an east view", severity="warning")
    if direction == "W" and bias > 0.22:
        return QualityWarning(code="direction_likely_incorrect", message="Facing looks right-heavy for a west view", severity="warning")
    if direction in ("N", "S") and abs(bias) > 0.38:
        return QualityWarning(code="direction_likely_incorrect", message="Front/back facing looks strongly side-biased", severity="warning")
    return None


def validate_sprite(
    image: Image.Image,
    expected_size: int,
    palette_limit: int,
    source_size: int | None = None,
    reference: Image.Image | None = None,
    palette: list[tuple[int, int, int]] | None = None,
    direction: Direction | None = None,
) -> QualityValidation:
    warnings: list[QualityWarning] = []
    width, height = image.size
    if width != expected_size or height != expected_size:
        warnings.append(
            QualityWarning(
                code="wrong_dimensions",
                message=f"Sprite is {width}x{height}, expected {expected_size}x{expected_size}",
                severity="error",
            )
        )

    metrics = _metrics(image)
    occupancy = metrics["occupancy"]
    if metrics["opaque"] == 0:
        warnings.append(QualityWarning(code="empty_sprite", message="Sprite has no opaque pixels", severity="error"))
    elif occupancy < 0.04:
        warnings.append(QualityWarning(code="too_much_transparency", message="Sprite is almost empty", severity="warning"))
    elif occupancy < 0.08:
        warnings.append(QualityWarning(code="sprite_too_small", message="Sprite occupies too little of the canvas", severity="warning"))
    if occupancy > 0.78 or metrics["height_ratio"] > 0.98:
        warnings.append(QualityWarning(code="sprite_too_large", message="Sprite is too large or cropped on the canvas", severity="warning"))
    if len(metrics["unique"]) > palette_limit:
        warnings.append(
            QualityWarning(
                code="palette_exceeds",
                message=f"Sprite uses {len(metrics['unique'])} colors, limit is {palette_limit}",
                severity="warning",
            )
        )
    if metrics["touches_edge"]:
        warnings.append(QualityWarning(code="touches_edges", message="Opaque pixels touch the canvas edge", severity="warning"))
    if source_size and source_size >= expected_size * 4:
        warnings.append(
            QualityWarning(
                code="downscaled_source",
                message=f"Source was {source_size}px then reduced to {expected_size}px with pixel-aware downsample.",
                severity="warning",
            )
        )
    if width != height:
        warnings.append(QualityWarning(code="inconsistent_canvas", message="Canvas is not square", severity="warning"))

    mismatch = _palette_mismatch(metrics["unique"], palette)
    if palette and mismatch > 28:
        warnings.append(
            QualityWarning(
                code="palette_mismatch",
                message=f"Colors drift from the accepted character palette (mean distance {mismatch:.0f})",
                severity="warning",
            )
        )

    ref_metrics = _metrics(reference) if reference is not None else None
    if ref_metrics and ref_metrics["opaque"]:
        dx = abs(metrics["center_x"] - ref_metrics["center_x"])
        dy = abs(metrics["center_y"] - ref_metrics["center_y"])
        if dx > 0.12 or dy > 0.14:
            warnings.append(
                QualityWarning(
                    code="center_of_mass_shift",
                    message="Center of mass shifted too far from the accepted base",
                    severity="warning",
                )
            )
        if ref_metrics["height_ratio"] and abs(metrics["height_ratio"] - ref_metrics["height_ratio"]) > 0.16:
            warnings.append(
                QualityWarning(
                    code="height_inconsistent",
                    message="Character height is inconsistent with the accepted base",
                    severity="warning",
                )
            )
        if ref_metrics["width_ratio"] and abs(metrics["width_ratio"] - ref_metrics["width_ratio"]) > 0.18:
            warnings.append(
                QualityWarning(
                    code="silhouette_width_inconsistent",
                    message="Silhouette width is inconsistent with the accepted base",
                    severity="warning",
                )
            )
        if metrics["blobs"] >= max(4, ref_metrics["blobs"] + 2):
            warnings.append(
                QualityWarning(
                    code="probable_extra_limbs",
                    message="Too many separate opaque blobs; possible extra limbs or debris",
                    severity="warning",
                )
            )
    elif metrics["blobs"] >= 5:
        warnings.append(
            QualityWarning(
                code="probable_extra_limbs",
                message="Too many separate opaque blobs; possible extra limbs or debris",
                severity="warning",
            )
        )

    facing = _direction_warning(direction, metrics)
    if facing:
        warnings.append(facing)

    score = 100
    for warning in warnings:
        score -= 18 if warning.severity == "error" else 8
    score = max(0, min(100, score))

    return QualityValidation(
        ok=not any(w.severity == "error" for w in warnings),
        score=score,
        warnings=warnings,
        futureChecks=[],
        occupancy=round(occupancy, 4),
        heightRatio=round(metrics["height_ratio"], 4),
        widthRatio=round(metrics["width_ratio"], 4),
        centerX=round(metrics["center_x"], 4),
        centerY=round(metrics["center_y"], 4),
    )
