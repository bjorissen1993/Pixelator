"""Transparent recipe scoring. Seed is stored on records but never part of the fingerprint.

Score is a weighted sum of already-normalized rates:

    acceptRate         = accepts / attempts
    validatorPassRate  = validator_passes / attempts
    ratingScore        = (average rating / ratingScale)

    score = wAccept * acceptRate
          + wValidator * validatorPassRate
          + wRating * ratingScore

Weights are renormalized to sum to 1. Each rate is in [0, 1], so the score is in [0, 1].
Missing ratings contribute 0 through the rating term; they do not invent a rating.
Zero attempts scores 0.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from models.catalog import LearningRecord
from models.learning import GenerationRecipe, LearningPolicy, RecipeScore
from learning.policy import DEFAULT_POLICY, unit_interval


def recipe_fingerprint(recipe: GenerationRecipe) -> str:
    payload = {
        "modelId": recipe.modelId,
        "provider": recipe.provider,
        "positiveFragments": sorted({item.strip() for item in recipe.positiveFragments if item.strip()}),
        "negativeFragments": sorted({item.strip() for item in recipe.negativeFragments if item.strip()}),
        "guidance": round(float(recipe.guidance), 3),
        "steps": int(recipe.steps),
        "width": int(recipe.width),
        "height": int(recipe.height),
        "referenceStrategy": recipe.referenceStrategy,
        "referenceStrength": None if recipe.referenceStrength is None else round(float(recipe.referenceStrength), 3),
        "scheduler": recipe.scheduler,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def score_weights(policy: LearningPolicy) -> tuple[float, float, float]:
    weights = (
        max(0.0, float(policy.scoreWeightAccept)),
        max(0.0, float(policy.scoreWeightValidator)),
        max(0.0, float(policy.scoreWeightRating)),
    )
    total = sum(weights)
    if total <= 0:
        return 0.60, 0.25, 0.15
    return tuple(weight / total for weight in weights)


def recipe_score(
    accepts: int,
    rejects: int,
    validator_passes: int,
    rating_sum: float,
    rating_n: int,
    policy: LearningPolicy | None = None,
) -> float:
    policy = policy or DEFAULT_POLICY
    attempts = max(0, int(accepts) + int(rejects))
    if attempts <= 0:
        return 0.0
    accept_rate = unit_interval(accepts / attempts)
    validator_rate = unit_interval(validator_passes / attempts)
    scale = max(1.0, float(policy.ratingScale))
    rating_score = unit_interval((rating_sum / rating_n) / scale) if rating_n else 0.0
    w_accept, w_validator, w_rating = score_weights(policy)
    return round(w_accept * accept_rate + w_validator * validator_rate + w_rating * rating_score, 4)


def score_recipes(records: list[LearningRecord], policy: LearningPolicy | None = None) -> list[RecipeScore]:
    policy = policy or DEFAULT_POLICY
    buckets: dict[str, dict] = defaultdict(
        lambda: {
            "attempts": 0,
            "accepts": 0,
            "rejects": 0,
            "validator_passes": 0,
            "rating_sum": 0.0,
            "rating_n": 0,
            "reasons": CounterShim(),
        }
    )
    for item in records:
        key = item.recipeFingerprint or ""
        if not key:
            continue
        bucket = buckets[key]
        bucket["attempts"] += 1
        if item.decision == "accepted":
            bucket["accepts"] += 1
        else:
            bucket["rejects"] += 1
        if item.validationResults.get("ok") or item.validationResults.get("validForBase"):
            bucket["validator_passes"] += 1
        if item.manualRating is not None:
            bucket["rating_sum"] += item.manualRating
            bucket["rating_n"] += 1
        for reason in item.rejectionReasons:
            bucket["reasons"][reason] = bucket["reasons"].get(reason, 0) + 1
    scored: list[RecipeScore] = []
    for fingerprint, bucket in buckets.items():
        average = None
        if bucket["rating_n"]:
            average = round(bucket["rating_sum"] / bucket["rating_n"], 3)
        scored.append(
            RecipeScore(
                fingerprint=fingerprint,
                attempts=bucket["attempts"],
                accepts=bucket["accepts"],
                rejects=bucket["rejects"],
                validatorPassRate=round(bucket["validator_passes"] / max(1, bucket["attempts"]), 3),
                averageRating=average,
                rejectionReasons=dict(bucket["reasons"]),
                score=recipe_score(
                    bucket["accepts"],
                    bucket["rejects"],
                    bucket["validator_passes"],
                    bucket["rating_sum"],
                    bucket["rating_n"],
                    policy,
                ),
            )
        )
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored


class CounterShim(dict):
    def __missing__(self, key):
        return 0
