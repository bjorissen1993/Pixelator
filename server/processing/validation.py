from PIL import Image

from models.character import QualityValidation, QualityWarning


def validate_sprite(
    image: Image.Image, expected_size: int, palette_limit: int, source_size: int | None = None
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

    alpha = image.getchannel("A")
    opaque = 0
    unique: set[tuple[int, int, int]] = set()
    touches_edge = False
    pixels = image.convert("RGBA").load()
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            opaque += 1
            unique.add((r, g, b))
            if x == 0 or y == 0 or x == width - 1 or y == height - 1:
                touches_edge = True

    total = max(1, width * height)
    if opaque == 0:
        warnings.append(QualityWarning(code="empty_sprite", message="Sprite has no opaque pixels", severity="error"))
    elif opaque / total < 0.04:
        warnings.append(
            QualityWarning(code="too_much_transparency", message="Sprite is almost empty", severity="warning")
        )
    if len(unique) > palette_limit:
        warnings.append(
            QualityWarning(
                code="palette_exceeds",
                message=f"Sprite uses {len(unique)} colors, limit is {palette_limit}",
                severity="warning",
            )
        )
    if touches_edge:
        warnings.append(
            QualityWarning(code="touches_edges", message="Opaque pixels touch the canvas edge", severity="warning")
        )
    if source_size and source_size >= expected_size * 3:
        warnings.append(
            QualityWarning(
                code="downscaled_source",
                message=f"Source was {source_size}px then cleaned to {expected_size}px. Prefer a native/smaller pixel model.",
                severity="warning",
            )
        )
    if width != height:
        warnings.append(
            QualityWarning(code="inconsistent_canvas", message="Canvas is not square", severity="warning")
        )

    return QualityValidation(
        ok=not any(w.severity == "error" for w in warnings),
        warnings=warnings,
        futureChecks=[
            "incorrect_body_type",
            "forbidden_legs_for_spirit",
            "broken_silhouette",
            "palette_mismatch",
        ],
    )
