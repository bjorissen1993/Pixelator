from fastapi import APIRouter, Body, HTTPException, Query

from models.export import ExportRequest
from services import export as export_service

router = APIRouter()


def _http(exc: Exception):
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=str(exc) or "Not found") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/characters/{character_id}/export/png")
def export_png(character_id: str, payload: ExportRequest = Body(default_factory=ExportRequest)):
    try:
        path = export_service.export_png(character_id, payload.stateId, payload.direction)
        return export_service.file_response(path, path.name, "image/png")
    except Exception as exc:
        _http(exc)


@router.get("/api/characters/{character_id}/export/png")
def export_png_get(
    character_id: str,
    stateId: str | None = Query(default=None),
    direction: str | None = Query(default=None),
):
    try:
        path = export_service.export_png(character_id, stateId, direction)
        return export_service.file_response(path, path.name, "image/png")
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/export/state-sheet")
def export_state_sheet(character_id: str, payload: ExportRequest):
    if not payload.stateId:
        raise HTTPException(status_code=400, detail="stateId is required")
    try:
        path = export_service.export_state_sheet(character_id, payload.stateId)
        return export_service.file_response(path, path.name, "image/png")
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/export/character-sheet")
def export_character_sheet(character_id: str):
    try:
        path = export_service.export_character_sheet(character_id)
        return export_service.file_response(path, path.name, "image/png")
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/export/metadata")
def export_metadata(character_id: str):
    try:
        path = export_service.export_metadata(character_id)
        return export_service.file_response(path, path.name, "application/json")
    except Exception as exc:
        _http(exc)


@router.post("/api/characters/{character_id}/export/zip")
def export_zip(character_id: str):
    try:
        path = export_service.export_zip(character_id)
        return export_service.file_response(path, path.name, "application/zip")
    except Exception as exc:
        _http(exc)
