from fastapi import APIRouter

from models.catalog import AssetLabGenerateRequest, AssetType
from services import asset_lab as asset_lab_service
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
    projectId: str = asset_lab_service.DEFAULT_PROJECT,
    assetType: AssetType = asset_lab_service.DEFAULT_ASSET_TYPE,
    assetId: str = asset_lab_service.DEFAULT_ASSET_ID,
):
    try:
        return asset_lab_service.load_session(projectId, assetType, assetId)
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_session"})


@router.post("/api/tests/asset-lab/generate")
def generate(payload: AssetLabGenerateRequest | None = None):
    try:
        body = payload or AssetLabGenerateRequest()
        return asset_lab_service.generate_candidates(
            body.projectId, body.assetType, body.assetId, body.count
        )
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_generate"})


@router.post("/api/tests/asset-lab/accept/{candidate_id}")
def accept(
    candidate_id: str,
    projectId: str = asset_lab_service.DEFAULT_PROJECT,
    assetType: AssetType = asset_lab_service.DEFAULT_ASSET_TYPE,
    assetId: str = asset_lab_service.DEFAULT_ASSET_ID,
):
    try:
        return asset_lab_service.accept_candidate(candidate_id, projectId, assetType, assetId)
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_accept", "candidateId": candidate_id})


@router.post("/api/tests/asset-lab/reject/{candidate_id}")
def reject(
    candidate_id: str,
    projectId: str = asset_lab_service.DEFAULT_PROJECT,
    assetType: AssetType = asset_lab_service.DEFAULT_ASSET_TYPE,
    assetId: str = asset_lab_service.DEFAULT_ASSET_ID,
):
    try:
        return asset_lab_service.reject_candidate(candidate_id, projectId, assetType, assetId)
    except Exception as exc:
        http_error(exc, context={"action": "asset_lab_reject", "candidateId": candidate_id})
