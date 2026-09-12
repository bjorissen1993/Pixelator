"""Compatibility wrapper. Berwynn-specific rules live on the Berwynn asset profile."""

from __future__ import annotations

from PIL import Image

from domain.catalog import BERWYNN_ASSET, CHIMERA_STYLE
from models.character import QualityValidation
from processing.validators import validate_candidate
from processing.validators.heuristics import knockout_plain_background

__all__ = ["knockout_plain_background", "validate_canonical_base"]


def validate_canonical_base(image: Image.Image) -> tuple[QualityValidation, list[str], bool]:
    return validate_candidate(image, BERWYNN_ASSET, CHIMERA_STYLE)
