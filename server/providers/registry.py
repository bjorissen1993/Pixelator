from functools import lru_cache

import config
from providers.base import GenerationProvider
from providers.diffusers_provider import DiffusersProvider
from providers.pixellab_provider import PixelLabProvider


@lru_cache(maxsize=1)
def get_provider() -> GenerationProvider:
    if config.PIXELLAB_API_KEY:
        return PixelLabProvider()
    if config.PIXEL_MODEL_ID:
        return DiffusersProvider(model_id=config.PIXEL_MODEL_ID, native=True)
    return DiffusersProvider()
