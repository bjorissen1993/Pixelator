"""Resolve hierarchical recommendations. Asset evidence never becomes global."""

from __future__ import annotations

from models.catalog import AssetProfile, LearningRecord
from models.learning import LearningControls, LearningPolicy, LearningSnapshot, LearningStats, RecipeAdjustment
from learning.context import LearningContext, record_matches
from learning.policy import load_policy, unit_interval
from learning.recipes import allocate_batch, build_next_recipe
from learning.scoring import score_recipes
from learning.signals import collect_signals, generation_records, split_rejection_reasons

__all__ = ["LearningContext", "apply_controls", "resolve_learning"]


def _after_reset(record: LearningRecord, controls: LearningControls, scope: str) -> bool:
    marker = controls.resetAfter.get(scope)
    if not marker:
        return True
    return (record.createdAt or "") >= marker


def apply_controls(items: list[RecipeAdjustment], controls: LearningControls) -> list[RecipeAdjustment]:
    disabled = set(controls.disabledIds)
    pinned_neg = {item.lower() for item in controls.pinnedFragments.get("negative", [])}
    pinned_pos = {item.lower() for item in controls.pinnedFragments.get("positive", [])}
    result: list[RecipeAdjustment] = []
    for item in items:
        copy = item.model_copy()
        if copy.id in disabled:
            copy.disabled = True
            copy.applied = False
        if copy.kind == "negative_fragment" and str(copy.value).lower() in pinned_neg:
            copy.pinned = True
            copy.applied = True
        if copy.kind == "positive_fragment" and str(copy.value).lower() in pinned_pos:
            copy.pinned = True
            copy.applied = True
        if copy.kind in {"guidance", "steps", "reference_strength"}:
            pinned = controls.pinnedSettings.get(copy.kind) or controls.pinnedSettings.get(
                "referenceStrength" if copy.kind == "reference_strength" else copy.kind
            )
            if pinned is not None:
                copy.pinned = True
                copy.applied = False
                copy.explanation = f"{copy.kind} is pinned to {pinned} and cannot be overridden by learning."
        result.append(copy)
    for fragment in controls.pinnedFragments.get("negative", []):
        if not any(item.kind == "negative_fragment" and str(item.value).lower() == fragment.lower() for item in result):
            result.append(
                RecipeAdjustment(
                    id=f"pin:neg:{fragment.lower()}",
                    kind="negative_fragment",
                    value=fragment,
                    sourceScope="asset",
                    source="pinned",
                    confidence=1.0,
                    applied=True,
                    pinned=True,
                    explanation=f"Pinned negative fragment '{fragment}'.",
                )
            )
    for fragment in controls.pinnedFragments.get("positive", []):
        if not any(item.kind == "positive_fragment" and str(item.value).lower() == fragment.lower() for item in result):
            result.append(
                RecipeAdjustment(
                    id=f"pin:pos:{fragment.lower()}",
                    kind="positive_fragment",
                    value=fragment,
                    sourceScope="asset",
                    source="pinned",
                    confidence=1.0,
                    applied=True,
                    pinned=True,
                    explanation=f"Pinned positive fragment '{fragment}'.",
                )
            )
    return result


def _stats(records: list[LearningRecord], context: LearningContext) -> LearningStats:
    scoped = [
        item
        for item in generation_records(records)
        if item.projectId == context.projectId
        and item.assetType == context.assetType
        and item.assetId == context.assetId
    ]
    accepted = sum(1 for item in scoped if item.decision == "accepted")
    rejected = sum(1 for item in scoped if item.decision == "rejected")
    attempts = accepted + rejected
    reasons: dict[str, int] = {}
    automatic: dict[str, int] = {}
    manual: dict[str, int] = {}
    for item in scoped:
        auto_reasons, manual_reasons = split_rejection_reasons(item)
        for reason in auto_reasons:
            automatic[reason] = automatic.get(reason, 0) + 1
            reasons[reason] = reasons.get(reason, 0) + 1
        for reason in manual_reasons:
            manual[reason] = manual.get(reason, 0) + 1
            reasons[reason] = reasons.get(reason, 0) + 1
    top = [key for key, _value in sorted(reasons.items(), key=lambda pair: pair[1], reverse=True)[:5]]
    top_auto = [key for key, _value in sorted(automatic.items(), key=lambda pair: pair[1], reverse=True)[:5]]
    top_manual = [key for key, _value in sorted(manual.items(), key=lambda pair: pair[1], reverse=True)[:5]]
    return LearningStats(
        attempts=attempts,
        accepted=accepted,
        rejected=rejected,
        successRate=round(accepted / attempts, 3) if attempts else 0,
        topRejectionReasons=top,
        topAutomaticReasons=top_auto,
        topManualReasons=top_manual,
    )


def resolve_learning(
    asset: AssetProfile,
    records: list[LearningRecord],
    controls: LearningControls | None = None,
    policy: LearningPolicy | None = None,
    batch_size: int | None = None,
) -> LearningSnapshot:
    context = LearningContext(
        projectId=asset.projectId,
        assetType=asset.assetType,
        assetId=asset.assetId,
        state=asset.state,
        direction=asset.direction,
    )
    controls = controls or LearningControls()
    policy = policy or load_policy()
    usable = [
        item
        for item in records
        if _after_reset(item, controls, item.scope or "asset")
    ]
    recommendations = apply_controls(collect_signals(context, usable, policy), controls)
    recipe_scores = score_recipes(
        [
            item
            for item in usable
            if record_matches(item, context, "asset") or record_matches(item, context, "state")
        ],
        policy,
    )
    next_recipe = build_next_recipe(asset, recommendations, policy, controls)
    stats = _stats(usable, context)
    why = [item.explanation for item in next_recipe.adjustments if item.applied and item.explanation]
    if not why:
        why = ["Using the asset's required generation spec. Learning has not crossed the apply threshold yet."]
    batch = max(1, int(batch_size if batch_size is not None else policy.previewBatchSize))
    allocated_exploit, allocated_explore = allocate_batch(batch, policy.exploitRatio)
    requested_exploit = unit_interval(policy.exploitRatio)
    requested_explore = round(1 - requested_exploit, 3)
    return LearningSnapshot(
        projectId=asset.projectId,
        assetType=asset.assetType,
        assetId=asset.assetId,
        state=asset.state,
        direction=asset.direction,
        stats=stats,
        policy=policy,
        exploitRatio=requested_exploit,
        exploreRatio=requested_explore,
        requestedExploitRatio=requested_exploit,
        requestedExploreRatio=requested_explore,
        allocationBatchSize=batch,
        allocatedExploit=allocated_exploit,
        allocatedExplore=allocated_explore,
        allocatedExploitRatio=round(allocated_exploit / batch, 3),
        allocatedExploreRatio=round(allocated_explore / batch, 3),
        recommendations=recommendations,
        recipeScores=recipe_scores[:8],
        nextRecipe=next_recipe,
        why=why,
    )
