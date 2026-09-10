from datetime import datetime, timezone
from uuid import uuid4

from PIL import Image

import config
from domain.directions import HEAD_VARIANTS
from models.character import AcceptedBase, CharacterProfile, HeadAnchor, SpriteAsset
from models.enums import Direction, HeadVariant, LayerKind
from models.generation import PromptLayers
from persistence.store import asset_path
from processing.layers import split_head_body
from processing.pipeline import PixelPipeline, estimate_head_anchor, extract_palette
from prompts.builder import build_prompt
from providers.registry import get_provider
from services import characters as character_service

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


def locked_palette(character: CharacterProfile) -> list[tuple[int, int, int]] | None:
    if not (character.identityLock.lockPalette and character.palette.locked and character.palette.colors):
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
        locked_palette(character),
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
) -> SpriteAsset:
    path = save_image(character.slug, relative, image)
    return SpriteAsset(
        id=new_id(),
        kind=kind,  # type: ignore[arg-type]
        path=path,
        width=image.width,
        height=image.height,
        seed=seed,
        prompt=prompt,
        createdAt=utc_now(),
        accepted=False,
        validation=validation,
        head=head,
    )


def reference_image(character: CharacterProfile) -> Image.Image | None:
    if character.acceptedBase is None:
        return None
    return load_image(character.acceptedBase.sprite.path)


def generate_image(
    character: CharacterProfile,
    prompt: PromptLayers,
    use_reference: bool,
    seed: int | None,
    strength: float = 0.42,
):
    provider = get_provider()
    ref = reference_image(character) if use_reference else None
    used_reference = False
    if ref is not None and provider.info.supportsReference:
        generated = provider.generate_from_reference(prompt, ref, seed=seed, strength=strength)
        used_reference = True
    else:
        generated = provider.generate_direction(prompt, seed=seed)
    sprite, _preview, validation = process_generated(character, generated.image)
    return generated, sprite, validation, used_reference


def generate_base(character_id: str, seed: int | None = None, override: str = "") -> dict:
    character = character_service.get_character(character_id)
    prompt = build_prompt(character, override=override)
    generated, sprite, validation, used_reference = generate_image(
        character, prompt, use_reference=False, seed=seed or character.seed
    )
    anchor = estimate_head_anchor(sprite, character.spriteSize)
    asset = make_asset(character, sprite, "base/pending.png", prompt.final, generated.seed, "full", validation, anchor)
    character.pendingBase = asset
    character_service.save_character(character)
    return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}


def accept_base(character_id: str, lock_palette: bool = True) -> CharacterProfile:
    character = character_service.get_character(character_id)
    source = character.pendingBase or (character.acceptedBase.sprite if character.acceptedBase else None)
    if source is None:
        raise ValueError("No pending or existing base sprite to accept")
    image = load_image(source.path)
    if image is None:
        raise ValueError("Base sprite file is missing")
    accepted_path = save_image(character.slug, "base/accepted.png", image)
    accepted_asset = source.model_copy(update={"path": accepted_path, "accepted": True, "createdAt": utc_now()})
    character.acceptedBase = AcceptedBase(
        sprite=accepted_asset,
        acceptedAt=utc_now(),
        seed=accepted_asset.seed,
        prompt=accepted_asset.prompt,
    )
    if lock_palette:
        palette = extract_palette(image, character.palette.colorCount)
        character.palette.colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette]
        character.palette.locked = True
        character.identityLock.lockPalette = True
    return character_service.save_character(character)


def replace_base(character_id: str) -> CharacterProfile:
    return accept_base(character_id, lock_palette=True)


def clear_reference(character_id: str) -> CharacterProfile:
    character = character_service.get_character(character_id)
    character.acceptedBase = None
    character.palette.locked = False
    return character_service.save_character(character)


