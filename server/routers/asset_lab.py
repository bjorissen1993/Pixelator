from fastapi import APIRouter

from domain.catalog import get_asset
from learning.policy import parse_batch_size
from models.catalog import (
    AssetLabAcceptRequest,
    AssetLabExtractFlagRequest,
    AssetLabGenerateRequest,
    AssetLabRejectRequest,
    AssetType,
)
from models.learning import LearningControlRequest
from services import asset_lab as asset_lab_service
from services import learning as learning_service
from services.errors import http_error

router = APIRouter()


@router.get("/api/tests/asset-lab/catalog")
def get_catalog():
    try:
        return asset_lab_service.catalog()
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_catalog"})


@router.get("/api/tests/asset-lab")
def get_session(
    projectId: str | None = None,
    assetType: AssetType | None = None,
    assetId: str | None = None,
    batchSize: int | None = None,
):
    try:
        project_id, asset_type, asset_id = asset_lab_service.resolve_selection(projectId, assetType, assetId)
        session = asset_lab_service.load_session(project_id, asset_type, asset_id)
        if batchSize is not None:
            session.batchSize = parse_batch_size(batchSize)
            session.learning = learning_service.snapshot_for(
                get_asset(project_id, asset_type, asset_id), session.batchSize
            ).model_dump()
        return session
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_session"})


@router.post("/api/tests/asset-lab/generate")
def generate(payload: AssetLabGenerateRequest | None = None):
    try:
        body = payload or AssetLabGenerateRequest()
        project_id, asset_type, asset_id = asset_lab_service.resolve_selection(
            body.projectId, body.assetType, body.assetId
        )
        return asset_lab_service.generate_candidates(
            project_id, asset_type, asset_id, body.resolved_batch_size()
        )
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_generate"})


@router.post("/api/tests/asset-lab/accept/{candidate_id}")
def accept(
    candidate_id: str,
    projectId: str | None = None,
    assetType: AssetType | None = None,
    assetId: str | None = None,
    payload: AssetLabAcceptRequest | None = None,
):
    try:
        project_id, asset_type, asset_id = asset_lab_service.resolve_selection(projectId, assetType, assetId)
        return asset_lab_service.accept_candidate(
            candidate_id, project_id, asset_type, asset_id, payload or AssetLabAcceptRequest()
        )
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_accept", "candidateId": candidate_id})


@router.post("/api/tests/asset-lab/reject/{candidate_id}")
def reject(
    candidate_id: str,
    projectId: str | None = None,
    assetType: AssetType | None = None,
    assetId: str | None = None,
    payload: AssetLabRejectRequest | None = None,
):
    try:
        project_id, asset_type, asset_id = asset_lab_service.resolve_selection(projectId, assetType, assetId)
        return asset_lab_service.reject_candidate(
            candidate_id, project_id, asset_type, asset_id, payload or AssetLabRejectRequest()
        )
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_reject", "candidateId": candidate_id})


@router.post("/api/tests/asset-lab/extract/{candidate_id}")
def reextract(
    candidate_id: str,
    projectId: str | None = None,
    assetType: AssetType | None = None,
    assetId: str | None = None,
):
    try:
        project_id, asset_type, asset_id = asset_lab_service.resolve_selection(projectId, assetType, assetId)
        return asset_lab_service.reextract_transparency(candidate_id, project_id, asset_type, asset_id)
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_reextract", "candidateId": candidate_id})


@router.post("/api/tests/asset-lab/extract/{candidate_id}/flag")
def flag_extract(
    candidate_id: str,
    projectId: str | None = None,
    assetType: AssetType | None = None,
    assetId: str | None = None,
    payload: AssetLabExtractFlagRequest | None = None,
):
    try:
        project_id, asset_type, asset_id = asset_lab_service.resolve_selection(projectId, assetType, assetId)
        return asset_lab_service.flag_extraction(
            candidate_id, project_id, asset_type, asset_id, payload or AssetLabExtractFlagRequest()
        )
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_flag_extraction", "candidateId": candidate_id})


@router.get("/api/tests/asset-lab/learning")
def get_learning(
    projectId: str | None = None,
    assetType: AssetType | None = None,
    assetId: str | None = None,
    batchSize: int | None = None,
):
    try:
        project_id, asset_type, asset_id = asset_lab_service.resolve_selection(projectId, assetType, assetId)
        size = parse_batch_size(batchSize) if batchSize is not None else None
        return learning_service.snapshot_for(get_asset(project_id, asset_type, asset_id), size)
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_learning"})


@router.post("/api/tests/asset-lab/learning/control")
def control_learning(payload: LearningControlRequest):
    try:
        return learning_service.apply_learning_control(payload)
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_learning_control"})
