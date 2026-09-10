from PIL import Image, ImageFilter

from models.enums import OutlineStyle


def apply_outline(image: Image.Image, style: OutlineStyle) -> Image.Image:
    if style in ("none", "lineless"):
        return image
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    dilated = alpha.filter(ImageFilter.MaxFilter(3))
    width, height = rgba.size
    pixels = rgba.load()
    alpha_px = alpha.load()
    dilated_px = dilated.load()
    for y in range(height):
        for x in range(width):
            if alpha_px[x, y] != 0 or dilated_px[x, y] == 0:
                continue
            if style in ("colored",):
                neighbor = _neighbor_color(pixels, alpha_px, x, y, width, height)
                pixels[x, y] = (max(0, neighbor[0] - 40), max(0, neighbor[1] - 40), max(0, neighbor[2] - 40), 255)
            elif style in ("dark", "black"):
                pixels[x, y] = (16, 18, 14, 255)
            else:
                pixels[x, y] = (36, 46, 34, 220)
    return rgba


def _neighbor_color(pixels, alpha_px, x: int, y: int, width: int, height: int) -> tuple[int, int, int]:
    for ny in range(max(0, y - 1), min(height, y + 2)):
        for nx in range(max(0, x - 1), min(width, x + 2)):
            if alpha_px[nx, ny] > 0:
                pixel = pixels[nx, ny]
                return (pixel[0], pixel[1], pixel[2])
    return (20, 24, 18)
