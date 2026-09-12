"""Configurable evidence thresholds. Defaults live here; data/learning/policy.json may override."""

from __future__ import annotations

from pathlib import Path

import config
from models.learning import LearningPolicy

DEFAULT_POLICY = LearningPolicy()
ALLOWED_BATCH_SIZES = (4, 8, 12, 20)
DEFAULT_BATCH_SIZE = 4


def parse_batch_size(value: int | None) -> int:
    """Asset Lab generation accepts only the configured discrete batch sizes."""
    if value is None:
        return DEFAULT_BATCH_SIZE
    size = int(value)
    if size not in ALLOWED_BATCH_SIZES:
        allowed = ", ".join(str(item) for item in ALLOWED_BATCH_SIZES)
        raise ValueError(f"batchSize must be one of {allowed}.")
    return size


def policy_path() -> Path:
    return config.DATA_DIR / "learning" / "policy.json"


def load_policy() -> LearningPolicy:
    path = policy_path()
    if not path.is_file():
        return DEFAULT_POLICY.model_copy()
    return LearningPolicy.model_validate_json(path.read_text(encoding="utf-8"))


def unit_interval(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def confidence_for(evidence: float, consistency: float, policy: LearningPolicy) -> tuple[float, bool, str]:
    """confidence = unit(band_scale) * unit(consistency). Always in [0, 1]."""
    consistency = unit_interval(consistency)
    if evidence < policy.minSuggest:
        return 0.0, False, "record"
    if evidence < policy.minApply:
        return round(unit_interval(policy.suggestConfidence) * consistency, 3), False, "suggest"
    if evidence < policy.minStrong:
        return round(unit_interval(policy.applyConfidence) * consistency, 3), True, "apply"
    return round(unit_interval(policy.strongConfidence) * consistency, 3), True, "strong"
