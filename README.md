# Chimera Pixel Generator / Pixelator

Local-first AI pixel character workspace. Character System v2.1 is a visual sprite studio: generate a base, accept it as an identity reference, then generate 8 directions as one job.

The default local backend is still Diffusers (SDXL Turbo unless you change it). Turbo generates at 512px, then Pixelator pixelizes that raster. **That cannot match PixelLab.** For PixelLab quality, set `PIXELLAB_API_KEY` from [your PixelLab account](https://pixellab.ai/account). Pixelator then calls PixelLab's `create-character-v3` API and keeps the native sprite. Credits are billed by PixelLab. This is not a clone of their product.

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
PIXELLAB_API_KEY=
DEVICE=cuda
ENABLE_BG_REMOVAL=true
GENERATION_SIZE=512
INFERENCE_STEPS=4
GUIDANCE_SCALE=0
```

`PIXELLAB_API_KEY` switches the studio to PixelLab's official API (`create-character-v3`, 8 directions, animation). Without it, local Turbo stays the backend and will not look like PixelLab. `GENERATION_SIZE` is only for the local Diffusers raster. `PIXEL_MODEL_ID` selects a local pixel-oriented checkpoint.

## Workflow
1. Generate Base → review Pending Sprite → Accept as Base. Re-pixelize re-runs cleanup on the last source without a new model pass.
2. Accepted Base is the img2img identity reference (source image, not just prompt text)
3. Generate 8 Directions as one operation (PixelLab returns them as a set; local Diffusers is sequential)
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
