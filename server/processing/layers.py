from PIL import Image

from models.character import HeadAnchor


def split_head_body(image: Image.Image, anchor: HeadAnchor) -> tuple[Image.Image, Image.Image]:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    neck_y = max(1, min(height - 1, anchor.headAnchorY + anchor.headOffsetY))
    head = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    body = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    src = rgba.load()
    head_px = head.load()
    body_px = body.load()
    for y in range(height):
        for x in range(width):
            pixel = src[x, y]
            if pixel[3] == 0:
                continue
            if y <= neck_y:
                head_px[x, y] = pixel
            else:
                body_px[x, y] = pixel
    return head, body
