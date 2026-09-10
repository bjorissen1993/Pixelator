from fastapi import APIRouter, HTTPException

from models.project import StyleProfile
from services import memory
from services import styles

router = APIRouter()


@router.get("/api/styles")
def list_styles():
    return styles.list_styles()


@router.post("/api/styles")
def create_style(payload: dict):
    return styles.create_style(str(payload.get("name") or "Untitled style"))


@router.put("/api/styles/{style_id}")
def update_style(style_id: str, payload: StyleProfile):
    if payload.id != style_id:
        payload.id = style_id
    return styles.save_style(payload)


@router.post("/api/characters/{character_id}/apply-style/{style_id}")
def apply_style(character_id: str, style_id: str):
    from services import characters as character_service

    try:
        character = character_service.get_character(character_id)
        updated = styles.apply_style(character, style_id)
        return character_service.save_character(updated)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/memory")
def list_memory(characterId: str | None = None, kind: str | None = None):
    return memory.list_entries(characterId, kind)


@router.get("/api/memory/suggestions")
def memory_suggestions(characterId: str | None = None):
    return memory.suggestions(characterId)
