from fastapi import APIRouter, HTTPException

from models.common import CreateCharacterRequest, CreateStateRequest, ProviderInfo, UpdateStateRequest
from models.patch import CharacterPatch
from providers.registry import get_provider
from services import characters as character_service

router = APIRouter()


def _http(exc: Exception, not_found: bool = False):
    if isinstance(exc, KeyError) or not_found:
        raise HTTPException(status_code=404, detail=str(exc) or "Not found") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/providers", response_model=ProviderInfo)
def provider_info():
    return get_provider().info


@router.get("/api/characters")
def list_characters():
    return character_service.list_characters()


@router.post("/api/characters")
def create_character(payload: CreateCharacterRequest):
    try:
        return character_service.create_character(payload)
    except Exception as exc:
        _http(exc)


@router.get("/api/characters/{character_id}")
def get_character(character_id: str):
    try:
        return character_service.get_character(character_id)
    except Exception as exc:
        _http(exc, not_found=True)


@router.patch("/api/characters/{character_id}")
def patch_character(character_id: str, payload: CharacterPatch):
    try:
        return character_service.patch_character(character_id, payload)
    except Exception as exc:
        _http(exc)


@router.delete("/api/characters/{character_id}")
def delete_character(character_id: str):
    try:
        character_service.delete_character(character_id)
        return {"ok": True}
    except Exception as exc:
        _http(exc, not_found=True)


@router.get("/api/characters/{character_id}/states")
def list_states(character_id: str):
    try:
        return character_service.get_character(character_id).states
    except Exception as exc:
        _http(exc, not_found=True)


@router.post("/api/characters/{character_id}/states")
def add_state(character_id: str, payload: CreateStateRequest):
    try:
        return character_service.add_state(character_id, payload)
    except Exception as exc:
        _http(exc)


@router.patch("/api/characters/{character_id}/states/{state_id}")
def update_state(character_id: str, state_id: str, payload: UpdateStateRequest):
    try:
        return character_service.update_state(character_id, state_id, payload)
    except Exception as exc:
        _http(exc)


@router.delete("/api/characters/{character_id}/states/{state_id}")
def delete_state(character_id: str, state_id: str):
    try:
        return character_service.delete_state(character_id, state_id)
    except Exception as exc:
        _http(exc)
