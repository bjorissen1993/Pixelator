from pydantic import BaseModel, Field

from models.character import EmotionProfile, IdentityLock, PaletteSettings, SpiritSettings
from models.enums import CameraAngle, DetailLevel, OutlineStyle


class CharacterPatch(BaseModel):
    name: str | None = None
    masterPrompt: str | None = None
    appearance: str | None = None
    clothing: str | None = None
    bodyType: str | None = None
    species: str | None = None
    spirit: SpiritSettings | None = None
    spriteSize: int | None = Field(default=None, ge=16, le=128)
    camera: CameraAngle | None = None
    palette: PaletteSettings | None = None
    outline: OutlineStyle | None = None
    detail: DetailLevel | None = None
    seed: int | None = None
    identityLock: IdentityLock | None = None
    emotion: EmotionProfile | None = None
