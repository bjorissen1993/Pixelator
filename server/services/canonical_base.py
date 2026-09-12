"""Isolated canonical Berwynn south-base creation. Not the production Studio engine."""

from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import config
from models.canonical_base import CanonicalBaseCandidate, CanonicalBaseSession
from processing.canonical_base_validation import validate_canonical_base

MODEL_TESTS_DIR = Path(__file__).resolve().parents[1] / "scripts" / "model_tests"
if str(MODEL_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_TESTS_DIR))

from helpers import (  # noqa: E402
    assert_clip_prompt_budget,
    assert_exact_model,
    load_text2image_pipeline,
    sha256_file,
)

MODEL_ID = "PublicPrompts/All-In-One-Pixel-Model"
WIDTH = 512
HEIGHT = 512
STEPS = 30
GUIDANCE = 7.5
PROMPT = (
    "pixelsprite, full body elderly male spirit, front facing, grey hair, thick grey beard, "
    "worn dark village tunic, faded mantle, spectral ghost tail instead of legs, "
    "no armor, no weapons, centered, plain background"
)
NEGATIVE_PROMPT = (
    "legs, boots, armor, helmet, shoulder pads, weapon, staff, portrait, cropped, "
    "multiple characters, spritesheet, busy background, realistic, 3d, text"
)

REVIEW_ROOT = config.DATA_DIR / "test_review" / "berwynn"
CANDIDATE_DIR = REVIEW_ROOT / "candidates"
ACCEPTED_DIR = REVIEW_ROOT / "accepted"
SESSION_PATH = REVIEW_ROOT / "session.json"
ACCEPTED_PATH = ACCEPTED_DIR / "canonical.png"

_pipe_lock = threading.Lock()
_pipe = None
_loaded_id = ""


def accepted_canonical_path() -> Path:
    return ACCEPTED_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)


def _empty_session() -> CanonicalBaseSession:
    return CanonicalBaseSession(
        modelId=MODEL_ID,
        prompt=PROMPT,
        negativePrompt=NEGATIVE_PROMPT,
        directionGenerationUnlocked=False,
        usingCurrentDirectionSet=False,
        notes=[
            "This isolated flow creates a canonical south-facing Berwynn base only.",
            "Current Studio / direction-set images are not used as identity.",
            "IP-Adapter unlocks only after one valid base is accepted.",
            "Direction generation stays locked.",
        ],
    )


def _refresh_candidate(item: CanonicalBaseCandidate) -> CanonicalBaseCandidate:
    from PIL import Image

    source = config.DATA_DIR / item.path
    if item.status == "accepted":
        source = ACCEPTED_PATH if ACCEPTED_PATH.is_file() else source
    if not source.is_file():
        return item
    validation, reasons, _busy = validate_canonical_base(Image.open(source))
    item.validation = validation
    item.rejectReasons = reasons
    item.valid = not reasons
    item.sha256 = sha256_file(source)
    return item


def load_session() -> CanonicalBaseSession:
    _ensure_dirs()
    if not SESSION_PATH.is_file():
        session = _empty_session()
        save_session(session)
        return session
    payload = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    session = CanonicalBaseSession.model_validate(payload)
    session.candidates = [_refresh_candidate(item) for item in session.candidates]
    if session.accepted:
        session.accepted = _refresh_candidate(session.accepted)
        session.ipAdapterUnlocked = bool(session.accepted.valid and session.accepted.status == "accepted")
    session.directionGenerationUnlocked = False
    session.usingCurrentDirectionSet = False
    return session


def save_session(session: CanonicalBaseSession) -> None:
    _ensure_dirs()
    SESSION_PATH.write_text(session.model_dump_json(indent=2), encoding="utf-8")


def _public_path(path: Path) -> str:
    return path.resolve().relative_to(config.DATA_DIR.resolve()).as_posix()


