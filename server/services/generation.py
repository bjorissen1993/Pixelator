import logging
import shutil
from datetime import datetime, timezone
from random import randint
from uuid import uuid4

from PIL import Image

import config
from domain.directions import EXPORT_DIRECTION_ORDER, HEAD_VARIANTS, closest_reference
from models.character import AcceptedBase, CharacterProfile, GenerationDebug, HeadAnchor, SpriteAsset
from models.enums import Direction, HeadVariant, LayerKind
from models.generation import PromptLayers
from persistence.paths import public_asset_path, resolve_data_path
from persistence.store import asset_path, character_dir
from processing.layers import split_head_body
from processing.pipeline import PixelPipeline, estimate_head_anchor, extract_palette
from processing.preview import make_preview, preview_relative
from processing.cleanup import cleanup_sprite
from processing.validation import invalid_base_reasons, is_valid_base, is_valid_direction, validate_sprite
from prompts.builder import build_prompt, build_pixellab_description
from prompts.composition import FRAMING_RETRY, composition_constraints
from providers.base import DirectionSpec, GeneratedImage
from providers.registry import get_provider
from services import characters as character_service
from services import jobs
from services import memory
from services import progress

pipeline = PixelPipeline()
logger = logging.getLogger("pixelator.generation")


def log_generation(action: str, character: CharacterProfile | None = None, **context) -> None:
    provider = get_provider()
    parts = [
        f"action={action}",
        f"characterId={getattr(character, 'id', context.get('characterId', ''))}",
        f"slug={getattr(character, 'slug', '')}",
        f"provider={provider.info.id}",
        f"model={provider.info.modelId}",
        f"lora={provider.info.loraPath if provider.info.loraLoaded else 'none'}",
    ]
    for key, value in context.items():
        if value is None or key == "characterId":
            continue
        text = str(value)
        if key in {"prompt", "negative"} and len(text) > 800:
            text = text[:800] + "…"
        parts.append(f"{key}={text}")
    logger.info(" | ".join(parts))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex


def public_path(slug: str, relative: str) -> str:
    return public_asset_path(slug, relative)


def save_image(slug: str, relative: str, image: Image.Image) -> str:
    path = asset_path(slug, relative)
    logger.info("Saving image slug=%s relative=%s path=%s", slug, relative, path)
    try:
        image.save(path, format="PNG")
    except OSError:
        logger.exception("Failed to save image path=%s", path)
        raise
    return public_path(slug, relative)


def load_image(relative: str | None) -> Image.Image | None:
    path = resolve_data_path(relative)
    if path is None or not path.exists() or not path.is_file():
        if relative:
            logger.warning("Image missing or invalid relative=%s resolved=%s", relative, path)
        return None
    try:
        return Image.open(path).convert("RGBA")
    except OSError:
        logger.exception("Failed to open image path=%s relative=%s", path, relative)
        raise


def resolve_seed(character: CharacterProfile, requested: int | None = None, mode: str = "reuse_base") -> int | None:
    if requested is not None:
        return requested
    if mode == "locked" or character.seedLocked:
        return character.seed
    if mode == "reuse_base":
        return character.acceptedBase.seed if character.acceptedBase and character.acceptedBase.seed is not None else character.seed
    if mode == "variation" and character.seed is not None:
        return character.seed + randint(1, 9999)
    if mode == "random" or character.seed is None:
        return randint(1, 2_147_483_647)
    return character.seed


def palette_mode_name(character: CharacterProfile) -> str:
    mode = character.paletteMode
    if mode == "locked":
        return "strict"
    if mode == "generated":
        return "unlocked"
    if mode == "accepted":
        return "accepted"
    return mode


def palette_colors(character: CharacterProfile) -> list[tuple[int, int, int]] | None:
    mode = palette_mode_name(character)
    if mode in ("accepted", "strict", "soft", "custom", "project", "locked") or (
        character.identityLock.lockPalette and character.palette.locked and character.palette.colors
    ):
        return locked_palette(character)
    return None


def locked_palette(character: CharacterProfile) -> list[tuple[int, int, int]] | None:
    if not character.palette.colors:
        return None
    colors: list[tuple[int, int, int]] = []
    for value in character.palette.colors:
        hex_value = value.lstrip("#")
        if len(hex_value) != 6:
            continue
        colors.append((int(hex_value[0:2], 16), int(hex_value[2:4], 16), int(hex_value[4:6], 16)))
    return colors or None


def usable_accepted_base(character: CharacterProfile):
    if character.acceptedBase is None:
        return None
    validation = character.acceptedBase.sprite.validation
    if validation is None:
        validation = _revalidate_base_asset(character, character.acceptedBase.sprite)
        character.acceptedBase.sprite.validation = validation
    if not is_valid_base(validation):
        return None
    return character.acceptedBase


def identity_sprite(character: CharacterProfile) -> Image.Image | None:
    base = usable_accepted_base(character)
    if base is None:
        return None
    return load_image(base.sprite.path)


def _job_step(character_id: str, step: str, status: str = "processing") -> None:
    progress.set_step(character_id, step)
    active = jobs.active_for(character_id)
    if active:
        jobs.set_progress(active.id, active.current, active.total, step, status)


def process_generated(character: CharacterProfile, image: Image.Image, direction=None, for_base: bool = False):
    provider = get_provider()
    comp = character.composition
    margin = getattr(comp, "safeMargin", 0.10) if comp.fitSafeMargins or comp.preventCropping else 0.04
    scale = getattr(comp, "characterScale", 0) or 0
    if scale > 0:
        margin = max(margin, max(0.02, (1.0 - min(1.0, scale)) / 2))
    on_step = lambda step: _job_step(character.id, step)
    kwargs = dict(
        image=image,
        size=character.spriteSize,
        colors=character.palette.colorCount,
        locked_palette=palette_colors(character),
        palette_mode=palette_mode_name(character),
        reference=None if for_base else identity_sprite(character),
        direction=direction,
        fit_margin=margin,
        center=comp.centerCharacter,
        spirit_form=character.spirit.enabled or character.spirit.noLegs,
        for_base=for_base,
        one_character=comp.oneCharacterOnly,
        on_step=on_step,
    )
    if provider.info.fallbackTurbo:
        return pipeline.process(
            kwargs["image"],
            character.spriteSize,
            character.palette.colorCount,
            character.outline,
            config.ENABLE_BG_REMOVAL,
            kwargs["locked_palette"],
            on_step=on_step,
            native=False,
            working_size=512,
            palette_mode=kwargs["palette_mode"],
            reference=kwargs["reference"],
            direction=direction,
            fit_margin=margin,
            center=comp.centerCharacter,
            spirit_form=kwargs["spirit_form"],
            for_base=for_base,
            one_character=comp.oneCharacterOnly,
        )
    return cleanup_sprite(**kwargs)


