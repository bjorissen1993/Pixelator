from PIL import Image

from models.character import HeadAnchor, QualityValidation
from models.enums import OutlineStyle
from processing.outline import apply_outline
from processing.validation import validate_sprite


def remove_background(image: Image.Image, enabled: bool) -> Image.Image:
    rgba = image.convert("RGBA")
    if not enabled:
        return rgba
    try:
        from rembg import remove

        return remove(rgba).convert("RGBA")
    except Exception:
        return rgba


def crop_alpha(image: Image.Image) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    return image.crop(bbox) if bbox else image


def extract_palette(image: Image.Image, limit: int) -> list[tuple[int, int, int]]:
    rgba = image.convert("RGBA")
    colors: dict[tuple[int, int, int], int] = {}
    for r, g, b, a in rgba.getdata():
        if a < 16:
            continue
        key = (r, g, b)
        colors[key] = colors.get(key, 0) + 1
    ranked = sorted(colors, key=lambda c: colors[c], reverse=True)
    if len(ranked) <= limit:
        return ranked
    quantized = image.convert("RGB").quantize(colors=limit, method=Image.Quantize.MEDIANCUT).convert("RGB")
    unique: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for pixel in quantized.getdata():
        if pixel not in seen:
            seen.add(pixel)
            unique.append(pixel)
        if len(unique) >= limit:
            break
    return unique


def map_to_palette(image: Image.Image, palette: list[tuple[int, int, int]]) -> Image.Image:
    if not palette:
        return image
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < 16:
                continue
            nearest = min(palette, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2)
            pixels[x, y] = (*nearest, a)
    return rgba


def remove_specks(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    opaque = [[pixels[x, y][3] >= 16 for x in range(width)] for y in range(height)]
    for y in range(height):
        for x in range(width):
            if not opaque[y][x]:
                continue
            neighbors = 0
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if (nx != x or ny != y) and opaque[ny][nx]:
                        neighbors += 1
            if neighbors == 0:
                pixels[x, y] = (0, 0, 0, 0)
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


def fit_to_canvas(image: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cropped = crop_alpha(image.convert("RGBA"))
    max_w = max(1, int(size * 0.88))
    max_h = max(1, int(size * 0.94))
    ratio = min(max_w / max(1, cropped.width), max_h / max(1, cropped.height))
    target = (max(1, int(cropped.width * ratio)), max(1, int(cropped.height * ratio)))
    # BOX downscale keeps chunkier pixels than LANCZOS. Final blit is nearest-neighbor already at canvas size.
    resample = Image.Resampling.BOX if (target[0] < cropped.width or target[1] < cropped.height) else Image.Resampling.NEAREST
    fitted = cropped.resize(target, resample)
    x = (size - fitted.width) // 2
    y = size - fitted.height
    canvas.alpha_composite(fitted, (x, y))
    return canvas


def reduce_palette(image: Image.Image, colors: int) -> Image.Image:
    alpha = image.getchannel("A")
    rgb = image.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGB")
    return Image.merge("RGBA", (*rgb.split(), alpha))


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
        on_step=None,
    ) -> tuple[Image.Image, Image.Image, QualityValidation]:
        if on_step:
            on_step("removing background")
        rgba = remove_background(image, remove_bg)
        if on_step:
            on_step("cropping sprite")
        sprite = fit_to_canvas(rgba, size)
        if on_step:
            on_step("reducing palette")
        if locked_palette:
            sprite = map_to_palette(sprite, locked_palette)
        else:
            sprite = reduce_palette(sprite, colors)
        sprite = apply_outline(sprite, outline)
        if cleanup:
            sprite = remove_specks(sprite)
        preview = sprite.resize((size * 8, size * 8), Image.Resampling.NEAREST)
        validation = validate_sprite(sprite, size, colors)
        return sprite, preview, validation
