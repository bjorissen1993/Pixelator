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

# Two prompt variants x four seeds = 8 images. No spritesheet trigger words.
PROMPTS = {
    "A": (
        "single full body pixel art sprite, one elderly male village chief spirit, "
        "front facing, south facing, centered, one character only, full body visible, "
        "worn dark tunic, faded mantle, grey beard, spectral tail instead of legs, "
        "plain background, game sprite"
    ),
    "B": (
        "single character pixel art game sprite, full body, one elderly male village chief spirit, "
        "south facing, front view, centered in frame, entire silhouette visible, "
        "short messy grey hair, thick rough grey beard, worn dark village tunic, faded chief mantle, "
        "spectral ghost tail instead of legs, no armor, plain simple background"
    ),
}

NEGATIVE_PROMPT = (
    "sprite sheet, spritesheet, collage, grid, contact sheet, multiple views, "
    "multiple poses, multiple characters, duplicate character, portrait, bust, "
    "close-up, cropped, UI frame, border, text, watermark, realistic, painterly, "
    "3d render, armor, boots, weapon, SDXL, photographic"
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
}
