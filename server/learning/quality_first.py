"""Quality-first review: promote generic quality signals, never content identity.

Technical quality and pixel readability may become global recipe-setting evidence.
Silhouette and proportions may become character-type recipe-setting evidence.
Those ratings must not become prompt fragments.
Transparency extraction stays on the extraction channel.
Asset-specific notes and prompts stay on the source asset.
"""

from __future__ import annotations

from typing import Any

from models.catalog import AssetProfile, GenerationCandidate, LearningRecord, QualityReview

GENERATION_DIMENSIONS = {
    "technicalQuality": ("global", "poor technical quality"),
    "pixelReadability": ("global", "poor pixel readability"),
    "silhouette": ("asset_type", "poor silhouette"),
    "proportions": ("asset_type", "poor proportions"),
}

QUALITY_FIELDS = (*GENERATION_DIMENSIONS, "transparencyExtraction")


def is_quality_first(asset: AssetProfile) -> bool:
    return asset.reviewMode == "quality_first"


def is_quality_dimension_record(record: Any) -> bool:
    """Promoted quality ratings: recipe settings only, never prompt fragments."""
    extra = getattr(record, "validationResults", None) or {}
    if extra.get("qualityFirst"):
        return True
    scope = getattr(record, "scope", "asset") or "asset"
    return getattr(record, "reviewMode", "standard") == "quality_first" and scope in {"global", "asset_type"}


def require_quality_review(review: QualityReview | None) -> QualityReview:
    if review is None:
        raise ValueError("Quality-first review requires explicit good/bad ratings.")
    missing = [field for field in QUALITY_FIELDS if getattr(review, field, None) not in {"good", "bad"}]
    if missing:
        raise ValueError(f"Rate every quality field: {', '.join(missing)}.")
    return review


def promoted_quality_records(
    asset: AssetProfile,
    candidate: GenerationCandidate,
    review: QualityReview,
    *,
    created_at: str,
    record_id_prefix: str,
) -> list[LearningRecord]:
    settings = candidate.modelSettings or {
        "width": asset.generation.width,
        "height": asset.generation.height,
        "steps": asset.generation.steps,
        "guidance": asset.generation.guidance,
    }
    records: list[LearningRecord] = []
    for field, (scope, reason) in GENERATION_DIMENSIONS.items():
        rating = getattr(review, field)
        records.append(
            _quality_record(
                asset,
                candidate,
                created_at=created_at,
                record_id=f"{record_id_prefix}-{field}",
                scope=scope,
                decision="accepted" if rating == "good" else "rejected",
                reason=reason,
                settings=settings,
                quality_review=review,
                dimension=field,
            )
        )
    extraction_bad = review.transparencyExtraction == "bad"
    records.append(
        LearningRecord(
            id=f"{record_id_prefix}-transparencyExtraction",
            createdAt=created_at,
            projectId=asset.projectId,
            assetType=asset.assetType,
            assetId=asset.assetId,
            state=asset.state,
            direction=asset.direction,
            seed=candidate.seed,
            modelId=candidate.modelId or asset.generation.modelId,
            provider="isolated-asset-lab",
            modelSettings=settings,
            decision="rejected" if extraction_bad else "accepted",
            rejectionReasons=["transparency extraction failed"] if extraction_bad else [],
            automaticRejectionReasons=[],
            manualRejectionReasons=["transparency extraction failed"] if extraction_bad else [],
            candidatePath=candidate.isolatedPath or candidate.path,
            sha256=candidate.sha256,
            scope="asset",
            feedbackChannel="extraction",
            reviewMode="quality_first",
            qualityReview=review.model_dump(),
            validationResults={"channel": "extraction", "dimension": "transparencyExtraction"},
        )
    )
    return records


def _quality_record(
    asset: AssetProfile,
    candidate: GenerationCandidate,
    *,
    created_at: str,
    record_id: str,
    scope: str,
    decision: str,
    reason: str,
    settings: dict[str, Any],
    quality_review: QualityReview,
    dimension: str = "",
) -> LearningRecord:
    rejected = decision == "rejected"
    return LearningRecord(
        id=record_id,
        createdAt=created_at,
        projectId=asset.projectId,
        assetType=asset.assetType,
        assetId=asset.assetId,
        state=asset.state,
        direction=asset.direction,
        prompt="",
        negativePrompt="",
        seed=candidate.seed,
        modelId=candidate.modelId or asset.generation.modelId,
        provider="isolated-asset-lab",
        modelSettings=settings,
        decision=decision,  # type: ignore[arg-type]
        rejectionReasons=[reason] if rejected else [],
        automaticRejectionReasons=[],
        manualRejectionReasons=[reason] if rejected else [],
        candidatePath=candidate.rawPath or candidate.path,
        sha256=candidate.sha256,
        scope=scope,  # type: ignore[arg-type]
        recipeFingerprint=candidate.recipeFingerprint,
        recipeMode=candidate.recipeMode,
        referenceStrategy=str((candidate.modelSettings or {}).get("referenceStrategy") or "none"),
        referenceStrength=(candidate.modelSettings or {}).get("referenceStrength"),
        feedbackChannel="generation",
        reviewMode="quality_first",
        qualityReview=quality_review.model_dump(),
        validationResults={"channel": "generation", "qualityFirst": True, "scope": scope, "dimension": dimension},
    )
