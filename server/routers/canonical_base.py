from fastapi import APIRouter

from models.canonical_base import CanonicalGenerateRequest
from services import canonical_base as canonical_base_service
from services.errors import http_error

router = APIRouter()


@router.get("/api/tests/berwynn-canonical")
def get_session():
    try:
        return canonical_base_service.load_session()
    except Exception as exc:
        http_error(exc, context={"action": "canonical_base_session"})


@router.post("/api/tests/berwynn-canonical/generate")
def generate(payload: CanonicalGenerateRequest | None = None):
    try:
        count = payload.count if payload else 4
        return canonical_base_service.generate_candidates(count)
    except Exception as exc:
        http_error(exc, context={"action": "canonical_base_generate"})


@router.post("/api/tests/berwynn-canonical/accept/{candidate_id}")
def accept(candidate_id: str):
    try:
        return canonical_base_service.accept_candidate(candidate_id)
    except Exception as exc:
        http_error(exc, context={"action": "canonical_base_accept", "candidateId": candidate_id})


@router.post("/api/tests/berwynn-canonical/reject/{candidate_id}")
def reject(candidate_id: str):
    try:
        return canonical_base_service.reject_candidate(candidate_id)
    except Exception as exc:
        http_error(exc, context={"action": "canonical_base_reject", "candidateId": candidate_id})
