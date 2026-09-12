"""Hierarchical learning records. Context stays on every row so rules cannot leak globally.

A rejection like "armor is bad" is stored with project/asset-type/asset IDs.
Future learners must filter by that hierarchy; this writer never promotes an
asset-specific reason to a global rule.
"""

from __future__ import annotations

import json
from pathlib import Path

import config
from models.catalog import LearningRecord
from persistence.projects import ASSET_TYPE_FOLDERS, learning_dir, project_root


def _append_jsonl(path: Path, record: LearningRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json() + "\n")


def write_learning_record(record: LearningRecord) -> LearningRecord:
    asset_folder = learning_dir(record.projectId, record.assetType, record.assetId)
    asset_folder.mkdir(parents=True, exist_ok=True)
    (asset_folder / f"{record.id}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")

    type_folder = ASSET_TYPE_FOLDERS[record.assetType]
    _append_jsonl(config.DATA_DIR / "learning" / "global.jsonl", record)
    _append_jsonl(project_root(record.projectId) / "learning.jsonl", record)
    _append_jsonl(project_root(record.projectId) / "assets" / type_folder / "learning.jsonl", record)
    _append_jsonl(asset_folder / "events.jsonl", record)
    return record
