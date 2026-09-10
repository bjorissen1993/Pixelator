from functools import lru_cache

import config
from providers.base import GenerationProvider
from providers.diffusers_provider import DiffusersProvider
from providers.pixellab_provider import PixelLabProvider


def _local_provider() -> DiffusersProvider:
    model_id = config.PIXEL_MODEL_ID or config.MODEL_ID
    native = bool(config.PIXEL_MODEL_ID) and "turbo" not in model_id.lower()
    return DiffusersProvider(model_id=model_id, native=native)


@lru_cache(maxsize=1)
def get_provider() -> GenerationProvider:
    choice = config.PIXELATOR_PROVIDER
    if choice == "pixellab":
        if config.PIXELLAB_API_KEY:
            return PixelLabProvider()
        return _local_provider()
    if choice in ("diffusers", "diffusers-local"):
        return DiffusersProvider(model_id=config.MODEL_ID, native=False)
    if choice in ("pixel-diffusers", "pixel"):
        return DiffusersProvider(model_id=config.PIXEL_MODEL_ID or config.MODEL_ID, native=True)
    if config.PIXELLAB_API_KEY:
        return PixelLabProvider()
    return _local_provider()