def looks_cropped(validation) -> bool:
    if validation is None:
        return False
    return any(
        warning.code
        in {
            "likely_cropped",
            "touches_edges",
            "touches_top",
            "touches_bottom",
            "touches_left",
            "touches_right",
            "silhouette_incomplete",
        }
        for warning in validation.warnings
    )


def _revalidate_base_asset(character: CharacterProfile, asset: SpriteAsset | None):
    if asset is None:
        return None
    sprite = load_image(asset.path)
    if sprite is None:
        return asset.validation
    source = load_image(asset.sourcePath) if asset.sourcePath else None
    return validate_sprite(
        sprite,
        character.spriteSize,
        character.palette.colorCount,
        source=source,
        palette=palette_colors(character),
        spirit_form=character.spirit.enabled or character.spirit.noLegs,
        for_base=True,
        one_character=character.composition.oneCharacterOnly,
    )


def _require_valid_pending_base(character: CharacterProfile) -> SpriteAsset:
    pending = character.pendingBase
    if pending is None:
        raise ValueError("No pending sprite to promote")
    validation = _revalidate_base_asset(character, pending)
    pending.validation = validation
    reasons = invalid_base_reasons(validation)
    if reasons:
        character_service.save_character(character)
        raise ValueError(" ".join(reasons))
    return pending


def make_asset(
    character: CharacterProfile,
    image: Image.Image,
    relative: str,
    prompt: str,
    seed: int | None,
    kind: str,
    validation,
    head: HeadAnchor | None,
    preview: Image.Image | None = None,
    source: Image.Image | None = None,
    negative: str = "",
    status: str = "pending",
    from_direction: Direction | None = None,
    reference_direction: Direction | None = None,
    reference_asset_id: str = "",
    reference_state: str = "",
    reference_file: str = "",
    strength: float | None = None,
    debug: GenerationDebug | None = None,
) -> SpriteAsset:
    progress.set_step(character.id, "saving preview")
    path = save_image(character.slug, relative, image)
    preview_image = preview if preview is not None else make_preview(image)
    preview_path = save_image(character.slug, preview_relative(relative), preview_image)
    source_path = ""
    if source is not None:
        source_rel = relative[:-4] + "-source.png" if relative.endswith(".png") else relative + "-source.png"
        source_path = save_image(character.slug, source_rel, source.convert("RGBA"))
    info = get_provider().info
    debug = debug or GenerationDebug()
    debug.provider = debug.provider or info.id
    debug.model = debug.model or info.modelId
    debug.lora = debug.lora or (info.loraPath if info.loraLoaded else "")
    debug.loraLoaded = debug.loraLoaded or info.loraLoaded
    debug.seed = seed if seed is not None else debug.seed
    debug.prompt = debug.prompt or prompt
    debug.negativePrompt = debug.negativePrompt or negative
    debug.workingResolution = debug.workingResolution or info.workingSize or config.WORKING_SIZE
    debug.targetResolution = character.spriteSize
    debug.paletteMode = character.paletteMode
    debug.referenceDirection = reference_direction or debug.referenceDirection
    debug.referenceAssetId = reference_asset_id or debug.referenceAssetId
    debug.referenceState = reference_state or debug.referenceState
    debug.referenceFile = reference_file or debug.referenceFile
    debug.view = debug.view or character.camera
    debug.rotationStrategy = debug.rotationStrategy or getattr(character, "rotationStrategy", "stable")
    debug.strength = strength if strength is not None else debug.strength
    debug.usedReference = debug.usedReference or bool(reference_asset_id or reference_direction or reference_file)
    debug.targetDirection = debug.targetDirection or from_direction
    if validation is not None:
        debug.artifactDetected = bool(getattr(validation, "artifactDetected", False))
        debug.compositionFailed = bool(getattr(validation, "compositionFailed", False))
        debug.directionScore = getattr(validation, "directionScore", None)
    return SpriteAsset(
        id=new_id(),
        kind=kind,  # type: ignore[arg-type]
        path=path,
        previewPath=preview_path,
        sourcePath=source_path,
        width=image.width,
        height=image.height,
        seed=seed,
        prompt=prompt,
        negativePrompt=negative,
        createdAt=utc_now(),
        accepted=status == "accepted",
        status=status,  # type: ignore[arg-type]
        validation=validation,
        head=head,
        providerId=info.id,
        fromDirection=from_direction,
        referenceDirection=reference_direction,
        referenceAssetId=reference_asset_id,
        referenceState=reference_state,
        referenceFile=reference_file,
        strength=strength,
        debug=debug,
    )


def reference_image(character: CharacterProfile, direction: Direction | None = None, state_id: str | None = None) -> Image.Image | None:
    if state_id and direction:
        try:
            state = character_service.find_state(character, state_id)
            slot = character_service.find_slot(state, direction)
            if slot.frames and slot.status in ("accepted", "locked", "pending"):
                asset = slot.frames[0]
                return load_image(asset.sourcePath or asset.path)
        except KeyError:
            pass
    if character.acceptedBase is None:
        return None
    asset = character.acceptedBase.sprite
    return load_image(asset.sourcePath or asset.path)


def resolve_direction_reference(
    character: CharacterProfile,
    state,
    direction: Direction,
    requested_from: Direction | None,
    use_reference: bool,
):
    if not use_reference:
        return None, "", None
    accepted: list[Direction] = []
    generated: list[Direction] = []
    assets: dict[Direction, SpriteAsset] = {}
    for slot in state.directions:
        if not slot.frames:
            continue
        assets[slot.direction] = slot.frames[0]
        if slot.locked or slot.status in ("accepted", "locked"):
            accepted.append(slot.direction)
        elif slot.status == "pending":
            generated.append(slot.direction)
    target_from = requested_from or closest_reference(direction, accepted) or closest_reference(direction, generated)
    ref_image = None
    ref_id = ""
    if target_from and target_from in assets:
        asset = assets[target_from]
        ref_image = load_image(asset.sourcePath or asset.path)
        ref_id = asset.id
    if ref_image is None and character.acceptedBase:
        ref_image = load_image(character.acceptedBase.sprite.sourcePath or character.acceptedBase.sprite.path)
        ref_id = character.acceptedBase.sprite.id
        target_from = target_from or "S"
    return target_from, ref_id, ref_image


