from PIL import Image

from models.common import ProviderCapabilities, ProviderInfo
from models.generation import PromptLayers
from providers.base import GeneratedImage, GenerationProvider


class UnconfiguredProvider(GenerationProvider):
    """Honest empty provider. Nothing is generated until a pixel model or PixelLab key is set."""

    def __init__(self, reason: str = ""):
        self.reason = reason or (
            "No pixel-art generation provider is configured. Set PIXELATOR_MODEL_ID to a local pixel checkpoint, "
            "PIXELLAB_API_KEY for PixelLab, or PIXELATOR_ALLOW_TURBO_FALLBACK=true to opt into the old SDXL-Turbo path."
        )

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="unconfigured",
            name="Unconfigured",
            modelId="",
            supportsReference=False,
            nativePixelOutput=False,
            notes=self.reason,
            capabilities=ProviderCapabilities(
                seed=False,
                preferredSizes=[32, 48, 64, 96, 128],
                preferredSize=48,
                workingSize=48,
            ),
            fallbackTurbo=False,
            device="",
            dtype="",
            workingSize=48,
        )

    def _fail(self) -> GeneratedImage:
        raise ValueError(self.reason)

    def generate_base_character(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._fail()

    def generate_state(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._fail()

    def generate_direction(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._fail()

    def generate_animation_frames(
        self,
        prompt: PromptLayers,
        frame_count: int,
        seed: int | None = None,
        init_image: Image.Image | None = None,
    ) -> list[GeneratedImage]:
        self._fail()
        return []

    def generate_head_variant(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self._fail()

    def generate_from_reference(
        self,
        prompt: PromptLayers,
        reference: Image.Image,
        seed: int | None = None,
        strength: float = 0.42,
        init_image: Image.Image | None = None,
    ) -> GeneratedImage:
        return self._fail()
