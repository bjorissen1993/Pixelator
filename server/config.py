import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
load_dotenv(SERVER_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
PIXELATOR_PROVIDER = os.getenv("PIXELATOR_PROVIDER", "auto").strip().lower()
MODEL_ID = os.getenv("MODEL_ID", "stabilityai/sdxl-turbo")
PIXEL_MODEL_ID = os.getenv("PIXEL_MODEL_ID", "").strip()
LORA_PATH = os.getenv("LORA_PATH", "").strip()
LORA_STRENGTH = float(os.getenv("LORA_STRENGTH", "0.8"))
CONTROLNET_MODEL = os.getenv("CONTROLNET_MODEL", "").strip()
IP_ADAPTER_MODEL = os.getenv("IP_ADAPTER_MODEL", "").strip()
PIXELLAB_API_KEY = os.getenv("PIXELLAB_API_KEY", "").strip()
PIXELLAB_API_BASE = os.getenv("PIXELLAB_API_BASE", "https://api.pixellab.ai/v2").rstrip("/")
DEVICE = os.getenv("DEVICE", "cuda")
DTYPE = os.getenv("DTYPE", "").strip().lower()
ENABLE_BG_REMOVAL = os.getenv("ENABLE_BG_REMOVAL", "true").lower() == "true"
INFERENCE_STEPS = int(os.getenv("INFERENCE_STEPS", "4"))
GUIDANCE_SCALE = float(os.getenv("GUIDANCE_SCALE", "0"))
CANDIDATE_COUNT = max(1, min(4, int(os.getenv("CANDIDATE_COUNT", "3"))))

_SIZE_PRESETS = {
    "native48": 48,
    "48": 48,
    "64": 64,
    "96": 96,
    "128": 128,
    "256": 256,
    "512": 512,
}


def _parse_size(raw: str, default: int) -> int:
    key = raw.strip().lower()
    if key in _SIZE_PRESETS:
        return _SIZE_PRESETS[key]
    try:
        return max(32, min(512, int(raw)))
    except ValueError:
        return default


WORKING_SIZE = _parse_size(os.getenv("WORKING_SIZE", os.getenv("GENERATION_PRESET", "128")), 128)
# Backward compatible alias; working size is the generation canvas, not assumed 512.
GENERATION_SIZE = _parse_size(os.getenv("GENERATION_SIZE", str(WORKING_SIZE)), WORKING_SIZE)

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]
