PIXELATOR_STYLE = (
    "true 2D pixel-art game sprite, deliberate square pixel clusters, limited indexed color palette, "
    "crisp hard pixel edges, no anti-aliasing, no smooth gradients, no photorealism, no 3D render, "
    "no PBR materials, no painterly blending, single character centered, game-ready sprite, "
    "plain or transparent background, no text, no scenery, no extra characters"
)

CAMERA_CLAUSES = {
    "high-top-down": "high top-down RPG camera, three-quarter overhead view",
    "low-top-down": "low top-down RPG camera, slight overhead view",
    "front": "front-facing RPG sprite view",
}

DETAIL_CLAUSES = {
    "simple": "simple readable forms, minimal micro-detail",
    "balanced": "balanced pixel detail, readable silhouette",
    "high": "highly detailed pixel clusters while preserving a readable silhouette",
}

OUTLINE_CLAUSES = {
    "none": "no external outline",
    "soft": "subtle selective pixel outline",
    "dark": "clear dark pixel outline",
}


def global_style(camera: str, detail: str, outline: str, sprite_size: int) -> str:
    return ", ".join(
        [
            PIXELATOR_STYLE,
            CAMERA_CLAUSES.get(camera, CAMERA_CLAUSES["high-top-down"]),
            DETAIL_CLAUSES.get(detail, DETAIL_CLAUSES["balanced"]),
            OUTLINE_CLAUSES.get(outline, OUTLINE_CLAUSES["soft"]),
            f"intended final sprite size {sprite_size}x{sprite_size} pixels",
        ]
    )
