"""Generic subject isolation for derived transparent assets.

Works from edge-connected background color, then conservatively restores
thin subject structure. It does not name a character and does not use the
Studio background-removal path. Raw generation files are left untouched.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from processing.transparency_quality import TransparencyQuality, assess_transparency
from processing.validators.heuristics import color_dist, corner_stats

ALPHA_CUTOFF = 16
DEFAULT_TOLERANCE = 30
RESTORE_MIN_DIST = 12
STRONG_SUBJECT_DIST = 18
RESTORE_RADIUS = 3
HOLE_FILL_MAX = 48
DILATE_PX = 1
CLEANUP_BG_DIST = 10
MIN_COMPONENT = 0.002
EXTRACTION_VERSION = 2
EXTRACTION_METHOD = "edge_flood_refine"

MASK_SETTINGS = {
    "floodTolerance": DEFAULT_TOLERANCE,
    "restoreMinDist": RESTORE_MIN_DIST,
    "strongSubjectDist": STRONG_SUBJECT_DIST,
    "restoreRadius": RESTORE_RADIUS,
    "holeFillMax": HOLE_FILL_MAX,
    "dilatePx": DILATE_PX,
    "cleanupBgDist": CLEANUP_BG_DIST,
    "binaryAlpha": True,
}


@dataclass
class IsolationReport:
    has_alpha: bool = False
    transparent_ratio: float = 0
    remnant_ratio: float = 0
    occupancy: float = 0
    subject_count: int = 0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    touches_top: bool = False
    touches_bottom: bool = False
    touches_left: bool = False
    touches_right: bool = False
    cropped: bool = False
    bbox_reasonable: bool = False
    busy_background: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class ExtractionOutput:
    image: Image.Image
    report: IsolationReport
    quality: TransparencyQuality
    method: str = EXTRACTION_METHOD
    version: int = EXTRACTION_VERSION
    settings: dict = field(default_factory=lambda: dict(MASK_SETTINGS))


def _already_has_alpha(image: Image.Image) -> bool:
    extrema = image.getchannel("A").getextrema()
    return bool(extrema and extrema[0] < ALPHA_CUTOFF)


def _rgba_arrays(image: Image.Image) -> tuple[np.ndarray, np.ndarray]:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    return rgba, rgba[:, :, 3]


def _color_dist(rgb: np.ndarray, bg: tuple[int, int, int]) -> np.ndarray:
    delta = rgb.astype(np.int16) - np.array(bg, dtype=np.int16)
    return np.sqrt(np.sum(delta * delta, axis=2))


def _flood_background(rgb: np.ndarray, alpha: np.ndarray, bg: tuple[int, int, int], tolerance: int) -> np.ndarray:
    height, width = alpha.shape
    background = np.zeros((height, width), dtype=bool)
    visited = np.zeros((height, width), dtype=bool)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))
    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height or visited[y, x]:
            continue
        visited[y, x] = True
        if alpha[y, x] < ALPHA_CUTOFF:
            background[y, x] = True
            continue
        if color_dist((int(rgb[y, x, 0]), int(rgb[y, x, 1]), int(rgb[y, x, 2])), bg) > tolerance:
            continue
        background[y, x] = True
        queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return background


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask.copy()
    height, width = mask.shape
    out = mask.copy()
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        out[max(0, y - radius) : min(height, y + radius + 1), max(0, x - radius) : min(width, x + radius + 1)] = True
    return out


def _components(mask: np.ndarray, minimum: int = 1) -> list[np.ndarray]:
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    found: list[np.ndarray] = []
    for start_y in range(height):
        for start_x in range(width):
            if seen[start_y, start_x] or not mask[start_y, start_x]:
                continue
            queue = deque([(start_x, start_y)])
            seen[start_y, start_x] = True
            cells: list[tuple[int, int]] = []
            while queue:
                x, y = queue.popleft()
                cells.append((x, y))
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height or seen[ny, nx] or not mask[ny, nx]:
                        continue
                    seen[ny, nx] = True
                    queue.append((nx, ny))
            if len(cells) >= minimum:
                component = np.zeros_like(mask, dtype=bool)
                xs, ys = zip(*cells)
                component[list(ys), list(xs)] = True
                found.append(component)
    return found


def _touches_border(mask: np.ndarray) -> bool:
    return bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any())


def _restore_attached_subject(keep: np.ndarray, dist: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    height, width = keep.shape
    restored = keep.copy()
    near = _dilate(keep, RESTORE_RADIUS)
    queue: deque[tuple[int, int]] = deque()
    ys, xs = np.nonzero(keep)
    for y, x in zip(ys.tolist(), xs.tolist()):
        queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height or restored[ny, nx] or not allowed[ny, nx]:
                continue
            gap = float(dist[ny, nx])
            if gap < RESTORE_MIN_DIST:
                continue
            if gap < STRONG_SUBJECT_DIST and not near[ny, nx]:
                continue
            restored[ny, nx] = True
            queue.append((nx, ny))
    return restored


def _fill_interior_holes(keep: np.ndarray) -> np.ndarray:
    filled = keep.copy()
    for hole in _components(~keep, minimum=1):
        if _touches_border(hole):
            continue
        if int(hole.sum()) <= HOLE_FILL_MAX:
            filled |= hole
    return filled


def _apply_keep_mask(rgba: np.ndarray, keep: np.ndarray) -> Image.Image:
    out = rgba.copy()
    out[:, :, 3] = np.where(keep, 255, 0).astype(np.uint8)
    return Image.fromarray(out)


def _describe_from_arrays(rgba: np.ndarray, keep: np.ndarray, source_rgb: np.ndarray, bg: tuple[int, int, int]) -> IsolationReport:
    height, width = keep.shape
    total = max(1, height * width)
    opaque = int(keep.sum())
    transparent = total - opaque
    remnant = int((keep & (_color_dist(source_rgb, bg) <= DEFAULT_TOLERANCE)).sum())
    rows = np.any(keep, axis=1)
    cols = np.any(keep, axis=0)
    if not rows.any():
        bbox = (0, 0, 0, 0)
        touches = (False, False, False, False)
        bbox_area = 0.0
    else:
        ys = np.where(rows)[0]
        xs = np.where(cols)[0]
        top, bottom = int(ys[0]), int(ys[-1]) + 1
        left, right = int(xs[0]), int(xs[-1]) + 1
        bbox = (left, top, right, bottom)
        touches = (top <= 1, bottom >= height - 1, left <= 1, right >= width - 1)
        bbox_area = max(0, (right - left) * (bottom - top)) / total
    occupancy = opaque / total
    minimum = max(8, int(total * MIN_COMPONENT))
    return IsolationReport(
        has_alpha=transparent > 0,
        transparent_ratio=transparent / total,
        remnant_ratio=remnant / max(1, opaque),
        occupancy=occupancy,
        subject_count=len(_components(keep, minimum=minimum)),
        bbox=bbox,
        touches_top=touches[0],
        touches_bottom=touches[1],
        touches_left=touches[2],
        touches_right=touches[3],
        cropped=sum(touches) >= 3,
        bbox_reasonable=0.02 <= bbox_area <= 0.92 and 0.03 <= occupancy <= 0.78,
    )


def describe_isolation(image: Image.Image, source: Image.Image | None = None) -> IsolationReport:
    rgba, alpha = _rgba_arrays(image)
    source_rgb = np.asarray((source or image).convert("RGB"), dtype=np.uint8)
    bg = corner_stats(source or image)["bg"]
    keep = alpha >= ALPHA_CUTOFF
    return _describe_from_arrays(rgba, keep, source_rgb, bg)


def _refine_keep(keep: np.ndarray, dist: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    keep = _restore_attached_subject(keep, dist, allowed)
    keep = _fill_interior_holes(keep)
    if DILATE_PX:
        dilated = _dilate(keep, DILATE_PX)
        added = dilated & ~keep & allowed
        keep = keep | (added & (dist >= CLEANUP_BG_DIST))
    return keep


def extract_transparent_asset(image: Image.Image, tolerance: int = DEFAULT_TOLERANCE) -> ExtractionOutput:
    rgba, alpha = _rgba_arrays(image)
    rgb = rgba[:, :, :3]
    stats = corner_stats(image)
    bg = stats["bg"]
    dist = _color_dist(rgb, bg)
    notes: list[str] = []

    allowed = alpha >= ALPHA_CUTOFF
    if _already_has_alpha(image.convert("RGBA")):
        keep = _refine_keep(allowed, dist, allowed)
        notes.append("Used existing alpha channel.")
    elif stats["spread"] > 55 or not stats["medians"]:
        keep = np.ones(alpha.shape, dtype=bool)
        notes.append("Corners do not agree on a background color.")
        isolated = _apply_keep_mask(rgba, keep)
        report = describe_isolation(isolated, image)
        report.busy_background = True
        report.notes = notes
        quality = assess_transparency(image, isolated, report)
        quality.grade = "failed"
        if "background_remnants" not in quality.issues:
            quality.issues.append("background_remnants")
        return ExtractionOutput(image=isolated, report=report, quality=quality)
    else:
        background = _flood_background(rgb, alpha, bg, tolerance)
        keep = ~background
        keep = _refine_keep(keep, dist, allowed)
        notes.append("Edge flood with conservative subject restore.")

    isolated = _apply_keep_mask(rgba, keep)
    report = _describe_from_arrays(rgba, keep, rgb, bg)
    report.notes = notes
    if report.transparent_ratio < 0.08:
        report.busy_background = True
        report.notes.append("Edge flood did not clear enough background.")
    quality = assess_transparency(image, isolated, report)
    return ExtractionOutput(image=isolated, report=report, quality=quality)


def isolate_subject(image: Image.Image, tolerance: int = DEFAULT_TOLERANCE) -> tuple[Image.Image, IsolationReport]:
    result = extract_transparent_asset(image, tolerance)
    return result.image, result.report
