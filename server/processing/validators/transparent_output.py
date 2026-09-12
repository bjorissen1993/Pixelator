"""Generic validators for derived transparent asset files.

These apply to the isolated artifact, not the raw review image, and they do
not mention a specific character or project.
"""

from __future__ import annotations

from PIL import Image

from models.character import QualityWarning
from processing.isolation import IsolationReport, describe_isolation
from processing.validation import _warn

ISOLATED_MESSAGES = {
    "isolated_missing_alpha": "Isolated output: missing alpha channel",
    "isolated_low_transparency": "Isolated output: transparent coverage is too low",
    "isolated_background_remnants": "Isolated output: too much background remains",
    "isolated_multiple_subjects": "Isolated output: more than one subject",
    "isolated_cropped": "Isolated output: subject is cropped",
    "isolated_bbox": "Isolated output: bounding box is not reasonable",
}


def transparent_output_warnings(
    isolated: Image.Image,
    report: IsolationReport | None = None,
) -> list[QualityWarning]:
    report = report or describe_isolation(isolated)
    extra: list[QualityWarning] = []
    if not report.has_alpha:
        extra.append(_warn("isolated_missing_alpha", ISOLATED_MESSAGES["isolated_missing_alpha"], "error"))
    if report.transparent_ratio < 0.18:
        extra.append(_warn("isolated_low_transparency", ISOLATED_MESSAGES["isolated_low_transparency"], "error"))
    if report.remnant_ratio > 0.12:
        extra.append(_warn("isolated_background_remnants", ISOLATED_MESSAGES["isolated_background_remnants"], "error"))
    if report.subject_count != 1:
        extra.append(_warn("isolated_multiple_subjects", ISOLATED_MESSAGES["isolated_multiple_subjects"], "error"))
    if report.cropped:
        extra.append(_warn("isolated_cropped", ISOLATED_MESSAGES["isolated_cropped"], "error"))
    if not report.bbox_reasonable:
        extra.append(_warn("isolated_bbox", ISOLATED_MESSAGES["isolated_bbox"], "error"))
    return extra


def isolated_reason_messages(warnings: list[QualityWarning]) -> list[str]:
    return [warning.message for warning in warnings if warning.message]
