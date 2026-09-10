from fastapi import APIRouter, Body, HTTPException

from models.generation import (
    AcceptBaseRequest,
    GenerateBaseRequest,
    GenerateDirectionRequest,
    GenerateHeadRequest,
    GenerateMissingRequest,
    GenerateStateRequest,
    MasterPromptRequest,
    UpdateAnchorsRequest,
)
from services import generation as generation_service
from services import progress as progress_service

router = APIRouter()


def _http(exc: Exception):
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc) or "Not found") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/characters/{character_id}/generate/base")
def generate_base(character_id: str, payload: GenerateBaseRequest = Body(default_factory=GenerateBaseRequest)):
    try:
        return generation_service.generate_base(character_id, payload.seed, payload.override)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/accept-base")
def accept_base(character_id: str, payload: AcceptBaseRequest = Body(default_factory=AcceptBaseRequest)):
    try:
        return generation_service.accept_base(character_id, payload.lockPalette)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/replace-base")
def replace_base(character_id: str):
    try:
        return generation_service.replace_base(character_id)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/clear-reference")
def clear_reference(character_id: str):
    try:
        return generation_service.clear_reference(character_id)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/discard-pending")
def discard_pending(character_id: str):
    try:
        return generation_service.discard_pending(character_id)
    except Exception as exc:
        _http(exc)


@router.get("/api/characters/{character_id}/generation-progress")
def generation_progress(character_id: str):
    return progress_service.get(character_id)


@router.post("/api/characters/{character_id}/generate-variation")
def generate_variation(character_id: str, payload: GenerateBaseRequest = Body(default_factory=GenerateBaseRequest)):
    try:
        return generation_service.generate_variation(character_id, payload.seed, payload.override)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/generate/state/{state_id}")
def generate_state(character_id: str, state_id: str, payload: GenerateStateRequest = Body(default_factory=GenerateStateRequest)):
    try:
        return generation_service.generate_state(
            character_id, state_id, payload.useReference, payload.seed, payload.override
        )
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/generate/direction")
def generate_direction(character_id: str, payload: GenerateDirectionRequest):
    try:
        return generation_service.generate_direction(
            character_id,
            payload.stateId,
            payload.direction,
            payload.frameIndex,
            payload.layer,
            payload.useReference,
            payload.seed,
            payload.override,
        )
    except Exception as ext:
        _http(ext)


@router.post("/api/characters/{character_id}/generate/missing-directions")
def generate_missing(character_id: str, payload: GenerateMissingRequest):
    try:
        return generation_service.generate_missing_directions(character_id, payload.stateId, payload.useReference)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/generate/all-states")
def generate_all(character_id: str, payload: GenerateStateRequest = Body(default_factory=GenerateStateRequest)):
    try:
        return generation_service.generate_all_states(character_id, payload.useReference)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/generate/head-variants")
def generate_heads(character_id: str, payload: GenerateHeadRequest):
    try:
        return generation_service.generate_head_variants(
            character_id, payload.stateId, payload.direction, payload.variants, payload.useReference
        )
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/master-prompt")
def master_prompt(character_id: str, payload: MasterPromptRequest):
    try:
        return generation_service.apply_master_prompt(
            character_id, payload.masterPrompt, payload.applyMode, payload.stateId, payload.direction
        )
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/head-anchors")
def update_anchors(character_id: str, payload: UpdateAnchorsRequest):
    try:
        return generation_service.update_anchors(
            character_id,
            payload.stateId,
            payload.direction,
            payload.headAnchorX,
            payload.headAnchorY,
            payload.headOffsetX,
            payload.headOffsetY,
        )
    except Exception as exc:
        _http(exc)
