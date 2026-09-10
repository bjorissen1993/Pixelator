from pathlib import Path

from PIL import Image

import config
from models.character import GenerationDebug
from models.common import ProviderCapabilities, ProviderInfo
from models.generation import PromptLayers
from providers.base import GeneratedImage, GenerationProvider


def _is_turbo(model_id: str) -> bool:
    return "turbo" in model_id.lower()


def _resolve_dtype(torch, device: str):
    name = config.DTYPE
    mapping = {
        "fp16": torch.float16,
        "float16": torch.float16,
        "bf16": torch.bfloat16,
        "bfloat16": torch.bfloat16,
        "fp32": torch.float32,
        "float32": torch.float32,
    }
    if name in mapping:
        return mapping[name]
    return torch.float16 if device == "cuda" else torch.float32


class DiffusersProvider(GenerationProvider):
    """Local Diffusers backend.

    MODEL_ID / PIXEL_MODEL_ID / LORA_PATH come from env. SDXL-Turbo is fallback only.
    A Turbo checkpoint is never reported as a specialized pixel-art model.
    """

    def __init__(self, model_id: str | None = None, native: bool = False):
        self.torch = None
        self.device = config.DEVICE
        self.dtype_name = config.DTYPE or ("float16" if config.DEVICE == "cuda" else "float32")
        self.txt2img = None
        self.img2img = None
        self.model_id = (model_id or config.PIXEL_MODEL_ID or config.MODEL_ID).strip()
        self.native = native and not _is_turbo(self.model_id)
        self.working_size = max(32, min(512, config.WORKING_SIZE))
        self.fallback_turbo = _is_turbo(self.model_id)
        # Turbo is not a native pixel checkpoint; keep its trained 512 canvas, then pixel-aware downsample.
        self.size = 512 if self.fallback_turbo else self.working_size
        if config.WORKING_SIZE == 48:
            self.size = 48
        self.steps = config.INFERENCE_STEPS if not self.native else max(config.INFERENCE_STEPS, 8)
        self.guidance = config.GUIDANCE_SCALE if not self.native else max(config.GUIDANCE_SCALE, 1.0)
        self.lora_path = config.LORA_PATH
        self.lora_strength = config.LORA_STRENGTH
        self.lora_loaded = False
        self.lora_error = ""
        self.controlnet_loaded = False
        self.ip_adapter_loaded = False
        self.img2img_ready = False

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
        dtype = _resolve_dtype(torch, self.device)
        self.dtype_name = str(dtype).replace("torch.", "")
        self.txt2img = AutoPipelineForText2Image.from_pretrained(self.model_id, torch_dtype=dtype)
        self.txt2img = self.txt2img.to(self.device)
        self._load_lora(self.txt2img)
        self._load_ip_adapter(self.txt2img)
        self._load_controlnet()
        try:
            self.img2img = AutoPipelineForImage2Image.from_pipe(self.txt2img)
        except Exception:
            try:
                self.img2img = AutoPipelineForImage2Image.from_pretrained(self.model_id, torch_dtype=dtype)
                self.img2img = self.img2img.to(self.device)
                self._load_lora(self.img2img)
                self._load_ip_adapter(self.img2img)
            except Exception:
                self.img2img = None
        self.img2img_ready = self.img2img is not None

    def _load_lora(self, pipe) -> None:
        if not self.lora_path:
            return
        path = Path(self.lora_path)
        try:
            kwargs = {}
            if path.is_file():
                kwargs["weight_name"] = path.name
                pipe.load_lora_weights(str(path.parent), **kwargs)
            else:
                pipe.load_lora_weights(self.lora_path)
            if hasattr(pipe, "fuse_lora"):
                try:
                    pipe.fuse_lora(lora_scale=self.lora_strength)
                except TypeError:
                    pipe.fuse_lora()
            elif hasattr(pipe, "set_adapters"):
                pipe.set_adapters(["default"], adapter_weights=[self.lora_strength])
            self.lora_loaded = True
        except Exception as exc:
            self.lora_loaded = False
            self.lora_error = str(exc)

    def _load_ip_adapter(self, pipe) -> None:
        if not config.IP_ADAPTER_MODEL or not hasattr(pipe, "load_ip_adapter"):
            return
        try:
            model = config.IP_ADAPTER_MODEL
            if "/" in model and not Path(model).exists():
                pipe.load_ip_adapter(model, subfolder="sdxl_models", weight_name="ip-adapter_sdxl.bin")
            else:
                pipe.load_ip_adapter(model)
            if hasattr(pipe, "set_ip_adapter_scale"):
                pipe.set_ip_adapter_scale(0.55)
            self.ip_adapter_loaded = True
        except Exception:
            self.ip_adapter_loaded = False

    def _load_controlnet(self) -> None:
        # Reserved for a future ControlNet generate path. Do not report it as active until wired.
        self.controlnet_loaded = False

    @property
    def info(self) -> ProviderInfo:
        caps = ProviderCapabilities(
            supportsTextToImage=True,
            supportsImg2Img=self.img2img_ready or self.txt2img is None,
            supportsImageToImage=self.img2img_ready or self.txt2img is None,
            supportsReferenceImage=True,
            supportsNegativePrompt=self.guidance > 0 or True,
            supportsLoRA=bool(self.lora_path),
            supportsControlNet=self.controlnet_loaded,
            supportsIPAdapter=self.ip_adapter_loaded,
            supportsPaletteConditioning=False,
            supportsDirectionGeneration=True,
            supportsBatchDirections=True,
            supportsTargetPalette=False,
            supportsInitImage=True,
            supportsInpainting=False,
            supportsAnimation=True,
            supportsSkeletonGuidance=False,
            nativePixelOutput=self.native and not self.fallback_turbo,
            preferredSizes=[48, 64, 96, 128, 256, 512],
            preferredSize=self.size,
            workingSize=self.working_size,
            batchIsSequential=True,
        )
        if self.fallback_turbo:
            notes = (
                f"Fallback SDXL-Turbo (`{self.model_id}`) at {self.size}px, then pixel-aware downsample to the sprite canvas. "
                "This is not a pixel-art checkpoint. Identity uses img2img/IP-Adapter from the accepted source when present. "
                "Set MODEL_ID / PIXEL_MODEL_ID / LORA_PATH for a pixel model, or PIXELLAB_API_KEY for PixelLab."
            )
            if self.lora_path:
                notes += f" LoRA {'loaded' if self.lora_loaded else 'configured but not loaded'}."
        elif self.native:
            notes = (
                f"Pixel-oriented Diffusers model `{self.model_id}` generating at {self.size}px. "
                "Not a trained Pixelator identity lock. 8-direction generation is sequential from neighbor references."
            )
        else:
            notes = (
                f"Diffusers (`{self.model_id}`) at {self.size}px working canvas, then nearest/block downsample to the sprite. "
                "Identity uses real img2img from the accepted/neighbor reference when the pipeline supports it."
            )
        return ProviderInfo(
            id="pixel-diffusers" if self.native and not self.fallback_turbo else "diffusers-local",
            name="Pixel Diffusers" if self.native and not self.fallback_turbo else "Local Diffusers",
            modelId=self.model_id,
            supportsReference=True,
            nativePixelOutput=self.native and not self.fallback_turbo,
            notes=notes,
            capabilities=caps,
            loraPath=self.lora_path,
            loraLoaded=self.lora_loaded,
            loraStrength=self.lora_strength if self.lora_loaded else 0,
            controlnetLoaded=self.controlnet_loaded,
            ipAdapterLoaded=self.ip_adapter_loaded,
            fallbackTurbo=self.fallback_turbo,
            device=self.device,
            dtype=self.dtype_name,
            workingSize=self.working_size,
        )

    def _debug(
        self,
        prompt: PromptLayers,
        seed: int | None,
        strength: float | None = None,
        used_reference: bool = False,
        used_ip: bool = False,
    ) -> GenerationDebug:
        return GenerationDebug(
            provider=self.info.id,
            model=self.model_id,
            lora=self.lora_path if self.lora_loaded else "",
            loraLoaded=self.lora_loaded,
            seed=seed,
            steps=self.steps if not used_reference else max(self.steps, 6),
            guidance=max(self.guidance, 1.0) if used_reference else self.guidance,
            strength=strength,
            prompt=prompt.final,
            negativePrompt=prompt.negative,
            workingResolution=self.size,
            targetResolution=None,
            paletteMode="",
            usedReference=used_reference,
            usedIpAdapter=used_ip and self.ip_adapter_loaded,
        )

    def _generator(self, seed: int | None):
        self._ensure_loaded()
        if seed is None:
            return None
        return self.torch.Generator(device=self.device).manual_seed(seed)

    def _negative(self, prompt: PromptLayers) -> str | None:
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
        if negative and self.guidance > 0:
            kwargs["negative_prompt"] = negative
        result = self.txt2img(**kwargs).images[0]
        debug = self._debug(prompt, seed)
        return GeneratedImage(result.convert("RGB"), seed, prompt, debug)

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
        used_ip = False
        if self.ip_adapter_loaded:
            kwargs["ip_adapter_image"] = reference.convert("RGB")
            used_ip = True
        try:
            result = self.img2img(**kwargs).images[0]
        except Exception:
            kwargs.pop("ip_adapter_image", None)
            used_ip = False
            result = self.img2img(**kwargs).images[0]
        debug = self._debug(prompt, seed, strength=strength, used_reference=True, used_ip=used_ip)
        generated = GeneratedImage(result.convert("RGB"), seed, prompt, debug)
        generated.used_reference = True
        generated.strength = strength
        return generated

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