def provider_prompt(character: CharacterProfile, prompt: PromptLayers, override: str = "") -> PromptLayers:
    if get_provider().capabilities.nativePixelOutput:
        description = build_pixellab_description(character, override)
        return prompt.model_copy(update={"masterPrompt": description, "final": description, "negative": ""})
    return prompt


def generate_image(
    character: CharacterProfile,
    prompt: PromptLayers,
    use_reference: bool,
    seed: int | None,
    strength: float = 0.42,
    init_image: Image.Image | None = None,
    state_id: str | None = None,
    direction: Direction | None = None,
    allow_crop_retry: bool = True,
    for_base: bool = False,
):
    provider = get_provider()
    native = provider.capabilities.nativePixelOutput
    attempts = 1
    if allow_crop_retry and not native and character.composition.preventCropping:
        if for_base and character.composition.fullBodySprite:
            attempts = 3
        elif not for_base:
            attempts = 2
    last = None
    retries = 0
    working_prompt = prompt
    working_seed = seed
    for attempt in range(attempts):
        if attempt > 0:
            retries = attempt
            progress.set_step(character.id, "retrying cropped sprite" if not for_base else "retrying invalid base framing")
            stronger = composition_constraints(character, stronger=True)
            working_prompt = prompt.model_copy(
                update={
                    "override": ", ".join(part for part in (prompt.override, FRAMING_RETRY) if part),
                    "composition": stronger,
                    "final": f"{prompt.final}, {FRAMING_RETRY}",
                }
            )
            working_seed = None if seed is None else seed + 17 * attempt
        _job_step(character.id, "Generating South" if for_base else "Generating sprite", "generating")
        model_prompt = provider_prompt(character, working_prompt)
        log_generation(
            "generate_image",
            character,
            direction=direction,
            state=state_id or ("idle" if for_base else ""),
            seed=working_seed,
            attempt=attempt + 1,
            useReference=use_reference,
            forBase=for_base,
            prompt=model_prompt.final,
            negative=model_prompt.negative,
        )
        ref = init_image or (reference_image(character, direction, state_id) if use_reference else None)
        used_reference = False
        if ref is not None and (
            provider.capabilities.supportsReferenceImage
            or provider.capabilities.supportsImg2Img
            or provider.capabilities.supportsImageToImage
        ):
            generated = provider.generate_from_reference(
                model_prompt, ref, seed=working_seed, strength=strength, init_image=init_image or ref
            )
            used_reference = True
        else:
            generated = provider.generate_direction(model_prompt, seed=working_seed)
        sprite, preview, validation = process_generated(character, generated.image, direction=direction, for_base=for_base)
        if generated.debug:
            generated.debug.cropRetries = retries
            generated.debug.retryTriggered = retries > 0
            generated.debug.prompt = working_prompt.final
        if validation:
            validation.retryTriggered = retries > 0
        last = (generated, sprite, preview, validation, used_reference)
        if for_base:
            if is_valid_base(validation):
                break
        elif is_valid_direction(validation):
            break
    if last is None:
        raise RuntimeError("Generation produced no image")
    return last


def _track(character_id: str, label: str):
    nested = progress.is_active(character_id)
    if not nested:
        progress.start(character_id, label)
    return nested


def generate_base(character_id: str, seed: int | None = None, override: str = "") -> dict:
    nested = _track(character_id, "Generating south")
    try:
        character = character_service.get_character(character_id)
        idle = _idle_state(character)
        prompt = build_prompt(character, state=idle, direction="S", override=override)
        provider = get_provider()
        logger.info(
            "generate_base character=%s slug=%s provider=%s model=%s seed=%s",
            character.id,
            character.slug,
            provider.info.id,
            provider.info.modelId,
            seed,
        )
        chosen_seed = resolve_seed(character, seed, "reuse_base")
        pack = None
        if hasattr(provider, "create_character_pack"):
            pack = provider.create_character_pack(
                provider_prompt(character, prompt, override),
                seed=chosen_seed,
                size=character.spriteSize,
                view=character.camera,
                outline=character.outline,
                detail=character.detail,
                name=character.name,
                on_step=lambda step: progress.set_step(character.id, step),
            )
        progress.set_step(character.id, "Generating South")
        if pack:
            generated = GeneratedImage(pack["south"], pack.get("seed", chosen_seed), prompt)
            generated.external_id = pack.get("external_id")
            generated.direction_images = pack.get("directions")
            sprite, preview, validation = process_generated(character, generated.image, direction="S", for_base=True)
            used_reference = False
            if pack.get("external_id"):
                character.externalProviderId = provider.info.id
                character.externalCharacterId = pack["external_id"]
        else:
            generated = provider.generate_south(prompt, seed=chosen_seed, size=character.spriteSize, view=character.camera)
            sprite, preview, validation = process_generated(character, generated.image, direction="S", for_base=True)
            used_reference = False
        if generated.debug:
            generated.debug.referenceDirection = "S"
        anchor = estimate_head_anchor(sprite, character.spriteSize)
        asset = make_asset(
            character,
            sprite,
            "base/pending.png",
            prompt.final,
            generated.seed,
            "full",
            validation,
            anchor,
            preview,
            source=generated.image,
            negative=prompt.negative,
            debug=generated.debug,
            from_direction="S",
            reference_direction="S",
        )
        character.pendingBase = asset
        _sync_south_slot(character, asset)
        character_service.save_character(character)
        log_generation(
            "generate_base",
            character,
            direction="S",
            state=idle.id if idle else "idle",
            seed=generated.seed,
            path=asset.path,
            previewPath=asset.previewPath,
            sourcePath=asset.sourcePath,
            prompt=prompt.final,
            negative=prompt.negative,
        )
        return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}
    except Exception:
        logger.exception("generate_base failed characterId=%s", character_id)
        raise
    finally:
        if not nested:
            progress.finish(character_id)


def _idle_state(character: CharacterProfile):
    for state in character.states:
        if state.baseType == "idle" or state.name.lower() == "idle":
            return state
    return character.states[0] if character.states else None


def _sync_south_slot(character: CharacterProfile, asset: SpriteAsset) -> None:
    state = _idle_state(character)
    if state is None:
        return
    character_service.ensure_slots(state, character.spriteSize)
    try:
        slot = character_service.find_slot(state, "S")
    except KeyError:
        return
    if slot.locked or slot.status in ("accepted", "locked"):
        return
    south = asset.model_copy(update={"fromDirection": "S", "referenceDirection": "S", "status": "pending", "accepted": False})
    slot.frames = [south]
    slot.candidates = [south]
    slot.status = "pending"
    slot.seed = south.seed
    if asset.head:
        slot.headAnchor = asset.head


