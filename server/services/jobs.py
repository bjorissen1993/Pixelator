import logging
import threading
from datetime import datetime, timezone
from uuid import uuid4

from models.generation import GenerationJob
from services.errors import error_payload

logger = logging.getLogger("pixelator.jobs")

_lock = threading.Lock()
_jobs: dict[str, GenerationJob] = {}
_results: dict[str, dict] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create(character_id: str, operation: str, label: str, total: int | None = None) -> GenerationJob:
    job = GenerationJob(
        id=uuid4().hex,
        characterId=character_id,
        operation=operation,
        status="queued",
        label=label,
        current=0,
        total=total,
        currentItem="",
        createdAt=utc_now(),
        updatedAt=utc_now(),
    )
    with _lock:
        _jobs[job.id] = job
    return job


def update(job_id: str, **fields) -> GenerationJob | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        data = job.model_dump()
        data.update(fields)
        data["updatedAt"] = utc_now()
        job = GenerationJob(**data)
        _jobs[job.id] = job
        return job


def set_progress(job_id: str, current: int, total: int | None, item: str, status: str = "generating") -> None:
    update(job_id, current=current, total=total, currentItem=item, status=status)


def complete(job_id: str, result: dict, used_reference: bool = False) -> None:
    with _lock:
        _results[job_id] = result
    update(job_id, status="completed", usedReference=used_reference, currentItem="done")


def fail(job_id: str, error: str, details: str = "", trace_id: str = "") -> None:
    logger.error("job failed id=%s error=%s\n%s", job_id, error, details)
    update(job_id, status="failed", error=error, errorDetails=details, traceId=trace_id)


def get(job_id: str) -> GenerationJob | None:
    with _lock:
        return _jobs.get(job_id)


def result(job_id: str) -> dict | None:
    with _lock:
        return _results.get(job_id)


def for_character(character_id: str) -> list[GenerationJob]:
    with _lock:
        jobs = [job for job in _jobs.values() if job.characterId == character_id]
    return sorted(jobs, key=lambda job: job.updatedAt, reverse=True)


def active_for(character_id: str) -> GenerationJob | None:
    jobs = [
        job
        for job in for_character(character_id)
        if job.status in ("queued", "generating", "processing")
    ]
    return jobs[0] if jobs else None


def run_in_background(job: GenerationJob, fn) -> GenerationJob:
    def worker():
        update(job.id, status="generating")
        try:
            payload = fn(job)
            complete(job.id, payload, bool(payload.get("usedReference")))
        except Exception as exc:
            payload = error_payload(
                exc,
                context={"jobId": job.id, "characterId": job.characterId, "operation": job.operation},
            )
            fail(job.id, payload["message"], payload["details"], payload["traceId"])

    threading.Thread(target=worker, daemon=True).start()
    return job
