from pydantic import BaseModel, Field

from models.enums import DirectionsMode, StateKind


class StateTemplate(BaseModel):
    id: str
    name: str
    category: str
    baseType: str
    prompt: str
    directionsMode: DirectionsMode = "1"
    frameCount: int = 1
    loop: bool = True
    animationSpeed: float = 8
    kind: StateKind = "static"


class CreateCharacterRequest(BaseModel):
    name: str
    masterPrompt: str = ""
    appearance: str = ""
    clothing: str = ""
    bodyType: str = ""
    species: str = "human"
    spriteSize: int = 48


class CreateStateRequest(BaseModel):
    name: str
    baseType: str = "custom"
    customPrompt: str = ""
    directionsMode: DirectionsMode = "8"
    frameCount: int = 1
    loop: bool = True
    animationSpeed: float = 8
    kind: StateKind = "static"
    headSeparated: bool = False
    blinkingEnabled: bool = False
    lookAtTargetEnabled: bool = False
    templateId: str | None = None


class UpdateStateRequest(BaseModel):
    name: str | None = None
    customPrompt: str | None = None
    directionsMode: DirectionsMode | None = None
    selectedDirections: list[str] | None = None
    frameCount: int | None = Field(default=None, ge=1, le=16)
    loop: bool | None = None
    animationSpeed: float | None = None
    kind: StateKind | None = None
    headSeparated: bool | None = None
    blinkingEnabled: bool | None = None
    lookAtTargetEnabled: bool | None = None


class ProviderInfo(BaseModel):
    id: str
    name: str
    modelId: str
    supportsReference: bool
    nativePixelOutput: bool
    notes: str
