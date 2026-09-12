from __future__ import annotations

from dataclasses import dataclass

from models.catalog import AssetType, LearningRecord
from models.learning import LearningScope

SCOPE_WEIGHT: dict[LearningScope, int] = {
    "global": 1,
    "project": 2,
    "asset_type": 3,
    "asset": 4,
    "state": 5,
}


@dataclass(frozen=True)
class LearningContext:
    projectId: str
    assetType: AssetType
    assetId: str
    state: str | None = None
    direction: str | None = None

    def source_label(self, scope: LearningScope) -> str:
        if scope == "global":
            return "global"
        if scope == "project":
            return f"project:{self.projectId}"
        if scope == "asset_type":
            return f"asset_type:{self.projectId}/{self.assetType}"
        if scope == "asset":
            return f"asset:{self.projectId}/{self.assetType}/{self.assetId}"
        variant = self.state or self.direction or "default"
        return f"state:{self.projectId}/{self.assetType}/{self.assetId}/{variant}"


def record_scope(record: LearningRecord) -> LearningScope:
    return record.scope or "asset"


def record_matches(record: LearningRecord, context: LearningContext, scope: LearningScope) -> bool:
    if record_scope(record) != scope:
        return False
    if scope == "global":
        return True
    if record.projectId != context.projectId:
        return False
    if scope == "project":
        return True
    if record.assetType != context.assetType:
        return False
    if scope == "asset_type":
        return True
    if record.assetId != context.assetId:
        return False
    if scope == "asset":
        return True
    wanted = context.state or context.direction
    got = record.state or record.direction
    return bool(wanted) and wanted == got
