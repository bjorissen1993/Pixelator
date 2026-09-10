from abc import ABC, abstractmethod

from PIL import Image

from models.common import ProviderInfo
from models.generation import PromptLayers


class GeneratedImage:
    def __init__(self, image: Image.Image, seed: int | None, prompt: PromptLayers):
        self.image = image
        self.seed = seed
        self.prompt = prompt


class GenerationProvider(ABC):
    @property
    @abstractmethod
    def info(self) -> ProviderInfo:
        raise NotImplementedError

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
        self, prompt: PromptLayers, frame_count: int, seed: int | None = None
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
    ) -> GeneratedImage:
        raise NotImplementedError
