"""Isolated candidate: SD 1.5 + VaroDZAKY/Varo_pixel_Art LoRA.

Not Pixelator's production South-base engine. Manual inspection required.
"""

MODEL_ID = "stable-diffusion-v1-5/stable-diffusion-v1-5"
LORA = "VaroDZAKY/Varo_pixel_Art"
LORA_ADAPTER_NAME = "varo"
LORA_LOADER = "peft_unet"
LORA_STRENGTHS = (0.8, 1.0)
OUTPUT_NAME = "varodzak_pixel_art_short_prompt"
REQUIRE_CUDA = True
ALLOW_SDXL = False
WIDTH = 512
HEIGHT = 512
STEPS = 30
GUIDANCE = 7.5
SEEDS = (12345, 22345, 32345, 42345)

PROMPT = (
    "pixelart_style, full body elderly male spirit, front facing, grey hair, thick grey beard, "
    "stern kind face, worn dark village tunic, faded mantle, spectral blue ghost tail instead of legs, "
    "no armor, centered, single character, RPG sprite"
)

NEGATIVE_PROMPT = (
    "portrait, bust, close-up, cropped, armor, helmet, weapon, legs, boots, "
    "multiple characters, spritesheet, collage, realistic, 3d, painterly, blurry, text"
)
