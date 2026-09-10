from pydantic import BaseModel, Field

from models.character import PaletteSettings
from models.enums import CameraAngle, DetailLevel, Direction, OutlineStyle, RejectionReason, ShadingStyle


class StyleProfile(BaseModel):
    id: str
    name: str
    palette: PaletteSettings = Field(default_factory=PaletteSettings)
    camera: CameraAngle = "high-top-down"
    outline: OutlineStyle = "selective"
    shading: ShadingStyle = "basic"
    detail: DetailLevel = "medium"
    spriteSize: int = 48
    globalPositive: str = ""
    globalNegative: str = ""
    referencePaths: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class MemoryEntry(BaseModel):
    id: str
    kind: str
    characterId: str
    characterName: str
    prompt: str = ""
    negativePrompt: str = ""
    seed: int | None = None
    outline: OutlineStyle = "selective"
    shading: ShadingStyle = "basic"
    detail: DetailLevel = "medium"
    camera: CameraAngle = "high-top-down"
    palette: list[str] = Field(default_factory=list)
    providerId: str = ""
    stateName: str = ""
    direction: Direction | None = None
    rejectionReason: RejectionReason | None = None
    customReason: str = ""
    assetPath: str = ""
    createdAt: str


class MemorySuggestions(BaseModel):
    recommendedSeeds: list[int] = Field(default_factory=list)
    recommendedPalettes: list[list[str]] = Field(default_factory=list)
    promptFragments: list[str] = Field(default_factory=list)
    defaultOutline: OutlineStyle | None = None
    defaultShading: ShadingStyle | None = None
    defaultDetail: DetailLevel | None = None
    notes: list[str] = Field(default_factory=list)
