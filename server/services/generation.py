from datetime import datetime, timezone
from random import randint
from uuid import uuid4

from PIL import Image

import config
from domain.directions import EXPORT_DIRECTION_ORDER, HEAD_VARIANTS, closest_reference
from models.character import AcceptedBase, CharacterProfile, GenerationDebug, HeadAnchor, SpriteAsset
from models.enums import Direction, HeadVariant, LayerKind
from models.generation import PromptLayers
from persistence.store import asset_path
from processing.layers import split_head_body
from processing.pipeline import PixelPipeline, estimate_head_anchor, extract_palette
from processing.preview import make_preview, preview_relative
from prompts.builder import build_prompt, build_pixellab_description
from prompts.composition import FRAMING_RETRY
from providers.base import DirectionSpec, GeneratedImage
from providers.registry import get_provider
from services import characters as character_service
from services import jobs
from services import memory
from services import progress

pipeline = PixelPipeline()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex


def public_path(slug: str, relative: str) -> str:
    return f"characters/{slug}/{relative}".replace("\\", "/")


def save_image(slug: str, relative: str, image: Image.Image) -> str:
    path = asset_path(slug, relative)
    image.save(path, format="PNG")
    return public_path(slug, relative)


def load_image(relative: str | None) -> Image.Image | None:
    if not relative:
        return None
    path = config.DATA_DIR / relative
    if not path.exists():
        return None
    return Image.open(path).convert("RGBA")


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
    return mode


def palette_colors(character: CharacterProfile) -> list[tuple[int, int, int]] | None:
    mode = palette_mode_name(character)
    if mode in ("strict", "soft", "custom", "project") or (
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


def identity_sprite(character: CharacterProfile) -> Image.Image | None:
    if character.acceptedBase is None:
        return None
    return load_image(character.acceptedBase.sprite.path)


def process_generated(character: CharacterProfile, image: Image.Image, direction=None):
    provider = get_provider()
    native = provider.capabilities.nativePixelOutput
    skip_palette = native and provider.info.id == "pixellab"
    working = character.spriteSize if native else max(character.spriteSize, config.WORKING_SIZE)
    comp = character.composition
    margin = 0.10 if comp.fitSafeMargins or comp.preventCropping else 0.04
    return pipeline.process(
        image,
        character.spriteSize,
        character.palette.colorCount,
        character.outline,
        False if native else config.ENABLE_BG_REMOVAL,
        None if skip_palette else palette_colors(character),
        on_step=lambda step: progress.set_step(character.id, step),
        native=native,
        working_size=working,
        palette_mode=palette_mode_name(character),
        reference=identity_sprite(character),
        direction=direction,
        fit_margin=margin,
        center=comp.centerCharacter,
        spirit_form=character.spirit.enabled or character.spirit.noLegs,
    )


def looks_cropped(validation) -> bool:
    if validation is None:
        return False
    return any(warning.code in {"likely_cropped", "touches_edges", "silhouette_incomplete"} for warning in validation.warnings)


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
    debug.strength = strength if strength is not None else debug.strength
    debug.usedReference = debug.usedReference or bool(reference_asset_id or reference_direction)
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
):
    provider = get_provider()
    attempts = 1
    if (
        allow_crop_retry
        and character.composition.preventCropping
        and not provider.capabilities.nativePixelOutput
    ):
        attempts = 2
    last = None
    retries = 0
    working_prompt = prompt
    working_seed = seed
    for attempt in range(attempts):
        if attempt > 0:
            retries = attempt
            progress.set_step(character.id, "retrying cropped sprite")
            working_prompt = prompt.model_copy(
                update={
                    "override": ", ".join(part for part in (prompt.override, FRAMING_RETRY) if part),
                    "composition": ", ".join(part for part in (prompt.composition, FRAMING_RETRY) if part),
                    "final": f"{prompt.final}, {FRAMING_RETRY}",
                }
            )
            working_seed = None if seed is None else seed + 17 * attempt
        progress.set_step(character.id, "generating source image")
        model_prompt = provider_prompt(character, working_prompt)
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
        sprite, preview, validation = process_generated(character, generated.image, direction=direction)
        if generated.debug:
            generated.debug.cropRetries = retries
            generated.debug.prompt = working_prompt.final
        last = (generated, sprite, preview, validation, used_reference)
        if not looks_cropped(validation):
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
    nested = _track(character_id, "Generating base")
    try:
        character = character_service.get_character(character_id)
        prompt = build_prompt(character, override=override)
        provider = get_provider()
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
        if pack:
            generated = GeneratedImage(pack["south"], pack.get("seed", chosen_seed), prompt)
            generated.external_id = pack.get("external_id")
            generated.direction_images = pack.get("directions")
            sprite, preview, validation = process_generated(character, generated.image)
            used_reference = False
            if pack.get("external_id"):
                character.externalProviderId = provider.info.id
                character.externalCharacterId = pack["external_id"]
        else:
            generated, sprite, preview, validation, used_reference = generate_image(
                character, prompt, use_reference=False, seed=chosen_seed
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
            source=generated.image,
            negative=prompt.negative,
            debug=generated.debug,
        )
        character.pendingBase = asset
        character_service.save_character(character)
        return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}
    finally:
        if not nested:
            progress.finish(character_id)


