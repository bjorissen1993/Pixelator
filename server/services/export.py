import json
import zipfile
from pathlib import Path

from PIL import Image
from fastapi.responses import FileResponse

import config
from domain.directions import ordered_for_export
from models.character import CharacterProfile
from persistence.store import asset_path
from services import characters as character_service


def _open(relative: str | None, size: int) -> Image.Image:
    if not relative:
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))
    path = config.DATA_DIR / relative
    if not path.exists():
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return Image.open(path).convert("RGBA")


def _sheet(rows: list[list[Image.Image]], size: int) -> Image.Image:
    height = max(1, len(rows))
    width = max((len(row) for row in rows), default=1)
    sheet = Image.new("RGBA", (width * size, height * size), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, frame in enumerate(row):
            if frame.size != (size, size):
                frame = frame.resize((size, size), Image.Resampling.NEAREST)
            sheet.alpha_composite(frame, (x * size, y * size))
    return sheet


def build_metadata(character: CharacterProfile) -> dict:
    states_meta = {}
    filenames: list[str] = []
    for state in character.states:
        directions_meta = {}
        for direction in ordered_for_export(state.selectedDirections):
            slot = next((item for item in state.directions if item.direction == direction), None)
            if slot is None:
                continue
            frame_paths = [frame.path for frame in slot.frames[: state.frameCount]]
            filenames.extend(frame_paths)
            if slot.head:
                filenames.append(slot.head.path)
            if slot.body:
                filenames.append(slot.body.path)
            for asset in slot.headVariants.values():
                filenames.append(asset.path)
            directions_meta[direction] = {
                "frames": frame_paths,
                "frameCount": len(frame_paths),
                "headAnchor": slot.headAnchor.model_dump(),
                "head": slot.head.path if slot.head else None,
                "body": slot.body.path if slot.body else None,
                "headVariants": {key: value.path for key, value in slot.headVariants.items()},
                "overlays": [overlay.path for overlay in slot.overlays],
            }
        states_meta[state.id] = {
            "id": state.id,
            "name": state.name,
            "baseType": state.baseType,
            "kind": state.kind,
            "frameCount": state.frameCount,
            "animationSpeed": state.animationSpeed,
            "loop": state.loop,
            "headSeparated": state.headSeparated,
            "blinkingEnabled": state.blinkingEnabled,
            "lookAtTargetEnabled": state.lookAtTargetEnabled,
            "directionsMode": state.directionsMode,
            "directions": directions_meta,
            "frameOrder": list(range(state.frameCount)),
        }
    if character.acceptedBase:
        filenames.append(character.acceptedBase.sprite.path)
    return {
        "characterId": character.id,
        "name": character.name,
        "slug": character.slug,
        "spriteSize": character.spriteSize,
        "directionOrder": ordered_for_export(
            list({direction for state in character.states for direction in state.selectedDirections})
        ),
        "states": states_meta,
        "headVariants": ["center", "left", "right", "slightUp", "slightDown"],
        "filenames": sorted(set(filenames)),
    }


def export_png(character_id: str, state_id: str | None, direction: str | None) -> Path:
    character = character_service.get_character(character_id)
    if character.acceptedBase and not state_id:
        return config.DATA_DIR / character.acceptedBase.sprite.path
    if not state_id or not direction:
        if character.pendingBase:
            return config.DATA_DIR / character.pendingBase.path
        raise ValueError("Choose a state and direction, or accept a base sprite first")
    state = character_service.find_state(character, state_id)
    slot = character_service.find_slot(state, direction)
    if not slot.frames:
        raise ValueError("That direction has no generated frames yet")
    return config.DATA_DIR / slot.frames[0].path


def export_state_sheet(character_id: str, state_id: str) -> Path:
    character = character_service.get_character(character_id)
    state = character_service.find_state(character, state_id)
    size = character.spriteSize
    rows: list[list[Image.Image]] = []
    for direction in ordered_for_export(state.selectedDirections):
        slot = next((item for item in state.directions if item.direction == direction), None)
        frames = []
        for index in range(state.frameCount):
            path = slot.frames[index].path if slot and index < len(slot.frames) else None
            frames.append(_open(path, size))
        rows.append(frames)
    sheet = _sheet(rows, size)
    relative = f"exports/{state.name.lower().replace(' ', '-')}-sheet.png"
    path = asset_path(character.slug, relative)
    sheet.save(path, format="PNG")
    return path


def export_character_sheet(character_id: str) -> Path:
    character = character_service.get_character(character_id)
    size = character.spriteSize
    rows: list[list[Image.Image]] = []
    for state in character.states:
        for direction in ordered_for_export(state.selectedDirections):
            slot = next((item for item in state.directions if item.direction == direction), None)
            frames = []
            for index in range(max(1, state.frameCount)):
                path = slot.frames[index].path if slot and index < len(slot.frames) else None
                frames.append(_open(path, size))
            rows.append(frames)
    sheet = _sheet(rows, size)
    path = asset_path(character.slug, "exports/character-sheet.png")
    sheet.save(path, format="PNG")
    return path


def export_metadata(character_id: str) -> Path:
    character = character_service.get_character(character_id)
    payload = build_metadata(character)
    path = asset_path(character.slug, "exports/metadata.json")
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def export_zip(character_id: str) -> Path:
    character = character_service.get_character(character_id)
    meta_path = export_metadata(character_id)
    zip_path = asset_path(character.slug, "exports/character-package.zip")
    root = config.DATA_DIR / "characters" / character.slug
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(meta_path, arcname="metadata.json")
        for file_path in root.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in {".png", ".json"} and file_path != zip_path:
                archive.write(file_path, arcname=str(file_path.relative_to(root)))
    return zip_path


def file_response(path: Path, filename: str | None = None, media_type: str | None = None) -> FileResponse:
    return FileResponse(path, filename=filename or path.name, media_type=media_type)