def _copy_pending_to_accepted(character: CharacterProfile, lock_palette: bool) -> CharacterProfile:
    pending = _require_valid_pending_base(character)
    sprite_image = load_image(pending.path)
    if sprite_image is None:
        raise ValueError("Pending sprite file is missing")
    preview_image = load_image(pending.previewPath) if pending.previewPath else None
    if preview_image is None:
        preview_image = make_preview(sprite_image)
    accepted_path = save_image(character.slug, "base/accepted.png", sprite_image)
    accepted_preview = save_image(character.slug, "base/accepted-preview.png", preview_image)
    source_image = load_image(pending.sourcePath) if pending.sourcePath else None
    accepted_source = ""
    if source_image is not None:
        accepted_source = save_image(character.slug, "base/accepted-source.png", source_image)
    accepted_asset = pending.model_copy(
        update={
            "id": new_id(),
            "path": accepted_path,
            "previewPath": accepted_preview,
            "sourcePath": accepted_source or pending.sourcePath,
            "accepted": True,
            "status": "accepted",
            "createdAt": utc_now(),
        }
    )
    character.acceptedBase = AcceptedBase(
        sprite=accepted_asset,
        acceptedAt=utc_now(),
        seed=accepted_asset.seed,
        prompt=accepted_asset.prompt,
    )
    if lock_palette:
        palette = extract_palette(sprite_image, character.palette.colorCount)
        character.palette.colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette]
        character.palette.locked = True
        character.identityLock.lockPalette = True
        character.paletteMode = "accepted"
    saved = character_service.save_character(character)
    memory.record(saved, "accepted", accepted_asset, state_name="base", provider_id=get_provider().info.id)
    return saved


def accept_base(character_id: str, lock_palette: bool = True, palette_mode: str = "accepted") -> CharacterProfile:
    character = character_service.get_character(character_id)
    saved = _copy_pending_to_accepted(character, lock_palette)
    if lock_palette and palette_mode in ("soft", "strict", "unlocked"):
        saved.paletteMode = palette_mode
        if saved.paletteMode == "unlocked":
            saved.palette.locked = False
        character_service.save_character(saved)
    return saved


def replace_base(character_id: str) -> CharacterProfile:
    character = character_service.get_character(character_id)
    return _copy_pending_to_accepted(character, lock_palette=True)


def clear_reference(character_id: str) -> CharacterProfile:
    character = character_service.get_character(character_id)
    character.acceptedBase = None
    return character_service.save_character(character)


def discard_pending(character_id: str) -> CharacterProfile:
    character = character_service.get_character(character_id)
    character.pendingBase = None
    return character_service.save_character(character)


def reprocess_from_source(character_id: str) -> dict:
    nested = _track(character_id, "Re-pixelizing source")
    try:
        character = character_service.get_character(character_id)
        pending = character.pendingBase
        accepted = character.acceptedBase.sprite if character.acceptedBase else None
        source_asset = pending or accepted
        if source_asset is None:
            raise ValueError("No source image to re-pixelize. Generate a base first.")
        source = load_image(source_asset.sourcePath) if source_asset.sourcePath else None
        if source is None:
            source = load_image(source_asset.path)
        if source is None:
            raise ValueError("Source image file is missing")
        sprite, preview, validation = process_generated(character, source, for_base=True)
        asset = make_asset(
            character,
            sprite,
            "base/pending.png",
            source_asset.prompt,
            source_asset.seed,
            "full",
            validation,
            estimate_head_anchor(sprite, character.spriteSize),
            preview,
            source=source,
            negative=source_asset.negativePrompt,
        )
        character.pendingBase = asset
        character_service.save_character(character)
        return {
            "character": character,
            "prompt": build_prompt(character),
            "usedReference": False,
            "asset": asset,
        }
    finally:
        if not nested:
            progress.finish(character_id)


def generate_variation(character_id: str, seed: int | None = None, override: str = "") -> dict:
    nested = _track(character_id, "Generating variation")
    try:
        character = character_service.get_character(character_id)
        if character.acceptedBase is None:
            raise ValueError("Accept a base character before generating a variation")
        prompt = build_prompt(character, override=override or "subtle identity-preserving variation")
        generated, sprite, preview, validation, used_reference = generate_image(
            character, prompt, use_reference=True, seed=seed or character.seed, strength=0.35, for_base=True
        )
        anchor = estimate_head_anchor(sprite, character.spriteSize)
        asset = make_asset(
            character,
            sprite,
            "base/pending.png",
            prompt.final,
            generated.seed,
            "full",
            validation,
            anchor,
            preview,
            from_direction="S",
            reference_direction="S",
        )
        character.pendingBase = asset
        _sync_south_slot(character, asset)
        character_service.save_character(character)
        return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}
    finally:
        if not nested:
            progress.finish(character_id)


