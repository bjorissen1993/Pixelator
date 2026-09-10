# Chimera Pixel Generator / Pixelator

Local-first AI pixel character workspace. Character System v2.1 is a visual sprite studio: generate a base, accept it as an identity reference, then generate 8 directions as one job.

The default image backend is still local Diffusers (SDXL Turbo unless you change it). It generates at the provider's preferred size (default 256), then Pixelator runs **cleanup** (background, fit, palette, outline). That is **not** PixelLab-quality native pixel art. Set `PIXEL_MODEL_ID` to a pixel-art checkpoint to switch without changing the workflow.

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

Open the printed localhost URL. Vite proxies `/api`, `/health`, and `/data` to FastAPI.

## Environment
```
MODEL_ID=stabilityai/sdxl-turbo
PIXEL_MODEL_ID=
DEVICE=cuda
ENABLE_BG_REMOVAL=true
GENERATION_SIZE=256
INFERENCE_STEPS=4
GUIDANCE_SCALE=0
```

`GENERATION_SIZE` is the provider's internal raster size. Do not set this to 512 unless the model requires it. `PIXEL_MODEL_ID` selects a pixel-oriented Diffusers checkpoint and marks `nativePixelOutput` honestly only for that path.

## Workflow
1. Generate Base → review Pending Sprite → Accept as Base
2. Accepted Base is the img2img identity reference (source image, not just prompt text)
3. Generate 8 Directions as one operation (sequential internally)
4. Accept / reject / lock / regenerate individual facings
5. Add states and animations from accepted identity
6. Export sprite sheets, metadata, or an accepted-only training dataset (no training is performed)

## Data
```
data/characters/<slug>/
  character.json
  base/
  states/<stateId>/<direction>/
  exports/
data/project/
  styles.json
  memory.json
```
