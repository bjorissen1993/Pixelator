from PIL import Image, ImageFilter

from models.enums import OutlineStyle


def apply_outline(image: Image.Image, style: OutlineStyle) -> Image.Image:
    if style == "none":
        return image
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    dilated = alpha.filter(ImageFilter.MaxFilter(3))
    width, height = rgba.size
    pixels = rgba.load()
    alpha_px = alpha.load()
    dilated_px = dilated.load()
    color = (20, 24, 18, 255) if style == "dark" else (36, 46, 34, 220)
    for y in range(height):
        for x in range(width):
            if alpha_px[x, y] == 0 and dilated_px[x, y] > 0:
                pixels[x, y] = color
    return rgba
