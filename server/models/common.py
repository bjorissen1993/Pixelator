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


class ProviderCapabilities(BaseModel):
    supportsTextToImage: bool = True
    supportsImg2Img: bool = False
    supportsImageToImage: bool = False
    supportsReferenceImage: bool = False
    supportsNegativePrompt: bool = False
    supportsLoRA: bool = False
    supportsControlNet: bool = False
    supportsIPAdapter: bool = False
    supportsPaletteConditioning: bool = False
    supportsDirectionGeneration: bool = False
    supportsBatchDirections: bool = False
    supportsTargetPalette: bool = False
    supportsInitImage: bool = False
    supportsInpainting: bool = False
    supportsAnimation: bool = False
    supportsSkeletonGuidance: bool = False
    nativePixelOutput: bool = False
    preferredSizes: list[int] = Field(default_factory=lambda: [64, 96, 128, 256, 512])
    preferredSize: int = 128
    workingSize: int = 128
    batchIsSequential: bool = True


class ProviderInfo(BaseModel):
    id: str
    name: str
    modelId: str
    supportsReference: bool
    nativePixelOutput: bool
    notes: str
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)
    loraPath: str = ""
    loraLoaded: bool = False
    loraStrength: float = 0
    controlnetLoaded: bool = False
    ipAdapterLoaded: bool = False
    fallbackTurbo: bool = False
    device: str = ""
    dtype: str = ""
    workingSize: int = 128
