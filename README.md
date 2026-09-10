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
MODEL_ID=stabilityai/sdxl-turbo
PIXEL_MODEL_ID=
LORA_PATH=
LORA_STRENGTH=0.8
CONTROLNET_MODEL=
IP_ADAPTER_MODEL=
DEVICE=cuda
DTYPE=
WORKING_SIZE=128
GENERATION_SIZE=128
INFERENCE_STEPS=4
GUIDANCE_SCALE=0
CANDIDATE_COUNT=3
PIXELLAB_API_KEY=
ENABLE_BG_REMOVAL=true
```

`PIXELATOR_PROVIDER` is `auto`, `pixellab`, `diffusers`, or `pixel-diffusers`. `auto` uses PixelLab when `PIXELLAB_API_KEY` is set, otherwise the local Diffusers model. `WORKING_SIZE` presets: `native48`, `64`, `96`, `128`, `256`, `512`. Local rasters are reduced to the 48×48 sprite with nearest/block-mode, never Lanczos. Turbo fallback still renders at 512 internally because that checkpoint is not native pixel-art.

## Workflow
1. Generate Base → review Pending Sprite → Accept as Base (soft palette lock). Re-pixelize re-runs cleanup on the last source without a new model pass.
2. Accepted Base is a real img2img / neighbor-graph identity reference
3. Generate 8 Directions sequentially (S → SW → W → NW → N → NE → E → SE). Each facing produces 2–4 candidates.
4. Accept one candidate. Accepted directions are not overwritten.
5. Reject with a reason; the next regenerate uses that feedback in the prompt/strength. This is not model training.
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
