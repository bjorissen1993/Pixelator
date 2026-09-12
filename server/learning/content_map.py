"""Explicit content-reason → prompt fragment registry.

Quality review labels never appear here. Unmapped text is ignored.
"""

from __future__ import annotations

from dataclasses import dataclass


QUALITY_PROMPT_STOPWORDS = {
    "pixel",
    "readability",
    "technical",
    "quality",
    "proportions",
    "silhouette",
    "poor",
    "transparency",
    "extraction",
    "blurry",
}

QUALITY_REASON_PHRASES = (
    "poor technical quality",
    "poor pixel readability",
    "poor silhouette",
    "poor proportions",
    "transparency extraction failed",
    "wrong silhouette",
    "style mismatch",
    "unreadable at this size",
)


@dataclass(frozen=True)
class ContentPromptRule:
    id: str
    aliases: tuple[str, ...]
    negative: tuple[str, ...]
    scope: str = "asset"


CONTENT_PROMPT_RULES = (
    ContentPromptRule(
        id="visible_legs",
        aliases=("visible legs", "legs are visible", "no_visible_legs"),
        negative=("legs", "boots"),
        scope="asset",
    ),
    ContentPromptRule(
        id="armor_shoulder",
        aliases=("armor / shoulder armor", "armor or shoulder pieces", "no_armor", "rejected: armor"),
        negative=("armor", "shoulder armor"),
        scope="asset",
    ),
    ContentPromptRule(
        id="missing_spectral_tail",
        aliases=("missing spectral lower body / ghost tail", "spectral lower body / ghost tail is missing"),
        negative=("ghost tail",),
        scope="asset",
    ),
    ContentPromptRule(
        id="multiple_subjects",
        aliases=("multiple subjects", "more than one subject", "multiple characters"),
        negative=("multiple characters",),
        scope="global",
    ),
    ContentPromptRule(
        id="busy_background",
        aliases=("busy background", "background is busy"),
        negative=("busy background",),
        scope="global",
    ),
    ContentPromptRule(
        id="cropped_not_full_body",
        aliases=("cropped / not full body", "subject is cropped", "silhouette is not full body", "cropped body"),
        negative=("cropped body",),
        scope="global",
    ),
    ContentPromptRule(
        id="not_isolated",
        aliases=("subject is not isolated", "not isolated"),
        negative=("extra objects",),
        scope="asset",
    ),
    ContentPromptRule(
        id="wrong_clothing",
        aliases=("wrong clothing",),
        negative=("wrong clothing",),
        scope="asset",
    ),
    ContentPromptRule(
        id="weapon",
        aliases=("weapon", "staff"),
        negative=("weapon",),
        scope="asset",
    ),
)


def is_quality_reason_text(text: str) -> bool:
    lowered = text.lower().strip()
    return any(phrase in lowered for phrase in QUALITY_REASON_PHRASES)


def is_banned_quality_fragment(value: str) -> bool:
    token = value.lower().strip()
    return token in QUALITY_PROMPT_STOPWORDS or any(word in QUALITY_PROMPT_STOPWORDS for word in token.split())


def fragments_for_reason(text: str) -> list[str]:
    if not text or is_quality_reason_text(text):
        return []
    lowered = text.lower().strip()
    matched: list[str] = []
    for rule in CONTENT_PROMPT_RULES:
        aliases = (rule.id, *rule.aliases)
        if any(alias in lowered for alias in aliases):
            for fragment in rule.negative:
                if fragment not in matched and not is_banned_quality_fragment(fragment):
                    matched.append(fragment)
    return matched


def fragments_for_reasons(reasons: list[str]) -> list[str]:
    found: list[str] = []
    for reason in reasons:
        for fragment in fragments_for_reason(reason):
            if fragment not in found:
                found.append(fragment)
    return found
