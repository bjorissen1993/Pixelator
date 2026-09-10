import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import config
from models.character import CharacterProfile, SpriteAsset
from models.enums import Direction, RejectionReason
from models.project import MemoryEntry, MemorySuggestions

_PATH = lambda: config.DATA_DIR / "project" / "memory.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[MemoryEntry]:
    path = _PATH()
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [MemoryEntry.model_validate(item) for item in raw]


def _save(entries: list[MemoryEntry]) -> None:
    path = _PATH()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([entry.model_dump() for entry in entries], indent=2), encoding="utf-8")


def record(
    character: CharacterProfile,
    kind: str,
    asset: SpriteAsset | None,
    state_name: str = "",
    direction: Direction | None = None,
    reason: RejectionReason | None = None,
    custom_reason: str = "",
    provider_id: str = "",
) -> MemoryEntry:
    entry = MemoryEntry(
        id=uuid4().hex,
        kind=kind,
        characterId=character.id,
        characterName=character.name,
        prompt=asset.prompt if asset else character.masterPrompt,
        negativePrompt=asset.negativePrompt if asset else character.negativePrompt,
        seed=asset.seed if asset else character.seed,
        outline=character.outline,
        shading=character.shading,
        detail=character.detail,
        camera=character.camera,
        palette=list(character.palette.colors),
        providerId=provider_id or (asset.providerId if asset else ""),
        stateName=state_name,
        direction=direction,
        rejectionReason=reason,
        customReason=custom_reason,
        assetPath=asset.path if asset else "",
        createdAt=utc_now(),
    )
    entries = _load()
    entries.append(entry)
    _save(entries[-400:])
    return entry


def list_entries(character_id: str | None = None, kind: str | None = None) -> list[MemoryEntry]:
    entries = _load()
    if character_id:
        entries = [entry for entry in entries if entry.characterId == character_id]
    if kind:
        entries = [entry for entry in entries if entry.kind == kind]
    return list(reversed(entries))


def suggestions(character_id: str | None = None) -> MemorySuggestions:
    accepted = list_entries(character_id, "accepted")
    rejected = list_entries(character_id, "rejected")
    seeds = [entry.seed for entry in accepted if entry.seed is not None][:8]
    palettes = [entry.palette for entry in accepted if entry.palette][:5]
    fragments = []
    for entry in accepted[:12]:
        for part in entry.prompt.split(","):
            text = part.strip()
            if 12 < len(text) < 80 and text not in fragments:
                fragments.append(text)
            if len(fragments) >= 8:
                break
    notes = [
        "This memory ranks accepted settings. It does not train or fine-tune the image model.",
    ]
    if rejected:
        reasons = {entry.rejectionReason for entry in rejected if entry.rejectionReason}
        if reasons:
            notes.append("Frequent rejection themes: " + ", ".join(sorted(str(item) for item in reasons if item)))
    return MemorySuggestions(
        recommendedSeeds=seeds,
        recommendedPalettes=palettes,
        promptFragments=fragments[:8],
        defaultOutline=accepted[0].outline if accepted else None,
        defaultShading=accepted[0].shading if accepted else None,
        defaultDetail=accepted[0].detail if accepted else None,
        notes=notes,
    )


def generation_hints(character_id: str, direction: Direction | None = None) -> dict:
    rejected = [entry for entry in list_entries(character_id, "rejected") if direction is None or entry.direction == direction]
    recent = rejected[:8]
    strength_delta = 0.0
    extras: list[str] = []
    last_reason = recent[0].rejectionReason if recent else None
    for entry in recent:
        reason = entry.rejectionReason
        if reason == "wrong_identity":
            strength_delta -= 0.08
            extras.append("match the accepted identity more closely, same face, same beard, same silhouette")
        elif reason == "wrong_direction":
            strength_delta += 0.08
            extras.append("correct compass facing for the requested direction")
        elif reason == "wrong_clothing":
            extras.append("same clothing and tunic as the accepted base, do not change outfit")
        elif reason == "wrong_spirit_form":
            extras.append("no legs, no boots, spectral lower body, preserve spirit form")
        elif reason in ("wrong_proportions", "wrong_body_shape"):
            strength_delta -= 0.05
            extras.append("same body proportions and height as the accepted base")
        elif reason == "poor_pixel_quality":
            extras.append("chunky 2D pixel clusters, hard edges, no blur, no anti-aliasing")
        elif reason == "wrong_colors":
            extras.append("quantize toward the accepted character palette")
        if entry.customReason:
            extras.append(entry.customReason.strip()[:120])
    unique: list[str] = []
    for item in extras:
        if item and item not in unique:
            unique.append(item)
    return {
        "strength_delta": max(-0.18, min(0.18, strength_delta)),
        "extra_clauses": unique[:6],
        "last_reason": last_reason,
    }
