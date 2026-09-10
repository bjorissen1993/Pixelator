import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
load_dotenv(SERVER_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))

PIXELATOR_PROVIDER = os.getenv("PIXELATOR_PROVIDER", "auto").strip().lower()
PIXELATOR_MODEL_ID = (
    os.getenv("PIXELATOR_MODEL_ID") or os.getenv("PIXEL_MODEL_ID") or os.getenv("MODEL_ID") or ""
).strip()
PIXELATOR_LORA = (os.getenv("PIXELATOR_LORA") or os.getenv("LORA_PATH") or "").strip()
PIXELATOR_DEVICE = (os.getenv("PIXELATOR_DEVICE") or os.getenv("DEVICE") or "cuda").strip()
PIXELATOR_DTYPE = (os.getenv("PIXELATOR_DTYPE") or os.getenv("DTYPE") or "").strip().lower()
PIXELATOR_ALLOW_TURBO_FALLBACK = os.getenv("PIXELATOR_ALLOW_TURBO_FALLBACK", "false").lower() == "true"

# Backward-compatible aliases. None of these default to SDXL-Turbo.
MODEL_ID = PIXELATOR_MODEL_ID
PIXEL_MODEL_ID = os.getenv("PIXEL_MODEL_ID", "").strip()
LORA_PATH = PIXELATOR_LORA
LORA_STRENGTH = float(os.getenv("LORA_STRENGTH", "0.8"))
CONTROLNET_MODEL = os.getenv("CONTROLNET_MODEL", "").strip()
IP_ADAPTER_MODEL = os.getenv("IP_ADAPTER_MODEL", "").strip()
PIXELLAB_API_KEY = os.getenv("PIXELLAB_API_KEY", "").strip()
PIXELLAB_API_BASE = os.getenv("PIXELLAB_API_BASE", "https://api.pixellab.ai/v2").rstrip("/")
DEVICE = PIXELATOR_DEVICE
DTYPE = PIXELATOR_DTYPE
ENABLE_BG_REMOVAL = os.getenv("ENABLE_BG_REMOVAL", "false").lower() == "true"
INFERENCE_STEPS = int(os.getenv("INFERENCE_STEPS", "12"))
GUIDANCE_SCALE = float(os.getenv("GUIDANCE_SCALE", "3.5"))
CANDIDATE_COUNT = max(1, min(4, int(os.getenv("CANDIDATE_COUNT", "2"))))

SPRITE_SIZES = (32, 48, 64, 96, 128)
TURBO_MODEL_ID = "stabilityai/sdxl-turbo"


def is_turbo_model(model_id: str) -> bool:
    return "turbo" in (model_id or "").lower()


def clamp_sprite_size(value: int, default: int = 48) -> int:
    if value in SPRITE_SIZES:
        return value
    return min(SPRITE_SIZES, key=lambda size: abs(size - (value or default)))


try:
    WORKING_SIZE = clamp_sprite_size(int(os.getenv("WORKING_SIZE", "48") or 48), 48)
except ValueError:
    WORKING_SIZE = 48
GENERATION_SIZE = WORKING_SIZE

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]
