from fastapi import APIRouter

from domain.state_templates import STATE_TEMPLATES

router = APIRouter()


@router.get("/api/templates/states")
def state_templates():
    return STATE_TEMPLATES
