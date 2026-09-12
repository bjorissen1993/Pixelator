"""Isolated Asset Lab: generic canonical-reference review.

Not the production Studio generator. Generation is only enabled when an asset
profile has an isolated generation spec.
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
from domain.catalog import all_assets, all_projects, default_selection, get_asset, get_project, get_style
from models.catalog import (
    AssetLabExtractFlagRequest,
    AssetLabRejectRequest,
    AssetLabSession,
    AssetProfile,
    AssetType,
    CatalogSummary,
    ExtractionMetadata,
    GenerationCandidate,
    LearningRecord,
    ValidatorFeedback,
)
from models.canonical_base import CanonicalBaseCandidate, CanonicalBaseSession
from persistence.projects import (
    accepted_canonical_path,
    accepted_dir,
    accepted_isolated_path,
    accepted_preview_path,
    candidate_dir,
    candidate_isolated_path,
    candidate_preview_path,
    candidate_raw_path,
    ensure_asset_dirs,
    rejected_dir,
    seed_project_placeholders,
    session_path,
)
from learning.policy import ALLOWED_BATCH_SIZES, parse_batch_size
from learning.recipes import plan_candidate_recipes
from learning.store import load_controls
from processing.isolation import EXTRACTION_VERSION, describe_isolation, extract_transparent_asset
from processing.output_mode import background_mode_for, expects_isolated_output
from processing.transparency_quality import assess_transparency, issue_labels
from processing.validators import validate_candidate
from processing.validators.review_reasons import reasons_for_asset, resolve_manual_reasons
from processing.validators.transparent_output import isolated_reason_messages, transparent_output_warnings
from services.learning import snapshot_for, write_learning_record
from services.legacy_review import migrate_legacy_review

MODEL_TESTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "model_tests"
if str(MODEL_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_TESTS_DIR))

from helpers import (  # noqa: E402
    assert_clip_prompt_budget,
    assert_exact_model,
    load_text2image_pipeline,
    sha256_file,
)

_pipe_lock = threading.Lock()
_pipes: dict[str, object] = {}
_loaded_ids: dict[str, str] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_path(path: Path) -> str:
    return path.resolve().relative_to(config.DATA_DIR.resolve()).as_posix()


def resolve_selection(
    project_id: str | None = None,
    asset_type: AssetType | None = None,
    asset_id: str | None = None,
) -> tuple[str, AssetType, str]:
    if project_id and asset_type and asset_id:
        return project_id, asset_type, asset_id
    default_project, default_type, default_id = default_selection()
    return project_id or default_project, asset_type or default_type, asset_id or default_id


def catalog() -> CatalogSummary:
    _seed_known_projects()
    projects = sorted(all_projects(), key=lambda item: (not item.isDefault, item.name.lower()))
    default_project, default_type, default_id = default_selection()
    return CatalogSummary(
        projects=projects,
        assets=all_assets(),
        defaultProjectId=default_project,
        defaultAssetType=default_type,
        defaultAssetId=default_id,
        allowedBatchSizes=list(ALLOWED_BATCH_SIZES),
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
    migrate_legacy_review(asset, _empty_session, _legacy_to_candidate, _public_path)
    return asset, _empty_session(asset)


def _empty_session(asset: AssetProfile) -> AssetLabSession:
    project = get_project(asset.projectId)
    notes = [
        "Asset Lab creates a canonical reference for the selected asset only.",
        "This is not the production Studio generator.",
        "Current Studio / direction-set images are not used as identity.",
        "A later reference-conditioned pass unlocks only after one valid reference is accepted.",
        "Review preview stays on a plain background. When the asset type requires transparent output, a separate isolated asset is derived after generation.",
    ]
    if asset.assetType == "character":
        notes.append("Direction generation stays locked until that later character pass exists.")
    if not asset.generation.enabled:
        notes.append("Generation is not enabled for this asset yet.")
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
        reviewReasons=reasons_for_asset(asset),
        modelId=asset.generation.modelId,
        prompt=asset.generation.prompt,
        negativePrompt=asset.generation.negativePrompt,
        generationEnabled=asset.generation.enabled,
        directionGenerationUnlocked=False,
        usingCurrentDirectionSet=False,
        notes=notes,
        backgroundMode=background_mode_for(asset),
    )


def _resolve_raw_path(asset: AssetProfile, item: GenerationCandidate) -> Path:
    by_id = candidate_raw_path(asset.projectId, asset.assetType, asset.assetId, item.id)
    listed = [config.DATA_DIR / item.rawPath] if item.rawPath else []
    listed.append(by_id)
    if item.path:
        listed.append(config.DATA_DIR / item.path)
    for path in listed:
        if path.is_file() and path.name != "canonical.png":
            return path
    for path in listed:
        if path.is_file():
            return path
    return by_id


def _metadata_from_extraction(result, flagged: bool = False) -> ExtractionMetadata:
    return ExtractionMetadata(
        method=result.method,
        version=result.version,
        maskSettings=dict(result.settings),
        quality=result.quality.grade,  # type: ignore[arg-type]
        qualityScore=result.quality.score,
        issues=list(result.quality.issues),
        flaggedIncorrect=flagged,
        extractedAt=_now(),
    )


def _apply_extraction_result(item: GenerationCandidate, result, isolated_file: Path, flagged: bool = False) -> None:
    warnings = transparent_output_warnings(result.image, result.report)
    item.isolatedPath = _public_path(isolated_file)
    item.isolatedReasons = isolated_reason_messages(warnings, result.quality)
    if result.report.busy_background and "Isolated output: background could not be isolated" not in item.isolatedReasons:
        item.isolatedReasons.append("Isolated output: background could not be isolated")
    item.extraction = _metadata_from_extraction(result, flagged)
    item.isolatedStatus = "failed" if result.quality.grade == "failed" else "ok"


def _apply_output_artifacts(
    asset: AssetProfile,
    item: GenerationCandidate,
    raw_file: Path,
    force_extract: bool = False,
) -> GenerationCandidate:
    from PIL import Image

    mode = background_mode_for(asset)
    item.backgroundMode = mode
    item.rawPath = _public_path(raw_file)
    item.path = _public_path(raw_file)

    preview_file = candidate_preview_path(asset.projectId, asset.assetType, asset.assetId, item.id)
    preview_file.parent.mkdir(parents=True, exist_ok=True)
    if not preview_file.is_file():
        Image.open(raw_file).convert("RGBA").save(preview_file)
    item.previewPath = _public_path(preview_file)

    if not expects_isolated_output(asset):
        item.isolatedStatus = "skipped"
        item.isolatedReasons = []
        item.isolatedPath = ""
        item.extraction = None
        return item

    isolated_file = candidate_isolated_path(asset.projectId, asset.assetType, asset.assetId, item.id)
    isolated_file.parent.mkdir(parents=True, exist_ok=True)
    raw_image = Image.open(raw_file)
    stale = not item.extraction or item.extraction.version < EXTRACTION_VERSION
    if force_extract or not isolated_file.is_file() or stale:
        result = extract_transparent_asset(raw_image)
        result.image.save(isolated_file)
        _apply_extraction_result(item, result, isolated_file)
    else:
        isolated = Image.open(isolated_file)
        report = describe_isolation(isolated, raw_image)
        quality = assess_transparency(raw_image, isolated, report)
        flagged = bool(item.extraction and item.extraction.flaggedIncorrect)
        item.isolatedPath = _public_path(isolated_file)
        item.isolatedReasons = isolated_reason_messages(transparent_output_warnings(isolated, report), quality)
        item.extraction = ExtractionMetadata(
            method=(item.extraction.method if item.extraction else "") or "edge_flood_refine",
            version=item.extraction.version if item.extraction else EXTRACTION_VERSION,
            maskSettings=item.extraction.maskSettings if item.extraction else {},
            quality=quality.grade,  # type: ignore[arg-type]
            qualityScore=quality.score,
            issues=list(quality.issues),
            flaggedIncorrect=flagged,
            extractedAt=(item.extraction.extractedAt if item.extraction else "") or _now(),
        )
        item.isolatedStatus = "failed" if quality.grade == "failed" else "ok"

    accepted_preview = accepted_preview_path(asset.projectId, asset.assetType, asset.assetId)
    accepted_isolated = accepted_isolated_path(asset.projectId, asset.assetType, asset.assetId)
    if item.status == "accepted" and accepted_preview.is_file() and not force_extract:
        item.previewPath = _public_path(accepted_preview)
    if item.status == "accepted" and (force_extract or stale):
        accepted_isolated.parent.mkdir(parents=True, exist_ok=True)
        Image.open(isolated_file).save(accepted_isolated)
        item.isolatedPath = _public_path(accepted_isolated)
    elif item.status == "accepted" and accepted_isolated.is_file():
        item.isolatedPath = _public_path(accepted_isolated)
    return item


def _refresh_candidate(asset: AssetProfile, item: GenerationCandidate) -> GenerationCandidate:
    from PIL import Image

    style = get_style(asset.projectId)
    source = _resolve_raw_path(asset, item)
    if not source.is_file():
        item.backgroundMode = background_mode_for(asset)
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
    return _apply_output_artifacts(asset, item, source)


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


def _apply_followup_locks(session: AssetLabSession, asset: AssetProfile, unlocked: bool) -> None:
    session.referenceUnlocked = unlocked
    session.ipAdapterUnlocked = unlocked and asset.assetType == "character"
    session.directionGenerationUnlocked = False
    session.usingCurrentDirectionSet = False


def load_session(
    project_id: str | None = None,
    asset_type: AssetType | None = None,
    asset_id: str | None = None,
) -> AssetLabSession:
    project_id, asset_type, asset_id = resolve_selection(project_id, asset_type, asset_id)
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
    session.reviewReasons = reasons_for_asset(asset)
    session.backgroundMode = background_mode_for(asset)
    session.modelId = asset.generation.modelId or session.modelId
    session.prompt = asset.generation.prompt or session.prompt
    session.negativePrompt = asset.generation.negativePrompt or session.negativePrompt
    session.generationEnabled = asset.generation.enabled
    session.notes = empty.notes
    session.candidates = [_refresh_candidate(asset, item) for item in session.candidates]
    if session.accepted:
        session.accepted = _refresh_candidate(asset, session.accepted)
        unlocked = bool(session.accepted.valid and session.accepted.status == "accepted")
        _apply_followup_locks(session, asset, unlocked)
    else:
        _apply_followup_locks(session, asset, False)
    session.learning = snapshot_for(asset, session.batchSize).model_dump()
    save_session(session)
    return session


def save_session(session: AssetLabSession) -> None:
    path = session_path(session.projectId, session.assetType, session.assetId)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session.model_dump_json(indent=2), encoding="utf-8")


def accepted_path(
    project_id: str | None = None,
    asset_type: AssetType | None = None,
    asset_id: str | None = None,
) -> Path:
    project_id, asset_type, asset_id = resolve_selection(project_id, asset_type, asset_id)
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
    project_id: str | None = None,
    asset_type: AssetType | None = None,
    asset_id: str | None = None,
    count: int = 4,
) -> AssetLabSession:
    import torch
    from PIL import Image

    project_id, asset_type, asset_id = resolve_selection(project_id, asset_type, asset_id)
    asset = get_asset(project_id, asset_type, asset_id)
    if not asset.generation.enabled:
        raise ValueError(f"Generation is not enabled for {asset.projectId}/{asset.assetType}/{asset.assetId}.")
    spec = asset.generation
    count = parse_batch_size(count)
    snapshot = snapshot_for(asset, count)
    recipes = plan_candidate_recipes(
        asset,
        snapshot.recommendations,
        snapshot.policy,
        count,
        load_controls(asset.projectId, asset.assetType, asset.assetId),
    )
    base_recipe = recipes[0]
    pipe, loaded_id = _load_pipe(spec.modelId, base_recipe.prompt or spec.prompt, base_recipe.negativePrompt or spec.negativePrompt)
    session = load_session(project_id, asset_type, asset_id)
    session.modelId = loaded_id or spec.modelId
    session.prompt = base_recipe.prompt
    session.negativePrompt = base_recipe.negativePrompt
    session.directionGenerationUnlocked = False
    session.usingCurrentDirectionSet = False
    dest_dir = candidate_dir(project_id, asset_type, asset_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    style = get_style(project_id)

    for recipe in recipes:
        seed = int(time.time() * 1000) % 1_000_000_000 + uuid4().int % 90_000
        recipe.seed = seed
        candidate_id = uuid4().hex[:10]
        dest = dest_dir / f"{candidate_id}.png"
        generator = torch.Generator(device="cuda").manual_seed(seed)
        image = pipe(
            prompt=recipe.prompt or spec.prompt,
            negative_prompt=recipe.negativePrompt or spec.negativePrompt,
            width=recipe.width,
            height=recipe.height,
            num_inference_steps=recipe.steps,
            guidance_scale=recipe.guidance,
            generator=generator,
        ).images[0]
        image.save(dest)
        validation, reasons, _busy = validate_candidate(Image.open(dest), asset, style)
        candidate = GenerationCandidate(
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
            prompt=recipe.prompt,
            negativePrompt=recipe.negativePrompt,
            modelId=loaded_id or spec.modelId,
            modelSettings={
                "width": recipe.width,
                "height": recipe.height,
                "steps": recipe.steps,
                "guidance": recipe.guidance,
                "referenceStrength": recipe.referenceStrength,
                "referenceStrategy": recipe.referenceStrategy,
            },
            recipeFingerprint=recipe.fingerprint,
            recipeMode=recipe.mode,
            learnedAdjustments=[item.model_dump() for item in recipe.adjustments],
            recipeWhy=recipe.why,
        )
        session.candidates.insert(0, _apply_output_artifacts(asset, candidate, dest))
    session.batchSize = count
    session.learning = snapshot_for(asset, count).model_dump()
    save_session(session)
    return session


def _record_decision(
    asset: AssetProfile,
    candidate: GenerationCandidate,
    decision: str,
    extra_reasons: list[str] | None = None,
    manual_reasons: list[str] | None = None,
    manual_note: str = "",
    validator_feedback: ValidatorFeedback | None = None,
) -> None:
    automatic = list(candidate.rejectReasons)
    manual = list(manual_reasons or extra_reasons or [])
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
            rejectionReasons=[*automatic, *manual],
            automaticRejectionReasons=automatic,
            manualRejectionReasons=manual,
            manualNote=manual_note,
            validatorFeedback=validator_feedback,
            candidatePath=candidate.path,
            sha256=candidate.sha256,
            recipeFingerprint=candidate.recipeFingerprint,
            recipeMode=candidate.recipeMode,
            referenceStrategy=str((candidate.modelSettings or {}).get("referenceStrategy") or "none"),
            referenceStrength=(candidate.modelSettings or {}).get("referenceStrength"),
            learnedAdjustments=candidate.learnedAdjustments,
            feedbackChannel="generation",
        )
    )


def accept_candidate(
    candidate_id: str,
    project_id: str | None = None,
    asset_type: AssetType | None = None,
    asset_id: str | None = None,
) -> AssetLabSession:
    from PIL import Image

    project_id, asset_type, asset_id = resolve_selection(project_id, asset_type, asset_id)
    asset = get_asset(project_id, asset_type, asset_id)
    session = load_session(project_id, asset_type, asset_id)
    chosen = next((item for item in session.candidates if item.id == candidate_id), None)
    if chosen is None:
        raise KeyError(f"Unknown candidate {candidate_id}")
    if chosen.rejectReasons or not chosen.valid:
        raise ValueError("Hard fail: this candidate failed validation.")
    source = _resolve_raw_path(asset, chosen)
    if not source.is_file():
        raise FileNotFoundError(f"Candidate image missing: {source}")
    _apply_output_artifacts(asset, chosen, source)
    accepted_dir(project_id, asset_type, asset_id).mkdir(parents=True, exist_ok=True)
    preview_source = config.DATA_DIR / chosen.previewPath if chosen.previewPath else source
    if not preview_source.is_file():
        preview_source = source
    Image.open(preview_source).save(accepted_canonical_path(project_id, asset_type, asset_id))
    Image.open(preview_source).save(accepted_preview_path(project_id, asset_type, asset_id))
    if chosen.isolatedPath:
        isolated_source = config.DATA_DIR / chosen.isolatedPath
        if isolated_source.is_file():
            Image.open(isolated_source).save(accepted_isolated_path(project_id, asset_type, asset_id))
            chosen.isolatedPath = _public_path(accepted_isolated_path(project_id, asset_type, asset_id))
    chosen.status = "accepted"
    chosen.path = _public_path(source)
    chosen.rawPath = _public_path(source)
    chosen.previewPath = _public_path(accepted_preview_path(project_id, asset_type, asset_id))
    for item in session.candidates:
        if item.id != chosen.id and item.status == "accepted":
            item.status = "rejected"
    session.accepted = chosen
    _apply_followup_locks(session, asset, True)
    _record_decision(asset, chosen, "accepted")
    session.learning = snapshot_for(asset, session.batchSize).model_dump()
    save_session(session)
    return session


def reject_candidate(
    candidate_id: str,
    project_id: str | None = None,
    asset_type: AssetType | None = None,
    asset_id: str | None = None,
    payload: AssetLabRejectRequest | None = None,
) -> AssetLabSession:
    project_id, asset_type, asset_id = resolve_selection(project_id, asset_type, asset_id)
    asset = get_asset(project_id, asset_type, asset_id)
    session = load_session(project_id, asset_type, asset_id)
    chosen = next((item for item in session.candidates if item.id == candidate_id), None)
    if chosen is None:
        raise KeyError(f"Unknown candidate {candidate_id}")
    source = _resolve_raw_path(asset, chosen)
    dest_dir = rejected_dir(project_id, asset_type, asset_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        target = dest_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
    if session.accepted and session.accepted.id == candidate_id:
        session.accepted = None
        for extra in (
            accepted_canonical_path(project_id, asset_type, asset_id),
            accepted_preview_path(project_id, asset_type, asset_id),
            accepted_isolated_path(project_id, asset_type, asset_id),
        ):
            if extra.exists():
                extra.unlink()
    body = payload or AssetLabRejectRequest()
    manual = resolve_manual_reasons(asset, body.reasonIds, body.note)
    if (
        payload is not None
        and not manual
        and not body.note.strip()
        and not body.validatorFeedback
    ):
        raise ValueError("Choose at least one rejection reason, a short note, or a validator-feedback marker.")
    chosen.status = "rejected"
    chosen.manualRejectReasons = manual
    chosen.manualNote = body.note.strip()
    chosen.validatorFeedback = body.validatorFeedback
    _apply_followup_locks(session, asset, False)
    _record_decision(
        asset,
        chosen,
        "rejected",
        manual_reasons=manual,
        manual_note=body.note.strip(),
        validator_feedback=body.validatorFeedback,
    )
    session.learning = snapshot_for(asset, session.batchSize).model_dump()
    save_session(session)
    return session


def reextract_transparency(
    candidate_id: str,
    project_id: str | None = None,
    asset_type: AssetType | None = None,
    asset_id: str | None = None,
) -> AssetLabSession:
    project_id, asset_type, asset_id = resolve_selection(project_id, asset_type, asset_id)
    asset = get_asset(project_id, asset_type, asset_id)
    if not expects_isolated_output(asset):
        raise ValueError("Transparent extraction is not required for this asset type.")
    session = load_session(project_id, asset_type, asset_id)
    chosen = next((item for item in session.candidates if item.id == candidate_id), None)
    if chosen is None:
        raise KeyError(f"Unknown candidate {candidate_id}")
    source = _resolve_raw_path(asset, chosen)
    if not source.is_file():
        raise FileNotFoundError(f"Candidate image missing: {source}")
    _apply_output_artifacts(asset, chosen, source, force_extract=True)
    if session.accepted and session.accepted.id == candidate_id:
        session.accepted = chosen
    save_session(session)
    return session


def flag_extraction(
    candidate_id: str,
    project_id: str | None = None,
    asset_type: AssetType | None = None,
    asset_id: str | None = None,
    payload: AssetLabExtractFlagRequest | None = None,
) -> AssetLabSession:
    project_id, asset_type, asset_id = resolve_selection(project_id, asset_type, asset_id)
    asset = get_asset(project_id, asset_type, asset_id)
    session = load_session(project_id, asset_type, asset_id)
    chosen = next((item for item in session.candidates if item.id == candidate_id), None)
    if chosen is None:
        raise KeyError(f"Unknown candidate {candidate_id}")
    body = payload or AssetLabExtractFlagRequest()
    if chosen.extraction is None:
        chosen.extraction = ExtractionMetadata()
    chosen.extraction.flaggedIncorrect = True
    issues = list(chosen.extraction.issues)
    labels = issue_labels(issues) or ["extraction flagged incorrect"]
    write_learning_record(
        LearningRecord(
            id=f"{chosen.id}-extraction-{uuid4().hex[:6]}",
            createdAt=_now(),
            projectId=asset.projectId,
            assetType=asset.assetType,
            assetId=asset.assetId,
            state=asset.state,
            direction=asset.direction,
            seed=chosen.seed,
            modelId=chosen.modelId or asset.generation.modelId,
            provider="isolated-asset-lab",
            decision="rejected",
            rejectionReasons=["subject cut off by alpha mask", *labels],
            automaticRejectionReasons=[],
            manualRejectionReasons=["extraction flagged incorrect", *labels],
            manualNote=body.note.strip(),
            candidatePath=chosen.isolatedPath or chosen.path,
            sha256=chosen.sha256,
            feedbackChannel="extraction",
            validationResults={"channel": "extraction", "issues": issues, "quality": chosen.extraction.quality},
        )
    )
    if session.accepted and session.accepted.id == candidate_id:
        session.accepted = chosen
    save_session(session)
    return session

