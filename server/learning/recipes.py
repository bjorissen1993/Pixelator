"""Compose GenerationRecipe from required identity + learned fragments + bounded exploration."""

from __future__ import annotations

from models.catalog import AssetProfile
from models.learning import GenerationRecipe, LearningControls, LearningPolicy, RecipeAdjustment, RecipeMode
from learning.policy import unit_interval
from learning.quality_first import is_quality_first
from learning.quality_recipes import exploit_ratio_for
from learning.scoring import recipe_fingerprint

STANDARD_EXPLORE_PROFILES = (
    {"guidance": 0.5, "steps": 2, "label": "nearby stronger / longer"},
    {"guidance": -0.5, "steps": -2, "label": "nearby softer / shorter"},
)
QUALITY_EXPLORE_PROFILES = (
    {"guidance": -0.7, "steps": -2, "label": "softer / shorter"},
    {"guidance": 0.5, "steps": 2, "label": "stronger / longer"},
    {"guidance": -0.5, "steps": 2, "label": "softer / longer"},
    {"guidance": 0.8, "steps": -2, "label": "stronger / shorter"},
)


def nearest_int(value: float) -> int:
    """Half-up for positive values so 3.2→3 and 8.5→9 stay deterministic."""
    return int(value + 0.5) if value >= 0 else int(value - 0.5)


def allocate_batch(count: int, exploit_ratio: float) -> tuple[int, int]:
    """Return (exploit_count, explore_count) for a candidate batch.

    exploit_count = nearest integer of count * requested_ratio, clipped to [0, count].
    Requested 0.8 therefore yields 3/1, 4/1, 8/2, 16/4 for batches 4, 5, 10, 20.
    A batch of 0 allocates nothing.
    """
    count = int(count)
    if count <= 0:
        return 0, 0
    ratio = unit_interval(exploit_ratio)
    exploit_n = min(count, max(0, nearest_int(count * ratio)))
    return exploit_n, count - exploit_n


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
    explore_index: int = 0,
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
        if not is_quality_first(asset):
            optional = [item for item in recommendations if item.kind.endswith("fragment") and not item.applied and not item.disabled]
            if optional:
                extra = optional[0]
                if extra.kind == "negative_fragment":
                    negatives.append(str(extra.value))
                else:
                    positives.append(str(extra.value))
                extra = extra.model_copy(update={"applied": True, "explanation": extra.explanation + " Explored as a nearby optional fragment."})
                applied.append(extra)
        profiles = QUALITY_EXPLORE_PROFILES if is_quality_first(asset) else STANDARD_EXPLORE_PROFILES
        profile = profiles[explore_index % len(profiles)]
        before_guidance = guidance
        before_steps = steps
        guidance += float(profile["guidance"])
        steps += int(profile["steps"])
        if reference_strength is not None:
            reference_strength += policy.exploreReferenceDelta
        recipe.why.append(
            f"Explore {profile['label']}: guidance {before_guidance:g}→{guidance:g}, steps {before_steps}→{steps}."
        )

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
    exploit_n, explore_n = allocate_batch(count, exploit_ratio_for(asset, policy))
    modes: list[RecipeMode] = ["exploit"] * exploit_n + ["explore"] * explore_n
    recipes: list[GenerationRecipe] = []
    explore_index = 0
    for mode in modes:
        recipes.append(build_next_recipe(asset, recommendations, policy, controls, mode, explore_index))
        if mode == "explore":
            explore_index += 1
    return recipes
