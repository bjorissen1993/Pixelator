from PIL import Image

from models.common import ProviderCapabilities, ProviderInfo
from models.enums import Direction
from models.generation import PromptLayers
from providers.base import DirectionSpec, GeneratedImage, GenerationProvider
from providers import pixellab_client as pixellab

OUTLINE_HINT = {
    "black": "single color black outline",
    "dark": "single color black outline",
    "colored": "single color outline",
    "selective": "selective outline",
    "soft": "selective outline",
    "lineless": "lineless",
    "none": "lineless",
}

DETAIL_HINT = {
    "low": "low detail",
    "simple": "low detail",
    "medium": "medium detail",
    "balanced": "medium detail",
    "high": "highly detailed",
}

VIEW_HINT = {
    "high-top-down": "high top-down",
    "low-top-down": "low top-down",
    "side": "side",
    "front": "side",
}


class PixelLabProvider(GenerationProvider):
    """Official PixelLab HTTP API. This is not a local model and is not a PixelLab clone."""

    def __init__(self):
        self.size = 48

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            id="pixellab",
            name="PixelLab API",
            modelId="pixellab/create-character-v3",
            supportsReference=True,
            nativePixelOutput=True,
            notes=(
                "Uses your PixelLab account via PIXELLAB_API_KEY. "
                "South generation and generate8Directions are native pixel jobs; "
                "stable 8-direction output is a native batch, incremental rotation is sequential. "
                "Credits are billed by PixelLab. This is their model, not a local substitute."
            ),
            capabilities=ProviderCapabilities(
                textToSprite=True,
                imageToSprite=True,
                rotateSprite=True,
                generate8Directions=True,
                generateState=True,
                generateAnimation=True,
                initImage=True,
                inpainting=False,
                paletteConditioning=False,
                negativePrompt=False,
                seed=True,
                poseConditioning=True,
                supportsTextToImage=True,
                supportsImg2Img=True,
                supportsImageToImage=True,
                supportsReferenceImage=True,
                supportsNegativePrompt=False,
                supportsLoRA=False,
                supportsControlNet=False,
                supportsIPAdapter=False,
                supportsPaletteConditioning=False,
                supportsDirectionGeneration=True,
                supportsBatchDirections=True,
                supportsTargetPalette=False,
                supportsInitImage=True,
                supportsInpainting=False,
                supportsAnimation=True,
                supportsSkeletonGuidance=True,
                nativePixelOutput=True,
                preferredSizes=[32, 48, 64, 96, 128],
                preferredSize=min(128, max(32, self.size)),
                workingSize=min(128, max(32, self.size)),
                batchIsSequential=False,
            ),
            fallbackTurbo=False,
            workingSize=min(128, max(32, self.size)),
            device="api",
            dtype="",
        )

    def _description(self, prompt: PromptLayers) -> str:
        text = (prompt.masterPrompt or prompt.final or "").strip()
        if len(text) > 2000:
            text = text[:1997] + "..."
        if not text:
            raise ValueError("PixelLab needs a character description")
        return text

    def _size(self, fallback: int | None = None) -> dict:
        side = max(32, min(256, fallback or self.size))
        return {"width": side, "height": side}

    def create_character_pack(
        self,
        prompt: PromptLayers,
        seed: int | None = None,
        size: int = 48,
        view: str = "high-top-down",
        outline: str = "black",
        detail: str = "medium",
        name: str = "",
        reference: Image.Image | None = None,
        on_step=None,
    ) -> dict:
        payload = {
            "description": self._description(prompt),
            "image_size": self._size(size),
            "view": VIEW_HINT.get(view, "high top-down"),
            "template_id": "mannequin",
            "no_background": True,
            "outline": OUTLINE_HINT.get(outline, "single color black outline"),
            "detail": DETAIL_HINT.get(detail, "medium detail"),
            "enhance_prompt": reference is None,
        }
        if name:
            payload["name"] = name[:80]
        if seed is not None:
            payload["seed"] = max(0, int(seed))
        if reference is not None:
            payload["reference_image"] = pixellab.encode_image(reference)
            payload["enhance_prompt"] = False
        if on_step:
            on_step("submitting PixelLab character job")
        created = pixellab.request("POST", "/create-character-v3", payload)
        job_id = created["background_job_id"]
        character_id = created["character_id"]
        pixellab.poll_job(job_id, on_step=on_step)
        if on_step:
            on_step("downloading PixelLab rotations")
        detail_payload = pixellab.request("GET", f"/characters/{character_id}")
        directions = pixellab.collect_direction_images(detail_payload)
        if "S" not in directions:
            raise RuntimeError("PixelLab character completed without a south sprite")
        return {
            "south": directions["S"],
            "directions": directions,
            "external_id": character_id,
            "seed": seed,
        }

    def fetch_rotations(self, character_id: str, on_step=None) -> dict[str, Image.Image]:
        if on_step:
            on_step("loading PixelLab rotations")
        detail_payload = pixellab.request("GET", f"/characters/{character_id}")
        directions = pixellab.collect_direction_images(detail_payload)
        if not directions:
            raise RuntimeError("PixelLab character has no rotation images yet")
        return directions

    def rotate_reference(
        self,
        reference: Image.Image,
        prompt: PromptLayers,
        seed: int | None = None,
        on_step=None,
    ) -> dict[str, Image.Image]:
        payload = {
            "first_frame": pixellab.encode_image(reference),
            "description": self._description(prompt),
            "no_background": True,
        }
        if seed is not None:
            payload["seed"] = max(0, int(seed))
        if on_step:
            on_step("submitting PixelLab 8-direction job")
        created = pixellab.request("POST", "/generate-8-rotations-v3", payload)
        result = pixellab.poll_job(created["background_job_id"], on_step=on_step)
        directions = pixellab.collect_direction_images(result)
        if "S" not in directions and reference is not None:
            directions["S"] = reference.convert("RGBA")
        if len(directions) < 4:
            raise RuntimeError("PixelLab 8-direction job did not return enough facings")
        return directions

    def generate_south(self, prompt: PromptLayers, seed: int | None = None, size: int = 48, view: str = "") -> GeneratedImage:
        self.size = max(32, min(128, size))
        generated = self.generate_base_character(prompt, seed)
        generated.debug.view = view
        generated.debug.targetDirection = "S"
        return generated

    def rotate_sprite(
        self,
        reference: Image.Image,
        from_direction,
        to_direction,
        prompt: PromptLayers,
        seed: int | None = None,
        from_view: str = "",
        to_view: str = "",
        strength: float = 0.36,
        size: int = 48,
        guidance: float | None = None,
        palette=None,
    ) -> GeneratedImage:
        if reference is None:
            raise ValueError("rotateSprite requires a real reference image")
        self.size = max(32, min(128, size))
        directions = self.rotate_reference(reference, prompt, seed=seed)
        image = directions.get(to_direction) or directions.get(from_direction) or reference
        generated = GeneratedImage(image, seed, prompt)
        generated.debug.usedReference = True
        generated.debug.referenceDirection = from_direction
        generated.debug.targetDirection = to_direction
        generated.debug.view = to_view or from_view
        generated.direction_images = directions
        return generated

    def generate_8_directions(
        self,
        reference_south: Image.Image,
        prompt: PromptLayers,
        seed: int | None = None,
        view: str = "",
        size: int = 48,
        palette=None,
        strategy: str = "stable",
        on_progress=None,
    ):
        if reference_south is None:
            raise ValueError("generate8Directions requires a South reference image")
        if strategy == "incremental":
            return super().generate_8_directions(
                reference_south, prompt, seed, view, size, palette, strategy, on_progress
            )
        self.size = max(32, min(128, size))
        directions = self.rotate_reference(reference_south, prompt, seed=seed)
        results = {}
        order = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
        for index, direction in enumerate(order, start=1):
            image = directions.get(direction) or (reference_south if direction == "S" else None)
            if image is None:
                continue
            generated = GeneratedImage(image, seed, prompt)
            generated.debug.usedReference = True
            generated.debug.referenceDirection = "S"
            generated.debug.targetDirection = direction
            generated.debug.view = view
            generated.debug.rotationStrategy = "stable"
            results[direction] = generated
            if on_progress:
                on_progress(index, 8, f"Generating rotations {index}/8 ({direction})")
        return results

    def generate_base_character(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        pack = self.create_character_pack(prompt, seed=seed, size=self.size)
        image = GeneratedImage(pack["south"], seed, prompt)
        image.external_id = pack["external_id"]
        image.direction_images = pack["directions"]
        return image

    def generate_state(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self.generate_base_character(prompt, seed)

    def generate_direction(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self.generate_base_character(prompt, seed)

    def generate_from_reference(
        self,
        prompt: PromptLayers,
        reference: Image.Image,
        seed: int | None = None,
        strength: float = 0.42,
        init_image: Image.Image | None = None,
    ) -> GeneratedImage:
        source = init_image or reference
        if strength >= 0.7:
            pack = self.create_character_pack(prompt, seed=seed, size=self.size)
        else:
            directions = self.rotate_reference(source, prompt, seed=seed)
            pack = {
                "south": directions.get("S", source.convert("RGBA")),
                "directions": directions,
                "external_id": None,
            }
        image = GeneratedImage(pack["south"], seed, prompt)
        image.external_id = pack.get("external_id")
        image.direction_images = pack.get("directions")
        return image

    def generate_head_variant(self, prompt: PromptLayers, seed: int | None = None) -> GeneratedImage:
        return self.generate_base_character(prompt, seed)

    def generate_animation_frames(
        self,
        prompt: PromptLayers,
        frame_count: int,
        seed: int | None = None,
        init_image: Image.Image | None = None,
    ) -> list[GeneratedImage]:
        if init_image is None:
            raise ValueError("PixelLab animation needs a start frame. Accept a base first.")
        count = max(4, min(16, frame_count if frame_count % 2 == 0 else frame_count + 1))
        payload = {
            "first_frame": pixellab.encode_image(init_image),
            "action": (prompt.override or prompt.state or prompt.final or "idle")[:1000],
            "frame_count": count,
            "no_background": True,
            "enhance_prompt": True,
        }
        if seed is not None:
            payload["seed"] = max(0, int(seed))
        created = pixellab.request("POST", "/animate-with-text-v3", payload)
        result = pixellab.poll_job(created["background_job_id"])
        frames = pixellab.collect_frames(result)
        if not frames:
            raise RuntimeError("PixelLab animation job returned no frames")
        return [GeneratedImage(frame, None if seed is None else seed + index, prompt) for index, frame in enumerate(frames)]

    def generate_direction_set(
        self,
        specs: list[DirectionSpec],
        accepted_reference: Image.Image | None,
        on_progress=None,
    ) -> list[GeneratedImage]:
        if accepted_reference is None:
            raise ValueError("PixelLab 8-direction generation needs an accepted south reference")
        prompt = specs[0].prompt if specs else PromptLayers()
        seed = specs[0].seed if specs else None
        directions = self.rotate_reference(accepted_reference, prompt, seed=seed)
        results: list[GeneratedImage] = []
        total = len(specs)
        for index, spec in enumerate(specs, start=1):
            image = directions.get(spec.target) or directions.get("S") or accepted_reference
            results.append(GeneratedImage(image, spec.seed, spec.prompt))
            if on_progress:
                on_progress(index, total, spec.target)
        return results
