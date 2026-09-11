"""Isolated candidate: SD 1.5 + VaroDZAKY/Varo_pixel_Art LoRA.

Not Pixelator's production South-base engine. Manual inspection required.
"""

MODEL_ID = "stable-diffusion-v1-5/stable-diffusion-v1-5"
LORA = "VaroDZAKY/Varo_pixel_Art"
LORA_ADAPTER_NAME = "varo"
LORA_STRENGTHS = (0.8, 1.0)
OUTPUT_NAME = "varodzak_pixel_art"
REQUIRE_CUDA = True
ALLOW_SDXL = False
WIDTH = 512
HEIGHT = 512
STEPS = 30
GUIDANCE = 7.5
SEEDS = (12345, 22345, 32345, 42345)

PROMPT = (
    "pixelart_style, single full body pixel art game character sprite, "
    "one elderly male former village chief spirit, front facing, south facing, centered, "
    "full body visible, short messy grey hair, thick rough grey beard, weathered tired face, "
    "stern but kind expression, broad shoulders, slightly hunched posture, worn dark village tunic, "
    "faded chief mantle, practical medieval village clothing, no armor, spectral ghost lower body, "
    "pale blue spirit tail instead of legs, one character only, plain simple background, "
    "retro dark fantasy RPG sprite, sharp pixel edges, flat colors, no gradient"
)

NEGATIVE_PROMPT = (
    "sprite sheet, spritesheet, collage, grid, contact sheet, multiple views, multiple poses, "
    "multiple characters, duplicate character, portrait, bust, close-up, upper body only, cropped, "
    "cut off, armor, plate armor, legs, boots, weapon, realistic, photorealistic, 3d render, "
    "painterly, smooth shading, gradient, blurry, anti-aliased, text, watermark, UI frame"
)
