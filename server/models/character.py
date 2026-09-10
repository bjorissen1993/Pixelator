from pydantic import BaseModel, Field, field_validator, model_validator

from models.enums import (
    AssetStatus,
    BodyTemplate,
    CameraAngle,
    DetailLevel,
    Direction,
    DirectionsMode,
    Expressiveness,
    BodyMovement,
    FacialRange,
    HeadVariant,
    OutlineStyle,
    PaletteMode,
    ShadingStyle,
    SpriteKind,
    StateKind,
    WarningSeverity,
)


class IdentityLock(BaseModel):
    lockFace: bool = True
    lockHair: bool = True
    lockClothing: bool = True
    lockPalette: bool = True
    lockBodyProportions: bool = True
    lockSilhouette: bool = True
    lockSpiritForm: bool = True
    lockAccessories: bool = True


class SpiritSettings(BaseModel):
    enabled: bool = False
    noLegs: bool = False
    spectralTail: bool = False
    mistFade: bool = False
    auraColor: str = "#9ecbff"
    notes: str = ""


class CompositionSettings(BaseModel):
    fullBodySprite: bool = True
    entireSilhouetteVisible: bool = True
    preventCropping: bool = True
    preventPortrait: bool = True
    preventCloseup: bool = True
    centerCharacter: bool = True
    fitSafeMargins: bool = True
    oneCharacterOnly: bool = True
    showFullSpiritBody: bool = True
    showFullSpiritTail: bool = True
    noPortraitCloseup: bool = True

    @model_validator(mode="before")
    @classmethod
    def map_legacy_composition(cls, value):
        if not isinstance(value, dict):
            return value
        if "noPortraitCloseup" in value:
            flag = bool(value["noPortraitCloseup"])
            value.setdefault("preventPortrait", flag)
            value.setdefault("preventCloseup", flag)
        return value


class PaletteSettings(BaseModel):
    colorCount: int = Field(default=20, ge=8, le=64)
    locked: bool = False
    colors: list[str] = Field(default_factory=list)


class EmotionProfile(BaseModel):
    expressiveness: Expressiveness = "medium"
    bodyMovement: BodyMovement = "natural"
    facialRange: FacialRange = "balanced"
    defaultMood: str = "neutral"
    laughterStyle: str = "natural laugh"
    sadnessStyle: str = "quiet sadness"
    angerStyle: str = "controlled anger"
    talkingStyle: str = "clear speaking pose"
    customEmotionNotes: str = ""


class HeadAnchor(BaseModel):
    headAnchorX: int = 24
    headAnchorY: int = 14
    headOffsetX: int = 0
    headOffsetY: int = 0


class QualityWarning(BaseModel):
    code: str
    message: str
    severity: WarningSeverity = "warning"


class QualityValidation(BaseModel):
    ok: bool = True
    score: int = 100
    compositionScore: int = 100
    validForBase: bool = True
    warnings: list[QualityWarning] = Field(default_factory=list)
    futureChecks: list[str] = Field(default_factory=list)
    occupancy: float = 0
    heightRatio: float = 0
    widthRatio: float = 0
    centerX: float = 0
    centerY: float = 0
    bboxLeft: int = 0
    bboxTop: int = 0
    bboxRight: int = 0
    bboxBottom: int = 0
    touchesTop: bool = False
    touchesBottom: bool = False
    touchesLeft: bool = False
    touchesRight: bool = False
    portraitFailed: bool = False
    cropFailed: bool = False
    fullBodyFailed: bool = False
    retryTriggered: bool = False


class GenerationDebug(BaseModel):
    provider: str = ""
    model: str = ""
    lora: str = ""
    loraLoaded: bool = False
    seed: int | None = None
    steps: int | None = None
    guidance: float | None = None
    strength: float | None = None
    referenceDirection: Direction | None = None
    referenceAssetId: str = ""
    prompt: str = ""
    negativePrompt: str = ""
    workingResolution: int | None = None
    targetResolution: int | None = None
    paletteMode: str = ""
    usedReference: bool = False
    usedIpAdapter: bool = False
    cropRetries: int = 0
    retryTriggered: bool = False


