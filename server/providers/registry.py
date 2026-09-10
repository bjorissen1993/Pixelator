from functools import lru_cache

from providers.base import GenerationProvider
from providers.diffusers_provider import DiffusersProvider


@lru_cache(maxsize=1)
def get_provider() -> GenerationProvider:
    return DiffusersProvider()