def generate_direction(
    character_id: str,
    state_id: str,
    direction: Direction,
    frame_index: int = 0,
    layer: LayerKind = "full",
    use_reference: bool = True,
    seed: int | None = None,
    override: str = "",
    from_direction: Direction | None = None,
    strength: float = 0.42,
    job_id: str | None = None,
    candidate_count: int | None = None,
) -> dict:
    nested = _track(character_id, "Generating direction")
    try:
        character = character_service.get_character(character_id)
        state = character_service.find_state(character, state_id)
        character_service.ensure_slots(state, character.spriteSize)
        slot = character_service.find_slot(state, direction)
        if slot.locked and frame_index == 0:
            return {
                "character": character,
                "prompt": build_prompt(character, state, direction),
                "usedReference": False,
                "asset": slot.frames[0] if slot.frames else None,
                "candidates": slot.candidates,
            }
        hints = memory.generation_hints(character.id, direction)
        strength = max(0.12, min(0.85, strength + hints["strength_delta"]))
        if use_reference and usable_accepted_base(character) is not None:
            use_reference = True
        requested_from = from_direction
        if requested_from is None and getattr(character, "rotationStrategy", "stable") == "incremental":
            from domain.rotation import INCREMENTAL_CHAINS
            for chain in INCREMENTAL_CHAINS:
                if direction in chain:
                    index = chain.index(direction)
                    if index > 0:
                        requested_from = chain[index - 1]
                        break
        from_dir, ref_asset_id, ref_image = resolve_direction_reference(
            character, state, direction, requested_from, use_reference
        )
        prompt = build_prompt(
            character,
            state=state,
            direction=direction,
            override=override,
            layer=layer,
            frame_index=frame_index,
            frame_count=state.frameCount,
            from_direction=from_dir,  # type: ignore[arg-type]
            extra_clauses=hints["extra_clauses"],
        )
        chosen_seed = resolve_seed(character, seed if seed is not None else slot.seed, "reuse_base")
        log_generation(
            "generate_direction",
            character,
            direction=direction,
            state=state.id,
            slotStatus=slot.status,
            seed=chosen_seed,
            fromDirection=from_dir,
            prompt=prompt.final,
            negative=prompt.negative,
        )
        native_images = native_direction_images(character, prompt, chosen_seed)
        if native_images.get(direction):
            asset = _save_direction_image(
                character,
                state,
                slot,
                direction,
                native_images[direction],
                prompt,
                chosen_seed,
                from_dir,  # type: ignore[arg-type]
                reference_asset_id=ref_asset_id,
                strength=strength,
            )
            slot.candidates = [asset]
            character_service.save_character(character)
            if job_id:
                jobs.set_progress(job_id, 1, 1, direction, "processing")
            return {
                "character": character,
                "prompt": prompt,
                "usedReference": True,
                "asset": asset,
                "candidates": slot.candidates,
            }

        count = candidate_count or config.CANDIDATE_COUNT
        if layer != "full":
            count = 1
        candidates: list[SpriteAsset] = []
        used_reference = False
        provider = get_provider()
        for index in range(count):
            cand_seed = None if chosen_seed is None else chosen_seed + index * 7919
            if ref_image is not None:
                generated = provider.rotate_sprite(
                    ref_image,
                    from_dir or "S",
                    direction,
                    prompt,
                    seed=cand_seed,
                    from_view=character.camera,
                    to_view=character.camera,
                    strength=strength,
                    size=character.spriteSize,
                )
                used_reference = True
                sprite, preview, validation = process_generated(character, generated.image, direction=direction)
            elif direction == "S":
                generated = provider.generate_south(prompt, seed=cand_seed, size=character.spriteSize, view=character.camera)
                sprite, preview, validation = process_generated(character, generated.image, direction="S", for_base=True)
            else:
                raise ValueError("Direction generation needs an accepted South reference. Generate and accept a South sprite first.")
            if not slot.frames and index == 0:
                slot.headAnchor = estimate_head_anchor(sprite, character.spriteSize)
            relative = f"states/{state.id}/{direction}/{layer}_frame_{frame_index:02d}_c{index}.png"
            debug = generated.debug
            if debug:
                debug.usedReference = used_reference
                debug.referenceDirection = from_dir
                debug.referenceAssetId = ref_asset_id
                debug.strength = strength
                debug.targetDirection = direction
                debug.artifactDetected = bool(getattr(validation, "artifactDetected", False))
                debug.compositionFailed = bool(getattr(validation, "compositionFailed", False))
                debug.directionScore = getattr(validation, "directionScore", None)
            ref_file = ""
            if character.acceptedBase and (from_dir in (None, "S") or ref_asset_id == character.acceptedBase.sprite.id):
                ref_file = character.acceptedBase.sprite.path
            asset = make_asset(
                character,
                sprite,
                relative,
                prompt.final,
                generated.seed,
                layer,
                validation,
                slot.headAnchor,
                preview,
                source=generated.image,
                negative=prompt.negative,
                from_direction=from_dir,  # type: ignore[arg-type]
                reference_direction=from_dir,  # type: ignore[arg-type]
                reference_asset_id=ref_asset_id,
                reference_state=state.id,
                reference_file=ref_file,
                strength=strength,
                debug=debug,
            )
            candidates.append(asset)

        if layer == "full":
            slot.candidates = candidates
            usable = [item for item in candidates if is_valid_direction(item.validation)]
            preview_asset = max(
                usable or candidates,
                key=lambda item: (
                    (item.validation.score if item.validation else 0),
                    (item.validation.directionScore if item.validation else 0),
                ),
            )
            accepted = slot.status in ("accepted", "locked") or slot.locked
            if not accepted:
                while len(slot.frames) <= frame_index:
                    slot.frames.append(preview_asset)
                slot.frames[frame_index] = preview_asset
                if usable:
                    slot.status = "pending"
                    preview_asset.status = "pending"
                else:
                    slot.status = "rejected"
                    preview_asset.status = "rejected"
                slot.seed = preview_asset.seed
                if state.headSeparated:
                    sprite_image = load_image(preview_asset.path)
                    if sprite_image is not None:
                        head, body = split_head_body(sprite_image, slot.headAnchor)
                        slot.head = make_asset(
                            character,
                            head,
                            f"states/{state.id}/{direction}/head.png",
                            prompt.final,
                            preview_asset.seed,
                            "head",
                            preview_asset.validation,
                            slot.headAnchor,
                            negative=prompt.negative,
                        )
                        slot.body = make_asset(
                            character,
                            body,
                            f"states/{state.id}/{direction}/body.png",
                            prompt.final,
                            preview_asset.seed,
                            "body",
                            preview_asset.validation,
                            slot.headAnchor,
                            negative=prompt.negative,
                        )
            asset = preview_asset if not accepted else (slot.frames[0] if slot.frames else preview_asset)
        elif layer == "head":
            slot.head = candidates[0]
            asset = candidates[0]
        else:
            slot.body = candidates[0]
            asset = candidates[0]
        character_service.save_character(character)
        if job_id:
            jobs.set_progress(job_id, 1, 1, direction, "processing")
        return {
            "character": character,
            "prompt": prompt,
            "usedReference": used_reference,
            "asset": asset,
            "candidates": candidates,
        }
    finally:
        if not nested:
            progress.finish(character_id)


def generate_state(
    character_id: str,
    state_id: str,
    use_reference: bool = True,
    seed: int | None = None,
    override: str = "",
) -> dict:
    nested = _track(character_id, "Generating state")
    try:
        character = character_service.get_character(character_id)
        state = character_service.find_state(character, state_id)
        if usable_accepted_base(character) is not None:
            use_reference = True
        last = {"character": character, "prompt": PromptLayers(), "usedReference": False, "asset": None}
        for direction in state.selectedDirections:
            slot = character_service.find_slot(state, direction)
            if slot.locked or slot.status in ("accepted", "locked"):
                continue
            for frame_index in range(state.frameCount):
                last = generate_direction(
                    character_id,
                    state_id,
                    direction,
                    frame_index=frame_index,
                    use_reference=use_reference,
                    seed=None if seed is None else seed + frame_index,
                    override=override,
                )
        return last
    finally:
        if not nested:
            progress.finish(character_id)


