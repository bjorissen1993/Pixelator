import logging
from collections.abc import Iterator

from PIL import Image

from models.character import CharacterProfile, SpriteAsset
from persistence.paths import resolve_data_path

logger = logging.getLogger("pixelator.preview")


def preview_relative(relative: str) -> str:
    from persistence.paths import strip_url_query

    cleaned = strip_url_query(relative or "")
    if cleaned.endswith(".png"):
        return cleaned[:-4] + "-preview.png"
    return cleaned + "-preview.png"


def make_preview(image: Image.Image) -> Image.Image:
    return image.resize((max(1, image.width * 8), max(1, image.height * 8)), Image.Resampling.NEAREST)


def iter_assets(character: CharacterProfile) -> Iterator[SpriteAsset]:
    if character.pendingBase:
        yield character.pendingBase
    if character.acceptedBase:
        yield character.acceptedBase.sprite
    for state in character.states:
        for slot in state.directions:
            yield from slot.frames
            if slot.body:
                yield slot.body
            if slot.head:
                yield slot.head
            yield from slot.overlays
            yield from slot.headVariants.values()
            yield from slot.candidates


def ensure_asset_preview(asset: SpriteAsset | None) -> bool:
    if asset is None or not asset.path:
        return False
    preview_rel = asset.previewPath or preview_relative(asset.path)
    preview_file = resolve_data_path(preview_rel)
    source_file = resolve_data_path(asset.path)
    if preview_file is None or source_file is None:
        logger.warning("Skipping preview for invalid path path=%r preview=%r", asset.path, preview_rel)
        return False
    if preview_file.exists() and preview_file.is_file():
        normalized = str(preview_rel).replace("\\", "/")
        if asset.previewPath == normalized:
            return False
        asset.previewPath = normalized
        return True
    if not source_file.exists() or not source_file.is_file():
        return False
    try:
        image = Image.open(source_file).convert("RGBA")
        preview_file.parent.mkdir(parents=True, exist_ok=True)
        make_preview(image).save(preview_file, format="PNG")
    except OSError:
        logger.exception("Failed to build preview source=%s preview=%s", source_file, preview_file)
        return False
    asset.previewPath = str(preview_rel).replace("\\", "/")
    return True


def ensure_character_previews(character: CharacterProfile) -> bool:
    changed = False
    for asset in iter_assets(character):
        try:
            if ensure_asset_preview(asset):
                changed = True
        except OSError:
            logger.exception("Preview refresh failed for %s", getattr(asset, "path", None))
    return changed
