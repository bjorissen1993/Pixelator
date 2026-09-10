# Chimera Pixel Generator / Pixelator

Local-first AI pixel character workspace. Character System v2.1 is a visual sprite studio: generate a base, accept it as an identity reference, then generate 8 directions as one job.

Generation Engine v2 is a provider abstraction. **SDXL-Turbo is fallback only** and is not a pixel-art checkpoint. For professional sprites, set a pixel-art `MODEL_ID` / `LORA_PATH`, or `PIXELLAB_API_KEY` from [your PixelLab account](https://pixellab.ai/account).

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
PIXELATOR_PROVIDER=auto
PIXELATOR_MODEL_ID=
PIXELATOR_LORA=
PIXELATOR_DEVICE=cuda
PIXELATOR_DTYPE=
PIXELATOR_ALLOW_TURBO_FALLBACK=false
WORKING_SIZE=48
INFERENCE_STEPS=12
GUIDANCE_SCALE=3.5
CANDIDATE_COUNT=2
PIXELLAB_API_KEY=
ENABLE_BG_REMOVAL=false
```

`PIXELATOR_PROVIDER` is `auto`, `pixellab`, `local`, or `fallback`. `auto` uses PixelLab when `PIXELLAB_API_KEY` is set, otherwise a local pixel checkpoint from `PIXELATOR_MODEL_ID`. SDXL-Turbo is not the default engine. Sprite sizes are 32, 48, 64, 96, and 128. Post-processing only cleans palette, alpha, and nearest-neighbor fit — it does not invent pixel-art style. The optional Turbo fallback still renders at 512 internally because that checkpoint is photographic.

## Workflow
1. Generate creates one canonical South idle sprite. Accept it as Base to lock identity and the accepted palette.
2. Generate All Directions rotates from that reference image (stable identity from South, or incremental 45° steps).
3. States and animations start from accepted sprites, not from text alone.
4. Reject keeps the record; Remove deletes the asset. This memory is not model training.
5. Export sprite sheets, metadata, or an accepted-only training dataset (no training is performed)

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
