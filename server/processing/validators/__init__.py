"""Layered validation: global → asset-type → project/style → asset-specific."""

from __future__ import annotations

from PIL import Image

from models.catalog import AssetProfile, StyleProfile
from models.character import QualityValidation, QualityWarning
from processing.validators.asset_rules import asset_reject_message, asset_warnings
from processing.validators.asset_type import type_reject_message, type_warnings
from processing.validators.global_rules import BUSY_BG_CODE, MULTI_CODE, global_warnings
from processing.validators.project_rules import project_warnings

GLOBAL_MESSAGES = {
    BUSY_BG_CODE: "Rejected: background is busy",
    MULTI_CODE: "Rejected: more than one subject appears",
    "image_integrity": "Rejected: image is empty or unreadable",
    "expected_dimensions": "Rejected: image dimensions do not match the request",
    "image_corrupt": "Rejected: image is corrupt",
    "item_not_isolated": "Rejected: subject is not isolated",
    "item_unreadable": "Rejected: subject is not readable at this size",
}


def _empty_validation() -> QualityValidation:
    return QualityValidation()


def _merge(validation: QualityValidation, extra: list[QualityWarning]) -> QualityValidation:
    seen = {warning.code for warning in validation.warnings}
    merged = list(validation.warnings)
    for warning in extra:
        if warning.code not in seen:
            merged.append(warning)
            seen.add(warning.code)
    validation.warnings = merged
    return validation


def reject_reasons(
    asset: AssetProfile,
    validation: QualityValidation,
    extra: list[QualityWarning],
) -> list[str]:
    reasons: list[str] = []
    for warning in [*validation.warnings, *extra]:
        message = (
            asset_reject_message(asset, warning.code)
            or type_reject_message(warning.code)
            or GLOBAL_MESSAGES.get(warning.code)
        )
        if message and message not in reasons:
            reasons.append(message)
    return reasons


def validate_candidate(
    image: Image.Image,
    asset: AssetProfile,
    style: StyleProfile | None = None,
) -> tuple[QualityValidation, list[str], bool]:
    masked, global_extra = global_warnings(image, asset)
    type_validation, type_extra = type_warnings(masked, asset)
    validation = type_validation or _empty_validation()
    extra = [*global_extra, *type_extra, *project_warnings(masked, style), *asset_warnings(masked, asset, validation)]
    validation = _merge(validation, extra)
    reasons = reject_reasons(asset, validation, extra)
    valid = not reasons
    validation.validForBase = valid
    validation.ok = valid
    busy = any(warning.code == BUSY_BG_CODE for warning in extra)
    return validation, reasons, busy
