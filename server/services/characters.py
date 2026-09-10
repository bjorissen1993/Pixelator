from datetime import datetime, timezone
from uuid import uuid4

from domain.berwynn import make_state_from_template
from domain.directions import DIRECTIONS_8, directions_for_mode
from models.character import CharacterProfile, CharacterState, DirectionSlot, HeadAnchor
from models.common import CreateCharacterRequest, CreateStateRequest, UpdateStateRequest
from models.patch import CharacterPatch
from persistence.paths import sanitize_slug
from persistence.store import store
from processing.preview import ensure_character_previews


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid4().hex


def slugify(name: str) -> str:
    return sanitize_slug(name)


def unique_slug(name: str) -> str:
    base = slugify(name)
    existing = {c.slug for c in store.list_characters()}
    if base not in existing:
        return base
    index = 2
    while f"{base}-{index}" in existing:
        index += 1
    return f"{base}-{index}"


def _stale_base_validation(validation) -> bool:
    if validation is None:
        return True
    return validation.occupancy > 0 and validation.bboxRight == 0 and validation.bboxBottom == 0


def _refresh_stale_base_validation(character: CharacterProfile) -> bool:
    from services.generation import _revalidate_base_asset

    changed = False
    if character.pendingBase and _stale_base_validation(character.pendingBase.validation):
        character.pendingBase.validation = _revalidate_base_asset(character, character.pendingBase)
        changed = True
    if character.acceptedBase and _stale_base_validation(character.acceptedBase.sprite.validation):
        character.acceptedBase.sprite.validation = _revalidate_base_asset(character, character.acceptedBase.sprite)
        changed = True
    return changed


def _with_previews(character: CharacterProfile) -> CharacterProfile:
    changed = False
    try:
        changed = ensure_character_previews(character)
        if _refresh_stale_base_validation(character):
            changed = True
    except OSError:
        import logging

        logging.getLogger("pixelator").exception("Preview/validation refresh failed for %s", character.id)
    if changed:
        return store.save(character)
    return character


def get_character(character_id: str) -> CharacterProfile:
    character = store.get(character_id)
    if character is None:
        raise KeyError(character_id)
    return _with_previews(character)


def find_state(character: CharacterProfile, state_id: str) -> CharacterState:
    for state in character.states:
        if state.id == state_id:
            return state
    raise KeyError(state_id)


def find_slot(state: CharacterState, direction: str) -> DirectionSlot:
    for slot in state.directions:
        if slot.direction == direction:
            return slot
    raise KeyError(direction)


def ensure_slots(state: CharacterState, sprite_size: int) -> None:
    existing = {slot.direction: slot for slot in state.directions}
    default_anchor = HeadAnchor(headAnchorX=sprite_size // 2, headAnchorY=max(8, sprite_size // 3))
    merged: list[DirectionSlot] = []
    for direction in state.selectedDirections:
        if direction in existing:
            merged.append(existing[direction])
        else:
            merged.append(DirectionSlot(direction=direction, headAnchor=default_anchor.model_copy()))
    for direction, slot in existing.items():
        if direction not in state.selectedDirections:
            merged.append(slot)
    state.directions = merged


def list_characters() -> list[CharacterProfile]:
    return [_with_previews(character) for character in store.list_characters()]


def create_character(payload: CreateCharacterRequest) -> CharacterProfile:
    now = utc_now()
    idle = make_state_from_template("idle", payload.spriteSize)
    character = CharacterProfile(
        id=new_id(),
        slug=unique_slug(payload.name),
        name=payload.name,
        masterPrompt=payload.masterPrompt or payload.name,
        appearance=payload.appearance,
        clothing=payload.clothing,
        bodyType=payload.bodyType,
        species=payload.species,
        spriteSize=payload.spriteSize,
        states=[idle] if idle else [],
        createdAt=now,
        updatedAt=now,
    )
    return store.save(character)


def patch_character(character_id: str, payload: CharacterPatch) -> CharacterProfile:
    character = get_character(character_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(character, key, value)
    character.updatedAt = utc_now()
    return store.save(character)


def delete_character(character_id: str) -> None:
    if not store.delete(character_id):
        raise KeyError(character_id)


def add_state(character_id: str, payload: CreateStateRequest) -> CharacterProfile:
    character = get_character(character_id)
    if payload.templateId:
        state = make_state_from_template(payload.templateId, character.spriteSize)
        if state is None:
            raise ValueError("Unknown state template")
        if payload.name:
            state.name = payload.name
    else:
        state = CharacterState(
            id=new_id(),
            name=payload.name,
            baseType=payload.baseType,
            customPrompt=payload.customPrompt,
            directionsMode=payload.directionsMode,
            selectedDirections=list(directions_for_mode(payload.directionsMode)),
            frameCount=payload.frameCount,
            loop=payload.loop,
            animationSpeed=payload.animationSpeed,
            kind=payload.kind,
            headSeparated=payload.headSeparated,
            blinkingEnabled=payload.blinkingEnabled,
            lookAtTargetEnabled=payload.lookAtTargetEnabled,
            createdAt=utc_now(),
            directions=[],
        )
        ensure_slots(state, character.spriteSize)
    character.states.append(state)
    character.updatedAt = utc_now()
    return store.save(character)


def update_state(character_id: str, state_id: str, payload: UpdateStateRequest) -> CharacterProfile:
    character = get_character(character_id)
    state = find_state(character, state_id)
    data = payload.model_dump(exclude_unset=True)
    selected = data.pop("selectedDirections", None)
    for key, value in data.items():
        setattr(state, key, value)
    if selected is not None:
        state.selectedDirections = [d for d in selected if d in DIRECTIONS_8]
    elif payload.directionsMode is not None:
        state.selectedDirections = directions_for_mode(payload.directionsMode)
    if state.frameCount > 1:
        state.kind = "animated"
    ensure_slots(state, character.spriteSize)
    character.updatedAt = utc_now()
    return store.save(character)


def delete_state(character_id: str, state_id: str) -> CharacterProfile:
    character = get_character(character_id)
    character.states = [state for state in character.states if state.id != state_id]
    character.updatedAt = utc_now()
    return store.save(character)


def save_character(character: CharacterProfile) -> CharacterProfile:
    character.updatedAt = utc_now()
    return store.save(character)
