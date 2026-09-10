from collections import Counter

from PIL import Image

from models.character import HeadAnchor, QualityValidation
from models.enums import OutlineStyle
from processing.outline import apply_outline
from processing.validation import validate_sprite

ALPHA_CUTOFF = 140
WORK_SCALE = 4


def knock_out_flat_background(image: Image.Image, tolerance: int = 30) -> Image.Image:
    rgba = image.convert("RGBA")
    extrema = rgba.getchannel("A").getextrema()
    if extrema and extrema[0] < ALPHA_CUTOFF:
        return rgba
    width, height = rgba.size
    pixels = rgba.load()
    corners = [
        pixels[0, 0][:3],
        pixels[width - 1, 0][:3],
        pixels[0, height - 1][:3],
        pixels[width - 1, height - 1][:3],
    ]
    bg = tuple(sum(channel[i] for channel in corners) // 4 for i in range(3))
    spread = max((c[0] - bg[0]) ** 2 + (c[1] - bg[1]) ** 2 + (c[2] - bg[2]) ** 2 for c in corners)
    if spread > (tolerance * 2) ** 2:
        return rgba
    limit = tolerance ** 2
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if (r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2 <= limit:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def remove_background(image: Image.Image, enabled: bool) -> Image.Image:
    rgba = image.convert("RGBA")
    if not enabled:
        return rgba
    try:
        from rembg import remove

        rgba = remove(rgba).convert("RGBA")
    except Exception:
        pass
    return knock_out_flat_background(rgba)


def flatten_alpha(image: Image.Image, cutoff: int = ALPHA_CUTOFF) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < cutoff:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                pixels[x, y] = (r, g, b, 255)
    return rgba


def crop_alpha(image: Image.Image, pad: int = 0) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        return image
    if pad:
        left, top, right, bottom = bbox
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(image.width, right + pad)
        bottom = min(image.height, bottom + pad)
        bbox = (left, top, right, bottom)
    return image.crop(bbox)


def fit_to_canvas(
    image: Image.Image,
    size: int,
    resample: Image.Resampling | None = None,
    margin: float = 0.10,
    center: bool = True,
    allow_upscale: bool = True,
    recrop: bool = True,
) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rgba = image.convert("RGBA")
    pad = max(2, int(round(size * max(0.04, min(margin, 0.22)))))
    bbox = rgba.getchannel("A").getbbox()
    if not bbox:
        return canvas
    if not recrop and rgba.size == (size, size):
        left, top, right, bottom = bbox
        inside = left >= pad and top >= pad and right <= size - pad and bottom <= size - pad
        if inside:
            cropped = rgba.crop(bbox)
            x = (size - cropped.width) // 2 if center else max(pad, min(left, size - pad - cropped.width))
            y = (size - cropped.height) // 2 if center else max(pad, min(top, size - pad - cropped.height))
            x = max(pad, min(x, size - pad - cropped.width))
            y = max(pad, min(y, size - pad - cropped.height))
            canvas.alpha_composite(cropped, (x, y))
            return canvas
        recrop = True
        allow_upscale = False
    cropped = crop_alpha(rgba) if recrop else rgba
    inner = max(1, size - pad * 2)
    ratio = min(inner / max(1, cropped.width), inner / max(1, cropped.height))
    if not allow_upscale:
        ratio = min(ratio, 1.0)
    target = (max(1, int(cropped.width * ratio)), max(1, int(cropped.height * ratio)))
    shrinking = target[0] < cropped.width or target[1] < cropped.height
    if resample is None:
        resample = Image.Resampling.BOX if shrinking else Image.Resampling.NEAREST
    fitted = cropped.resize(target, resample)
    x = (size - fitted.width) // 2
    if center:
        y = (size - fitted.height) // 2
    else:
        y = size - pad - fitted.height
    x = max(pad, min(x, size - pad - fitted.width))
    y = max(pad, min(y, size - pad - fitted.height))
    canvas.alpha_composite(fitted, (x, y))
    return canvas


def _opaque_fill_color(image: Image.Image) -> tuple[int, int, int]:
    counts: Counter[tuple[int, int, int]] = Counter()
    for r, g, b, a in image.convert("RGBA").getdata():
        if a < ALPHA_CUTOFF:
            continue
        counts[(r, g, b)] += 1
    if not counts:
        return (0, 0, 0)
    return counts.most_common(1)[0][0]


def _quantize_rgb(rgb: Image.Image, colors: int) -> Image.Image:
    colors = max(2, min(colors, 64))
    kwargs = {"colors": colors, "dither": Image.Dither.NONE}
    try:
        quantized = rgb.quantize(method=Image.Quantize.MAXCOVERAGE, **kwargs)
    except Exception:
        quantized = rgb.quantize(method=Image.Quantize.MEDIANCUT, **kwargs)
    return quantized.convert("RGB")


def extract_palette(image: Image.Image, limit: int) -> list[tuple[int, int, int]]:
    rgba = flatten_alpha(image)
    colors: dict[tuple[int, int, int], int] = {}
    for r, g, b, a in rgba.getdata():
        if a < ALPHA_CUTOFF:
            continue
        key = (r, g, b)
        colors[key] = colors.get(key, 0) + 1
    ranked = sorted(colors, key=lambda c: colors[c], reverse=True)
    if len(ranked) <= limit:
        return ranked
    fill = _opaque_fill_color(rgba)
    filled = Image.new("RGB", rgba.size, fill)
    filled.paste(rgba.convert("RGB"), mask=rgba.getchannel("A"))
    quantized = _quantize_rgb(filled, limit)
    unique: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for pixel in quantized.getdata():
        if pixel not in seen:
            seen.add(pixel)
            unique.append(pixel)
        if len(unique) >= limit:
            break
    return unique


def map_to_palette(image: Image.Image, palette: list[tuple[int, int, int]], mode: str = "strict") -> Image.Image:
    if not palette or mode in ("unlocked", "generated"):
        return image
    rgba = flatten_alpha(image)
    pixels = rgba.load()
    width, height = rgba.size
    soft = mode == "soft"
    limit = 48 * 48 if soft else 10**9
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < ALPHA_CUTOFF:
                continue
            nearest = min(palette, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
            dist = (nearest[0] - r) ** 2 + (nearest[1] - g) ** 2 + (nearest[2] - b) ** 2
            if not soft or dist <= limit:
                pixels[x, y] = (*nearest, 255)
            else:
                pixels[x, y] = (
                    (r * 3 + nearest[0]) // 4,
                    (g * 3 + nearest[1]) // 4,
                    (b * 3 + nearest[2]) // 4,
                    255,
                )
    return rgba


def remove_specks(image: Image.Image, min_neighbors: int = 2) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    opaque = [[pixels[x, y][3] >= ALPHA_CUTOFF for x in range(width)] for y in range(height)]
    for y in range(height):
        for x in range(width):
            if not opaque[y][x]:
                continue
            neighbors = 0
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if (nx != x or ny != y) and opaque[ny][nx]:
                        neighbors += 1
            if neighbors < min_neighbors:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def fill_holes(image: Image.Image, min_neighbors: int = 5) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] >= ALPHA_CUTOFF:
                continue
            neighbors: list[tuple[int, int, int]] = []
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if nx == x and ny == y:
                        continue
                    nr, ng, nb, na = pixels[nx, ny]
                    if na >= ALPHA_CUTOFF:
                        neighbors.append((nr, ng, nb))
            if len(neighbors) >= min_neighbors:
                color = Counter(neighbors).most_common(1)[0][0]
                pixels[x, y] = (*color, 255)
    return rgba


def estimate_head_anchor(image: Image.Image, size: int) -> HeadAnchor:
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        return HeadAnchor(headAnchorX=size // 2, headAnchorY=max(8, size // 3))
    left, top, right, bottom = bbox
    return HeadAnchor(
        headAnchorX=(left + right) // 2,
        headAnchorY=top + max(4, int((bottom - top) * 0.32)),
        headOffsetX=0,
        headOffsetY=0,
    )


def reduce_palette(image: Image.Image, colors: int) -> Image.Image:
    rgba = flatten_alpha(image)
    alpha = rgba.getchannel("A")
    fill = _opaque_fill_color(rgba)
    filled = Image.new("RGB", rgba.size, fill)
    filled.paste(rgba.convert("RGB"), mask=alpha)
    quantized = _quantize_rgb(filled, colors)
    return Image.merge("RGBA", (*quantized.split(), alpha))


def block_mode_downscale(image: Image.Image, target_size: int) -> Image.Image:
    rgba = flatten_alpha(image)
    width, height = rgba.size
    if width == target_size and height == target_size:
        return rgba
    src = rgba.load()
    out = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    dst = out.load()
    for y in range(target_size):
        for x in range(target_size):
            x0 = int(x * width / target_size)
            y0 = int(y * height / target_size)
            x1 = max(x0 + 1, int((x + 1) * width / target_size))
            y1 = max(y0 + 1, int((y + 1) * height / target_size))
            counts: Counter[tuple[int, int, int]] = Counter()
            transparent = 0
            total = 0
            for py in range(y0, min(height, y1)):
                for px in range(x0, min(width, x1)):
                    r, g, b, a = src[px, py]
                    total += 1
                    if a < ALPHA_CUTOFF:
                        transparent += 1
                    else:
                        counts[(r, g, b)] += 1
            if not counts or transparent * 2 >= total:
                dst[x, y] = (0, 0, 0, 0)
            else:
                color = counts.most_common(1)[0][0]
                dst[x, y] = (*color, 255)
    return out


def _prepare_source(image: Image.Image) -> Image.Image:
    return flatten_alpha(image)


def _apply_palette(work: Image.Image, colors: int, locked_palette: list[tuple[int, int, int]] | None, palette_mode: str) -> Image.Image:
    mode = palette_mode if palette_mode != "locked" else "strict"
    if locked_palette and mode in ("strict", "custom", "project"):
        return map_to_palette(work, locked_palette, "strict")
    if locked_palette and mode == "soft":
        softened = map_to_palette(work, locked_palette, "soft")
        return reduce_palette(softened, min(colors, max(len(locked_palette), 8)))
    return reduce_palette(work, colors)


class PixelPipeline:
    def process(
        self,
        image: Image.Image,
        size: int,
        colors: int,
        outline: OutlineStyle,
        remove_bg: bool,
        locked_palette: list[tuple[int, int, int]] | None = None,
        cleanup: bool = True,
        native: bool = False,
        on_step=None,
        working_size: int | None = None,
        palette_mode: str = "unlocked",
        reference: Image.Image | None = None,
        direction=None,
        fit_margin: float = 0.10,
        center: bool = True,
        spirit_form: bool = False,
        for_base: bool = False,
        one_character: bool = True,
    ) -> tuple[Image.Image, Image.Image, QualityValidation]:
        if native:
            return self.process_native(
                image,
                size,
                colors,
                on_step,
                locked_palette,
                palette_mode,
                reference,
                direction,
                fit_margin=fit_margin,
                center=center,
                spirit_form=spirit_form,
                for_base=for_base,
                one_character=one_character,
            )
        if on_step:
            on_step("removing background")
        rgba = _prepare_source(remove_background(image, remove_bg))
        source = rgba.copy()
        source_size = max(rgba.size)
        work_size = max(size, working_size or size)
        if on_step:
            on_step("fitting working canvas")
        if source_size <= size * 2 and work_size <= size:
            work = fit_to_canvas(rgba, size, resample=Image.Resampling.NEAREST, margin=fit_margin, center=center)
            sprite = _apply_palette(work, colors, locked_palette, palette_mode)
        else:
            work = fit_to_canvas(rgba, work_size, margin=fit_margin, center=center)
            if on_step:
                on_step("locking palette")
            work = _apply_palette(work, colors, locked_palette, palette_mode)
            if on_step:
                on_step("nearest-neighbor sprite reduce")
            if work_size == size:
                sprite = work
            else:
                sprite = block_mode_downscale(work, size)
                sprite = fit_to_canvas(
                    sprite,
                    size,
                    resample=Image.Resampling.NEAREST,
                    margin=fit_margin,
                    center=center,
                    allow_upscale=False,
                    recrop=False,
                )
        sprite = flatten_alpha(sprite)
        if cleanup:
            if on_step:
                on_step("cleaning silhouette")
            sprite = remove_specks(sprite, min_neighbors=1)
            sprite = fill_holes(sprite)
            sprite = flatten_alpha(sprite)
        if on_step:
            on_step("applying outline")
        sprite = apply_outline(sprite, outline)
        sprite = flatten_alpha(sprite, cutoff=16)
        sprite = fit_to_canvas(
            sprite,
            size,
            resample=Image.Resampling.NEAREST,
            margin=fit_margin,
            center=center,
            allow_upscale=False,
            recrop=False,
        )
        preview = sprite.resize((size * 8, size * 8), Image.Resampling.NEAREST)
        validation = validate_sprite(
            sprite,
            size,
            colors,
            source_size=source_size,
            reference=reference,
            palette=locked_palette,
            direction=direction,
            spirit_form=spirit_form,
            source=source,
            for_base=for_base,
            one_character=one_character,
        )
        return sprite, preview, validation

    def process_native(
        self,
        image: Image.Image,
        size: int,
        colors: int,
        on_step=None,
        locked_palette: list[tuple[int, int, int]] | None = None,
        palette_mode: str = "unlocked",
        reference: Image.Image | None = None,
        direction=None,
        fit_margin: float = 0.10,
        center: bool = True,
        spirit_form: bool = False,
        for_base: bool = False,
        one_character: bool = True,
    ) -> tuple[Image.Image, Image.Image, QualityValidation]:
        if on_step:
            on_step("fitting native pixel sprite")
        rgba = flatten_alpha(image.convert("RGBA"), cutoff=32)
        source = rgba.copy()
        sprite = fit_to_canvas(rgba, size, resample=Image.Resampling.NEAREST, margin=fit_margin, center=center)
        sprite = flatten_alpha(sprite, cutoff=32)
        sprite = fit_to_canvas(
            sprite,
            size,
            resample=Image.Resampling.NEAREST,
            margin=fit_margin,
            center=center,
            allow_upscale=False,
            recrop=False,
        )
        if locked_palette and palette_mode in ("strict", "locked", "soft", "custom", "project"):
            sprite = map_to_palette(sprite, locked_palette, "soft" if palette_mode == "soft" else "strict")
        preview = sprite.resize((size * 8, size * 8), Image.Resampling.NEAREST)
        validation = validate_sprite(
            sprite,
            size,
            colors,
            source_size=size,
            reference=reference,
            palette=locked_palette,
            direction=direction,
            spirit_form=spirit_form,
            source=source,
            for_base=for_base,
            one_character=one_character,
        )
        return sprite, preview, validation

