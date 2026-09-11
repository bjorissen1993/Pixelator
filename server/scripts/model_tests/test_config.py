"""Isolated single-sprite model test config.

Edit MODEL_ID (or pass --model) before a run. Nothing here is wired into Pixelator.
SDXL and rejected sheet-biased checkpoints must not be used as the default South base.
"""

from __future__ import annotations

# Leave empty and pass --model, or set a candidate Hub id here.
MODEL_ID = ""

# Folder name under server/test_outputs/. Empty -> derived from MODEL_ID.
OUTPUT_NAME = ""

WIDTH = 512
HEIGHT = 512
STEPS = 30
GUIDANCE = 7.5
SEEDS = (12345, 22345, 32345, 42345)

# Short Berwynn prompt kept under SD1.5 CLIP's 77-token window.
# Configs should prepend their own trigger; do not reuse pixelart_style (Varo).
PROMPT = (
    "full body elderly male spirit, front facing, grey hair, thick grey beard, "
    "stern kind face, worn dark village tunic, faded mantle, spectral blue ghost tail instead of legs, "
    "no armor, centered, single character, RPG sprite"
)
PROMPTS = {"A": PROMPT}

NEGATIVE_PROMPT = (
    "portrait, bust, close-up, cropped, armor, helmet, weapon, legs, boots, "
    "multiple characters, spritesheet, collage, realistic, 3d, painterly, blurry, text"
)

# Isolated South-base tests are SD1.5-class unless this is explicitly enabled.
ALLOW_SDXL = False
ALLOW_LORA = False
ALLOW_IP_ADAPTER = False
ALLOW_CONTROLNET = False

# Do not use these as Pixelator's canonical South-base generator.
REJECTED_SOUTH_BASE_MODELS = {
    "Onodofthenorth/SD_PixelArt_SpriteSheet_Generator": {
        "status": "rejected",
        "role": "canonical South-base character generator",
        "date": "2026-09-11",
        "keep_outputs": "server/test_outputs/onodof_single_sprite/",
        "reasons": [
            "Consistent 4-across / multi-sprite compositions",
            "Spritesheet bias even with negative prompts against sheets and collages",
            "Weak obedience to a single-character South-base request",
            "Weak Berwynn-specific adherence (identity and single-figure framing)",
        ],
        "notes": (
            "Pixel-art quality was better than the legacy SDXL-Turbo / SDXL-base downscale path, "
            "but the checkpoint still behaves as a sprite-sheet generator. Keep the isolated "
            "outputs for comparison. Do not integrate as the default South-base engine."
        ),
    },
    "VaroDZAKY/Varo_pixel_Art": {
        "status": "rejected",
        "role": "canonical South-base character generator",
        "date": "2026-09-11",
        "base_model": "stable-diffusion-v1-5/stable-diffusion-v1-5",
        "keep_outputs": [
            "server/test_outputs/varodzak_pixel_art/",
            "server/test_outputs/varodzak_pixel_art_short_prompt/",
        ],
        "reasons": [
            "Single-character output works and pixel-art styling is acceptable",
            "Character adherence is poor even when the full short prompt fits in CLIP",
            "Berwynn's defining silhouette is not followed: spectral ghost tail is ignored and legs remain",
            "Clothing identity and old village-chief appearance are inconsistent",
            "Results vary too heavily between seeds",
        ],
        "notes": (
            "Do not integrate this LoRA into production and do not reuse it as a fallback. "
            "Keep the isolated outputs for comparison."
        ),
    },
}
