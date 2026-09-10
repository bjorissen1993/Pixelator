from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from PIL import Image

from models.common import ProviderCapabilities, ProviderInfo
from models.enums import Direction
from models.generation import PromptLayers


class GeneratedImage:
    def __init__(self, image: Image.Image, seed: int | None, prompt: PromptLayers):
        self.image = image
        self.seed = seed
        self.prompt = prompt


@dataclass
class DirectionSpec:
    target: Direction
    from_direction: Direction | None = None
    prompt: PromptLayers = field(default_factory=PromptLayers)
    seed: int | None = None
    strength: float = 0.38
    init_image: Image.Image | None = None


class GenerationProvider(ABC):
    @property
    @abstractmethod
    def info(self) -> ProviderInfo:
        raise NotImplementedError

    @property
    def capabilities(self) -> ProviderCapabilities:
        return self.info.capabilities

    @abstractmethod
    def generate_base_character(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        raise NotImplementedError

    @abstractmethod
    def generate_state(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        raise NotImplementedError

    @abstractmethod
    def generate_direction(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        raise NotImplementedError

    @abstractmethod
    def generate_animation_frames(
        self,
        prompt: PromptLayers,
        frame_count: int,
        seed: int | None = None,
        init_image: Image.Image | None = None,
    ) -> list[GeneratedImage]:
        raise NotImplementedError

    @abstractmethod
    def generate_head_variant(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        raise NotImplementedError

    @abstractmethod
    def generate_from_reference(
        self,
        prompt: PromptLayers,
        reference: Image.Image,
        seed: int | None = None,
        strength: float = 0.42,
        init_image: Image.Image | None = None,
    ) -> GeneratedImage:
        raise NotImplementedError

    def generate_direction_set(
        self,
        specs: list[DirectionSpec],
        accepted_reference: Image.Image | None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> list[GeneratedImage]:
        """Default implementation is sequential. Providers may override with a true batch."""
        results: list[GeneratedImage] = []
        total = len(specs)
        for index, spec in enumerate(specs, start=1):
            reference = spec.init_image or accepted_reference
            if reference is not None and self.capabilities.supportsReferenceImage:
                result = self.generate_from_reference(
                    spec.prompt, reference, seed=spec.seed, strength=spec.strength, init_image=spec.init_image
                )
            else:
                result = self.generate_direction(spec.prompt, seed=spec.seed)
            results.append(result)
            if on_progress:
                on_progress(index, total, spec.target)
        return results

    def inpaint(
        self,
        prompt: PromptLayers,
        image: Image.Image,
        mask: Image.Image,
        seed: int | None = None,
    ) -> GeneratedImage:
        raise NotImplementedError("Current provider does not support inpainting")