def _load_pipe():
    global _pipe, _loaded_id
    with _pipe_lock:
        if _pipe is not None:
            return _pipe, _loaded_id
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("Hard fail: CUDA is unavailable for the canonical Berwynn base test.")
        dtype = torch.float16
        pipe = load_text2image_pipeline(MODEL_ID, dtype, allow_sdxl=False)
        loaded = assert_exact_model(pipe, MODEL_ID, allow_sdxl=False)
        pipe = pipe.to("cuda")
        if hasattr(pipe, "set_progress_bar_config"):
            pipe.set_progress_bar_config(disable=False)
        assert_clip_prompt_budget(pipe, PROMPT, NEGATIVE_PROMPT)
        _pipe = pipe
        _loaded_id = loaded
        return _pipe, _loaded_id


def generate_candidates(count: int = 4) -> CanonicalBaseSession:
    import torch
    from PIL import Image

    count = max(1, min(4, int(count)))
    pipe, loaded_id = _load_pipe()
    session = load_session()
    session.modelId = loaded_id or MODEL_ID
    session.prompt = PROMPT
    session.negativePrompt = NEGATIVE_PROMPT
    session.directionGenerationUnlocked = False
    session.usingCurrentDirectionSet = False

    for _ in range(count):
        seed = int(time.time() * 1000) % 1_000_000_000 + uuid4().int % 90_000
        candidate_id = uuid4().hex[:10]
        dest = CANDIDATE_DIR / f"{candidate_id}.png"
        generator = torch.Generator(device="cuda").manual_seed(seed)
        image = pipe(
            prompt=PROMPT,
            negative_prompt=NEGATIVE_PROMPT,
            width=WIDTH,
            height=HEIGHT,
            num_inference_steps=STEPS,
            guidance_scale=GUIDANCE,
            generator=generator,
        ).images[0]
        image.save(dest)
        validation, reasons, _busy = validate_canonical_base(Image.open(dest))
        session.candidates.insert(
            0,
            CanonicalBaseCandidate(
                id=candidate_id,
                seed=seed,
                path=_public_path(dest),
                createdAt=_now(),
                status="pending",
                sha256=sha256_file(dest),
                rejectReasons=reasons,
                valid=not reasons,
                validation=validation,
            ),
        )
    save_session(session)
    return session


def accept_candidate(candidate_id: str) -> CanonicalBaseSession:
    from PIL import Image

    session = load_session()
    chosen = next((item for item in session.candidates if item.id == candidate_id), None)
    if chosen is None:
        raise KeyError(f"Unknown canonical candidate {candidate_id}")
    if chosen.rejectReasons or not chosen.valid:
        raise ValueError("Hard fail: this candidate failed canonical Berwynn validation.")
    source = config.DATA_DIR / chosen.path
    if not source.is_file():
        raise FileNotFoundError(f"Candidate image missing: {source}")
    ACCEPTED_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(source)
    image.save(ACCEPTED_PATH)
    chosen.status = "accepted"
    chosen.path = _public_path(ACCEPTED_PATH)
    for item in session.candidates:
        if item.id != chosen.id and item.status == "accepted":
            item.status = "rejected"
    session.accepted = chosen
    session.ipAdapterUnlocked = True
    session.directionGenerationUnlocked = False
    session.usingCurrentDirectionSet = False
    save_session(session)
    return session


def reject_candidate(candidate_id: str) -> CanonicalBaseSession:
    session = load_session()
    chosen = next((item for item in session.candidates if item.id == candidate_id), None)
    if chosen is None:
        raise KeyError(f"Unknown canonical candidate {candidate_id}")
    chosen.status = "rejected"
    if session.accepted and session.accepted.id == candidate_id:
        session.accepted = None
        session.ipAdapterUnlocked = False
        if ACCEPTED_PATH.exists():
            ACCEPTED_PATH.unlink()
    session.directionGenerationUnlocked = False
    save_session(session)
    return session