def _copy_pending_to_accepted(character: CharacterProfile, lock_palette: bool) -> CharacterProfile:
    pending = character.pendingBase
    if pending is None:
        raise ValueError("No pending sprite to promote")
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
        character.paletteMode = "soft"
    saved = character_service.save_character(character)
    memory.record(saved, "accepted", accepted_asset, state_name="base", provider_id=get_provider().info.id)
    return saved


def accept_base(character_id: str, lock_palette: bool = True, palette_mode: str = "soft") -> CharacterProfile:
    character = character_service.get_character(character_id)
    saved = _copy_pending_to_accepted(character, lock_palette)
    if lock_palette:
        saved.paletteMode = palette_mode if palette_mode in ("soft", "strict", "unlocked") else "soft"
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
        sprite, preview, validation = process_generated(character, source)
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
            character, prompt, use_reference=True, seed=seed or character.seed, strength=0.35
        )
        anchor = estimate_head_anchor(sprite, character.spriteSize)
        asset = make_asset(
            character, sprite, "base/pending.png", prompt.final, generated.seed, "full", validation, anchor, preview
        )
        character.pendingBase = asset
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
        from_dir, ref_asset_id, ref_image = resolve_direction_reference(
            character, state, direction, from_direction, use_reference
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
        for index in range(count):
            cand_seed = None if chosen_seed is None else chosen_seed + index * 7919
            generated, sprite, preview, validation, used_reference = generate_image(
                character,
                prompt,
                use_reference=use_reference,
                seed=cand_seed,
                strength=strength,
                init_image=ref_image,
                state_id=state_id,
                direction=direction,
                allow_crop_retry=layer == "full",
            )
            if not slot.frames and index == 0:
                slot.headAnchor = estimate_head_anchor(sprite, character.spriteSize)
            relative = f"states/{state.id}/{direction}/{layer}_frame_{frame_index:02d}_c{index}.png"
            debug = generated.debug
            if debug:
                debug.usedReference = used_reference
                debug.referenceDirection = from_dir
                debug.referenceAssetId = ref_asset_id
                debug.strength = strength
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
                strength=strength,
                debug=debug,
            )
            candidates.append(asset)

        if layer == "full":
            slot.candidates = candidates
            preview_asset = max(candidates, key=lambda item: item.validation.score if item.validation else 0)
            accepted = slot.status in ("accepted", "locked") or slot.locked
            if not accepted:
                while len(slot.frames) <= frame_index:
                    slot.frames.append(preview_asset)
                slot.frames[frame_index] = preview_asset
                slot.status = "pending"
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
            progress.set_step(character_id, "generating source image")
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
):
    sprite, preview, validation = process_generated(character, image, direction=direction)
    if not slot.frames:
        slot.headAnchor = estimate_head_anchor(sprite, character.spriteSize)
    relative = f"states/{state.id}/{direction}/full_frame_00.png"
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
        strength=strength,
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


