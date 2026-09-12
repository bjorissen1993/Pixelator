"""Learning Loop V1 models. Adaptive recipes only — not weight training."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from models.catalog import AssetType

LearningScope = Literal["global", "project", "asset_type", "asset", "state"]
RecipeMode = Literal["exploit", "explore"]
RecommendationKind = Literal[
    "negative_fragment",
    "positive_fragment",
    "guidance",
    "steps",
    "reference_strength",
]


class LearningPolicy(BaseModel):
    """Configurable Learning Loop V1 knobs.

    Recipe score weights default to accept 0.60, validator 0.25, rating 0.15
    and are renormalized to sum to 1. Confidence band values are unit-interval
    scales multiplied by consistency. exploitRatio is the requested share of a
    batch; integer allocation is computed separately and reported alongside it.
    """

    minRecordOnly: int = 1
    minSuggest: int = 3
    minApply: int = 4
    minStrong: int = 7
    suggestConfidence: float = 0.35
    applyConfidence: float = 0.60
    strongConfidence: float = 0.85
    exploitRatio: float = 0.8
    exploreGuidanceDelta: float = 0.5
    exploreStepsDelta: int = 2
    exploreReferenceDelta: float = 0.1
    minGuidance: float = 5.0
    maxGuidance: float = 12.0
    minSteps: int = 20
    maxSteps: int = 40
    minReferenceStrength: float = 0.3
    maxReferenceStrength: float = 1.0
    applySettingBlend: float = 0.35
    strongSettingBlend: float = 0.55
    scoreWeightAccept: float = 0.60
    scoreWeightValidator: float = 0.25
    scoreWeightRating: float = 0.15
    ratingScale: float = 5.0
    previewBatchSize: int = 4
    manualEvidenceWeight: float = 1.0
    automaticEvidenceWeight: float = 0.25


class RecipeAdjustment(BaseModel):
    id: str
    kind: RecommendationKind
    value: str | float | int
    sourceScope: LearningScope
    source: str
    confidence: float
    accepted: int = 0
    rejected: int = 0
    evidence: float = 0
    manualEvidence: float = 0
    automaticEvidence: float = 0
    applied: bool = False
    disabled: bool = False
    pinned: bool = False
    explanation: str = ""
    learningClass: str = "asset_specific"


class GenerationRecipe(BaseModel):
    modelId: str = ""
    provider: str = "isolated-asset-lab"
    prompt: str = ""
    negativePrompt: str = ""
    identityPrompt: str = ""
    identityNegative: str = ""
    positiveFragments: list[str] = Field(default_factory=list)
    negativeFragments: list[str] = Field(default_factory=list)
    guidance: float = 7.5
    steps: int = 30
    width: int = 512
    height: int = 512
    referenceStrategy: str = "none"
    referenceStrength: float | None = None
    scheduler: str | None = None
    modelOptions: dict[str, Any] = Field(default_factory=dict)
    assetTypeOptions: dict[str, Any] = Field(default_factory=dict)
    fingerprint: str = ""
    mode: RecipeMode = "exploit"
    seed: int | None = None
    adjustments: list[RecipeAdjustment] = Field(default_factory=list)
    why: list[str] = Field(default_factory=list)


class RecipeScore(BaseModel):
    fingerprint: str
    attempts: int = 0
    accepts: int = 0
    rejects: int = 0
    validatorPassRate: float = 0
    averageRating: float | None = None
    rejectionReasons: dict[str, int] = Field(default_factory=dict)
    score: float = 0


class LearningControls(BaseModel):
    disabledIds: list[str] = Field(default_factory=list)
    pinnedFragments: dict[str, list[str]] = Field(default_factory=dict)
    pinnedSettings: dict[str, float | int | str] = Field(default_factory=dict)
    resetAfter: dict[str, str] = Field(default_factory=dict)


class LearningStats(BaseModel):
    attempts: int = 0
    accepted: int = 0
    rejected: int = 0
    successRate: float = 0
    topRejectionReasons: list[str] = Field(default_factory=list)
    topAutomaticReasons: list[str] = Field(default_factory=list)
    topManualReasons: list[str] = Field(default_factory=list)


class LearningSnapshot(BaseModel):
    projectId: str
    assetType: AssetType
    assetId: str
    state: str | None = None
    direction: str | None = None
    stats: LearningStats = Field(default_factory=LearningStats)
    policy: LearningPolicy = Field(default_factory=LearningPolicy)
    exploitRatio: float = 0.8
    exploreRatio: float = 0.2
    requestedExploitRatio: float = 0.8
    requestedExploreRatio: float = 0.2
    allocationBatchSize: int = 4
    allocatedExploit: int = 0
    allocatedExplore: int = 0
    allocatedExploitRatio: float = 0
    allocatedExploreRatio: float = 0
    recommendations: list[RecipeAdjustment] = Field(default_factory=list)
    recipeScores: list[RecipeScore] = Field(default_factory=list)
    nextRecipe: GenerationRecipe | None = None
    why: list[str] = Field(default_factory=list)


class LearningControlRequest(BaseModel):
    projectId: str
    assetType: AssetType
    assetId: str
    recommendationId: str | None = None
    pinKind: str | None = None
    pinValue: str | float | int | None = None
    resetScope: LearningScope | None = None
    confirmGlobal: bool = False
