"""Configurable evidence thresholds. Defaults live here; data/learning/policy.json may override."""

from __future__ import annotations

from pathlib import Path

import config
from models.learning import LearningPolicy

DEFAULT_POLICY = LearningPolicy()


def policy_path() -> Path:
    return config.DATA_DIR / "learning" / "policy.json"


def load_policy() -> LearningPolicy:
    path = policy_path()
    if not path.is_file():
        return DEFAULT_POLICY.model_copy()
    return LearningPolicy.model_validate_json(path.read_text(encoding="utf-8"))


def unit_interval(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def confidence_for(evidence: int, consistency: float, policy: LearningPolicy) -> tuple[float, bool, str]:
    """confidence = unit(band_scale) * unit(consistency). Always in [0, 1]."""
    consistency = unit_interval(consistency)
    if evidence < policy.minSuggest:
        return 0.0, False, "record"
    if evidence < policy.minApply:
        return round(unit_interval(policy.suggestConfidence) * consistency, 3), False, "suggest"
    if evidence < policy.minStrong:
        return round(unit_interval(policy.applyConfidence) * consistency, 3), True, "apply"
    return round(unit_interval(policy.strongConfidence) * consistency, 3), True, "strong"
