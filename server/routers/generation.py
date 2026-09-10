from fastapi import APIRouter, Body

from models.enums import Direction
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
from services.errors import http_error

router = APIRouter()


def _ctx(**kwargs):
    return {key: value for key, value in kwargs.items() if value is not None}


@router.post("/api/characters/{character_id}/generate/base")
def generate_base(character_id: str, payload: GenerateBaseRequest = Body(default_factory=GenerateBaseRequest)):
    try:
        if get_provider().capabilities.nativePixelOutput:
            return generation_service.start_job(
                character_id,
                "base",
                "Generate",
                1,
                lambda job_id: generation_service.generate_base(character_id, payload.seed, payload.override),
            )
        return generation_service.generate_base(character_id, payload.seed, payload.override)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="generate_base", direction="S", state="idle"))


@router.post("/api/generation/base")
def generate_base_alias(payload: dict = Body(default_factory=dict)):
    character_id = str(payload.get("characterId") or "")
    if not character_id:
        http_error(ValueError("characterId is required"), status=400, context={"action": "generate_base"})
    return generate_base(character_id, GenerateBaseRequest.model_validate(payload))


@router.post("/api/characters/{character_id}/accept-base")
def accept_base(character_id: str, payload: AcceptBaseRequest = Body(default_factory=AcceptBaseRequest)):
    try:
        return generation_service.accept_base(character_id, payload.lockPalette, payload.paletteMode)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="accept_base"))


@router.post("/api/characters/{character_id}/replace-base")
def replace_base(character_id: str):
    try:
        return generation_service.replace_base(character_id)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="replace_base"))


@router.post("/api/characters/{character_id}/clear-reference")
def clear_reference(character_id: str):
    try:
        return generation_service.clear_reference(character_id)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="clear_reference"))


@router.post("/api/characters/{character_id}/discard-pending")
def discard_pending(character_id: str):
    try:
        return generation_service.discard_pending(character_id)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="discard_pending"))


@router.post("/api/characters/{character_id}/reprocess-pending")
def reprocess_pending(character_id: str):
    try:
        return generation_service.reprocess_from_source(character_id)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="reprocess_pending"))


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        http_error(KeyError("Job not found"), status=404, context={"jobId": job_id})
    return {"job": job, "result": jobs.result(job_id)}


@router.get("/api/characters/{character_id}/generation-progress")
def generation_progress(character_id: str):
    return progress_service.get(character_id)


@router.get("/api/characters/{character_id}/jobs")
def character_jobs(character_id: str):
    return {"active": jobs.active_for(character_id), "jobs": jobs.for_character(character_id)[:20]}


@router.post("/api/characters/{character_id}/generate/directions")
def generate_direction_set(character_id: str, payload: GenerateDirectionSetRequest = Body(default_factory=GenerateDirectionSetRequest)):
    try:
        generation_service.require_direction_set(character_id, payload.stateId)
        return generation_service.start_job(
            character_id,
            "directions",
            "Generate All Directions",
            8,
            lambda job_id: generation_service.generate_direction_set(
                character_id, payload.stateId, payload.useReference, payload.seed, payload.override, payload.strength, job_id, payload.candidateCount
            ),
        )
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="generate_all_directions", state=payload.stateId))


@router.post("/api/generation/directions/all")
def generate_all_directions_alias(payload: dict = Body(default_factory=dict)):
    character_id = str(payload.get("characterId") or "")
    if not character_id:
        http_error(ValueError("characterId is required"), status=400, context={"action": "generate_all_directions"})
    return generate_direction_set(character_id, GenerateDirectionSetRequest.model_validate(payload))


@router.post("/api/characters/{character_id}/directions/accept-candidate")
def accept_candidate(character_id: str, payload: AcceptCandidateRequest):
    try:
        return generation_service.accept_candidate(character_id, payload.stateId, payload.direction, payload.assetId)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="accept_candidate", direction=payload.direction, state=payload.stateId))


@router.post("/api/characters/{character_id}/directions/accept")
def accept_direction(character_id: str, payload: DirectionStatusRequest):
    try:
        return generation_service.set_direction_status(character_id, payload.stateId, payload.direction, "accepted")
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="accept_direction", direction=payload.direction, state=payload.stateId))


@router.post("/api/characters/{character_id}/directions/reject")
def reject_direction(character_id: str, payload: DirectionStatusRequest):
    try:
        return generation_service.set_direction_status(
            character_id, payload.stateId, payload.direction, "rejected", payload.reason, payload.customReason
        )
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="reject_direction", direction=payload.direction, state=payload.stateId))


@router.post("/api/characters/{character_id}/directions/lock")
def lock_direction(character_id: str, payload: DirectionStatusRequest):
    try:
        return generation_service.set_direction_status(character_id, payload.stateId, payload.direction, "locked")
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="lock_direction", direction=payload.direction, state=payload.stateId))


