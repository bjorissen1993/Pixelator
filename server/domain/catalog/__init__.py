"""Versioned project / asset-type / asset profiles for the isolated Asset Lab."""

from domain.catalog.chimera import BERWYNN_ASSET, CHIMERA_PROJECT, CHIMERA_STYLE
from domain.catalog.registry import (
    all_assets,
    all_projects,
    all_styles,
    default_selection,
    get_asset,
    get_project,
    get_style,
)

__all__ = [
    "BERWYNN_ASSET",
    "CHIMERA_PROJECT",
    "CHIMERA_STYLE",
    "all_assets",
    "all_projects",
    "all_styles",
    "default_selection",
    "get_asset",
    "get_project",
    "get_style",
]
