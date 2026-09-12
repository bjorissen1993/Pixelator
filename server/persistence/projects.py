"""On-disk project / asset tree for the isolated Asset Lab.

Runtime layout (gitignored under data/):

  data/projects/<project>/
    project.json
    style-profile.json
    learning.jsonl
    assets/<asset-type-folder>/<asset-id>/
      asset.json
      session.json
      candidates/
      accepted/
      rejected/
      references/
      learning/
"""

from __future__ import annotations

from pathlib import Path

import config
from models.catalog import AssetProfile, AssetType, ProjectProfile, StyleProfile

ASSET_TYPE_FOLDERS: dict[AssetType, str] = {
    "character": "characters",
    "portrait": "portraits",
    "item": "items",
    "prop": "props",
    "tile": "tiles",
    "background": "backgrounds",
    "ui": "ui",
    "vfx": "vfx",
}

LEGACY_BERWYNN_REVIEW = config.DATA_DIR / "test_review" / "berwynn"


def project_root(project_id: str) -> Path:
    return config.DATA_DIR / "projects" / project_id


def asset_type_dir(project_id: str, asset_type: AssetType) -> Path:
    return project_root(project_id) / "assets" / ASSET_TYPE_FOLDERS[asset_type]


def asset_root(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return asset_type_dir(project_id, asset_type) / asset_id


def candidate_dir(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return asset_root(project_id, asset_type, asset_id) / "candidates"


def accepted_dir(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return asset_root(project_id, asset_type, asset_id) / "accepted"


def rejected_dir(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return asset_root(project_id, asset_type, asset_id) / "rejected"


def learning_dir(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return asset_root(project_id, asset_type, asset_id) / "learning"


def references_dir(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return asset_root(project_id, asset_type, asset_id) / "references"


def session_path(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return asset_root(project_id, asset_type, asset_id) / "session.json"


def accepted_canonical_path(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return accepted_dir(project_id, asset_type, asset_id) / "canonical.png"


def ensure_asset_dirs(project: ProjectProfile, style: StyleProfile | None, asset: AssetProfile) -> Path:
    root = asset_root(asset.projectId, asset.assetType, asset.assetId)
    for folder in (
        candidate_dir(asset.projectId, asset.assetType, asset.assetId),
        accepted_dir(asset.projectId, asset.assetType, asset.assetId),
        rejected_dir(asset.projectId, asset.assetType, asset.assetId),
        learning_dir(asset.projectId, asset.assetType, asset.assetId),
        references_dir(asset.projectId, asset.assetType, asset.assetId),
    ):
        folder.mkdir(parents=True, exist_ok=True)
    project_dir = project_root(asset.projectId)
    (project_dir / "project.json").write_text(project.model_dump_json(indent=2), encoding="utf-8")
    if style is not None:
        (project_dir / "style-profile.json").write_text(style.model_dump_json(indent=2), encoding="utf-8")
    (root / "asset.json").write_text(asset.model_dump_json(indent=2), encoding="utf-8")
    (config.DATA_DIR / "learning").mkdir(parents=True, exist_ok=True)
    return root


def seed_project_placeholders(project_id: str) -> None:
    """Create empty type folders so the tree is visible even before those generators exist."""
    for folder in ASSET_TYPE_FOLDERS.values():
        (project_root(project_id) / "assets" / folder).mkdir(parents=True, exist_ok=True)
