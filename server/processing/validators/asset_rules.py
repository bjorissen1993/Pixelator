"""Asset-specific validators. Rule IDs are generic; a profile opts into them."""

from __future__ import annotations

from collections.abc import Callable

from PIL import Image

from models.catalog import AssetProfile, ValidatorRule
from models.character import QualityValidation, QualityWarning
from processing.validation import _metrics, _warn
from processing.validators.heuristics import bulky_shoulder_or_metal, split_lower_body

SPIRIT_CODES = {
    "missing_lower_body",
    "lower_spirit_body_missing",
    "missing_spirit_tail",
}


def _no_visible_legs(image: Image.Image, _rule: ValidatorRule, _validation: QualityValidation | None) -> bool:
    return split_lower_body(_metrics(image), image)


def _no_armor(image: Image.Image, _rule: ValidatorRule, _validation: QualityValidation | None) -> bool:
    return bulky_shoulder_or_metal(_metrics(image), image)


def _spectral_lower_body(image: Image.Image, _rule: ValidatorRule, validation: QualityValidation | None) -> bool:
    if validation is not None and any(warning.code in SPIRIT_CODES for warning in validation.warnings):
        return True
    return split_lower_body(_metrics(image), image)


DETECTORS: dict[str, Callable[[Image.Image, ValidatorRule, QualityValidation | None], bool]] = {
    "no_visible_legs": _no_visible_legs,
    "no_armor": _no_armor,
    "spectral_lower_body": _spectral_lower_body,
}


def asset_warnings(
    image: Image.Image,
    asset: AssetProfile,
    validation: QualityValidation | None,
) -> list[QualityWarning]:
    extra: list[QualityWarning] = []
    for rule in asset.validatorRules:
        if not rule.enabled:
            continue
        detector = DETECTORS.get(rule.id)
        if detector is None:
            continue
        if detector(image, rule, validation):
            extra.append(_warn(rule.id, rule.message, "error"))
    return extra


def asset_reject_message(asset: AssetProfile, code: str) -> str | None:
    for rule in asset.validatorRules:
        if rule.id == code and rule.enabled:
            return rule.message
    return None
