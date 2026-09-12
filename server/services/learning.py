"""Hierarchical learning records. Context stays on every row so rules cannot leak globally.

A rejection like "armor is bad" is stored with project/asset-type/asset IDs.
Future learners must filter by that hierarchy; this writer never promotes an
asset-specific reason to a global rule.
"""

from __future__ import annotations

from pathlib import Path

import config
from models.catalog import AssetProfile, LearningRecord
from models.learning import LearningControlRequest, LearningSnapshot
from persistence.projects import ASSET_TYPE_FOLDERS, learning_dir, project_root
from learning.resolver import resolve_learning
from learning.store import (
    disable_recommendation,
    load_controls,
    load_records,
    pin_fragment,
    pin_setting,
    reset_learning,
)


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


def snapshot_for(asset: AssetProfile, batch_size: int | None = None) -> LearningSnapshot:
    return resolve_learning(
        asset,
        load_records(),
        load_controls(asset.projectId, asset.assetType, asset.assetId),
        batch_size=batch_size,
    )


def apply_learning_control(payload: LearningControlRequest) -> LearningSnapshot:
    if payload.resetScope:
        reset_learning(
            payload.projectId,
            payload.assetType,
            payload.assetId,
            payload.resetScope,
            payload.confirmGlobal,
        )
    elif payload.recommendationId:
        disable_recommendation(payload.projectId, payload.assetType, payload.assetId, payload.recommendationId)
    elif payload.pinKind and payload.pinValue is not None:
        if payload.pinKind in {"guidance", "steps", "referenceStrength", "reference_strength"}:
            key = "referenceStrength" if "reference" in payload.pinKind else payload.pinKind
            pin_setting(payload.projectId, payload.assetType, payload.assetId, key, payload.pinValue)
        else:
            pin_fragment(
                payload.projectId,
                payload.assetType,
                payload.assetId,
                payload.pinKind,
                str(payload.pinValue),
            )
    from domain.catalog import get_asset

    asset = get_asset(payload.projectId, payload.assetType, payload.assetId)
    return snapshot_for(asset)
