"""Sprite cleanup only. This does not invent pixel-art style."""

from PIL import Image

from models.character import QualityValidation
from processing.pipeline import flatten_alpha, fit_to_canvas, map_to_palette, remove_specks
from processing.validation import validate_sprite


def cleanup_sprite(
    image: Image.Image,
    size: int,
    colors: int,
    locked_palette: list[tuple[int, int, int]] | None = None,
    palette_mode: str = "generated",
    reference: Image.Image | None = None,
    direction=None,
    fit_margin: float = 0.10,
    center: bool = True,
    spirit_form: bool = False,
    for_base: bool = False,
    one_character: bool = True,
    on_step=None,
) -> tuple[Image.Image, Image.Image, QualityValidation]:
    if on_step:
        on_step("Applying palette")
    rgba = flatten_alpha(image.convert("RGBA"), cutoff=32)
    source = rgba.copy()
    if max(rgba.size) != size:
        if on_step:
            on_step("nearest-neighbor canvas fit")
        rgba = fit_to_canvas(rgba, size, resample=Image.Resampling.NEAREST, margin=fit_margin, center=center)
    sprite = flatten_alpha(rgba, cutoff=32)
    sprite = fit_to_canvas(
        sprite,
        size,
        resample=Image.Resampling.NEAREST,
        margin=fit_margin,
        center=center,
        allow_upscale=False,
        recrop=False,
    )
    if locked_palette and palette_mode in ("accepted", "strict", "locked", "soft", "custom", "project"):
        mode = "soft" if palette_mode in ("soft", "accepted") else "strict"
        sprite = map_to_palette(sprite, locked_palette, mode)
    if on_step:
        on_step("Saving assets")
    sprite = remove_specks(sprite, min_neighbors=1)
    sprite = flatten_alpha(sprite, cutoff=16)
    preview = sprite.resize((size * 8, size * 8), Image.Resampling.NEAREST)
    validation = validate_sprite(
        sprite,
        size,
        colors,
        source_size=max(source.size),
        reference=reference,
        palette=locked_palette,
        direction=direction,
        spirit_form=spirit_form,
        source=source,
        for_base=for_base,
        one_character=one_character,
    )
    return sprite, preview, validation