def generate_missing_directions(character_id: str, state_id: str, use_reference: bool = True) -> dict:
    nested = _track(character_id, "Generating missing directions")
    try:
        character = character_service.get_character(character_id)
        state = character_service.find_state(character, state_id)
        last = {"character": character, "prompt": PromptLayers(), "usedReference": False, "asset": None}
        for direction in state.selectedDirections:
            slot = character_service.find_slot(state, direction)
            if slot.locked or slot.status in ("accepted", "locked"):
                continue
            for frame_index in range(state.frameCount):
                if frame_index < len(slot.frames) and slot.frames[frame_index].path and slot.status not in ("rejected", "missing"):
                    continue
                last = generate_direction(character_id, state_id, direction, frame_index, use_reference=use_reference)
        return last
    finally:
        if not nested:
            progress.finish(character_id)


def generate_all_states(character_id: str, use_reference: bool = True) -> dict:
    nested = _track(character_id, "Generating all states")
    try:
        character = character_service.get_character(character_id)
        last = {"character": character, "prompt": PromptLayers(), "usedReference": False, "asset": None}
        for state in character.states:
            last = generate_state(character_id, state.id, use_reference=use_reference)
        return last
    finally:
        if not nested:
            progress.finish(character_id)


def generate_head_variants(
    character_id: str,
    state_id: str,
    direction: Direction,
    variants: list[HeadVariant] | None = None,
    use_reference: bool = True,
) -> dict:
    nested = _track(character_id, "Generating head variants")
    try:
        character = character_service.get_character(character_id)
        state = character_service.find_state(character, state_id)
        slot = character_service.find_slot(state, direction)
        wanted = variants or list(HEAD_VARIANTS)
        source = None
        if slot.frames:
            source = load_image(slot.frames[0].path)
        elif character.acceptedBase:
            source = load_image(character.acceptedBase.sprite.path)
        last = {"character": character, "prompt": PromptLayers(), "usedReference": False, "asset": None}
        for variant in wanted:
            progress.set_step(character_id, "Generating sprite")
            prompt = build_prompt(character, state=state, direction=direction, layer="head", head_variant=variant)
            provider = get_provider()
            used_reference = False
            if source is not None and provider.info.supportsReference and use_reference:
                head_layer, _body = split_head_body(source, slot.headAnchor)
                generated = provider.generate_from_reference(prompt, head_layer, seed=character.seed, strength=0.38)
                used_reference = True
            else:
                generated = provider.generate_head_variant(prompt, seed=character.seed)
            sprite, preview, validation = process_generated(character, generated.image)
            head_layer, _ = split_head_body(sprite, slot.headAnchor)
            asset = make_asset(
                character,
                head_layer,
                f"head/{state.id}/{direction}/{variant}.png",
                prompt.final,
                generated.seed,
                "head",
                validation,
                slot.headAnchor,
                preview,
            )
            slot.headVariants[variant] = asset
            last = {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}
        character_service.save_character(character)
        return last
    finally:
        if not nested:
            progress.finish(character_id)


def update_anchors(
    character_id: str,
    state_id: str,
    direction: Direction,
    head_anchor_x: int,
    head_anchor_y: int,
    head_offset_x: int = 0,
    head_offset_y: int = 0,
) -> CharacterProfile:
    character = character_service.get_character(character_id)
    state = character_service.find_state(character, state_id)
    slot = character_service.find_slot(state, direction)
    slot.headAnchor = HeadAnchor(
        headAnchorX=head_anchor_x,
        headAnchorY=head_anchor_y,
        headOffsetX=head_offset_x,
        headOffsetY=head_offset_y,
    )
    if slot.frames and state.headSeparated:
        image = load_image(slot.frames[0].path)
        if image is not None:
            head, body = split_head_body(image, slot.headAnchor)
            slot.head = make_asset(
                character,
                head,
                f"states/{state.id}/{direction}/head.png",
                slot.frames[0].prompt,
                slot.frames[0].seed,
                "head",
                slot.frames[0].validation,
                slot.headAnchor,
            )
            slot.body = make_asset(
                character,
                body,
                f"states/{state.id}/{direction}/body.png",
                slot.frames[0].prompt,
                slot.frames[0].seed,
                "body",
                slot.frames[0].validation,
                slot.headAnchor,
            )
    return character_service.save_character(character)


def apply_master_prompt(
    character_id: str,
    master_prompt: str,
    apply_mode: str,
    state_id: str | None = None,
    direction: Direction | None = None,
) -> dict:
    character = character_service.get_character(character_id)
    character.masterPrompt = master_prompt
    character_service.save_character(character)
    if apply_mode == "future_only":
        return {"character": character, "prompt": build_prompt(character), "usedReference": False, "asset": None}
    if apply_mode == "regenerate_current_state":
        if not state_id:
            raise ValueError("stateId is required to regenerate the current state")
        return generate_state(character_id, state_id)
    if apply_mode == "regenerate_selected_direction":
        if not state_id or not direction:
            raise ValueError("stateId and direction are required")
        return generate_direction(character_id, state_id, direction)
    if apply_mode == "regenerate_all_states":
        return generate_all_states(character_id)
    if apply_mode == "regenerate_head_layers":
        if not state_id or not direction:
            raise ValueError("stateId and direction are required to regenerate head layers")
        return generate_head_variants(character_id, state_id, direction)
    raise ValueError(f"Unknown apply mode: {apply_mode}")


def native_direction_images(character: CharacterProfile, prompt: PromptLayers, seed: int | None = None):
    provider = get_provider()
    if not provider.capabilities.nativePixelOutput:
        return {}
    on_step = lambda step: progress.set_step(character.id, step)
    if character.externalCharacterId and hasattr(provider, "fetch_rotations"):
        try:
            return provider.fetch_rotations(character.externalCharacterId, on_step=on_step)
        except Exception:
            pass
    ref = reference_image(character)
    if ref is None or not hasattr(provider, "rotate_reference"):
        return {}
    return provider.rotate_reference(ref, provider_prompt(character, prompt), seed, on_step=on_step)