class SpriteAsset(BaseModel):
    id: str
    kind: SpriteKind = "full"
    path: str
    previewPath: str = ""
    sourcePath: str = ""
    width: int
    height: int
    seed: int | None = None
    prompt: str = ""
    negativePrompt: str = ""
    createdAt: str
    accepted: bool = False
    status: AssetStatus = "pending"
    validation: QualityValidation | None = None
    head: HeadAnchor | None = None
    providerId: str = ""
    fromDirection: Direction | None = None
    referenceDirection: Direction | None = None
    referenceAssetId: str = ""
    strength: float | None = None
    debug: GenerationDebug | None = None


class DirectionSlot(BaseModel):
    direction: Direction
    frames: list[SpriteAsset] = Field(default_factory=list)
    candidates: list[SpriteAsset] = Field(default_factory=list)
    body: SpriteAsset | None = None
    head: SpriteAsset | None = None
    overlays: list[SpriteAsset] = Field(default_factory=list)
    headVariants: dict[HeadVariant, SpriteAsset] = Field(default_factory=dict)
    headAnchor: HeadAnchor = Field(default_factory=HeadAnchor)
    status: AssetStatus = "missing"
    locked: bool = False
    seed: int | None = None


class CharacterState(BaseModel):
    id: str
    name: str
    baseType: str
    customPrompt: str = ""
    directionsMode: DirectionsMode = "8"
    selectedDirections: list[Direction] = Field(default_factory=list)
    frameCount: int = Field(default=1, ge=1, le=16)
    loop: bool = True
    animationSpeed: float = 8
    headSeparated: bool = False
    blinkingEnabled: bool = False
    lookAtTargetEnabled: bool = False
    kind: StateKind = "static"
    createdAt: str
    directions: list[DirectionSlot] = Field(default_factory=list)
    seed: int | None = None


class AcceptedBase(BaseModel):
    sprite: SpriteAsset
    acceptedAt: str
    seed: int | None = None
    prompt: str = ""


class CharacterProfile(BaseModel):
    id: str
    slug: str
    name: str
    masterPrompt: str
    negativePrompt: str = ""
    appearance: str = ""
    clothing: str = ""
    bodyType: str = ""
    bodyTemplate: BodyTemplate = "custom"
    species: str = "human"
    spirit: SpiritSettings = Field(default_factory=SpiritSettings)
    spriteSize: int = Field(default=48, ge=16, le=128)
    camera: CameraAngle = "high-top-down"
    palette: PaletteSettings = Field(default_factory=PaletteSettings)
    paletteMode: PaletteMode = "generated"
    outline: OutlineStyle = "selective"
    shading: ShadingStyle = "basic"
    detail: DetailLevel = "medium"
    seed: int | None = None
    seedLocked: bool = False
    styleProfileId: str | None = None
    externalProviderId: str | None = None
    externalCharacterId: str | None = None
    identityLock: IdentityLock = Field(default_factory=IdentityLock)
    composition: CompositionSettings = Field(default_factory=CompositionSettings)
    emotion: EmotionProfile = Field(default_factory=EmotionProfile)
    states: list[CharacterState] = Field(default_factory=list)
    pendingBase: SpriteAsset | None = None
    acceptedBase: AcceptedBase | None = None
    createdAt: str
    updatedAt: str

    @field_validator("outline", mode="before")
    @classmethod
    def map_outline(cls, value: str) -> str:
        return {"none": "lineless", "soft": "selective", "dark": "black"}.get(value, value)

    @field_validator("detail", mode="before")
    @classmethod
    def map_detail(cls, value: str) -> str:
        return {"simple": "low", "balanced": "medium"}.get(value, value)

    @field_validator("camera", mode="before")
    @classmethod
    def map_camera(cls, value: str) -> str:
        return {"front": "side"}.get(value, value)

    @field_validator("paletteMode", mode="before")
    @classmethod
    def map_palette_mode(cls, value: str) -> str:
        return {"locked": "strict"}.get(value, value)
