"""Manual review reasons. Generic and type-specific entries live here; asset-specific
reasons come from the selected asset profile and must not be hardcoded globally.
"""

from __future__ import annotations

from models.catalog import AssetProfile, ReviewReason

GLOBAL_REVIEW_REASONS = [
    ReviewReason(id="wrong_silhouette", label="wrong silhouette", layer="global"),
    ReviewReason(id="wrong_direction_pose", label="wrong direction / pose", layer="global"),
    ReviewReason(id="cropped_not_full_body", label="cropped / not full body", layer="global"),
    ReviewReason(id="multiple_subjects", label="multiple subjects", layer="global"),
    ReviewReason(id="busy_background", label="busy background", layer="global"),
    ReviewReason(id="style_mismatch", label="style mismatch", layer="global"),
    ReviewReason(id="other", label="other", layer="global"),
]

TYPE_REVIEW_REASONS = [
    ReviewReason(
        id="wrong_age",
        label="wrong age",
        layer="asset_type",
        assetTypes=["character", "portrait"],
    ),
    ReviewReason(
        id="wrong_hair_beard",
        label="wrong hair / beard",
        layer="asset_type",
        assetTypes=["character", "portrait"],
    ),
    ReviewReason(
        id="wrong_clothing",
        label="wrong clothing",
        layer="asset_type",
        assetTypes=["character", "portrait"],
    ),
    ReviewReason(
        id="not_isolated",
        label="subject is not isolated",
        layer="asset_type",
        assetTypes=["item", "prop"],
    ),
    ReviewReason(
        id="unreadable",
        label="unreadable at this size",
        layer="asset_type",
        assetTypes=["item", "prop", "ui", "vfx"],
    ),
]


def reasons_for_asset(asset: AssetProfile) -> list[ReviewReason]:
    """Asset-specific first, then type, then generic. IDs stay unique."""
    seen: set[str] = set()
    result: list[ReviewReason] = []
    for item in [*asset.reviewReasons, *TYPE_REVIEW_REASONS, *GLOBAL_REVIEW_REASONS]:
        if item.assetTypes and asset.assetType not in item.assetTypes:
            continue
        if item.id in seen:
            continue
        seen.add(item.id)
        result.append(item)
    return result


def resolve_manual_reasons(asset: AssetProfile, reason_ids: list[str], note: str = "") -> list[str]:
    allowed = {item.id: item for item in reasons_for_asset(asset)}
    labels: list[str] = []
    unknown = [item for item in reason_ids if item not in allowed]
    if unknown:
        raise ValueError(f"Unknown review reason(s) for this asset: {', '.join(unknown)}")
    for reason_id in reason_ids:
        label = allowed[reason_id].label
        if label not in labels:
            labels.append(label)
    cleaned = note.strip()
    if cleaned and "other" in reason_ids and cleaned not in labels:
        labels.append(cleaned)
    return labels
