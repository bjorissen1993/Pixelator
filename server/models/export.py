from pydantic import BaseModel

from models.enums import Direction


class ExportRequest(BaseModel):
    stateId: str | None = None
    direction: Direction | None = None
    includeHead: bool = True


class ExportResult(BaseModel):
    path: str
    url: str
    filename: str
