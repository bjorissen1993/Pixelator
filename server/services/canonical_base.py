"""Berwynn vertical-slice aliases for the generic Asset Lab.

Kept so the existing isolated Berwynn test and IP-Adapter script keep working.
"""

from __future__ import annotations

from pathlib import Path

from models.catalog import AssetLabSession
from persistence.projects import LEGACY_BERWYNN_REVIEW
from services import asset_lab as asset_lab_service

DEFAULT_PROJECT = asset_lab_service.DEFAULT_PROJECT
DEFAULT_ASSET_TYPE = asset_lab_service.DEFAULT_ASSET_TYPE
DEFAULT_ASSET_ID = asset_lab_service.DEFAULT_ASSET_ID


def accepted_canonical_path() -> Path:
    current = asset_lab_service.accepted_path(DEFAULT_PROJECT, DEFAULT_ASSET_TYPE, DEFAULT_ASSET_ID)
    if current.is_file():
        return current
    legacy = LEGACY_BERWYNN_REVIEW / "accepted" / "canonical.png"
    return current if not legacy.is_file() else legacy


def load_session() -> AssetLabSession:
    return asset_lab_service.load_session(DEFAULT_PROJECT, DEFAULT_ASSET_TYPE, DEFAULT_ASSET_ID)


def generate_candidates(count: int = 4) -> AssetLabSession:
    return asset_lab_service.generate_candidates(
        DEFAULT_PROJECT, DEFAULT_ASSET_TYPE, DEFAULT_ASSET_ID, count
    )


def accept_candidate(candidate_id: str) -> AssetLabSession:
    return asset_lab_service.accept_candidate(
        candidate_id, DEFAULT_PROJECT, DEFAULT_ASSET_TYPE, DEFAULT_ASSET_ID
    )


def reject_candidate(candidate_id: str) -> AssetLabSession:
    return asset_lab_service.reject_candidate(
        candidate_id, DEFAULT_PROJECT, DEFAULT_ASSET_TYPE, DEFAULT_ASSET_ID
    )
