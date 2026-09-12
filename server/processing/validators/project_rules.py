"""Project / style validators. Enabled only by the current project's style profile."""

from __future__ import annotations

from PIL import Image

from models.catalog import StyleProfile
from models.character import QualityWarning
from processing.validation import _warn
from processing.validators.heuristics import unique_opaque_colors


def project_warnings(image: Image.Image, style: StyleProfile | None) -> list[QualityWarning]:
    if style is None:
        return []
    extra: list[QualityWarning] = []
    for rule in style.validatorRules:
        if not rule.enabled:
            continue
        if rule.id == "style_palette_limit":
            limit = int(rule.params.get("limit") or style.paletteLimit or 0)
            if limit and unique_opaque_colors(image) > limit:
                extra.append(_warn(rule.id, rule.message, "error"))
    return extra
