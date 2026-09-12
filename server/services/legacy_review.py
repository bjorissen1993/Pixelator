"""One-time migrate of the original Berwynn review folder into the generic project tree."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import config
from models.catalog import AssetLabSession, AssetProfile, GenerationCandidate
from models.canonical_base import CanonicalBaseCandidate, CanonicalBaseSession
from persistence.projects import (
    LEGACY_BERWYNN_REVIEW,
    accepted_canonical_path,
    candidate_dir,
    session_path,
)

VERTICAL_SLICE = ("chimera", "character", "berwynn")


def is_vertical_slice(asset: AssetProfile) -> bool:
    return (asset.projectId, asset.assetType, asset.assetId) == VERTICAL_SLICE


def migrate_legacy_review(
    asset: AssetProfile,
    empty_session: Callable[[AssetProfile], AssetLabSession],
    to_candidate: Callable[[AssetProfile, CanonicalBaseCandidate], GenerationCandidate],
    public_path: Callable[[Path], str],
) -> None:
    if not is_vertical_slice(asset):
        return
    dest_accepted = accepted_canonical_path(asset.projectId, asset.assetType, asset.assetId)
    legacy_accepted = LEGACY_BERWYNN_REVIEW / "accepted" / "canonical.png"
    if legacy_accepted.is_file() and not dest_accepted.is_file():
        dest_accepted.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_accepted, dest_accepted)

    dest_session = session_path(asset.projectId, asset.assetType, asset.assetId)
    legacy_session = LEGACY_BERWYNN_REVIEW / "session.json"
    if dest_session.is_file() or not legacy_session.is_file():
        return
    payload = json.loads(legacy_session.read_text(encoding="utf-8"))
    old = CanonicalBaseSession.model_validate(payload)
    session = empty_session(asset)
    dest_candidates = candidate_dir(asset.projectId, asset.assetType, asset.assetId)
    dest_candidates.mkdir(parents=True, exist_ok=True)
    copied: list[GenerationCandidate] = []
    for item in old.candidates:
        source = config.DATA_DIR / item.path
        if source.is_file():
            target = dest_candidates / source.name
            if not target.is_file():
                shutil.copy2(source, target)
            item.path = public_path(target)
        copied.append(to_candidate(asset, item))
    session.candidates = copied
    if old.accepted:
        if dest_accepted.is_file():
            old.accepted.path = public_path(dest_accepted)
        session.accepted = to_candidate(asset, old.accepted)
        session.accepted.status = "accepted"
        session.referenceUnlocked = True
        session.ipAdapterUnlocked = True
    dest_session.write_text(session.model_dump_json(indent=2), encoding="utf-8")
