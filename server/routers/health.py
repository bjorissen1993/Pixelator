from fastapi import APIRouter

from providers.registry import get_provider

router = APIRouter()


@router.get("/health")
def health():
    provider = get_provider()
    return {"ok": True, "provider": provider.info.model_dump()}
