from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field

from PIL import Image

from models.character import GenerationDebug
from models.common import ProviderCapabilities, ProviderInfo
from models.enums import Direction
from models.generation import PromptLayers


class GeneratedImage:
    def __init__(self, image: Image.Image, seed: int | None, prompt: PromptLayers, debug: GenerationDebug | None = None):
        self.image = image
        self.seed = seed
        self.prompt = prompt
        self.external_id: str | None = None
        self.direction_images: dict[Direction, Image.Image] | None = None
        self.debug = debug or GenerationDebug()
        self.used_reference = bool(self.debug.usedReference)
        self.strength = self.debug.strength


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

    def create_character_pack(self, *args, **kwargs):
        return None

    def generate_south(
        self,
        prompt: PromptLayers,
        seed: int | None = None,
        size: int = 48,
        view: str = "",
    ) -> GeneratedImage:
        return self.generate_base_character(prompt, seed)

    def rotate_sprite(
        self,
        reference: Image.Image,
        from_direction: Direction,
        to_direction: Direction,
        prompt: PromptLayers,
        seed: int | None = None,
        from_view: str = "",
        to_view: str = "",
        strength: float = 0.36,
        size: int = 48,
        guidance: float | None = None,
        palette: list[tuple[int, int, int]] | None = None,
    ) -> GeneratedImage:
        if reference is None:
            raise ValueError("rotateSprite requires a real reference image")
        return self.generate_from_reference(prompt, reference, seed=seed, strength=strength, init_image=reference)

    def generate_8_directions(
        self,
        reference_south: Image.Image,
        prompt: PromptLayers,
        seed: int | None = None,
        view: str = "",
        size: int = 48,
        palette: list[tuple[int, int, int]] | None = None,
        strategy: str = "stable",
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> dict[Direction, GeneratedImage]:
        from domain.rotation import EXPORT_ORDER, rotation_jobs

        if reference_south is None:
            raise ValueError("generate8Directions requires a South reference image")
        results: dict[Direction, GeneratedImage] = {}
        south = GeneratedImage(reference_south, seed, prompt)
        south.debug.usedReference = True
        south.debug.targetDirection = "S"
        results["S"] = south
        jobs = rotation_jobs(strategy, list(EXPORT_ORDER))
        total = len(jobs)
        for index, (source_dir, target) in enumerate(jobs, start=1):
            source = results.get(source_dir, south).image
            results[target] = self.rotate_sprite(
                source,
                source_dir,
                target,
                prompt,
                seed=None if seed is None else seed + index,
                from_view=view,
                to_view=view,
                size=size,
                palette=palette,
            )
            results[target].debug.rotationStrategy = strategy
            results[target].debug.view = view
            if on_progress:
                on_progress(index, total, f"Generating rotations {index}/{total} ({target})")
        return results

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
