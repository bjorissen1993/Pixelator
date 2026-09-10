import threading
from pathlib import Path

import config
from domain.berwynn import berwynn_profile
from models.character import CharacterProfile

_lock = threading.Lock()


def ensure_dirs() -> Path:
    data = config.DATA_DIR
    (data / "characters").mkdir(parents=True, exist_ok=True)
    return data


def character_dir(slug: str) -> Path:
    path = ensure_dirs() / "characters" / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def character_json_path(slug: str) -> Path:
    return character_dir(slug) / "character.json"


def asset_path(slug: str, relative: str) -> Path:
    path = character_dir(slug) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class JsonStore:
    def list_characters(self) -> list[CharacterProfile]:
        ensure_dirs()
        characters: list[CharacterProfile] = []
        for folder in sorted((config.DATA_DIR / "characters").glob("*")):
            json_path = folder / "character.json"
            if json_path.exists():
                characters.append(CharacterProfile.model_validate_json(json_path.read_text(encoding="utf-8")))
        return characters

    def get(self, character_id: str) -> CharacterProfile | None:
        for character in self.list_characters():
            if character.id == character_id or character.slug == character_id:
                return character
        return None

    def save(self, character: CharacterProfile) -> CharacterProfile:
        with _lock:
            path = character_json_path(character.slug)
            path.write_text(character.model_dump_json(indent=2), encoding="utf-8")
            return character

    def delete(self, character_id: str) -> bool:
        character = self.get(character_id)
        if character is None:
            return False
        with _lock:
            import shutil

            shutil.rmtree(character_dir(character.slug), ignore_errors=True)
            return True

    def seed_if_empty(self) -> None:
        ensure_dirs()
        if self.list_characters():
            return
        self.save(berwynn_profile())


store = JsonStore()
