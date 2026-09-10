from __future__ import annotations

import logging
import re
from pathlib import Path

import config

logger = logging.getLogger("pixelator.paths")

_INVALID_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
_URL_QUERY = re.compile(r"\?[^/]*=")
_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def strip_url_query(value: str) -> str:
    """Drop HTTP cache-bust queries like file.png?t=2026-09-10T20:53:48+00:00.

    A lone '?' in a filename is not treated as a query — those characters are
    sanitized instead, so extensions such as `.png` are preserved.
    """
    text = str(value or "").replace("\\", "/")
    return _URL_QUERY.split(text, maxsplit=1)[0].split("#")[0]


def sanitize_filename(name: str, fallback: str = "file") -> str:
    raw = strip_url_query(str(name or "")).split("/")[-1]
    cleaned = _INVALID_CHARS.sub("-", raw).strip(" .")
    if not cleaned:
        cleaned = fallback
    stem = cleaned.rsplit(".", 1)[0] if "." in cleaned else cleaned
    if stem.lower() in _RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:180]


def sanitize_slug(value: str, fallback: str = "character") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or fallback


def sanitize_relpath(relative: str) -> str:
    text = strip_url_query(str(relative or "")).lstrip("/")
    parts = [sanitize_filename(part) for part in text.split("/") if part and part not in (".", "..")]
    if not parts:
        raise ValueError("Empty file path")
    return "/".join(parts)


def public_asset_path(slug: str, relative: str) -> str:
    return f"characters/{sanitize_slug(slug)}/{sanitize_relpath(relative)}"


def resolve_data_path(relative: str | None) -> Path | None:
    if not relative:
        return None
    try:
        cleaned = sanitize_relpath(str(relative).replace("\\", "/"))
    except ValueError:
        logger.warning("Rejected empty path: %r", relative)
        return None
    root = config.DATA_DIR.resolve()
    candidate = (root / cleaned).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        logger.error("Path escaped data dir: relative=%r resolved=%s", relative, candidate)
        return None
    return candidate


def asset_file(slug: str, relative: str) -> Path:
    path = resolve_data_path(public_asset_path(slug, relative))
    if path is None:
        raise OSError("Invalid asset path")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
