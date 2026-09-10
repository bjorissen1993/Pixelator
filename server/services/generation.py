from datetime import datetime, timezone
from random import randint
from uuid import uuid4

from PIL import Image

import config
from domain.directions import EXPORT_DIRECTION_ORDER, HEAD_VARIANTS
from models.character import AcceptedBase, CharacterProfile, HeadAnchor, SpriteAsset
from models.enums import Direction, HeadVariant, LayerKind
from models.generation import PromptLayers
from persistence.store import asset_path
from processing.layers import split_head_body
from processing.pipeline import PixelPipeline, estimate_head_anchor, extract_palette
from processing.preview import make_preview, preview_relative
from prompts.builder import build_prompt
from providers.base import DirectionSpec
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


def palette_colors(character: CharacterProfile) -> list[tuple[int, int, int]] | None:
    if character.paletteMode in ("locked", "custom", "project") or (
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


def process_generated(character: CharacterProfile, image: Image.Image):
    return pipeline.process(
        image,
        character.spriteSize,
        character.palette.colorCount,
        character.outline,
        config.ENABLE_BG_REMOVAL,
        palette_colors(character),
        on_step=lambda step: progress.set_step(character.id, step),
    )


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
) -> SpriteAsset:
    progress.set_step(character.id, "saving preview")
    path = save_image(character.slug, relative, image)
    preview_image = preview if preview is not None else make_preview(image)
    preview_path = save_image(character.slug, preview_relative(relative), preview_image)
    source_path = ""
    if source is not None:
        source_rel = relative[:-4] + "-source.png" if relative.endswith(".png") else relative + "-source.png"
        source_path = save_image(character.slug, source_rel, source.convert("RGBA"))
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
        providerId=get_provider().info.id,
        fromDirection=from_direction,
    )


def reference_image(character: CharacterProfile, direction: Direction | None = None, state_id: str | None = None) -> Image.Image | None:
    if state_id and direction:
        try:
            state = character_service.find_state(character, state_id)
            slot = character_service.find_slot(state, direction)
            if slot.frames and slot.status in ("accepted", "locked"):
                asset = slot.frames[0]
                return load_image(asset.sourcePath or asset.path)
        except KeyError:
            pass
    if character.acceptedBase is None:
        return None
    asset = character.acceptedBase.sprite
    return load_image(asset.sourcePath or asset.path)


def generate_image(
    character: CharacterProfile,
    prompt: PromptLayers,
    use_reference: bool,
    seed: int | None,
    strength: float = 0.42,
    init_image: Image.Image | None = None,
    state_id: str | None = None,
    direction: Direction | None = None,
):
    progress.set_step(character.id, "generating source image")
    provider = get_provider()
    ref = init_image or (reference_image(character, direction, state_id) if use_reference else None)
    used_reference = False
    if ref is not None and provider.capabilities.supportsReferenceImage:
        generated = provider.generate_from_reference(prompt, ref, seed=seed, strength=strength, init_image=init_image)
        used_reference = True
    else:
        generated = provider.generate_direction(prompt, seed=seed)
    sprite, preview, validation = process_generated(character, generated.image)
    return generated, sprite, preview, validation, used_reference


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
        generated, sprite, preview, validation, used_reference = generate_image(
            character, prompt, use_reference=False, seed=resolve_seed(character, seed, "reuse_base")
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
        character.paletteMode = "locked"
    saved = character_service.save_character(character)
    memory.record(saved, "accepted", accepted_asset, state_name="base", provider_id=get_provider().info.id)
    return saved


def accept_base(character_id: str, lock_palette: bool = True) -> CharacterProfile:
    character = character_service.get_character(character_id)
    return _copy_pending_to_accepted(character, lock_palette)


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
) -> dict:
    nested = _track(character_id, "Generating direction")
    try:
        character = character_service.get_character(character_id)
        state = character_service.find_state(character, state_id)
        character_service.ensure_slots(state, character.spriteSize)
        slot = character_service.find_slot(state, direction)
        if slot.locked and frame_index == 0:
            return {"character": character, "prompt": build_prompt(character, state, direction), "usedReference": False, "asset": slot.frames[0] if slot.frames else None}
        from_dir = from_direction or ("S" if character.acceptedBase else None)
        prompt = build_prompt(
            character,
            state=state,
            direction=direction,
            override=override,
            layer=layer,
            frame_index=frame_index,
            frame_count=state.frameCount,
            from_direction=from_dir,  # type: ignore[arg-type]
        )
        chosen_seed = resolve_seed(character, seed if seed is not None else slot.seed, "reuse_base")
        generated, sprite, preview, validation, used_reference = generate_image(
            character,
            prompt,
            use_reference=use_reference,
            seed=chosen_seed,
            strength=strength,
            state_id=state_id,
            direction=from_dir,  # type: ignore[arg-type]
        )
        if not slot.frames:
            slot.headAnchor = estimate_head_anchor(sprite, character.spriteSize)
        relative = f"states/{state.id}/{direction}/{layer}_frame_{frame_index:02d}.png"
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
        )
        if layer == "full":
            while len(slot.frames) <= frame_index:
                slot.frames.append(asset)
            slot.frames[frame_index] = asset
            slot.status = "pending"
            slot.seed = generated.seed
            if state.headSeparated:
                head, body = split_head_body(sprite, slot.headAnchor)
                slot.head = make_asset(
                    character, head, f"states/{state.id}/{direction}/head.png", prompt.final, generated.seed, "head", validation, slot.headAnchor, source=generated.image, negative=prompt.negative
                )
                slot.body = make_asset(
                    character, body, f"states/{state.id}/{direction}/body.png", prompt.final, generated.seed, "body", validation, slot.headAnchor, source=generated.image, negative=prompt.negative
                )
        elif layer == "head":
            slot.head = asset
        elif layer == "body":
            slot.body = asset
        character_service.save_character(character)
        if job_id:
            jobs.set_progress(job_id, 1, 1, direction, "processing")
        return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}
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
            for frame_index in range(state.frameCount):
                if frame_index < len(slot.frames) and slot.frames[frame_index].path:
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


def generate_direction_set(
    character_id: str,
    state_id: str | None = None,
    use_reference: bool = True,
    seed: int | None = None,
    override: str = "",
    strength: float = 0.38,
    job_id: str | None = None,
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
    last = {"character": character, "prompt": build_prompt(character), "usedReference": False, "asset": None}
    total = len([d for d in wanted if not character_service.find_slot(state, d).locked])
    done = 0
    for direction in wanted:
        slot = character_service.find_slot(state, direction)
        if slot.locked:
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
            from_direction="S",
            strength=strength,
            job_id=job_id,
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

