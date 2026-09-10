from pydantic import BaseModel, Field

from models.character import CharacterProfile, SpriteAsset
from models.enums import ApplyMode, Direction, HeadVariant, LayerKind, RejectionReason, SeedMode


class PromptLayers(BaseModel):
    globalStyle: str = ""
    visualStyle: str = ""
    masterPrompt: str = ""
    identity: str = ""
    hardConstraints: str = ""
    composition: str = ""
    state: str = ""
    direction: str = ""
    expression: str = ""
    override: str = ""
    negative: str = ""
    final: str = ""


class GenerateBaseRequest(BaseModel):
    seed: int | None = None
    seedMode: SeedMode = "reuse_base"
    override: str = ""


class GenerateStateRequest(BaseModel):
    useReference: bool = True
    seed: int | None = None
    override: str = ""


class GenerateDirectionRequest(BaseModel):
    stateId: str
    direction: Direction
    frameIndex: int = Field(default=0, ge=0, le=15)
    layer: LayerKind = "full"
    useReference: bool = True
    seed: int | None = None
    override: str = ""
    fromDirection: Direction | None = None
    strength: float = 0.42
    candidateCount: int = Field(default=3, ge=1, le=4)


class GenerateDirectionSetRequest(BaseModel):
    stateId: str | None = None
    useReference: bool = True
    seed: int | None = None
    override: str = ""
    strength: float = 0.38
    candidateCount: int = Field(default=2, ge=1, le=4)
    rotationStrategy: str | None = None


class GenerateAnimationRequest(BaseModel):
    stateId: str
    direction: Direction
    frameCount: int = Field(default=8, ge=1, le=16)
    action: str = ""
    useReference: bool = True
    seed: int | None = None


class GenerateMissingRequest(BaseModel):
    stateId: str
    useReference: bool = True


class GenerateHeadRequest(BaseModel):
    stateId: str
    direction: Direction
    variants: list[HeadVariant] | None = None
    useReference: bool = True


class MasterPromptRequest(BaseModel):
    masterPrompt: str
    applyMode: ApplyMode = "future_only"
    stateId: str | None = None
    direction: Direction | None = None


class AcceptBaseRequest(BaseModel):
    lockPalette: bool = True
    paletteMode: str = "accepted"


class AcceptCandidateRequest(BaseModel):
    stateId: str
    direction: Direction
    assetId: str


class DirectionStatusRequest(BaseModel):
    stateId: str
    direction: Direction
    reason: RejectionReason | None = None
    customReason: str = ""


class RefineRequest(BaseModel):
    stateId: str | None = None
    direction: Direction | None = None
    frameIndex: int = 0
    strength: float = 0.35
    seed: int | None = None
    override: str = ""
    useAsReference: bool = True


class InpaintRequest(BaseModel):
    stateId: str | None = None
    direction: Direction | None = None
    maskPath: str = ""
    override: str = ""


class UpdateAnchorsRequest(BaseModel):
    stateId: str
    direction: Direction
    headAnchorX: int
    headAnchorY: int
    headOffsetX: int = 0
    headOffsetY: int = 0


class GenerationJob(BaseModel):
    id: str
    characterId: str
    operation: str
    status: str
    label: str
    current: int = 0
    total: int | None = None
    currentItem: str = ""
    error: str = ""
    errorDetails: str = ""
    traceId: str = ""
    usedReference: bool = False
    createdAt: str = ""
    updatedAt: str = ""


class GenerationResult(BaseModel):
    character: CharacterProfile
    prompt: PromptLayers
    usedReference: bool = False
    asset: SpriteAsset | None = None
    candidates: list[SpriteAsset] = Field(default_factory=list)
    job: GenerationJob | None = None
