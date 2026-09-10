from PIL import Image

import config
from models.common import ProviderInfo
from models.generation import PromptLayers
from providers.base import GeneratedImage, GenerationProvider


class DiffusersProvider(GenerationProvider):
    """Local Diffusers backend. Output is still a large raster that the pixel pipeline reduces.

    Swap MODEL_ID for a pixel-art checkpoint or attach a LoRA later without changing callers.
    This provider does not emit native 48x48 pixel art on its own.
    """

    def __init__(self):
        self.torch = None
        self.device = config.DEVICE
        self.txt2img = None
        self.img2img = None

    def _ensure_loaded(self) -> None:
        if self.txt2img is not None:
            return
        try:
            import torch
            from diffusers import AutoPipelineForImage2Image, AutoPipelineForText2Image
        except Exception as exc:
            raise RuntimeError(f"Could not import Diffusers backend: {exc}") from exc

        self.torch = torch
        requested = config.DEVICE
        self.device = requested if requested == "cpu" or torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.txt2img = AutoPipelineForText2Image.from_pretrained(config.MODEL_ID, torch_dtype=dtype)
        self.txt2img = self.txt2img.to(self.device)
        try:
            self.img2img = AutoPipelineForImage2Image.from_pretrained(config.MODEL_ID, torch_dtype=dtype)
            self.img2img = self.img2img.to(self.device)
        except Exception:
            self.img2img = None

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="diffusers-local",
            name="Local Diffusers",
            modelId=config.MODEL_ID,
            supportsReference=True,
            nativePixelOutput=False,
            notes=(
                "Generates at 512x512 then the Pixelator pipeline converts to a sprite. "
                "Identity consistency is prompt + optional img2img reference, not a trained pixel-art lock. "
                "Change MODEL_ID (and later LoRAs) without rewriting the character system."
            ),
        )

    def _generator(self, seed: int | None):
        self._ensure_loaded()
        if seed is None:
            return None
        return self.torch.Generator(device=self.device).manual_seed(seed)

    def _txt(self, prompt: PromptLayers, seed: int | None) -> GeneratedImage:
        self._ensure_loaded()
        result = self.txt2img(
            prompt=prompt.final,
            width=512,
            height=512,
            num_inference_steps=4,
            guidance_scale=0.0,
            generator=self._generator(seed),
        ).images[0]
        return GeneratedImage(result.convert("RGB"), seed, prompt)

    def _img(self, prompt: PromptLayers, reference: Image.Image, seed: int | None, strength: float) -> GeneratedImage:
        self._ensure_loaded()
        if self.img2img is None:
            return self._txt(prompt, seed)
        source = reference.convert("RGB").resize((512, 512), Image.Resampling.NEAREST)
        result = self.img2img(
            prompt=prompt.final,
            image=source,
            strength=strength,
            num_inference_steps=4,
            guidance_scale=0.0,
            generator=self._generator(seed),
        ).images[0]
        return GeneratedImage(result.convert("RGB"), seed, prompt)

    def generate_base_character(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._txt(prompt, seed)

    def generate_state(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._txt(prompt, seed)

    def generate_direction(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._txt(prompt, seed)

    def generate_animation_frames(
        self, prompt: PromptLayers, frame_count: int, seed: int | None = None
    ) -> list[GeneratedImage]:
        return [self._txt(prompt, None if seed is None else seed + index) for index in range(frame_count)]

    def generate_head_variant(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._txt(prompt, seed)

    def generate_from_reference(
        self,
        prompt: PromptLayers,
        reference: Image.Image,
        seed: int | None = None,
        strength: float = 0.42,
    ) -> GeneratedImage:
        return self._img(prompt, reference, seed, strength)
