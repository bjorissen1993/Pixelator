"""Generic image heuristics. Detectors are opt-in; they do not name a specific asset."""

from __future__ import annotations

from PIL import Image


def color_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def corner_stats(image: Image.Image) -> dict:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    inset_w = max(4, width // 8)
    inset_h = max(4, height // 8)
    patches = [
        (0, 0, inset_w, inset_h),
        (width - inset_w, 0, width, inset_h),
        (0, height - inset_h, inset_w, height),
        (width - inset_w, height - inset_h, width, height),
    ]
    medians: list[tuple[int, int, int]] = []
    unique: set[tuple[int, int, int]] = set()
    for x0, y0, x1, y1 in patches:
        colors: list[tuple[int, int, int]] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                r, g, b, a = pixels[x, y]
                if a < 16:
                    continue
                color = (r, g, b)
                colors.append(color)
                unique.add(color)
        if not colors:
            continue
        colors.sort()
        medians.append(colors[len(colors) // 2])
    spread = 0.0
    if len(medians) >= 2:
        spread = max(color_dist(a, b) for i, a in enumerate(medians) for b in medians[i + 1 :])
    bg = medians[0] if medians else (128, 128, 128)
    return {"bg": bg, "spread": spread, "unique": len(unique), "medians": medians}


def knockout_plain_background(image: Image.Image) -> tuple[Image.Image, bool]:
    """Treat a consistent corner color as background. Returns (masked, busy)."""
    stats = corner_stats(image)
    rgba = image.convert("RGBA")
    corners_disagree = stats["spread"] > 55
    if corners_disagree or not stats["medians"]:
        return rgba, True
    bg = stats["bg"]
    pixels = rgba.load()
    width, height = rgba.size
    removed = 0
    kept = 0
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            if color_dist((r, g, b), bg) <= 46:
                pixels[x, y] = (r, g, b, 0)
                removed += 1
            else:
                kept += 1
    if kept == 0 or removed / max(1, removed + kept) < 0.20:
        return image.convert("RGBA"), True
    occupancy = kept / max(1, width * height)
    busy = occupancy > 0.62
    return rgba, busy


def split_lower_body(metrics: dict, image: Image.Image) -> bool:
    """True when the lower silhouette looks like two separate limbs/feet."""
    bbox = metrics.get("bbox") or (0, 0, 0, 0)
    min_x, min_y, max_x, max_y = bbox
    if max_x <= min_x or max_y <= min_y:
        return False
    pixels = image.convert("RGBA").load()
    bbox_w = max(1, max_x - min_x)
    bbox_h = max(1, max_y - min_y)
    y0 = min_y + int(bbox_h * 0.76)
    left = mid = right = 0
    for y in range(y0, max_y):
        for x in range(min_x, max_x):
            if pixels[x, y][3] < 16:
                continue
            rel = (x - min_x) / bbox_w
            if rel < 0.33:
                left += 1
            elif rel > 0.67:
                right += 1
            else:
                mid += 1
    side = max(left, right)
    if left > 18 and right > 18 and mid < max(12, side * 0.42):
        return True
    y1 = min_y + int(bbox_h * 0.90)
    columns = [0] * max(1, bbox_w)
    for y in range(y1, max_y):
        for x in range(min_x, max_x):
            if pixels[x, y][3] >= 16:
                columns[x - min_x] += 1
    clusters = 0
    inside = False
    for count in columns:
        on = count >= 2
        if on and not inside:
            clusters += 1
            inside = True
        elif not on:
            inside = False
    return clusters >= 2 and left > 10 and right > 10


def bulky_shoulder_or_metal(metrics: dict, image: Image.Image) -> bool:
    """True when shoulders are much wider than the waist or metallic edge plates appear."""
    bbox = metrics.get("bbox") or (0, 0, 0, 0)
    min_x, min_y, max_x, max_y = bbox
    if max_x <= min_x or max_y <= min_y:
        return False
    pixels = image.convert("RGBA").load()
    bbox_w = max(1, max_x - min_x)
    bbox_h = max(1, max_y - min_y)

    def band_width(start: float, end: float) -> tuple[int, int]:
        y0 = min_y + int(bbox_h * start)
        y1 = min_y + int(bbox_h * end)
        left = max_x
        right = min_x
        count = 0
        for y in range(y0, max(y0 + 1, y1)):
            for x in range(min_x, max_x):
                r, g, b, a = pixels[x, y]
                if a < 16:
                    continue
                count += 1
                left = min(left, x)
                right = max(right, x)
        return (max(0, right - left + 1) if count else 0, count)

    shoulder_w, shoulder_n = band_width(0.16, 0.36)
    waist_w, _waist_n = band_width(0.48, 0.64)
    if waist_w and shoulder_w / waist_w >= 1.48 and shoulder_n > 40:
        return True

    metal = 0
    y0 = min_y + int(bbox_h * 0.12)
    y1 = min_y + int(bbox_h * 0.38)
    edge = max(4, int(bbox_w * 0.16))
    for y in range(y0, max(y0 + 1, y1)):
        for x in range(min_x, max_x):
            if x > min_x + edge and x < max_x - edge:
                continue
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            mx = max(r, g, b)
            mn = min(r, g, b)
            sat = mx - mn
            if mx >= 190 and sat <= 28:
                metal += 1
            if r >= 165 and g >= 130 and b <= 80 and sat >= 50:
                metal += 1
    return metal >= max(40, int(bbox_w * bbox_h * 0.018))


def unique_opaque_colors(image: Image.Image) -> int:
    rgba = image.convert("RGBA")
    colors: set[tuple[int, int, int]] = set()
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a >= 16:
                colors.add((r, g, b))
    return len(colors)