def generate_variation(character_id: str, seed: int | None = None, override: str = "") -> dict:
    character = character_service.get_character(character_id)
    if character.acceptedBase is None:
        raise ValueError("Accept a base character before generating a variation")
    prompt = build_prompt(character, override=override or "subtle identity-preserving variation")
    generated, sprite, validation, used_reference = generate_image(
        character, prompt, use_reference=True, seed=seed or character.seed, strength=0.35
    )
    anchor = estimate_head_anchor(sprite, character.spriteSize)
    asset = make_asset(character, sprite, "base/pending.png", prompt.final, generated.seed, "full", validation, anchor)
    character.pendingBase = asset
    character_service.save_character(character)
    return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}


def generate_direction(
    character_id: str,
    state_id: str,
    direction: Direction,
    frame_index: int = 0,
    layer: LayerKind = "full",
    use_reference: bool = True,
    seed: int | None = None,
    override: str = "",
) -> dict:
    character = character_service.get_character(character_id)
    state = character_service.find_state(character, state_id)
    character_service.ensure_slots(state, character.spriteSize)
    slot = character_service.find_slot(state, direction)
    prompt = build_prompt(
        character,
        state=state,
        direction=direction,
        override=override,
        layer=layer,
        frame_index=frame_index,
        frame_count=state.frameCount,
    )
    generated, sprite, validation, used_reference = generate_image(
        character, prompt, use_reference=use_reference, seed=seed or character.seed
    )
    if not slot.frames:
        slot.headAnchor = estimate_head_anchor(sprite, character.spriteSize)
    relative = f"states/{state.id}/{direction}/{layer}_frame_{frame_index:02d}.png"
    asset = make_asset(character, sprite, relative, prompt.final, generated.seed, layer, validation, slot.headAnchor)
    if layer == "full":
        while len(slot.frames) <= frame_index:
            slot.frames.append(asset)
        slot.frames[frame_index] = asset
        if state.headSeparated:
            head, body = split_head_body(sprite, slot.headAnchor)
            slot.head = make_asset(
                character,
                head,
                f"states/{state.id}/{direction}/head.png",
                prompt.final,
                generated.seed,
                "head",
                validation,
                slot.headAnchor,
            )
            slot.body = make_asset(
                character,
                body,
                f"states/{state.id}/{direction}/body.png",
                prompt.final,
                generated.seed,
                "body",
                validation,
                slot.headAnchor,
            )
    elif layer == "head":
        slot.head = asset
    elif layer == "body":
        slot.body = asset
    character_service.save_character(character)
    return {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}


def generate_state(
    character_id: str,
    state_id: str,
    use_reference: bool = True,
    seed: int | None = None,
    override: str = "",
) -> dict:
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


def generate_missing_directions(character_id: str, state_id: str, use_reference: bool = True) -> dict:
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


def generate_all_states(character_id: str, use_reference: bool = True) -> dict:
    character = character_service.get_character(character_id)
    last = {"character": character, "prompt": PromptLayers(), "usedReference": False, "asset": None}
    for state in character.states:
        last = generate_state(character_id, state.id, use_reference=use_reference)
    return last


def generate_head_variants(
    character_id: str,
    state_id: str,
    direction: Direction,
    variants: list[HeadVariant] | None = None,
    use_reference: bool = True,
) -> dict:
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
        prompt = build_prompt(character, state=state, direction=direction, layer="head", head_variant=variant)
        provider = get_provider()
        used_reference = False
        if source is not None and provider.info.supportsReference and use_reference:
            head_layer, _body = split_head_body(source, slot.headAnchor)
            generated = provider.generate_from_reference(prompt, head_layer, seed=character.seed, strength=0.38)
            used_reference = True
        else:
            generated = provider.generate_head_variant(prompt, seed=character.seed)
        sprite, _preview, validation = process_generated(character, generated.image)
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
        )
        slot.headVariants[variant] = asset
        last = {"character": character, "prompt": prompt, "usedReference": used_reference, "asset": asset}
    character_service.save_character(character)
    return last


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