@router.post("/api/characters/{character_id}/directions/unlock")
def unlock_direction(character_id: str, payload: DirectionStatusRequest):
    try:
        return generation_service.set_direction_status(character_id, payload.stateId, payload.direction, "unlocked")
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="unlock_direction", direction=payload.direction, state=payload.stateId))


@router.delete("/api/characters/{character_id}/states/{state_id}/directions/{direction}")
def remove_direction(character_id: str, state_id: str, direction: Direction):
    try:
        return generation_service.remove_direction(character_id, state_id, direction)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="remove_direction", direction=direction, state=state_id))


@router.post("/api/directions/{character_id}/{state_id}/{direction}/accept")
def accept_direction_alias(character_id: str, state_id: str, direction: Direction):
    return accept_direction(character_id, DirectionStatusRequest(stateId=state_id, direction=direction))


@router.post("/api/directions/{character_id}/{state_id}/{direction}/reject")
def reject_direction_alias(character_id: str, state_id: str, direction: Direction, payload: dict = Body(default_factory=dict)):
    return reject_direction(
        character_id,
        DirectionStatusRequest(
            stateId=state_id,
            direction=direction,
            reason=payload.get("reason"),
            customReason=payload.get("customReason") or "",
        ),
    )


@router.post("/api/directions/{character_id}/{state_id}/{direction}/lock")
def lock_direction_alias(character_id: str, state_id: str, direction: Direction):
    return lock_direction(character_id, DirectionStatusRequest(stateId=state_id, direction=direction))


@router.post("/api/directions/{character_id}/{state_id}/{direction}/regenerate")
def regenerate_direction_alias(character_id: str, state_id: str, direction: Direction, payload: dict = Body(default_factory=dict)):
    return generate_direction(
        character_id,
        GenerateDirectionRequest.model_validate({"stateId": state_id, "direction": direction, **payload}),
    )


@router.delete("/api/directions/{character_id}/{state_id}/{direction}")
def remove_direction_alias(character_id: str, state_id: str, direction: Direction):
    return remove_direction(character_id, state_id, direction)


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
        http_error(exc, context=_ctx(characterId=character_id, action="generate_animation", direction=payload.direction, state=payload.stateId))


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
        http_error(exc, context=_ctx(characterId=character_id, action="refine", direction=payload.direction, state=payload.stateId))


@router.post("/api/characters/{character_id}/inpaint")
def inpaint(character_id: str, payload: InpaintRequest):
    try:
        generation_service.inpaint_placeholder()
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="inpaint", direction=payload.direction, state=payload.stateId))


@router.post("/api/characters/{character_id}/generate-variation")
def generate_variation(character_id: str, payload: GenerateBaseRequest = Body(default_factory=GenerateBaseRequest)):
    try:
        return generation_service.generate_variation(character_id, payload.seed, payload.override)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="generate_variation"))


@router.post("/api/characters/{character_id}/generate/state/{state_id}")
def generate_state(character_id: str, state_id: str, payload: GenerateStateRequest = Body(default_factory=GenerateStateRequest)):
    try:
        return generation_service.generate_state(
            character_id, state_id, payload.useReference, payload.seed, payload.override
        )
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="generate_state", state=state_id))


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
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="generate_direction", direction=payload.direction, state=payload.stateId))


@router.post("/api/characters/{character_id}/generate/missing-directions")
def generate_missing(character_id: str, payload: GenerateMissingRequest):
    try:
        return generation_service.generate_missing_directions(character_id, payload.stateId, payload.useReference)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="generate_missing", state=payload.stateId))


@router.post("/api/characters/{character_id}/generate/all-states")
def generate_all(character_id: str, payload: GenerateStateRequest = Body(default_factory=GenerateStateRequest)):
    try:
        return generation_service.generate_all_states(character_id, payload.useReference)
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="generate_all_states"))


@router.post("/api/characters/{character_id}/generate/head-variants")
def generate_heads(character_id: str, payload: GenerateHeadRequest):
    try:
        return generation_service.generate_head_variants(
            character_id, payload.stateId, payload.direction, payload.variants, payload.useReference
        )
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="generate_head_variants", direction=payload.direction, state=payload.stateId))


@router.post("/api/characters/{character_id}/master-prompt")
def master_prompt(character_id: str, payload: MasterPromptRequest):
    try:
        return generation_service.apply_master_prompt(
            character_id, payload.masterPrompt, payload.applyMode, payload.stateId, payload.direction
        )
    except Exception as exc:
        http_error(exc, context=_ctx(characterId=character_id, action="master_prompt", direction=payload.direction, state=payload.stateId))


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
        http_error(exc, context=_ctx(characterId=character_id, action="update_anchors", direction=payload.direction, state=payload.stateId))
