PIXELATOR_STYLE = (
    "true 2D pixel-art game sprite, chunky square pixel clusters 2 to 4 pixels wide, "
    "limited indexed color palette, flat color fills, crisp hard pixel edges, "
    "no anti-aliasing, no dithering, no noisy speckles, no photorealism, no 3D render, "
    "no PBR materials, no painterly blending, single character centered, game-ready sprite, "
    "plain or transparent background, no text, no scenery, no extra characters"
)

CAMERA_CLAUSES = {
    "high-top-down": "high top-down RPG camera, three-quarter overhead view",
    "low-top-down": "low top-down RPG camera, slight overhead view",
    "side": "side-view RPG sprite, orthographic side camera",
    "front": "front-facing RPG sprite view",
}

DETAIL_CLAUSES = {
    "low": "low pixel detail, large readable clusters, simple blocky forms",
    "medium": "medium pixel detail, readable silhouette, large color clusters, few colors per shape",
    "high": "higher pixel detail while keeping chunky clusters and a readable silhouette",
    "simple": "low pixel detail, large readable clusters, simple blocky forms",
    "balanced": "medium pixel detail, readable silhouette, large color clusters, few colors per shape",
}

OUTLINE_CLAUSES = {
    "black": "clear black pixel outline",
    "colored": "colored outline using darkened local colors, not a flat black stroke",
    "selective": "subtle selective pixel outline, outline only where needed for readability",
    "lineless": "lineless pixel art, no external outline",
    "none": "lineless pixel art, no external outline",
    "soft": "subtle selective pixel outline",
    "dark": "clear black pixel outline",
}

SHADING_CLAUSES = {
    "none": "flat unshaded color fills, no lighting",
    "basic": "basic two-tone pixel shading",
    "medium": "medium pixel shading with a few light bands",
    "detailed": "detailed clustered pixel shading, still hard-edged, no gradients",
}

BODY_TEMPLATE_CLAUSES = {
    "bipedal": "bipedal humanoid body template",
    "semi-chibi-bipedal": "semi-chibi bipedal proportions, larger head, shorter legs",
    "quadrupedal": "quadrupedal body template",
    "custom": "custom body template matching the described silhouette",
}


def global_style(camera: str, detail: str, outline: str, shading: str, body_template: str, sprite_size: int) -> str:
    return ", ".join(
        [
            PIXELATOR_STYLE,
            CAMERA_CLAUSES.get(camera, CAMERA_CLAUSES["high-top-down"]),
            DETAIL_CLAUSES.get(detail, DETAIL_CLAUSES["medium"]),
            OUTLINE_CLAUSES.get(outline, OUTLINE_CLAUSES["selective"]),
            SHADING_CLAUSES.get(shading, SHADING_CLAUSES["basic"]),
            BODY_TEMPLATE_CLAUSES.get(body_template, BODY_TEMPLATE_CLAUSES["custom"]),
            f"target sprite canvas {sprite_size}x{sprite_size} pixels",
        ]
    )
