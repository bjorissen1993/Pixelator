from pydantic import BaseModel, Field

from models.character import CharacterProfile, SpriteAsset
from models.enums import ApplyMode, Direction, HeadVariant, LayerKind


class PromptLayers(BaseModel):
    globalStyle: str = ""
    masterPrompt: str = ""
    identity: str = ""
    state: str = ""
    direction: str = ""
    expression: str = ""
    override: str = ""
    final: str = ""


class GenerateBaseRequest(BaseModel):
    seed: int | None = None
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


class UpdateAnchorsRequest(BaseModel):
    stateId: str
    direction: Direction
    headAnchorX: int
    headAnchorY: int
    headOffsetX: int = 0
    headOffsetY: int = 0


class GenerationResult(BaseModel):
    character: CharacterProfile
    prompt: PromptLayers
    usedReference: bool = False
    asset: SpriteAsset | None = None
