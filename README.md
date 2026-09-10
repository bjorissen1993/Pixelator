# Chimera Pixel Generator / Pixelator

Local-first AI pixel character workspace. Character System v2 keeps a persistent profile, layered prompts, 8-direction states, emotion-aware pose language, head/body metadata, Phaser exports, and a swappable generation provider.

The current image backend is still local Diffusers (default: SDXL Turbo). It generates a 512 image, then Pixelator's pipeline converts it into a sprite. That is **not** PixelLab-quality native pixel art yet. The architecture is ready for a pixel-art checkpoint, LoRA, or reference-conditioned model.

## Requirements
- Node.js 20+
- Python 3.11+
- A CUDA GPU is strongly recommended for generation

## 1. Backend
```bash
cd server
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload --port 8000
```

## 2. Frontend
```bash
cd client
npm install
npm run dev
```

Open http://localhost:5173

The Vite dev server proxies `/api`, `/health`, and `/data` to the FastAPI process.

## Environment
```
MODEL_ID=stabilityai/sdxl-turbo
DEVICE=cuda
ENABLE_BG_REMOVAL=true
```

Optional: `DATA_DIR` overrides the JSON/asset store. Default is `../data` next to `server/`.

Swap `MODEL_ID` for a pixel-art checkpoint later. Do not change character/prompt/export code for that.

## Data
Characters, states, prompts, seeds and generated files live under:

```
data/characters/<slug>/
  character.json
  base/
  states/<stateId>/<direction>/
  head/
  exports/
```

Berwynn is seeded automatically if the store is empty.
