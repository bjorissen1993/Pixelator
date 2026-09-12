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
ReviewReasonLayer = Literal["global", "asset_type", "asset"]
ValidatorFeedback = Literal["missed_issue", "incorrect_detection"]


class ValidatorRule(BaseModel):
    id: str
    layer: ValidatorLayer
    message: str
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class ReviewReason(BaseModel):
    id: str
    label: str
    layer: ReviewReasonLayer = "global"
    assetTypes: list[AssetType] = Field(default_factory=list)


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
    reviewReasons: list[ReviewReason] = Field(default_factory=list)


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
    automaticRejectionReasons: list[str] = Field(default_factory=list)
    manualRejectionReasons: list[str] = Field(default_factory=list)
    manualNote: str = ""
    validatorFeedback: ValidatorFeedback | None = None
    manualRating: int | None = None
    candidatePath: str = ""
    sha256: str = ""
    scope: Literal["global", "project", "asset_type", "asset", "state"] = "asset"
    recipeFingerprint: str = ""
    recipeMode: str = ""
    referenceStrategy: str = "none"
    referenceStrength: float | None = None
    learnedAdjustments: list[dict[str, Any]] = Field(default_factory=list)


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
    manualRejectReasons: list[str] = Field(default_factory=list)
    manualNote: str = ""
    validatorFeedback: ValidatorFeedback | None = None
    valid: bool = False
    validation: QualityValidation | None = None
    prompt: str = ""
    negativePrompt: str = ""
    modelId: str = ""
    modelSettings: dict[str, Any] = Field(default_factory=dict)
    recipeFingerprint: str = ""
    recipeMode: str = ""
    learnedAdjustments: list[dict[str, Any]] = Field(default_factory=list)
    recipeWhy: list[str] = Field(default_factory=list)


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
    reviewReasons: list[ReviewReason] = Field(default_factory=list)
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
    learning: dict[str, Any] | None = None
    batchSize: int = 4


class AssetLabGenerateRequest(BaseModel):
    projectId: str | None = None
    assetType: AssetType | None = None
    assetId: str | None = None
    batchSize: int | None = None
    count: int | None = None

    def resolved_batch_size(self) -> int:
        from learning.policy import parse_batch_size

        return parse_batch_size(self.batchSize if self.batchSize is not None else self.count)


class AssetLabRejectRequest(BaseModel):
    reasonIds: list[str] = Field(default_factory=list)
    note: str = ""
    validatorFeedback: ValidatorFeedback | None = None


class CatalogSummary(BaseModel):
    projects: list[ProjectProfile]
    assets: list[AssetProfile]
    defaultProjectId: str
    defaultAssetType: AssetType
    defaultAssetId: str
    allowedBatchSizes: list[int] = Field(default_factory=lambda: [4, 8, 12, 20])
