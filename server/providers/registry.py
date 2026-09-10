from functools import lru_cache

import config
from providers.base import GenerationProvider
from providers.diffusers_provider import DiffusersProvider
from providers.pixellab_provider import PixelLabProvider
from providers.unconfigured import UnconfiguredProvider


def _is_native_pixel_checkpoint(model_id: str) -> bool:
    name = (model_id or "").lower()
    if not name or config.is_turbo_model(name):
        return False
    if "sdxl" in name or "stable-diffusion" in name:
        return False
    return True


def _pixel_provider(model_id: str) -> DiffusersProvider:
    return DiffusersProvider(model_id=model_id, native=_is_native_pixel_checkpoint(model_id))


def _turbo_fallback() -> DiffusersProvider:
    return DiffusersProvider(model_id=config.TURBO_MODEL_ID, native=False)


def _unconfigured(reason: str) -> UnconfiguredProvider:
    return UnconfiguredProvider(reason)


@lru_cache(maxsize=1)
def get_provider() -> GenerationProvider:
    choice = config.PIXELATOR_PROVIDER
    model = config.PIXELATOR_MODEL_ID
    key = config.PIXELLAB_API_KEY

    if choice == "pixellab":
        if key:
            return PixelLabProvider()
        return _unconfigured("PIXELATOR_PROVIDER=pixellab but PIXELLAB_API_KEY is empty.")

    if choice in {"fallback", "turbo", "sdxl-turbo"}:
        if config.PIXELATOR_ALLOW_TURBO_FALLBACK or choice in {"fallback", "turbo", "sdxl-turbo"}:
            return _turbo_fallback()
        return _unconfigured("SDXL-Turbo fallback is disabled. Set PIXELATOR_ALLOW_TURBO_FALLBACK=true.")

    if choice in {"diffusers", "diffusers-local", "pixel", "pixel-diffusers", "local"}:
        if not model:
            return _unconfigured("PIXELATOR_MODEL_ID is empty. Point it at a local pixel-art checkpoint.")
        if config.is_turbo_model(model) and not config.PIXELATOR_ALLOW_TURBO_FALLBACK:
            return _unconfigured(
                "PIXELATOR_MODEL_ID is SDXL-Turbo, which is not the default engine. "
                "Set a pixel checkpoint or PIXELATOR_ALLOW_TURBO_FALLBACK=true."
            )
        return _pixel_provider(model)

    if choice in {"auto", ""}:
        if key:
            return PixelLabProvider()
        if model and not config.is_turbo_model(model):
            return _pixel_provider(model)
        if model and config.is_turbo_model(model) and config.PIXELATOR_ALLOW_TURBO_FALLBACK:
            return _turbo_fallback()
        if model and config.is_turbo_model(model):
            return _unconfigured(
                "The configured MODEL_ID is SDXL-Turbo. Pixelator no longer uses that as the default engine. "
                "Set PIXELATOR_MODEL_ID to a pixel-art checkpoint, PIXELLAB_API_KEY, or PIXELATOR_ALLOW_TURBO_FALLBACK=true."
            )
        return _unconfigured(
            "No pixel-art provider is configured. Set PIXELATOR_MODEL_ID, PIXELLAB_API_KEY, "
            "or PIXELATOR_ALLOW_TURBO_FALLBACK=true for the optional Turbo fallback."
        )

    return _unconfigured(f"Unknown PIXELATOR_PROVIDER={choice!r}")
