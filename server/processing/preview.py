from collections.abc import Iterator

from PIL import Image

import config
from models.character import CharacterProfile, SpriteAsset


def preview_relative(relative: str) -> str:
    if relative.endswith(".png"):
        return relative[:-4] + "-preview.png"
    return relative + "-preview.png"


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


def ensure_asset_preview(asset: SpriteAsset | None) -> bool:
    if asset is None or not asset.path:
        return False
    preview_path = asset.previewPath or preview_relative(asset.path)
    preview_file = config.DATA_DIR / preview_path
    source_file = config.DATA_DIR / asset.path
    if preview_file.exists():
        if asset.previewPath == preview_path:
            return False
        asset.previewPath = preview_path.replace("\\", "/")
        return True
    if not source_file.exists():
        return False
    image = Image.open(source_file).convert("RGBA")
    preview_file.parent.mkdir(parents=True, exist_ok=True)
    make_preview(image).save(preview_file, format="PNG")
    asset.previewPath = preview_path.replace("\\", "/")
    return True


def ensure_character_previews(character: CharacterProfile) -> bool:
    changed = False
    for asset in iter_assets(character):
        if ensure_asset_preview(asset):
            changed = True
    return changed
