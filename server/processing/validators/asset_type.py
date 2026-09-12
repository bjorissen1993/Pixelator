"""Asset-type validators. Character checks use flags from the selected asset, not a named character."""

from __future__ import annotations

from PIL import Image

from models.catalog import AssetProfile
from models.character import QualityValidation, QualityWarning
from processing.validation import _warn, validate_sprite

CROP_CODES = {
    "likely_cropped",
    "touches_top",
    "touches_bottom",
    "touches_left",
    "touches_right",
    "touches_edges",
    "silhouette_incomplete",
}
FULL_BODY_CODES = {
    "likely_portrait",
    "likely_closeup",
    "likely_non_full_body",
    "missing_lower_body",
    "lower_spirit_body_missing",
    "missing_spirit_tail",
    "silhouette_incomplete",
}
SUBJECT_CODES = {
    "possible_duplicate_figure",
    "extra_characters",
    "extra_artifact",
}

TYPE_MESSAGES = {
    **{code: "Rejected: subject is cropped" for code in CROP_CODES},
    **{code: "Rejected: silhouette is not full body" for code in FULL_BODY_CODES},
    **{code: "Rejected: more than one subject appears" for code in SUBJECT_CODES},
    "busy_background": "Rejected: background is busy",
}


def character_validation(image: Image.Image, asset: AssetProfile) -> QualityValidation:
    return validate_sprite(
        image,
        expected_size=image.size[0],
        palette_limit=512,
        spirit_form=asset.flags.spiritForm,
        for_base=True,
        one_character=asset.flags.oneSubject,
        source=image,
    )


def item_warnings(image: Image.Image, asset: AssetProfile) -> list[QualityWarning]:
    extra: list[QualityWarning] = []
    if not asset.flags.isolatedSubject:
        return extra
    width, height = image.size
    pixels = image.convert("RGBA").load()
    opaque = 0
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] >= 16:
                opaque += 1
    occupancy = opaque / max(1, width * height)
    if occupancy > 0.72:
        extra.append(_warn("item_not_isolated", "Subject does not read as an isolated item", "error"))
    if min(width, height) >= 64 and occupancy < 0.04:
        extra.append(_warn("item_unreadable", "Subject is too small to read at this size", "error"))
    return extra


def tile_warnings(_image: Image.Image, _asset: AssetProfile) -> list[QualityWarning]:
    # Seamlessness / edge compatibility will attach here when tile generation exists.
    return []


def type_warnings(image: Image.Image, asset: AssetProfile) -> tuple[QualityValidation | None, list[QualityWarning]]:
    if asset.assetType == "character":
        return character_validation(image, asset), []
    if asset.assetType == "item":
        return None, item_warnings(image, asset)
    if asset.assetType == "tile":
        return None, tile_warnings(image, asset)
    return None, []


def type_reject_message(code: str) -> str | None:
    return TYPE_MESSAGES.get(code)
