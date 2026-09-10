from functools import lru_cache

import config
from providers.base import GenerationProvider
from providers.diffusers_provider import DiffusersProvider


@lru_cache(maxsize=1)
def get_provider() -> GenerationProvider:
    if config.PIXEL_MODEL_ID:
        return DiffusersProvider(model_id=config.PIXEL_MODEL_ID, native=True)
    return DiffusersProvider()
