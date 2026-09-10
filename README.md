# Chimera Pixel Generator

Local-first AI pixel character generator for Chimera. The app generates a character image with a local Diffusers model, removes the background, reduces it to a true sprite resolution, quantizes the palette, and exports both the real sprite and a nearest-neighbour preview.

## What you get
- React + Vite frontend
- FastAPI backend
- Local image generation through Hugging Face Diffusers
- Optional local background removal with `rembg`
- 32/48/56/64px sprite presets
- High top-down / low top-down / front camera prompts
- Chimera spirit preset: no legs, spectral tail, mist fade
- Palette reduction + nearest-neighbour preview
- PNG export

## Requirements
- Node.js 20+
- Python 3.11+
- A CUDA-capable GPU is strongly recommended for local generation

## 1. Backend
```bash
cd server
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload --port 8000
```

The default model is configurable through `MODEL_ID`. A local Diffusers-compatible text-to-image model works best. The default is only a starting point; swap it for a pixel-art-focused model later.

## 2. Frontend
```bash
cd client
npm install
npm run dev
```

Open http://localhost:5173

## Notes
Generation is local, so there are no per-image credits from this app itself. Model downloads can be several GB and GPU memory requirements depend on the model. CPU generation is technically possible but usually too slow for comfortable iteration.

## Best Chimera workflow
1. Generate at 512x512 internally.
2. Remove background.
3. Fit character onto 48x48 transparent canvas.
4. Quantize to 32-48 colors.
5. Export sprite at true 48x48.
6. Preview at 384x384 using nearest-neighbour scaling.

For consistent characters, keep the same camera, sprite size, palette size and prompt base across NPCs.
