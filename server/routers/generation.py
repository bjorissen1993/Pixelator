from fastapi import APIRouter, Body, HTTPException

from models.generation import (
    AcceptBaseRequest,
    AcceptCandidateRequest,
    DirectionStatusRequest,
    GenerateAnimationRequest,
    GenerateBaseRequest,
    GenerateDirectionRequest,
    GenerateDirectionSetRequest,
    GenerateHeadRequest,
    GenerateMissingRequest,
    GenerateStateRequest,
    InpaintRequest,
    MasterPromptRequest,
    RefineRequest,
    UpdateAnchorsRequest,
)
from providers.registry import get_provider
from services import generation as generation_service
from services import jobs
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
        if get_provider().capabilities.nativePixelOutput:
            return generation_service.start_job(
                character_id,
                "base",
                "Generate Base",
                1,
                lambda job_id: generation_service.generate_base(character_id, payload.seed, payload.override),
            )
        return generation_service.generate_base(character_id, payload.seed, payload.override)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/accept-base")
def accept_base(character_id: str, payload: AcceptBaseRequest = Body(default_factory=AcceptBaseRequest)):
    try:
        return generation_service.accept_base(character_id, payload.lockPalette, payload.paletteMode)
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


@router.post("/api/characters/{character_id}/reprocess-pending")
def reprocess_pending(character_id: str):
    try:
        return generation_service.reprocess_from_source(character_id)
    except Exception as exc:
        _http(exc)


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    payload = {"job": job, "result": jobs.result(job_id)}
    return payload


@router.get("/api/characters/{character_id}/generation-progress")
def generation_progress(character_id: str):
    return progress_service.get(character_id)


@router.get("/api/characters/{character_id}/jobs")
def character_jobs(character_id: str):
    return {"active": jobs.active_for(character_id), "jobs": jobs.for_character(character_id)[:20]}


@router.post("/api/characters/{character_id}/generate/directions")
def generate_direction_set(character_id: str, payload: GenerateDirectionSetRequest = Body(default_factory=GenerateDirectionSetRequest)):
    try:
        return generation_service.start_job(
            character_id,
            "directions",
            "Generate 8 Directions",
            8,
            lambda job_id: generation_service.generate_direction_set(
                character_id, payload.stateId, payload.useReference, payload.seed, payload.override, payload.strength, job_id, payload.candidateCount
            ),
        )
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/directions/accept-candidate")
def accept_candidate(character_id: str, payload: AcceptCandidateRequest):
    try:
        return generation_service.accept_candidate(character_id, payload.stateId, payload.direction, payload.assetId)
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/directions/accept")
def accept_direction(character_id: str, payload: DirectionStatusRequest):
    try:
        return generation_service.set_direction_status(character_id, payload.stateId, payload.direction, "accepted")
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/directions/reject")
def reject_direction(character_id: str, payload: DirectionStatusRequest):
    try:
        return generation_service.set_direction_status(
            character_id, payload.stateId, payload.direction, "rejected", payload.reason, payload.customReason
        )
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/directions/lock")
def lock_direction(character_id: str, payload: DirectionStatusRequest):
    try:
        return generation_service.set_direction_status(character_id, payload.stateId, payload.direction, "locked")
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/directions/unlock")
def unlock_direction(character_id: str, payload: DirectionStatusRequest):
    try:
        return generation_service.set_direction_status(character_id, payload.stateId, payload.direction, "unlocked")
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/generate/animation")
def generate_animation(character_id: str, payload: GenerateAnimationRequest):
    try:
        return generation_service.start_job(
            character_id,
            "animation",
            "Generating animation",
            payload.frameCount,
            lambda job_id: generation_service.generate_animation(
                character_id, payload.stateId, payload.direction, payload.frameCount, payload.action, payload.useReference, payload.seed, job_id
            ),
        )
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/refine")
def refine(character_id: str, payload: RefineRequest):
    try:
        return generation_service.refine_asset(
            character_id,
            payload.stateId,
            payload.direction,
            payload.frameIndex,
            payload.strength,
            payload.seed,
            payload.override,
            payload.useAsReference,
        )
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/inpaint")
def inpaint(character_id: str, payload: InpaintRequest):
    try:
        generation_service.inpaint_placeholder()
    except Exception as exc:
        _http(exc)


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
            payload.fromDirection,
            payload.strength,
            candidate_count=payload.candidateCount,
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
