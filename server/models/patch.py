from pydantic import BaseModel, Field

from models.character import EmotionProfile, IdentityLock, PaletteSettings, SpiritSettings
from models.enums import BodyTemplate, CameraAngle, DetailLevel, OutlineStyle, PaletteMode, ShadingStyle


class CharacterPatch(BaseModel):
    name: str | None = None
    masterPrompt: str | None = None
    negativePrompt: str | None = None
    appearance: str | None = None
    clothing: str | None = None
    bodyType: str | None = None
    bodyTemplate: BodyTemplate | None = None
    species: str | None = None
    spirit: SpiritSettings | None = None
    spriteSize: int | None = Field(default=None, ge=16, le=128)
    camera: CameraAngle | None = None
    palette: PaletteSettings | None = None
    paletteMode: PaletteMode | None = None
    outline: OutlineStyle | None = None
    shading: ShadingStyle | None = None
    detail: DetailLevel | None = None
    seed: int | None = None
    seedLocked: bool | None = None
    styleProfileId: str | None = None
    identityLock: IdentityLock | None = None
    emotion: EmotionProfile | None = None
