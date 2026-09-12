"""Per-dimension quality ratings → recipe-setting evidence. Never prompt words."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from learning.context import LearningContext, record_matches
from learning.policy import confidence_for
from learning.quality_first import is_quality_dimension_record
from models.catalog import AssetProfile, LearningRecord
from models.learning import LearningPolicy, QualityDimensionInsight, RecipeAdjustment

GENERATION_QUALITY_DIMENSIONS = (
    ("technicalQuality", "Technical quality", "global", "global_quality", ()),
    ("pixelReadability", "Pixel readability", "global", "global_quality", ()),
    ("silhouette", "Silhouette", "asset_type", "character_type_quality", ("character", "portrait")),
    ("proportions", "Proportions", "asset_type", "character_type_quality", ("character", "portrait")),
)

REASON_TO_DIMENSION = {
    "poor technical quality": "technicalQuality",
    "poor pixel readability": "pixelReadability",
    "poor silhouette": "silhouette",
    "poor proportions": "proportions",
}


@dataclass(frozen=True)
class _Cluster:
    guidance: float
    steps: int
    width: int
    height: int
    good: int
    bad: int

    @property
    def evidence(self) -> int:
        return self.good + self.bad

    @property
    def rate(self) -> float:
        return self.good / self.evidence if self.evidence else 0.0


def dimension_for_record(record: LearningRecord) -> str | None:
    extra = getattr(record, "validationResults", None) or {}
    dimension = extra.get("dimension")
    if dimension:
        return str(dimension)
    record_id = (getattr(record, "id", "") or "").lower()
    for field, *_rest in GENERATION_QUALITY_DIMENSIONS:
        if record_id.endswith(field.lower()) or f"-{field.lower()}" in record_id:
            return field
    reasons = [*(record.manualRejectionReasons or []), *(record.rejectionReasons or [])]
    for reason in reasons:
        mapped = REASON_TO_DIMENSION.get(reason.lower().strip())
        if mapped:
            return mapped
    return None


def _setting(record: LearningRecord, key: str, default: float | int | None = None) -> float | int | None:
    raw = (record.modelSettings or {}).get(key)
    if raw is None and key == "referenceStrength":
        raw = record.referenceStrength
    if raw is None:
        return default
    try:
        return float(raw) if key == "guidance" else int(float(raw))
    except (TypeError, ValueError):
        return default


def _cluster_key(record: LearningRecord) -> tuple[float, int, int, int] | None:
    guidance = _setting(record, "guidance")
    steps = _setting(record, "steps")
    if guidance is None or steps is None:
        return None
    width = int(_setting(record, "width", 512) or 512)
    height = int(_setting(record, "height", 512) or 512)
    return (round(float(guidance), 1), int(steps), width, height)


def _records_for_dimension(
    dimension: str,
    scope: str,
    context: LearningContext,
    records: list[LearningRecord],
) -> list[LearningRecord]:
    found: list[LearningRecord] = []
    for item in records:
        if not is_quality_dimension_record(item):
            continue
        if dimension_for_record(item) != dimension:
            continue
        if not record_matches(item, context, scope):  # type: ignore[arg-type]
            continue
        found.append(item)
    return found


def _clusters(records: list[LearningRecord]) -> list[_Cluster]:
    buckets: dict[tuple[float, int, int, int], list[LearningRecord]] = defaultdict(list)
    for item in records:
        key = _cluster_key(item)
        if key is None:
            continue
        buckets[key].append(item)
    result: list[_Cluster] = []
    for (guidance, steps, width, height), items in buckets.items():
        good = sum(1 for item in items if item.decision == "accepted")
        bad = sum(1 for item in items if item.decision == "rejected")
        result.append(_Cluster(guidance, steps, width, height, good, bad))
    return result


def _insight_for(
    dimension: str,
    label: str,
    scope: str,
    learning_class: str,
    records: list[LearningRecord],
    policy: LearningPolicy,
    applies: bool,
    baseline_guidance: float = 7.5,
    baseline_steps: int = 30,
) -> QualityDimensionInsight:
    clusters = _clusters(records)
    evidence = sum(item.evidence for item in clusters)
    good = sum(item.good for item in clusters)
    bad = sum(item.bad for item in clusters)
    insight = QualityDimensionInsight(
        id=dimension,
        label=label,
        scope=scope,
        learningClass=learning_class,
        evidence=evidence,
        good=good,
        bad=bad,
        applies=applies,
        status="no_data" if evidence == 0 else "insufficient",
        explanation="No quality ratings recorded yet for this dimension."
        if evidence == 0
        else f"No confident improvement yet. Evidence: {evidence}.",
    )
    if not applies:
        insight.explanation = "This dimension does not apply to the selected asset type."
        insight.status = "not_applicable"
        return insight
    usable = [item for item in clusters if item.evidence >= policy.minSuggest]
    if not usable:
        return insight
    best = max(usable, key=lambda item: (item.rate, item.evidence))
    close = [item for item in usable if item.rate >= best.rate - 0.05]
    insight.bestGuidanceMin = min(item.guidance for item in close)
    insight.bestGuidanceMax = max(item.guidance for item in close)
    insight.bestStepsMin = min(item.steps for item in close)
    insight.bestStepsMax = max(item.steps for item in close)
    insight.bestGuidance = best.guidance
    insight.bestSteps = best.steps
    insight.successRate = round(best.rate, 3)
    distinct = { (item.guidance, item.steps) for item in usable }
    can_compare = len(distinct) >= 2
    worst = min(usable, key=lambda item: item.rate)
    confidence, may_apply, band = confidence_for(best.evidence, best.rate, policy)
    insight.confidence = confidence
    shifted = abs(best.guidance - baseline_guidance) >= 0.2 or abs(best.steps - baseline_steps) >= 1
    if can_compare and shifted and best.rate - worst.rate >= 0.15 and band in {"apply", "strong"} and may_apply:
        insight.status = "confident"
        insight.applied = True
        insight.explanation = (
            f"Best observed range: guidance {insight.bestGuidanceMin:g}–{insight.bestGuidanceMax:g}, "
            f"steps {insight.bestStepsMin}–{insight.bestStepsMax}. Evidence: {evidence}."
        )
    else:
        insight.status = "observed" if evidence >= policy.minSuggest else "insufficient"
        insight.explanation = (
            f"Best observed range: guidance {insight.bestGuidanceMin:g}–{insight.bestGuidanceMax:g}, "
            f"steps {insight.bestStepsMin}–{insight.bestStepsMax}. Evidence: {evidence}."
            if evidence >= policy.minSuggest
            else f"No confident improvement yet. Evidence: {evidence}."
        )
    return insight


def quality_insights(
    asset: AssetProfile,
    context: LearningContext,
    records: list[LearningRecord],
    policy: LearningPolicy,
) -> list[QualityDimensionInsight]:
    insights: list[QualityDimensionInsight] = []
    for dimension, label, scope, learning_class, asset_types in GENERATION_QUALITY_DIMENSIONS:
        applies = not asset_types or asset.assetType in asset_types
        scoped = _records_for_dimension(dimension, scope, context, records) if applies else []
        insights.append(
            _insight_for(
                dimension,
                label,
                scope,
                learning_class,
                scoped,
                policy,
                applies,
                baseline_guidance=asset.generation.guidance,
                baseline_steps=asset.generation.steps,
            )
        )
    extraction = [
        item
        for item in records
        if getattr(item, "feedbackChannel", "generation") == "extraction"
        and record_matches(item, context, "asset")
    ]
    insights.append(
        QualityDimensionInsight(
            id="transparencyExtraction",
            label="Transparency extraction",
            scope="asset",
            learningClass="asset_specific",
            evidence=len(extraction),
            good=sum(1 for item in extraction if item.decision == "accepted"),
            bad=sum(1 for item in extraction if item.decision == "rejected"),
            applies=True,
            status="separate" if extraction else "no_data",
            explanation=(
                f"Extraction is post-processing. Evidence: {len(extraction)}. "
                "This does not change the diffusion recipe."
                if extraction
                else "No extraction ratings recorded yet. This does not change the diffusion recipe."
            ),
        )
    )
    return insights


def quality_setting_adjustments(
    insights: list[QualityDimensionInsight],
    policy: LearningPolicy,
) -> list[RecipeAdjustment]:
    usable = [item for item in insights if item.applied and item.bestGuidance is not None and item.bestSteps is not None]
    if not usable:
        return []
    weight = sum(max(1, item.evidence) for item in usable)
    guidance = sum(float(item.bestGuidance) * max(1, item.evidence) for item in usable) / weight
    steps = sum(int(item.bestSteps) * max(1, item.evidence) for item in usable) / weight
    evidence = sum(item.evidence for item in usable)
    learning_class = "global_quality" if any(item.learningClass == "global_quality" for item in usable) else usable[0].learningClass
    source = "quality"
    explanation = (
        f"Recipe settings moved toward guidance {guidance:g} / steps {round(steps)} "
        f"because {evidence} quality ratings favored that cluster."
    )
    return [
        RecipeAdjustment(
            id="set:guidance@quality",
            kind="guidance",
            value=round(guidance, 3),
            sourceScope="global" if learning_class == "global_quality" else "asset_type",
            source=source,
            confidence=max(item.confidence for item in usable),
            accepted=sum(item.good for item in usable),
            rejected=sum(item.bad for item in usable),
            evidence=evidence,
            applied=True,
            explanation=explanation,
            learningClass=learning_class,
        ),
        RecipeAdjustment(
            id="set:steps@quality",
            kind="steps",
            value=int(round(steps)),
            sourceScope="global" if learning_class == "global_quality" else "asset_type",
            source=source,
            confidence=max(item.confidence for item in usable),
            accepted=sum(item.good for item in usable),
            rejected=sum(item.bad for item in usable),
            evidence=evidence,
            applied=True,
            explanation=explanation,
            learningClass=learning_class,
        ),
    ]


def exploit_ratio_for(asset: AssetProfile, policy: LearningPolicy) -> float:
    from learning.quality_first import is_quality_first

    if is_quality_first(asset):
        return policy.qualityExploitRatio
    return policy.exploitRatio
