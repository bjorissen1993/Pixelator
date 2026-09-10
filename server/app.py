import base64
import io
import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image

load_dotenv()

app = FastAPI(title="Chimera Pixel Generator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Camera = Literal["high-top-down", "low-top-down", "front"]
Detail = Literal["simple", "balanced", "high"]
Outline = Literal["none", "soft", "dark"]


class GenerateRequest(BaseModel):
    name: str = "Berwynn"
    concept: str = Field(default="elderly former village chief spirit")
    appearance: str = Field(default="short messy grey hair, thick rough grey beard, tired stern but kind face, broad shoulders")
    clothing: str = Field(default="worn dark tunic, faded chief mantle, simple cloth belt, no armor")
    spirit: bool = True
    camera: Camera = "high-top-down"
    sprite_size: int = Field(default=48, ge=16, le=128)
    palette_colors: int = Field(default=40, ge=8, le=128)
    detail: Detail = "high"
    outline: Outline = "soft"
    seed: int | None = None


class GenerateResponse(BaseModel):
    prompt: str
    sprite_data_url: str
    preview_data_url: str


def build_prompt(r: GenerateRequest) -> str:
    camera = {
        "high-top-down": "high top-down RPG camera, three-quarter overhead view",
        "low-top-down": "low top-down RPG camera, slight overhead view",
        "front": "front-facing RPG sprite view",
    }[r.camera]
    detail = {
        "simple": "simple readable forms, minimal micro-detail",
        "balanced": "balanced pixel detail, readable silhouette",
        "high": "highly detailed pixel clusters while preserving a readable silhouette",
    }[r.detail]
    outline = {
        "none": "no external outline",
        "soft": "subtle selective pixel outline",
        "dark": "clear dark pixel outline",
    }[r.outline]

    spirit = ""
    if r.spirit:
        spirit = (
            "legless ghost, absolutely no human legs or boots, lower body ends at the waist and transforms into a floating spectral tail, "
            "body fades into pale blue mist and ghost particles below the waist, translucent spectral lower body"
        )

    return (
        f"{r.name}, {r.concept}, full-body 2D pixel art game sprite, {camera}, {r.appearance}, {r.clothing}, "
        f"{spirit}, dark melancholic fantasy, muted earthy colors with subtle pale blue spirit light, {detail}, {outline}, "
        "true pixel art, deliberate square pixel clusters, limited color palette, crisp hard pixel edges, transparent or plain background, "
        "single character centered, game-ready sprite, no text, no scenery, no 3D render, no realistic painting, no smooth shading, "
        "no PBR materials, no anti-aliased edges"
    )


@lru_cache(maxsize=1)
def get_pipeline():
    try:
        import torch
        from diffusers import AutoPipelineForText2Image

        model_id = os.getenv("MODEL_ID", "stabilityai/sdxl-turbo")
        requested_device = os.getenv("DEVICE", "cuda")
        device = requested_device if requested_device == "cpu" or torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        pipe = AutoPipelineForText2Image.from_pretrained(model_id, torch_dtype=dtype)
        pipe = pipe.to(device)
        return pipe, torch, device
    except Exception as e:
        raise RuntimeError(f"Could not load image model: {e}") from e


def remove_background(image: Image.Image) -> Image.Image:
    if os.getenv("ENABLE_BG_REMOVAL", "true").lower() != "true":
        return image.convert("RGBA")
    try:
        from rembg import remove
        output = remove(image.convert("RGBA"))
        return output.convert("RGBA")
    except Exception:
        return image.convert("RGBA")


def crop_alpha(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    return image.crop(bbox) if bbox else image


def pixel_process(image: Image.Image, size: int, colors: int) -> tuple[Image.Image, Image.Image]:
    image = crop_alpha(image.convert("RGBA"))
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    max_w = max(1, int(size * 0.88))
    max_h = max(1, int(size * 0.94))
    ratio = min(max_w / image.width, max_h / image.height)
    target = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
    image = image.resize(target, Image.Resampling.LANCZOS)

    # Quantize RGB while preserving alpha.
    alpha = image.getchannel("A")
    rgb = image.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    image = Image.merge("RGBA", (*rgb.split(), alpha))

    x = (size - image.width) // 2
    y = size - image.height
    canvas.alpha_composite(image, (x, y))

    preview = canvas.resize((size * 8, size * 8), Image.Resampling.NEAREST)
    return canvas, preview


def to_data_url(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate", response_model=GenerateResponse)
def generate(r: GenerateRequest):
    prompt = build_prompt(r)
    try:
        pipe, torch, device = get_pipeline()
        generator = None
        if r.seed is not None:
            generator = torch.Generator(device=device).manual_seed(r.seed)

        # SDXL Turbo-style defaults. Other models can ignore/override these by editing here.
        result = pipe(
            prompt=prompt,
            width=512,
            height=512,
            num_inference_steps=4,
            guidance_scale=0.0,
            generator=generator,
        ).images[0]

        rgba = remove_background(result)
        sprite, preview = pixel_process(rgba, r.sprite_size, r.palette_colors)
        return GenerateResponse(
            prompt=prompt,
            sprite_data_url=to_data_url(sprite),
            preview_data_url=to_data_url(preview),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
