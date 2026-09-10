from PIL import Image

import config
from models.common import ProviderCapabilities, ProviderInfo
from models.generation import PromptLayers
from providers.base import GeneratedImage, GenerationProvider


class DiffusersProvider(GenerationProvider):
    """Local Diffusers backend.

    This is a generic raster generator. It is not a specialized pixel-art model unless
    MODEL_ID / PIXEL_MODEL_ID points at one. SDXL-Turbo wants ~512px; Pixelator then
    pixelizes that raster onto the sprite canvas. Native pixel checkpoints stay smaller.
    """

    def __init__(self, model_id: str | None = None, native: bool = False):
        self.torch = None
        self.device = config.DEVICE
        self.txt2img = None
        self.img2img = None
        self.model_id = model_id or config.PIXEL_MODEL_ID or config.MODEL_ID
        self.native = native or bool(config.PIXEL_MODEL_ID)
        self.size = max(32, min(512, config.GENERATION_SIZE if not native else min(config.GENERATION_SIZE, 128)))
        self.steps = config.INFERENCE_STEPS if not native else max(config.INFERENCE_STEPS, 8)
        self.guidance = config.GUIDANCE_SCALE if not native else max(config.GUIDANCE_SCALE, 1.0)

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
        self.txt2img = AutoPipelineForText2Image.from_pretrained(self.model_id, torch_dtype=dtype)
        self.txt2img = self.txt2img.to(self.device)
        try:
            self.img2img = AutoPipelineForImage2Image.from_pretrained(self.model_id, torch_dtype=dtype)
            self.img2img = self.img2img.to(self.device)
        except Exception:
            self.img2img = None

    @property
    def info(self) -> ProviderInfo:
        caps = ProviderCapabilities(
            supportsTextToImage=True,
            supportsReferenceImage=True,
            supportsImageToImage=True,
            supportsDirectionGeneration=True,
            supportsBatchDirections=True,
            supportsTargetPalette=False,
            supportsInitImage=True,
            supportsInpainting=False,
            supportsAnimation=True,
            supportsSkeletonGuidance=False,
            supportsNegativePrompt=self.guidance > 0,
            nativePixelOutput=self.native,
            preferredSizes=[32, 48, 64, 96, 128, 256, 512],
            preferredSize=self.size,
            batchIsSequential=True,
        )
        if self.native:
            notes = (
                f"Pixel-oriented Diffusers model `{self.model_id}` generating at {self.size}px. "
                "This is still a local checkpoint, not a trained Pixelator identity lock. "
                "Batch 8-direction generation is sequential img2img from the accepted reference."
            )
        else:
            notes = (
                f"Generic Diffusers (`{self.model_id}`) at {self.size}px, then Pixelator pixelizes to the sprite canvas. "
                "Not native pixel-art. Identity uses img2img from the accepted source image when present. "
                "8-direction generation is one job, sequential internally. "
                "Set PIXEL_MODEL_ID to a pixel-art checkpoint to switch providers without changing the workflow."
            )
        return ProviderInfo(
            id="pixel-diffusers" if self.native else "diffusers-local",
            name="Pixel Diffusers" if self.native else "Local Diffusers",
            modelId=self.model_id,
            supportsReference=True,
            nativePixelOutput=self.native,
            notes=notes,
            capabilities=caps,
        )

    def _generator(self, seed: int | None):
        self._ensure_loaded()
        if seed is None:
            return None
        return self.torch.Generator(device=self.device).manual_seed(seed)

    def _negative(self, prompt: PromptLayers) -> str | None:
        if self.guidance <= 0:
            return None
        return prompt.negative or None

    def _txt(self, prompt: PromptLayers, seed: int | None) -> GeneratedImage:
        self._ensure_loaded()
        kwargs = {
            "prompt": prompt.final,
            "width": self.size,
            "height": self.size,
            "num_inference_steps": self.steps,
            "guidance_scale": self.guidance,
            "generator": self._generator(seed),
        }
        negative = self._negative(prompt)
        if negative:
            kwargs["negative_prompt"] = negative
        result = self.txt2img(**kwargs).images[0]
        return GeneratedImage(result.convert("RGB"), seed, prompt)

    def _img(
        self,
        prompt: PromptLayers,
        reference: Image.Image,
        seed: int | None,
        strength: float,
        init_image: Image.Image | None = None,
    ) -> GeneratedImage:
        self._ensure_loaded()
        if self.img2img is None:
            return self._txt(prompt, seed)
        source = (init_image or reference).convert("RGB").resize((self.size, self.size), Image.Resampling.NEAREST)
        kwargs = {
            "prompt": prompt.final,
            "image": source,
            "strength": max(0.05, min(0.95, strength)),
            "num_inference_steps": max(self.steps, 6),
            "guidance_scale": max(self.guidance, 1.0),
            "generator": self._generator(seed),
        }
        negative = prompt.negative or None
        if negative:
            kwargs["negative_prompt"] = negative
        result = self.img2img(**kwargs).images[0]
        return GeneratedImage(result.convert("RGB"), seed, prompt)

    def generate_base_character(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._txt(prompt, seed)

    def generate_state(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._txt(prompt, seed)

    def generate_direction(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._txt(prompt, seed)

    def generate_animation_frames(
        self,
        prompt: PromptLayers,
        frame_count: int,
        seed: int | None = None,
        init_image: Image.Image | None = None,
    ) -> list[GeneratedImage]:
        frames: list[GeneratedImage] = []
        previous = init_image
        for index in range(frame_count):
            frame_seed = None if seed is None else seed + index
            if previous is not None:
                frames.append(self._img(prompt, previous, frame_seed, strength=0.28, init_image=previous))
            else:
                frames.append(self._txt(prompt, frame_seed))
            previous = frames[-1].image
        return frames

    def generate_head_variant(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._txt(prompt, seed)

    def generate_from_reference(
        self,
        prompt: PromptLayers,
        reference: Image.Image,
        seed: int | None = None,
        strength: float = 0.42,
        init_image: Image.Image | None = None,
    ) -> GeneratedImage:
        return self._img(prompt, reference, seed, strength, init_image)
