"""Isolated Asset Lab: generic canonical-reference review.

Not the production Studio generator. Generation is only enabled when an asset
profile has an isolated generation spec. Berwynn is the default vertical slice.
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import config
from domain.catalog import all_assets, all_projects, get_asset, get_project, get_style
from models.catalog import (
    AssetLabSession,
    AssetProfile,
    AssetType,
    CatalogSummary,
    GenerationCandidate,
    LearningRecord,
)
from models.canonical_base import CanonicalBaseCandidate, CanonicalBaseSession
from persistence.projects import (
    LEGACY_BERWYNN_REVIEW,
    accepted_canonical_path,
    accepted_dir,
    candidate_dir,
    ensure_asset_dirs,
    rejected_dir,
    seed_project_placeholders,
    session_path,
)
from processing.validators import validate_candidate
from services.learning import write_learning_record

MODEL_TESTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "model_tests"
if str(MODEL_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_TESTS_DIR))

from helpers import (  # noqa: E402
    assert_clip_prompt_budget,
    assert_exact_model,
    load_text2image_pipeline,
    sha256_file,
)

DEFAULT_PROJECT = "chimera"
DEFAULT_ASSET_TYPE: AssetType = "character"
DEFAULT_ASSET_ID = "berwynn"

_pipe_lock = threading.Lock()
_pipes: dict[str, object] = {}
_loaded_ids: dict[str, str] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_path(path: Path) -> str:
    return path.resolve().relative_to(config.DATA_DIR.resolve()).as_posix()


def catalog() -> CatalogSummary:
    _seed_known_projects()
    projects = all_projects()
    return CatalogSummary(
        projects=projects,
        assets=all_assets(),
        defaultProjectId=DEFAULT_PROJECT,
        defaultAssetType=DEFAULT_ASSET_TYPE,
        defaultAssetId=DEFAULT_ASSET_ID,
    )


def _seed_known_projects() -> None:
    for project in all_projects():
        seed_project_placeholders(project.id)
        style = get_style(project.id)
        for asset in all_assets():
            if asset.projectId == project.id:
                ensure_asset_dirs(project, style, asset)


def _context(project_id: str, asset_type: AssetType, asset_id: str) -> tuple[AssetProfile, AssetLabSession]:
    project = get_project(project_id)
    style = get_style(project_id)
    asset = get_asset(project_id, asset_type, asset_id)
    seed_project_placeholders(project_id)
    ensure_asset_dirs(project, style, asset)
    _migrate_legacy_berwynn(asset)
    return asset, _empty_session(asset)


def _empty_session(asset: AssetProfile) -> AssetLabSession:
    project = get_project(asset.projectId)
    notes = [
        "Asset Lab creates a canonical reference for the selected asset only.",
        "This is not the production Studio generator.",
        "Current Studio / direction-set images are not used as identity.",
        "A later reference-conditioned pass unlocks only after one valid reference is accepted.",
        "Direction generation stays locked.",
    ]
    if not asset.generation.enabled:
        notes.append("Generation is not implemented for this asset type yet.")
    return AssetLabSession(
        projectId=asset.projectId,
        projectName=project.name,
        assetType=asset.assetType,
        assetId=asset.assetId,
        assetName=asset.name,
        canonicalKind=asset.canonicalKind,
        canonicalLabel=asset.canonicalLabel,
        state=asset.state,
        direction=asset.direction,
        reviewChecklist=list(asset.reviewChecklist),
        modelId=asset.generation.modelId,
        prompt=asset.generation.prompt,
        negativePrompt=asset.generation.negativePrompt,
        generationEnabled=asset.generation.enabled,
        directionGenerationUnlocked=False,
        usingCurrentDirectionSet=False,
        notes=notes,
    )


def _refresh_candidate(asset: AssetProfile, item: GenerationCandidate) -> GenerationCandidate:
    from PIL import Image

    style = get_style(asset.projectId)
    source = config.DATA_DIR / item.path
    accepted = accepted_canonical_path(asset.projectId, asset.assetType, asset.assetId)
    if item.status == "accepted":
        source = accepted if accepted.is_file() else source
    if not source.is_file():
        return item
    validation, reasons, _busy = validate_candidate(Image.open(source), asset, style)
    item.validation = validation
    item.rejectReasons = reasons
    item.valid = not reasons
    item.sha256 = sha256_file(source)
    item.projectId = asset.projectId
    item.assetType = asset.assetType
    item.assetId = asset.assetId
    item.state = asset.state
    item.direction = asset.direction
    item.prompt = item.prompt or asset.generation.prompt
    item.negativePrompt = item.negativePrompt or asset.generation.negativePrompt
    item.modelId = item.modelId or asset.generation.modelId
    return item


def _legacy_to_candidate(asset: AssetProfile, item: CanonicalBaseCandidate) -> GenerationCandidate:
    return GenerationCandidate(
        id=item.id,
        projectId=asset.projectId,
        assetType=asset.assetType,
        assetId=asset.assetId,
        state=asset.state,
        direction=asset.direction,
        seed=item.seed,
        path=item.path,
        createdAt=item.createdAt,
        status=item.status,
        sha256=item.sha256,
        rejectReasons=item.rejectReasons,
        valid=item.valid,
        validation=item.validation,
        prompt=asset.generation.prompt,
        negativePrompt=asset.generation.negativePrompt,
        modelId=asset.generation.modelId,
    )


def _migrate_legacy_berwynn(asset: AssetProfile) -> None:
    if asset.projectId != "chimera" or asset.assetType != "character" or asset.assetId != "berwynn":
        return
    dest_accepted = accepted_canonical_path(asset.projectId, asset.assetType, asset.assetId)
    legacy_accepted = LEGACY_BERWYNN_REVIEW / "accepted" / "canonical.png"
    if legacy_accepted.is_file() and not dest_accepted.is_file():
        dest_accepted.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_accepted, dest_accepted)

    dest_session = session_path(asset.projectId, asset.assetType, asset.assetId)
    legacy_session = LEGACY_BERWYNN_REVIEW / "session.json"
    if dest_session.is_file() or not legacy_session.is_file():
        return
    payload = json.loads(legacy_session.read_text(encoding="utf-8"))
    old = CanonicalBaseSession.model_validate(payload)
    session = _empty_session(asset)
    copied: list[GenerationCandidate] = []
    dest_candidates = candidate_dir(asset.projectId, asset.assetType, asset.assetId)
    dest_candidates.mkdir(parents=True, exist_ok=True)
    for item in old.candidates:
        source = config.DATA_DIR / item.path
        if source.is_file():
            target = dest_candidates / source.name
            if not target.is_file():
                shutil.copy2(source, target)
            item.path = _public_path(target)
        copied.append(_legacy_to_candidate(asset, item))
    session.candidates = copied
    if old.accepted:
        if dest_accepted.is_file():
            old.accepted.path = _public_path(dest_accepted)
        session.accepted = _legacy_to_candidate(asset, old.accepted)
        session.accepted.status = "accepted"
        session.referenceUnlocked = True
        session.ipAdapterUnlocked = True
    dest_session.write_text(session.model_dump_json(indent=2), encoding="utf-8")


def load_session(
    project_id: str = DEFAULT_PROJECT,
    asset_type: AssetType = DEFAULT_ASSET_TYPE,
    asset_id: str = DEFAULT_ASSET_ID,
) -> AssetLabSession:
    asset, empty = _context(project_id, asset_type, asset_id)
    path = session_path(project_id, asset_type, asset_id)
    if not path.is_file():
        save_session(empty)
        return empty
    payload = json.loads(path.read_text(encoding="utf-8"))
    try:
        session = AssetLabSession.model_validate(payload)
    except Exception:
        old = CanonicalBaseSession.model_validate(payload)
        session = empty
        session.candidates = [_legacy_to_candidate(asset, item) for item in old.candidates]
        if old.accepted:
            session.accepted = _legacy_to_candidate(asset, old.accepted)
    session.projectId = asset.projectId
    session.projectName = get_project(asset.projectId).name
    session.assetType = asset.assetType
    session.assetId = asset.assetId
    session.assetName = asset.name
    session.canonicalKind = asset.canonicalKind
    session.canonicalLabel = asset.canonicalLabel
    session.state = asset.state
    session.direction = asset.direction
    session.reviewChecklist = list(asset.reviewChecklist)
    session.modelId = asset.generation.modelId or session.modelId
    session.prompt = asset.generation.prompt or session.prompt
    session.negativePrompt = asset.generation.negativePrompt or session.negativePrompt
    session.generationEnabled = asset.generation.enabled
    session.candidates = [_refresh_candidate(asset, item) for item in session.candidates]
    if session.accepted:
        session.accepted = _refresh_candidate(asset, session.accepted)
        unlocked = bool(session.accepted.valid and session.accepted.status == "accepted")
        session.referenceUnlocked = unlocked
        session.ipAdapterUnlocked = unlocked
    session.directionGenerationUnlocked = False
    session.usingCurrentDirectionSet = False
    return session


def save_session(session: AssetLabSession) -> None:
    path = session_path(session.projectId, session.assetType, session.assetId)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session.model_dump_json(indent=2), encoding="utf-8")


def accepted_path(
    project_id: str = DEFAULT_PROJECT,
    asset_type: AssetType = DEFAULT_ASSET_TYPE,
    asset_id: str = DEFAULT_ASSET_ID,
) -> Path:
    return accepted_canonical_path(project_id, asset_type, asset_id)


def _load_pipe(model_id: str, prompt: str, negative_prompt: str):
    with _pipe_lock:
        if model_id in _pipes:
            return _pipes[model_id], _loaded_ids.get(model_id, model_id)
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("Hard fail: CUDA is unavailable for isolated Asset Lab generation.")
        dtype = torch.float16
        pipe = load_text2image_pipeline(model_id, dtype, allow_sdxl=False)
        loaded = assert_exact_model(pipe, model_id, allow_sdxl=False)
        pipe = pipe.to("cuda")
        if hasattr(pipe, "set_progress_bar_config"):
            pipe.set_progress_bar_config(disable=False)
        assert_clip_prompt_budget(pipe, prompt, negative_prompt)
        _pipes[model_id] = pipe
        _loaded_ids[model_id] = loaded
        return pipe, loaded


def generate_candidates(
    project_id: str = DEFAULT_PROJECT,
    asset_type: AssetType = DEFAULT_ASSET_TYPE,
    asset_id: str = DEFAULT_ASSET_ID,
    count: int = 4,
) -> AssetLabSession:
    import torch
    from PIL import Image

    asset = get_asset(project_id, asset_type, asset_id)
    if not asset.generation.enabled:
        raise ValueError(f"Generation is not implemented for {asset.assetType} assets yet.")
    spec = asset.generation
    count = max(1, min(4, int(count)))
    pipe, loaded_id = _load_pipe(spec.modelId, spec.prompt, spec.negativePrompt)
    session = load_session(project_id, asset_type, asset_id)
    session.modelId = loaded_id or spec.modelId
    session.prompt = spec.prompt
    session.negativePrompt = spec.negativePrompt
    session.directionGenerationUnlocked = False
    session.usingCurrentDirectionSet = False
    dest_dir = candidate_dir(project_id, asset_type, asset_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    style = get_style(project_id)
    settings = {"width": spec.width, "height": spec.height, "steps": spec.steps, "guidance": spec.guidance}

    for _ in range(count):
        seed = int(time.time() * 1000) % 1_000_000_000 + uuid4().int % 90_000
        candidate_id = uuid4().hex[:10]
        dest = dest_dir / f"{candidate_id}.png"
        generator = torch.Generator(device="cuda").manual_seed(seed)
        image = pipe(
            prompt=spec.prompt,
            negative_prompt=spec.negativePrompt,
            width=spec.width,
            height=spec.height,
            num_inference_steps=spec.steps,
            guidance_scale=spec.guidance,
            generator=generator,
        ).images[0]
        image.save(dest)
        validation, reasons, _busy = validate_candidate(Image.open(dest), asset, style)
        session.candidates.insert(
            0,
            GenerationCandidate(
                id=candidate_id,
                projectId=asset.projectId,
                assetType=asset.assetType,
                assetId=asset.assetId,
                state=asset.state,
                direction=asset.direction,
                seed=seed,
                path=_public_path(dest),
                createdAt=_now(),
                status="pending",
                sha256=sha256_file(dest),
                rejectReasons=reasons,
                valid=not reasons,
                validation=validation,
                prompt=spec.prompt,
                negativePrompt=spec.negativePrompt,
                modelId=loaded_id or spec.modelId,
                modelSettings=settings,
            ),
        )
    save_session(session)
    return session


def _record_decision(
    asset: AssetProfile,
    candidate: GenerationCandidate,
    decision: str,
    extra_reasons: list[str] | None = None,
) -> None:
    write_learning_record(
        LearningRecord(
            id=f"{candidate.id}-{decision}-{uuid4().hex[:6]}",
            createdAt=_now(),
            projectId=asset.projectId,
            assetType=asset.assetType,
            assetId=asset.assetId,
            state=asset.state,
            direction=asset.direction,
            prompt=candidate.prompt or asset.generation.prompt,
            negativePrompt=candidate.negativePrompt or asset.generation.negativePrompt,
            seed=candidate.seed,
            modelId=candidate.modelId or asset.generation.modelId,
            provider="isolated-asset-lab",
            modelSettings=candidate.modelSettings
            or {
                "width": asset.generation.width,
                "height": asset.generation.height,
                "steps": asset.generation.steps,
                "guidance": asset.generation.guidance,
            },
            references=[],
            validationResults=candidate.validation.model_dump() if candidate.validation else {},
            decision=decision,  # type: ignore[arg-type]
            rejectionReasons=list(extra_reasons or candidate.rejectReasons),
            candidatePath=candidate.path,
            sha256=candidate.sha256,
        )
    )


def accept_candidate(
    candidate_id: str,
    project_id: str = DEFAULT_PROJECT,
    asset_type: AssetType = DEFAULT_ASSET_TYPE,
    asset_id: str = DEFAULT_ASSET_ID,
) -> AssetLabSession:
    from PIL import Image

    asset = get_asset(project_id, asset_type, asset_id)
    session = load_session(project_id, asset_type, asset_id)
    chosen = next((item for item in session.candidates if item.id == candidate_id), None)
    if chosen is None:
        raise KeyError(f"Unknown candidate {candidate_id}")
    if chosen.rejectReasons or not chosen.valid:
        raise ValueError("Hard fail: this candidate failed validation.")
    source = config.DATA_DIR / chosen.path
    if not source.is_file():
        raise FileNotFoundError(f"Candidate image missing: {source}")
    dest = accepted_canonical_path(project_id, asset_type, asset_id)
    accepted_dir(project_id, asset_type, asset_id).mkdir(parents=True, exist_ok=True)
    Image.open(source).save(dest)
    chosen.status = "accepted"
    chosen.path = _public_path(dest)
    for item in session.candidates:
        if item.id != chosen.id and item.status == "accepted":
            item.status = "rejected"
    session.accepted = chosen
    session.referenceUnlocked = True
    session.ipAdapterUnlocked = True
    session.directionGenerationUnlocked = False
    session.usingCurrentDirectionSet = False
    save_session(session)
    _record_decision(asset, chosen, "accepted")
    return session


def reject_candidate(
    candidate_id: str,
    project_id: str = DEFAULT_PROJECT,
    asset_type: AssetType = DEFAULT_ASSET_TYPE,
    asset_id: str = DEFAULT_ASSET_ID,
) -> AssetLabSession:
    asset = get_asset(project_id, asset_type, asset_id)
    session = load_session(project_id, asset_type, asset_id)
    chosen = next((item for item in session.candidates if item.id == candidate_id), None)
    if chosen is None:
        raise KeyError(f"Unknown candidate {candidate_id}")
    chosen.status = "rejected"
    source = config.DATA_DIR / chosen.path
    dest_dir = rejected_dir(project_id, asset_type, asset_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        target = dest_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    if session.accepted and session.accepted.id == candidate_id:
        session.accepted = None
        session.referenceUnlocked = False
        session.ipAdapterUnlocked = False
        accepted = accepted_canonical_path(project_id, asset_type, asset_id)
        if accepted.exists():
            accepted.unlink()
    session.directionGenerationUnlocked = False
    save_session(session)
    _record_decision(asset, chosen, "rejected")
    return session
