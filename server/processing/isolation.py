"""Generic subject isolation for derived transparent assets.

Works from edge-connected background color. It does not name a character and
does not use the Studio background-removal path. Raw generation files are left
untouched by this module.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from PIL import Image

from processing.validators.heuristics import color_dist, corner_stats

ALPHA_CUTOFF = 16
DEFAULT_TOLERANCE = 46
MIN_COMPONENT = 0.002


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


def _already_has_alpha(image: Image.Image) -> bool:
    extrema = image.getchannel("A").getextrema()
    return bool(extrema and extrema[0] < ALPHA_CUTOFF)


def _flood_clear_background(image: Image.Image, bg: tuple[int, int, int], tolerance: int) -> Image.Image:
    out = image.copy()
    pixels = out.load()
    width, height = out.size
    visited = [[False] * width for _ in range(height)]
    queue: deque[tuple[int, int]] = deque()

    def matches(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a >= ALPHA_CUTOFF and color_dist((r, g, b), bg) <= tolerance

    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))

    while queue:
        x, y = queue.popleft()
        if x < 0 or y < 0 or x >= width or y >= height or visited[y][x]:
            continue
        visited[y][x] = True
        if not matches(x, y):
            continue
        r, g, b, _a = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)
        queue.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return out


def _components(image: Image.Image) -> list[int]:
    pixels = image.load()
    width, height = image.size
    seen = [[False] * width for _ in range(height)]
    sizes: list[int] = []
    minimum = max(8, int(width * height * MIN_COMPONENT))
    for start_y in range(height):
        for start_x in range(width):
            if seen[start_y][start_x] or pixels[start_x, start_y][3] < ALPHA_CUTOFF:
                continue
            queue = deque([(start_x, start_y)])
            seen[start_y][start_x] = True
            count = 0
            while queue:
                x, y = queue.popleft()
                count += 1
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if nx < 0 or ny < 0 or nx >= width or ny >= height or seen[ny][nx]:
                        continue
                    seen[ny][nx] = True
                    if pixels[nx, ny][3] >= ALPHA_CUTOFF:
                        queue.append((nx, ny))
            if count >= minimum:
                sizes.append(count)
    return sizes


def _bbox(image: Image.Image) -> tuple[int, int, int, int]:
    box = image.getchannel("A").point(lambda value: 255 if value >= ALPHA_CUTOFF else 0).getbbox()
    return box or (0, 0, 0, 0)


def describe_isolation(image: Image.Image, source: Image.Image | None = None) -> IsolationReport:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    transparent = 0
    opaque = 0
    remnant = 0
    bg = corner_stats(source or rgba)["bg"]
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < ALPHA_CUTOFF:
                transparent += 1
                continue
            opaque += 1
            if color_dist((r, g, b), bg) <= DEFAULT_TOLERANCE:
                remnant += 1
    total = max(1, width * height)
    left, top, right, bottom = _bbox(rgba)
    touches = (
        top <= 1,
        bottom >= height - 1,
        left <= 1,
        right >= width - 1,
    )
    occupancy = opaque / total
    bbox_area = max(0, (right - left) * (bottom - top)) / total
    return IsolationReport(
        has_alpha=transparent > 0,
        transparent_ratio=transparent / total,
        remnant_ratio=remnant / max(1, opaque),
        occupancy=occupancy,
        subject_count=len(_components(rgba)),
        bbox=(left, top, right, bottom),
        touches_top=touches[0],
        touches_bottom=touches[1],
        touches_left=touches[2],
        touches_right=touches[3],
        cropped=sum(touches) >= 3,
        bbox_reasonable=0.02 <= bbox_area <= 0.92 and 0.03 <= occupancy <= 0.78,
    )


def isolate_subject(image: Image.Image, tolerance: int = DEFAULT_TOLERANCE) -> tuple[Image.Image, IsolationReport]:
    rgba = image.convert("RGBA")
    if _already_has_alpha(rgba):
        report = describe_isolation(rgba, rgba)
        report.notes.append("Used existing alpha channel.")
        return rgba, report
    stats = corner_stats(rgba)
    if stats["spread"] > 55 or not stats["medians"]:
        report = describe_isolation(rgba, rgba)
        report.busy_background = True
        report.notes.append("Corners do not agree on a background color.")
        return rgba, report
    isolated = _flood_clear_background(rgba, stats["bg"], tolerance)
    report = describe_isolation(isolated, rgba)
    if report.transparent_ratio < 0.08:
        report.busy_background = True
        report.notes.append("Edge flood did not clear enough background.")
    return isolated, report
