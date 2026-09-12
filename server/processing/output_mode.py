"""Asset-type / profile output policy. No named-character special cases."""

from __future__ import annotations

from models.catalog import AssetProfile, AssetType, BackgroundMode

TRANSPARENT_ASSET_TYPES: frozenset[AssetType] = frozenset(
    {"character", "portrait", "item", "prop", "ui", "vfx"}
)
SOLID_ASSET_TYPES: frozenset[AssetType] = frozenset({"tile"})
SCENE_ASSET_TYPES: frozenset[AssetType] = frozenset({"background"})


def default_background_mode(asset_type: AssetType) -> BackgroundMode:
    if asset_type in SCENE_ASSET_TYPES:
        return "scene"
    if asset_type in TRANSPARENT_ASSET_TYPES:
        return "transparent"
    return "solid"


def background_mode_for(asset: AssetProfile) -> BackgroundMode:
    return asset.generation.backgroundMode or default_background_mode(asset.assetType)


def expects_isolated_output(asset: AssetProfile) -> bool:
    return background_mode_for(asset) == "transparent"
