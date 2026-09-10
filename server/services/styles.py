import json
from datetime import datetime, timezone
from uuid import uuid4

import config
from models.character import CharacterProfile, PaletteSettings
from models.project import StyleProfile

_PATH = lambda: config.DATA_DIR / "project" / "styles.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[StyleProfile]:
    path = _PATH()
    if not path.exists():
        profiles = [_chimera()]
        _save(profiles)
        return profiles
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [StyleProfile.model_validate(item) for item in raw]


def _save(profiles: list[StyleProfile]) -> None:
    path = _PATH()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item.model_dump() for item in profiles], indent=2), encoding="utf-8")


def _chimera() -> StyleProfile:
    now = utc_now()
    return StyleProfile(
        id="chimera",
        name="Chimera",
        palette=PaletteSettings(colorCount=20, locked=False, colors=[]),
        camera="high-top-down",
        outline="black",
        shading="basic",
        detail="medium",
        spriteSize=48,
        globalPositive="readable fantasy RPG pixel sprite, limited earthy palette, crisp clusters",
        globalNegative="photorealism, 3D, armor unless requested, modern clothing, smooth gradients",
        referencePaths=[],
        createdAt=now,
        updatedAt=now,
    )


def list_styles() -> list[StyleProfile]:
    return _load()


def get_style(style_id: str) -> StyleProfile:
    for profile in _load():
        if profile.id == style_id:
            return profile
    raise KeyError(style_id)


def save_style(profile: StyleProfile) -> StyleProfile:
    profiles = _load()
    next_profiles = [profile if item.id == profile.id else item for item in profiles]
    if all(item.id != profile.id for item in profiles):
        next_profiles.append(profile)
    profile.updatedAt = utc_now()
    _save(next_profiles)
    return profile


def create_style(name: str) -> StyleProfile:
    now = utc_now()
    profile = StyleProfile(
        id=uuid4().hex,
        name=name.strip() or "Untitled style",
        createdAt=now,
        updatedAt=now,
    )
    return save_style(profile)


def apply_style(character: CharacterProfile, style_id: str) -> CharacterProfile:
    profile = get_style(style_id)
    character.styleProfileId = profile.id
    character.camera = profile.camera
    character.outline = profile.outline
    character.shading = profile.shading
    character.detail = profile.detail
    character.spriteSize = profile.spriteSize
    character.palette.colorCount = profile.palette.colorCount
    if profile.palette.colors:
        character.palette.colors = list(profile.palette.colors)
    if profile.globalPositive and profile.globalPositive not in character.masterPrompt:
        character.masterPrompt = f"{character.masterPrompt}, {profile.globalPositive}".strip(", ")
    if profile.globalNegative:
        extras = [character.negativePrompt, profile.globalNegative]
        character.negativePrompt = ", ".join(part for part in extras if part)
    return character
