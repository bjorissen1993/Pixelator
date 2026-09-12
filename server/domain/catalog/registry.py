"""Generic catalog: builtins + versioned JSON + runtime data overlays.

New projects/assets can be added as JSON without changing core classes.
"""

from __future__ import annotations

import json
from pathlib import Path

import config
from domain.catalog.chimera import builtin_assets, builtin_projects, builtin_styles
from models.catalog import AssetProfile, AssetType, ProjectProfile, StyleProfile
from persistence.projects import ASSET_TYPE_FOLDERS

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"
FOLDER_TO_TYPE: dict[str, AssetType] = {folder: asset_type for asset_type, folder in ASSET_TYPE_FOLDERS.items()}


def _read_model(path: Path, model):
    return model.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _load_project_tree(root: Path) -> tuple[list[ProjectProfile], list[StyleProfile], list[AssetProfile]]:
    projects: list[ProjectProfile] = []
    styles: list[StyleProfile] = []
    assets: list[AssetProfile] = []
    if not root.is_dir():
        return projects, styles, assets
    for project_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        project_file = project_dir / "project.json"
        if project_file.is_file():
            projects.append(_read_model(project_file, ProjectProfile))
        style_file = project_dir / "style-profile.json"
        if style_file.is_file():
            styles.append(_read_model(style_file, StyleProfile))
        assets_root = project_dir / "assets"
        if not assets_root.is_dir():
            continue
        for type_dir in sorted(path for path in assets_root.iterdir() if path.is_dir()):
            asset_type = FOLDER_TO_TYPE.get(type_dir.name)
            if asset_type is None:
                continue
            for item in sorted([*type_dir.glob("*.json"), *type_dir.glob("*/asset.json")]):
                if item.is_file():
                    assets.append(_read_model(item, AssetProfile))
    return projects, styles, assets


def _index_projects(items: list[ProjectProfile]) -> dict[str, ProjectProfile]:
    return {item.id: item for item in items}


def _index_styles(items: list[StyleProfile]) -> dict[str, StyleProfile]:
    return {item.projectId: item for item in items}


def _asset_key(item: AssetProfile) -> tuple[str, str, str]:
    return item.projectId, item.assetType, item.assetId


def _merge() -> tuple[list[ProjectProfile], list[StyleProfile], list[AssetProfile]]:
    data_projects, data_styles, data_assets = _load_project_tree(config.DATA_DIR / "projects")
    profile_projects, profile_styles, profile_assets = _load_project_tree(PROFILES_DIR)

    # Runtime data can introduce new projects. Versioned / builtin metadata wins for known ids
    # so a stale data/project.json cannot turn Chimera into a non-default project.
    projects = _index_projects(data_projects)
    projects.update(_index_projects(profile_projects))
    projects.update(_index_projects(builtin_projects()))

    styles = _index_styles(data_styles)
    styles.update(_index_styles(profile_styles))
    styles.update(_index_styles(builtin_styles()))

    # Assets: runtime data can add new assets. Versioned profiles and builtins win for known ids
    # so a stale data/asset.json cannot drop catalog fields such as reviewMode.
    assets: dict[tuple[str, str, str], AssetProfile] = {}
    for group in (data_assets, profile_assets, builtin_assets()):
        for item in group:
            key = _asset_key(item)
            current = assets.get(key)
            if current and not item.reviewReasons and current.reviewReasons:
                item = item.model_copy(update={"reviewReasons": current.reviewReasons})
            assets[key] = item
    return list(projects.values()), list(styles.values()), list(assets.values())


def all_projects() -> list[ProjectProfile]:
    return _merge()[0]


def all_styles() -> list[StyleProfile]:
    return _merge()[1]


def all_assets() -> list[AssetProfile]:
    return _merge()[2]


def get_project(project_id: str) -> ProjectProfile:
    for item in all_projects():
        if item.id == project_id:
            return item
    raise KeyError(f"Unknown project {project_id}")


def get_style(project_id: str) -> StyleProfile | None:
    for item in all_styles():
        if item.projectId == project_id:
            return item
    return None


def get_asset(project_id: str, asset_type: str, asset_id: str) -> AssetProfile:
    for item in all_assets():
        if item.projectId == project_id and item.assetType == asset_type and item.assetId == asset_id:
            return item
    raise KeyError(f"Unknown asset {project_id}/{asset_type}/{asset_id}")


def default_selection() -> tuple[str, AssetType, str]:
    projects = all_projects()
    if not projects:
        raise KeyError("No Asset Lab projects are registered.")
    project = next((item for item in projects if item.isDefault), projects[0])
    asset_type = project.defaultAssetType
    asset_id = project.defaultAssetId
    if asset_type and asset_id:
        return project.id, asset_type, asset_id
    fallback = next((item for item in all_assets() if item.projectId == project.id), None)
    if fallback is None:
        raise KeyError(f"Project {project.id} has no assets.")
    return fallback.projectId, fallback.assetType, fallback.assetId
