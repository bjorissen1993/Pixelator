"""Compose GenerationRecipe from required identity + learned fragments + bounded exploration."""

from __future__ import annotations

from models.catalog import AssetProfile
from models.learning import GenerationRecipe, LearningControls, LearningPolicy, RecipeAdjustment, RecipeMode
from learning.scoring import recipe_fingerprint


def _join(base: str, fragments: list[str]) -> str:
    seen: set[str] = set()
    parts: list[str] = []
    if base.strip():
        parts.append(base.strip())
        seen.add(base.strip().lower())
    for fragment in fragments:
        text = str(fragment).strip()
        if not text or text.lower() in seen or text.lower() in base.lower():
            continue
        parts.append(text)
        seen.add(text.lower())
    return ", ".join(parts)


def build_base_recipe(asset: AssetProfile) -> GenerationRecipe:
    spec = asset.generation
    recipe = GenerationRecipe(
        modelId=spec.modelId,
        provider="isolated-asset-lab",
        prompt=spec.prompt,
        negativePrompt=spec.negativePrompt,
        identityPrompt=spec.prompt,
        identityNegative=spec.negativePrompt,
        guidance=spec.guidance,
        steps=spec.steps,
        width=spec.width,
        height=spec.height,
        referenceStrategy="none",
        why=["Required identity and style come from the selected asset profile."],
    )
    recipe.fingerprint = recipe_fingerprint(recipe)
    return recipe


def build_next_recipe(
    asset: AssetProfile,
    recommendations: list[RecipeAdjustment],
    policy: LearningPolicy,
    controls: LearningControls | None = None,
    mode: RecipeMode = "exploit",
) -> GenerationRecipe:
    controls = controls or LearningControls()
    recipe = build_base_recipe(asset)
    positives = list(controls.pinnedFragments.get("positive", []))
    negatives = list(controls.pinnedFragments.get("negative", []))
    guidance = float(controls.pinnedSettings.get("guidance") or recipe.guidance)
    steps = int(controls.pinnedSettings.get("steps") or recipe.steps)
    ref = controls.pinnedSettings.get("referenceStrength")
    reference_strength = float(ref) if ref is not None else recipe.referenceStrength
    applied: list[RecipeAdjustment] = []

    for item in recommendations:
        if item.disabled:
            continue
        if item.kind == "negative_fragment" and (item.applied or item.pinned):
            negatives.append(str(item.value))
            applied.append(item)
        elif item.kind == "positive_fragment" and (item.applied or item.pinned):
            positives.append(str(item.value))
            applied.append(item)
        elif item.kind == "guidance" and item.applied and "guidance" not in controls.pinnedSettings:
            blend = policy.strongSettingBlend if item.confidence >= policy.strongConfidence else policy.applySettingBlend
            guidance = recipe.guidance + blend * (float(item.value) - recipe.guidance)
            applied.append(item)
        elif item.kind == "steps" and item.applied and "steps" not in controls.pinnedSettings:
            blend = policy.strongSettingBlend if item.confidence >= policy.strongConfidence else policy.applySettingBlend
            steps = int(round(recipe.steps + blend * (float(item.value) - recipe.steps)))
            applied.append(item)
        elif item.kind == "reference_strength" and item.applied and "referenceStrength" not in controls.pinnedSettings:
            current = recipe.referenceStrength or float(item.value)
            blend = policy.strongSettingBlend if item.confidence >= policy.strongConfidence else policy.applySettingBlend
            reference_strength = current + blend * (float(item.value) - current)
            applied.append(item)

    if mode == "explore":
        optional = [item for item in recommendations if item.kind.endswith("fragment") and not item.applied and not item.disabled]
        if optional:
            extra = optional[0]
            if extra.kind == "negative_fragment":
                negatives.append(str(extra.value))
            else:
                positives.append(str(extra.value))
            extra = extra.model_copy(update={"applied": True, "explanation": extra.explanation + " Explored as a nearby optional fragment."})
            applied.append(extra)
        guidance += policy.exploreGuidanceDelta
        steps += policy.exploreStepsDelta
        if reference_strength is not None:
            reference_strength += policy.exploreReferenceDelta
        recipe.why.append("This candidate explores nearby settings instead of locking the first success.")

    guidance = max(policy.minGuidance, min(policy.maxGuidance, guidance))
    steps = max(policy.minSteps, min(policy.maxSteps, steps))
    if reference_strength is not None:
        reference_strength = max(policy.minReferenceStrength, min(policy.maxReferenceStrength, reference_strength))

    recipe.positiveFragments = positives
    recipe.negativeFragments = negatives
    recipe.prompt = _join(recipe.identityPrompt, positives)
    recipe.negativePrompt = _join(recipe.identityNegative, negatives)
    recipe.guidance = round(guidance, 3)
    recipe.steps = steps
    recipe.referenceStrength = None if reference_strength is None else round(reference_strength, 3)
    recipe.adjustments = applied
    recipe.mode = mode
    recipe.why = [*recipe.why, *[item.explanation for item in applied if item.explanation]]
    recipe.fingerprint = recipe_fingerprint(recipe)
    return recipe


def plan_candidate_recipes(
    asset: AssetProfile,
    recommendations: list[RecipeAdjustment],
    policy: LearningPolicy,
    count: int,
    controls: LearningControls | None = None,
) -> list[GenerationRecipe]:
    count = max(1, count)
    exploit_n = count if count == 1 else max(1, round(count * policy.exploitRatio))
    exploit_n = min(count, exploit_n)
    modes: list[RecipeMode] = ["exploit"] * exploit_n + ["explore"] * (count - exploit_n)
    return [build_next_recipe(asset, recommendations, policy, controls, mode) for mode in modes]
