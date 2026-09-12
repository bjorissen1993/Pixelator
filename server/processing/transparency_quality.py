"""Compare a transparent cutout against its raw candidate.

These checks are generic. They do not name a character or project, and they
are not generation-model validators.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from processing.validators.heuristics import corner_stats

ALPHA_CUTOFF = 16
SUBJECT_DIST = 20
MIN_COMPONENT = 0.002

ISSUE_LABELS = {
    "excessive_subject_loss": "Extraction: subject pixels were removed",
    "disconnected_subject_parts": "Extraction: subject parts are disconnected",
    "interior_alpha_holes": "Extraction: interior alpha holes",
    "background_remnants": "Extraction: background remnants remain",
    "alpha_edge_damage": "Extraction: silhouette edge was damaged",
}


@dataclass
class TransparencyQuality:
    grade: str = "failed"
    score: float = 0.0
    issues: list[str] = field(default_factory=list)
    subject_loss: float = 0.0
    edge_damage: float = 0.0
    hole_ratio: float = 0.0
    remnant_ratio: float = 0.0
    disconnected: bool = False


def _color_dist(rgb: np.ndarray, bg: tuple[int, int, int]) -> np.ndarray:
    delta = rgb.astype(np.int16) - np.array(bg, dtype=np.int16)
    return np.sqrt(np.sum(delta * delta, axis=2))


def _components(mask: np.ndarray, minimum: int = 1) -> list[int]:
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    sizes: list[int] = []
    from collections import deque

    for start_y in range(height):
        for start_x in range(width):
            if seen[start_y, start_x] or not mask[start_y, start_x]:
                continue
            queue = deque([(start_x, start_y)])
            seen[start_y, start_x] = True
            count = 0
            while queue:
                x, y = queue.popleft()
                count += 1
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height or seen[ny, nx] or not mask[ny, nx]:
                        continue
                    seen[ny, nx] = True
                    queue.append((nx, ny))
            if count >= minimum:
                sizes.append(count)
    return sizes


def _interior_hole_pixels(keep: np.ndarray) -> int:
    from collections import deque

    height, width = keep.shape
    outside = np.zeros_like(keep, dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))
    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height or outside[y, x] or keep[y, x]:
            continue
        outside[y, x] = True
        queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return int((~keep & ~outside).sum())


def _edge_pixels(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    padded = np.pad(mask, 1, mode="constant")
    neighbors = (
        padded[:-2, 1:-1]
        & padded[2:, 1:-1]
        & padded[1:-1, :-2]
        & padded[1:-1, 2:]
    )
    return mask & ~neighbors[:height, :width]


def assess_transparency(raw: Image.Image, isolated: Image.Image, report=None) -> TransparencyQuality:
    raw_rgb = np.asarray(raw.convert("RGB"), dtype=np.uint8)
    iso_rgba = np.asarray(isolated.convert("RGBA"), dtype=np.uint8)
    bg = corner_stats(raw)["bg"]
    dist = _color_dist(raw_rgb, bg)
    raw_subject = dist >= SUBJECT_DIST
    iso_subject = iso_rgba[:, :, 3] >= ALPHA_CUTOFF
    raw_count = max(1, int(raw_subject.sum()))
    lost = raw_subject & ~iso_subject
    subject_loss = float(lost.sum()) / raw_count
    edge = _edge_pixels(raw_subject)
    edge_count = max(1, int(edge.sum()))
    edge_damage = float((edge & lost).sum()) / edge_count
    hole_pixels = _interior_hole_pixels(iso_subject)
    hole_ratio = hole_pixels / max(1, int(iso_subject.sum()))
    remnant_ratio = float(getattr(report, "remnant_ratio", 0) or 0)
    minimum = max(8, int(iso_subject.size * MIN_COMPONENT))
    disconnected = len(_components(iso_subject, minimum=minimum)) > 1
    silhouette = float(iso_subject.sum()) / raw_count

    issues: list[str] = []
    failed = False
    warning = False
    if subject_loss >= 0.16 or silhouette < 0.78:
        issues.append("excessive_subject_loss")
        failed = True
    elif subject_loss >= 0.035:
        issues.append("excessive_subject_loss")
        warning = True
    if disconnected:
        issues.append("disconnected_subject_parts")
        warning = True
    if hole_pixels >= 6:
        issues.append("interior_alpha_holes")
        if hole_ratio >= 0.02:
            failed = True
        else:
            warning = True
    if remnant_ratio > 0.18 or (report is not None and getattr(report, "busy_background", False)):
        issues.append("background_remnants")
        failed = True
    elif remnant_ratio > 0.08:
        issues.append("background_remnants")
        warning = True
    if edge_damage >= 0.28:
        issues.append("alpha_edge_damage")
        failed = True
    elif edge_damage >= 0.08:
        issues.append("alpha_edge_damage")
        warning = True
    if report is not None and not getattr(report, "has_alpha", True):
        failed = True

    score = 1.0
    score -= min(0.55, subject_loss * 2.2)
    score -= min(0.25, edge_damage * 1.2)
    score -= min(0.20, remnant_ratio * 1.5)
    score -= min(0.20, hole_ratio * 4.0)
    if disconnected:
        score -= 0.12
    score = max(0.0, min(1.0, score))
    if failed or score < 0.45:
        grade = "failed"
    elif warning or score < 0.82:
        grade = "warning"
    else:
        grade = "good"
    return TransparencyQuality(
        grade=grade,
        score=round(score, 3),
        issues=list(dict.fromkeys(issues)),
        subject_loss=round(subject_loss, 4),
        edge_damage=round(edge_damage, 4),
        hole_ratio=round(hole_ratio, 4),
        remnant_ratio=round(remnant_ratio, 4),
        disconnected=disconnected,
    )


def issue_labels(issues: list[str]) -> list[str]:
    return [ISSUE_LABELS[issue] for issue in issues if issue in ISSUE_LABELS]
