import os
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVER_DIR.parent
load_dotenv(SERVER_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT_DIR / "data"))
MODEL_ID = os.getenv("MODEL_ID", "stabilityai/sdxl-turbo")
PIXEL_MODEL_ID = os.getenv("PIXEL_MODEL_ID", "").strip()
DEVICE = os.getenv("DEVICE", "cuda")
ENABLE_BG_REMOVAL = os.getenv("ENABLE_BG_REMOVAL", "true").lower() == "true"
GENERATION_SIZE = int(os.getenv("GENERATION_SIZE", "256"))
INFERENCE_STEPS = int(os.getenv("INFERENCE_STEPS", "4"))
GUIDANCE_SCALE = float(os.getenv("GUIDANCE_SCALE", "0"))
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
]
