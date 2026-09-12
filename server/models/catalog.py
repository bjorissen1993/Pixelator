"""Generic Pixelator catalog: Project → Asset Type → Asset.

Isolated from the production Studio character store.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from models.character import QualityValidation

AssetType = Literal[
    "character",
    "portrait",
    "item",
    "prop",
    "tile",
    "background",
    "ui",
    "vfx",
]

CanonicalKind = str

ValidatorLayer = Literal["global", "asset_type", "project", "asset"]


class ValidatorRule(BaseModel):
    id: str
    layer: ValidatorLayer
    message: str
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class GenerationSpec(BaseModel):
    enabled: bool = False
    modelId: str = ""
    width: int = 512
    height: int = 512
    steps: int = 30
    guidance: float = 7.5
    prompt: str = ""
    negativePrompt: str = ""


class StyleProfile(BaseModel):
    projectId: str
    name: str
    outline: str = ""
    shading: str = ""
    detail: str = ""
    paletteLimit: int | None = None
    notes: list[str] = Field(default_factory=list)
    validatorRules: list[ValidatorRule] = Field(default_factory=list)


class ProjectProfile(BaseModel):
    id: str
    name: str
    description: str = ""
    styleProfileId: str = ""
    defaultAssetType: AssetType | None = None
    defaultAssetId: str = ""
    isDefault: bool = False


class AssetFlags(BaseModel):
    oneSubject: bool = False
    fullBody: bool = False
    plainBackground: bool = False
    spiritForm: bool = False
    isolatedSubject: bool = False


class AssetProfile(BaseModel):
    projectId: str
    assetType: AssetType
    assetId: str
    name: str
    canonicalKind: CanonicalKind
    canonicalLabel: str
    state: str | None = None
    direction: str | None = None
    reviewChecklist: list[str] = Field(default_factory=list)
    flags: AssetFlags = Field(default_factory=AssetFlags)
    generation: GenerationSpec = Field(default_factory=GenerationSpec)
    validatorRules: list[ValidatorRule] = Field(default_factory=list)


class LearningRecord(BaseModel):
    id: str
    createdAt: str
    projectId: str
    assetType: AssetType
    assetId: str
    state: str | None = None
    direction: str | None = None
    prompt: str = ""
    negativePrompt: str = ""
    seed: int | None = None
    modelId: str = ""
    provider: str = "isolated-asset-lab"
    modelSettings: dict[str, Any] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)
    validationResults: dict[str, Any] = Field(default_factory=dict)
    decision: Literal["accepted", "rejected"]
    rejectionReasons: list[str] = Field(default_factory=list)
    manualRating: int | None = None
    candidatePath: str = ""
    sha256: str = ""


class GenerationCandidate(BaseModel):
    id: str
    projectId: str
    assetType: AssetType
    assetId: str
    state: str | None = None
    direction: str | None = None
    seed: int
    path: str
    createdAt: str
    status: str = "pending"
    sha256: str = ""
    rejectReasons: list[str] = Field(default_factory=list)
    valid: bool = False
    validation: QualityValidation | None = None
    prompt: str = ""
    negativePrompt: str = ""
    modelId: str = ""
    modelSettings: dict[str, Any] = Field(default_factory=dict)


class AssetLabSession(BaseModel):
    projectId: str
    projectName: str
    assetType: AssetType
    assetId: str
    assetName: str
    canonicalKind: CanonicalKind
    canonicalLabel: str
    state: str | None = None
    direction: str | None = None
    reviewChecklist: list[str] = Field(default_factory=list)
    modelId: str
    prompt: str
    negativePrompt: str
    generationEnabled: bool = False
    candidates: list[GenerationCandidate] = Field(default_factory=list)
    accepted: GenerationCandidate | None = None
    referenceUnlocked: bool = False
    ipAdapterUnlocked: bool = False
    directionGenerationUnlocked: bool = False
    usingCurrentDirectionSet: bool = False
    notes: list[str] = Field(default_factory=list)


class AssetLabGenerateRequest(BaseModel):
    projectId: str | None = None
    assetType: AssetType | None = None
    assetId: str | None = None
    count: int = 4


class CatalogSummary(BaseModel):
    projects: list[ProjectProfile]
    assets: list[AssetProfile]
    defaultProjectId: str
    defaultAssetType: AssetType
    defaultAssetId: str