def _save_direction_image(
    character: CharacterProfile,
    state,
    slot,
    direction: Direction,
    image: Image.Image,
    prompt: PromptLayers,
    seed: int | None,
    from_dir: Direction | None,
    reference_asset_id: str = "",
    strength: float | None = None,
    debug: GenerationDebug | None = None,
):
    sprite, preview, validation = process_generated(character, image, direction=direction)
    if not slot.frames:
        slot.headAnchor = estimate_head_anchor(sprite, character.spriteSize)
    relative = f"states/{state.id}/{direction}/full_frame_00.png"
    ref_file = ""
    if character.acceptedBase:
        ref_file = character.acceptedBase.sprite.path
    asset = make_asset(
        character,
        sprite,
        relative,
        prompt.final,
        seed,
        "full",
        validation,
        slot.headAnchor,
        preview,
        source=image,
        negative=prompt.negative,
        from_direction=from_dir,
        reference_direction=from_dir,
        reference_asset_id=reference_asset_id,
        reference_state=state.id,
        reference_file=ref_file,
        strength=strength,
        debug=debug,
    )
    if slot.status not in ("accepted", "locked") and not slot.locked:
        if not slot.frames:
            slot.frames.append(asset)
        else:
            slot.frames[0] = asset
        slot.status = "pending"
        slot.seed = seed
    slot.candidates = [asset]
    return asset


def require_direction_set(character_id: str, state_id: str | None = None) -> tuple[CharacterProfile, str]:
    character = character_service.get_character(character_id)
    if character.acceptedBase is not None:
        accepted_validation = _revalidate_base_asset(character, character.acceptedBase.sprite)
        character.acceptedBase.sprite.validation = accepted_validation
        character_service.save_character(character)
    resolved = state_id or (character.states[0].id if character.states else "")
    if not resolved:
        raise ValueError("Create a state before generating directions")
    return character, resolved


def generate_direction_set(
    character_id: str,
    state_id: str | None = None,
    use_reference: bool = True,
    seed: int | None = None,
    override: str = "",
    strength: float = 0.38,
    job_id: str | None = None,
    candidate_count: int | None = None,
    rotation_strategy: str | None = None,
) -> dict:
    character, state_id = require_direction_set(character_id, state_id)
    state = character_service.find_state(character, state_id)
    character_service.ensure_slots(state, character.spriteSize)
    wanted = [direction for direction in EXPORT_DIRECTION_ORDER if direction in state.selectedDirections]
    prompt = build_prompt(character, state=state, override=override, from_direction="S")
    log_generation(
        "generate_all_directions",
        character,
        state=state_id,
        prompt=prompt.final,
        negative=prompt.negative,
        acceptedBase=character.acceptedBase.sprite.path if character.acceptedBase else "",
        directions=",".join(wanted),
    )
    last = {"character": character, "prompt": prompt, "usedReference": False, "asset": None, "candidates": []}
    skippable = lambda slot: slot.locked or slot.status in ("accepted", "locked")
    strategy = rotation_strategy or getattr(character, "rotationStrategy", None) or "stable"
    if strategy in ("stable", "incremental") and character.rotationStrategy != strategy:
        character.rotationStrategy = strategy
        character_service.save_character(character)
    if usable_accepted_base(character) is None:
        south = character_service.find_slot(state, "S")
        if not skippable(south):
            if job_id:
                jobs.set_progress(job_id, 0, 8, "Generating South", "generating")
            last = generate_base(character_id, seed=seed, override=override)
            character = character_service.get_character(character_id)
            state = character_service.find_state(character, state_id)
            south = character_service.find_slot(state, "S")
            south_validation = character.pendingBase.validation if character.pendingBase else (
                south.frames[0].validation if south.frames else None
            )
            if not is_valid_base(south_validation) and not is_valid_direction(south_validation):
                if south.frames:
                    south.status = "rejected"
                    south.frames[0].status = "rejected"
                    character_service.save_character(character)
                raise ValueError(
                    "South failed validation and was not used as a reference for the other directions. "
                    "Review or regenerate South, then Accept as Base."
                )
    reference = identity_sprite(character)
    if reference is None:
        south = character_service.find_slot(state, "S")
        if south.frames:
            reference = load_image(south.frames[0].sourcePath or south.frames[0].path)
    if reference is None and character.pendingBase:
        reference = load_image(character.pendingBase.sourcePath or character.pendingBase.path)
    if reference is None:
        raise ValueError("Generate and accept a South sprite before generating the other directions.")
    provider = get_provider()

    def on_progress(current: int, total: int, item: str) -> None:
        progress.set_step(character.id, item)
        if job_id:
            jobs.set_progress(job_id, current, total, item, "generating")

    generated_map = provider.generate_8_directions(
        reference,
        prompt,
        seed=seed,
        view=character.camera,
        size=character.spriteSize,
        palette=palette_colors(character),
        strategy=strategy,
        on_progress=on_progress,
    )
    for direction in wanted:
        slot = character_service.find_slot(state, direction)
        if skippable(slot):
            continue
        generated = generated_map.get(direction)
        if generated is None:
            continue
        from_dir = getattr(generated.debug, "referenceDirection", None) or "S"
        asset = _save_direction_image(
            character,
            state,
            slot,
            direction,
            generated.image,
            prompt,
            generated.seed,
            from_dir,
            debug=generated.debug,
        )
        last = {"character": character, "prompt": prompt, "usedReference": True, "asset": asset, "candidates": slot.candidates}
    character_service.save_character(character)
    last["character"] = character
    return last


def remove_direction(character_id: str, state_id: str, direction: Direction) -> CharacterProfile:
    character = character_service.get_character(character_id)
    state = character_service.find_state(character, state_id)
    slot = character_service.find_slot(state, direction)
    if slot.locked or slot.status == "locked":
        raise ValueError("Locked directions cannot be removed. Unlock first.")
    log_generation("remove_direction", character, direction=direction, state=state_id, previousStatus=slot.status)
    folder = character_dir(character.slug) / "states" / state.id / direction
    if folder.exists() and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
    slot.frames = []
    slot.candidates = []
    slot.body = None
    slot.head = None
    slot.overlays = []
    slot.headVariants = {}
    slot.status = "missing"
    slot.locked = False
    slot.seed = None
    return character_service.save_character(character)


