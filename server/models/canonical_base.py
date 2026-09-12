from __future__ import annotations

from pydantic import BaseModel, Field

from models.character import QualityValidation


class CanonicalBaseCandidate(BaseModel):
    id: str
    seed: int
    path: str
    createdAt: str
    status: str = "pending"
    sha256: str = ""
    rejectReasons: list[str] = Field(default_factory=list)
    valid: bool = False
    validation: QualityValidation | None = None


class CanonicalBaseSession(BaseModel):
    modelId: str
    prompt: str
    negativePrompt: str
    candidates: list[CanonicalBaseCandidate] = Field(default_factory=list)
    accepted: CanonicalBaseCandidate | None = None
    ipAdapterUnlocked: bool = False
    directionGenerationUnlocked: bool = False
    usingCurrentDirectionSet: bool = False
    notes: list[str] = Field(default_factory=list)


class CanonicalGenerateRequest(BaseModel):
    count: int = 4
