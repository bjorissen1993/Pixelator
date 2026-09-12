"""Raw review records stay the source of truth. Controls are the only durable extra state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import config
from models.catalog import AssetType, LearningRecord
from models.learning import LearningControls
from persistence.projects import learning_dir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def controls_path(project_id: str, asset_type: AssetType, asset_id: str) -> Path:
    return learning_dir(project_id, asset_type, asset_id) / "controls.json"


def load_controls(project_id: str, asset_type: AssetType, asset_id: str) -> LearningControls:
    path = controls_path(project_id, asset_type, asset_id)
    if not path.is_file():
        return LearningControls()
    return LearningControls.model_validate_json(path.read_text(encoding="utf-8"))


def save_controls(project_id: str, asset_type: AssetType, asset_id: str, controls: LearningControls) -> LearningControls:
    path = controls_path(project_id, asset_type, asset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(controls.model_dump_json(indent=2), encoding="utf-8")
    return controls


def load_records() -> list[LearningRecord]:
    paths: list[Path] = [config.DATA_DIR / "learning" / "global.jsonl"]
    projects = config.DATA_DIR / "projects"
    if projects.is_dir():
        paths.extend(projects.glob("*/learning.jsonl"))
        paths.extend(projects.glob("*/assets/*/learning.jsonl"))
        paths.extend(projects.glob("*/assets/*/*/learning/events.jsonl"))
    found: dict[str, LearningRecord] = {}
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = LearningRecord.model_validate(json.loads(line))
            except Exception:
                continue
            found[record.id] = record
    for path in (config.DATA_DIR / "projects").glob("*/assets/*/*/learning/*.json") if projects.is_dir() else []:
        if path.name in {"controls.json", "summary.json"}:
            continue
        try:
            record = LearningRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        found[record.id] = record
    return list(found.values())


def disable_recommendation(project_id: str, asset_type: AssetType, asset_id: str, recommendation_id: str) -> LearningControls:
    controls = load_controls(project_id, asset_type, asset_id)
    if recommendation_id not in controls.disabledIds:
        controls.disabledIds.append(recommendation_id)
    return save_controls(project_id, asset_type, asset_id, controls)


def pin_fragment(
    project_id: str,
    asset_type: AssetType,
    asset_id: str,
    kind: str,
    value: str,
) -> LearningControls:
    controls = load_controls(project_id, asset_type, asset_id)
    bucket = "negative" if kind.startswith("neg") else "positive"
    items = list(controls.pinnedFragments.get(bucket, []))
    if value not in items:
        items.append(value)
    controls.pinnedFragments[bucket] = items
    return save_controls(project_id, asset_type, asset_id, controls)


def pin_setting(
    project_id: str,
    asset_type: AssetType,
    asset_id: str,
    key: str,
    value: float | int | str,
) -> LearningControls:
    controls = load_controls(project_id, asset_type, asset_id)
    controls.pinnedSettings[key] = value
    return save_controls(project_id, asset_type, asset_id, controls)


def reset_learning(
    project_id: str,
    asset_type: AssetType,
    asset_id: str,
    scope: str,
    confirm_global: bool = False,
) -> LearningControls:
    if scope == "global" and not confirm_global:
        raise ValueError("Global learning reset requires an explicit confirmGlobal flag.")
    controls = load_controls(project_id, asset_type, asset_id)
    controls.resetAfter[scope] = _now()
    return save_controls(project_id, asset_type, asset_id, controls)