def set_direction_status(
    character_id: str,
    state_id: str,
    direction: Direction,
    status: str,
    reason=None,
    custom_reason: str = "",
) -> CharacterProfile:
    character = character_service.get_character(character_id)
    slot = character_service.find_slot(character_service.find_state(character, state_id), direction)
    if status == "locked":
        slot.locked = True
        slot.status = "locked"
    elif status == "accepted":
        slot.locked = False
        slot.status = "accepted"
        if slot.frames:
            slot.frames[0].accepted = True
            slot.frames[0].status = "accepted"
            memory.record(character, "accepted", slot.frames[0], state_name=character_service.find_state(character, state_id).name, direction=direction, provider_id=get_provider().info.id)
    elif status == "rejected":
        slot.locked = False
        slot.status = "rejected"
        if slot.frames:
            slot.frames[0].status = "rejected"
            memory.record(character, "rejected", slot.frames[0], state_name=character_service.find_state(character, state_id).name, direction=direction, reason=reason, custom_reason=custom_reason, provider_id=get_provider().info.id)
    elif status == "unlocked":
        slot.locked = False
        slot.status = "pending" if slot.frames else "missing"
    return character_service.save_character(character)


def accept_candidate(character_id: str, state_id: str, direction: Direction, asset_id: str) -> CharacterProfile:
    character = character_service.get_character(character_id)
    state = character_service.find_state(character, state_id)
    slot = character_service.find_slot(state, direction)
    if slot.locked:
        raise ValueError("Direction is locked")
    chosen = next((item for item in slot.candidates if item.id == asset_id), None)
    if chosen is None and slot.frames:
        chosen = next((item for item in slot.frames if item.id == asset_id), None)
    if chosen is None:
        raise ValueError("Candidate not found")
    chosen = chosen.model_copy(update={"accepted": True, "status": "accepted"})
    if slot.frames:
        slot.frames[0] = chosen
    else:
        slot.frames.append(chosen)
    slot.status = "accepted"
    slot.locked = False
    slot.seed = chosen.seed
    slot.candidates = [item for item in slot.candidates if item.id != asset_id]
    memory.record(character, "accepted", chosen, state_name=state.name, direction=direction, provider_id=get_provider().info.id)
    return character_service.save_character(character)


def generate_animation(
    character_id: str,
    state_id: str,
    direction: Direction,
    frame_count: int = 8,
    action: str = "",
    use_reference: bool = True,
    seed: int | None = None,
    job_id: str | None = None,
) -> dict:
    character = character_service.get_character(character_id)
    state = character_service.find_state(character, state_id)
    slot = character_service.find_slot(state, direction)
    if slot.locked:
        raise ValueError("Direction is locked")
    state.frameCount = frame_count
    state.kind = "animated" if frame_count > 1 else "static"
    init = None
    if slot.frames:
        init = load_image(slot.frames[0].sourcePath or slot.frames[0].path)
    elif character.acceptedBase:
        init = load_image(character.acceptedBase.sprite.sourcePath or character.acceptedBase.sprite.path)
    if init is None:
        raise ValueError("Animation needs an existing accepted state or direction sprite. Do not generate frames from text alone.")
    prompt = build_prompt(
        character, state=state, direction=direction, action=action or state.customPrompt, frame_count=frame_count, from_direction="S"
    )
    provider = get_provider()
    frames = provider.generate_animation_frames(prompt, frame_count, seed=resolve_seed(character, seed), init_image=init)
    last_asset = None
    for index, generated in enumerate(frames):
        _job_step(character.id, f"Generating animation {index + 1}/{frame_count}", "generating")
        if job_id:
            jobs.set_progress(job_id, index + 1, frame_count, f"Generating animation {index + 1}/{frame_count}", "generating")
        sprite, preview, validation = process_generated(character, generated.image)
        asset = make_asset(
            character,
            sprite,
            f"states/{state.id}/{direction}/full_frame_{index:02d}.png",
            prompt.final,
            generated.seed,
            "full",
            validation,
            slot.headAnchor,
            preview,
            source=generated.image,
            negative=prompt.negative,
        )
        while len(slot.frames) <= index:
            slot.frames.append(asset)
        slot.frames[index] = asset
        last_asset = asset
    slot.status = "pending"
    character_service.save_character(character)
    return {"character": character, "prompt": prompt, "usedReference": bool(init) and use_reference, "asset": last_asset}


def refine_asset(
    character_id: str,
    state_id: str | None = None,
    direction: Direction | None = None,
    frame_index: int = 0,
    strength: float = 0.35,
    seed: int | None = None,
    override: str = "",
    use_as_reference: bool = True,
) -> dict:
    character = character_service.get_character(character_id)
    init = None
    if state_id and direction:
        slot = character_service.find_slot(character_service.find_state(character, state_id), direction)
        if slot.locked:
            raise ValueError("Direction is locked")
        if slot.frames:
            frame = slot.frames[min(frame_index, len(slot.frames) - 1)]
            init = load_image(frame.sourcePath or frame.path)
        return generate_direction(
            character_id,
            state_id,
            direction,
            frame_index=frame_index,
            seed=seed,
            override=override,
            strength=strength,
            use_reference=use_as_reference,
        )
    if character.pendingBase:
        init = load_image(character.pendingBase.sourcePath or character.pendingBase.path)
    prompt = build_prompt(character, override=override)
    generated, sprite, preview, validation, used_reference = generate_image(
        character, prompt, use_reference=use_as_reference, seed=resolve_seed(character, seed, "variation"), strength=strength, init_image=init, for_base=True
    )
    asset = make_asset(
        character, sprite, "base/pending.png", prompt.final, generated.seed, "full", validation, estimate_head_anchor(sprite, character.spriteSize), preview, source=generated.image, negative=prompt.negative
    )
    character.pendingBase = asset
    character_service.save_character(character)
    return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}


def use_as_reference(character_id: str, state_id: str, direction: Direction) -> CharacterProfile:
    character = set_direction_status(character_id, state_id, direction, "accepted")
    state = character_service.find_state(character, state_id)
    slot = character_service.find_slot(state, direction)
    if not slot.frames:
        raise ValueError("No sprite to use as reference")
    if direction == "S":
        character.pendingBase = slot.frames[0]
        return _copy_pending_to_accepted(character, lock_palette=True)
    return character


def inpaint_placeholder() -> None:
    raise ValueError("Inpainting is not available on the current provider. The API is ready for a provider that supports masks.")


def start_job(character_id: str, operation: str, label: str, total: int | None, fn) -> dict:
    job = jobs.create(character_id, operation, label, total)

    def work(_job):
        return fn(job.id)

    jobs.run_in_background(job, work)
    return {"job": job, "character": character_service.get_character(character_id)}

