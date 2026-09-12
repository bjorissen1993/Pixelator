"""Isolated candidate: PublicPrompts/All-In-One-Pixel-Model.

SD1.5 DreamBooth checkpoint. Trigger is pixelsprite (single sprites), not 16bitscene.
Not Pixelator's production South-base engine. Manual inspection required.
"""

MODEL_ID = "PublicPrompts/All-In-One-Pixel-Model"
LORA = ""
OUTPUT_NAME = "publicprompts_all_in_one_pixel_run2"
OUTPUT_FILENAME_TEMPLATE = "publicprompts_seed{seed}.png"
REQUIRE_CUDA = True
ALLOW_SDXL = False
WIDTH = 512
HEIGHT = 512
STEPS = 30
GUIDANCE = 7.5
SEEDS = (51721, 68403, 79117, 93641)

PROMPT = (
    "pixelsprite, full body elderly male spirit, front facing, grey hair, thick grey beard, "
    "stern kind face, worn dark village tunic, faded mantle, spectral blue ghost tail instead of legs, "
    "no armor, centered, single character, RPG sprite"
)

NEGATIVE_PROMPT = (
    "portrait, bust, close-up, cropped, armor, helmet, weapon, legs, boots, "
    "multiple characters, spritesheet, collage, realistic, 3d, painterly, blurry, text"
)