def generate_direction_set(
    character_id: str,
    state_id: str | None = None,
    use_reference: bool = True,
    seed: int | None = None,
    override: str = "",
    strength: float = 0.38,
    job_id: str | None = None,
    candidate_count: int | None = None,
) -> dict:
    character = character_service.get_character(character_id)
    if character.acceptedBase is None:
        raise ValueError("Accept a base character before generating directions")
    state_id = state_id or (character.states[0].id if character.states else "")
    if not state_id:
        raise ValueError("Create a state before generating directions")
    state = character_service.find_state(character, state_id)
    character_service.ensure_slots(state, character.spriteSize)
    wanted = [direction for direction in EXPORT_DIRECTION_ORDER if direction in state.selectedDirections]
    prompt = build_prompt(character, state=state, override=override, from_direction="S")
    last = {"character": character, "prompt": prompt, "usedReference": False, "asset": None, "candidates": []}
    native_images = native_direction_images(character, prompt, seed)
    skippable = lambda slot: slot.locked or slot.status in ("accepted", "locked")
    total = len([d for d in wanted if not skippable(character_service.find_slot(state, d))])
    done = 0
    if native_images:
        for direction in wanted:
            slot = character_service.find_slot(state, direction)
            if skippable(slot):
                continue
            image = native_images.get(direction)
            if image is None:
                continue
            done += 1
            if job_id:
                jobs.set_progress(job_id, done, total or 1, f"{direction} ({done}/{total})", "generating")
            asset = _save_direction_image(
                character, state, slot, direction, image, prompt, seed, "S"
            )
            last = {"character": character, "prompt": prompt, "usedReference": True, "asset": asset, "candidates": slot.candidates}
        character_service.save_character(character)
        last["character"] = character
        return last
    for direction in wanted:
        character = character_service.get_character(character_id)
        state = character_service.find_state(character, state_id)
        slot = character_service.find_slot(state, direction)
        if skippable(slot):
            continue
        done += 1
        if job_id:
            jobs.set_progress(job_id, done, total or 1, f"{direction} ({done}/{total})", "generating")
        last = generate_direction(
            character_id,
            state_id,
            direction,
            use_reference=use_reference,
            seed=None if seed is None else seed + done,
            override=override,
            from_direction=None,
            strength=strength,
            job_id=job_id,
            candidate_count=candidate_count,
        )
    return last


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
    prompt = build_prompt(
        character, state=state, direction=direction, action=action or state.customPrompt, frame_count=frame_count, from_direction="S"
    )
    provider = get_provider()
    frames = provider.generate_animation_frames(prompt, frame_count, seed=resolve_seed(character, seed), init_image=init if use_reference else None)
    last_asset = None
    for index, generated in enumerate(frames):
        if job_id:
            jobs.set_progress(job_id, index + 1, frame_count, f"frame {index + 1}/{frame_count}", "generating")
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
        character, prompt, use_reference=use_as_reference, seed=resolve_seed(character, seed, "variation"), strength=strength, init_image=init
    )
    asset = make_asset(
        character, sprite, "base/pending.png", prompt.final, generated.seed, "full", validation, estimate_head_anchor(sprite, character.spriteSize), preview, source=generated.image, negative=prompt.negative
    )
    character.pendingBase = asset
    character_service.save_character(character)
    return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}


def inpaint_placeholder() -> None:
    raise ValueError("Inpainting is not available on the current provider. The API is ready for a provider that supports masks.")


def start_job(character_id: str, operation: str, label: str, total: int | None, fn) -> dict:
    job = jobs.create(character_id, operation, label, total)

    def work(_job):
        return fn(job.id)

    jobs.run_in_background(job, work)
    return {"job": job, "character": character_service.get_character(character_id)}

