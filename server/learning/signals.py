"""Derive learning signals only from recorded fields. No invented semantics."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from models.catalog import LearningRecord
from models.learning import LearningPolicy, RecipeAdjustment
from learning.context import LearningContext, SCOPE_WEIGHT, record_matches
from learning.policy import confidence_for
from models.learning import LearningScope

STOPWORDS = {
    "rejected",
    "visible",
    "pieces",
    "because",
    "this",
    "asset",
    "needs",
    "are",
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "not",
    "was",
    "were",
    "than",
    "more",
    "one",
    "appears",
    "or",
    "of",
    "to",
    "a",
    "an",
    "is",
    "in",
    "on",
    "at",
    "by",
    "as",
    "it",
    "be",
    "instead",
    "manual",
    "architecture",
    "audit",
}

TOKEN_RE = re.compile(r"[a-z][a-z\-']{2,}")


def tokens_from_reason(reason: str) -> list[str]:
    words = TOKEN_RE.findall(reason.lower())
    return [word for word in words if word not in STOPWORDS]


def _records_for(scope: LearningScope, context: LearningContext, records: list[LearningRecord]) -> list[LearningRecord]:
    return [item for item in records if record_matches(item, context, scope)]


def _fragment_signals(
    scope: LearningScope,
    context: LearningContext,
    records: list[LearningRecord],
    policy: LearningPolicy,
) -> list[RecipeAdjustment]:
    scoped = _records_for(scope, context, records)
    rejected = [item for item in scoped if item.decision == "rejected"]
    accepted = [item for item in scoped if item.decision == "accepted"]
    counts: Counter[str] = Counter()
    accepted_counts: Counter[str] = Counter()
    for item in rejected:
        for token in {token for reason in item.rejectionReasons for token in tokens_from_reason(reason)}:
            counts[token] += 1
    for item in accepted:
        for token in {token for reason in item.rejectionReasons for token in tokens_from_reason(reason)}:
            accepted_counts[token] += 1
    adjustments: list[RecipeAdjustment] = []
    source = context.source_label(scope)
    for token, rejected_n in counts.most_common(12):
        accepted_n = accepted_counts.get(token, 0)
        evidence = rejected_n
        consistency = rejected_n / max(1, rejected_n + accepted_n)
        confidence, may_apply, band = confidence_for(evidence, consistency, policy)
        if evidence < policy.minRecordOnly:
            continue
        adjustments.append(
            RecipeAdjustment(
                id=f"neg:{token}@{source}",
                kind="negative_fragment",
                value=token,
                sourceScope=scope,
                source=source,
                confidence=confidence,
                accepted=accepted_n,
                rejected=rejected_n,
                evidence=evidence,
                applied=may_apply,
                explanation=(
                    f"Added negative fragment '{token}' because {rejected_n} "
                    f"{source} candidates were rejected for recorded reasons mentioning it."
                ),
            )
        )
        if band == "record":
            adjustments[-1].applied = False
    return adjustments


def _numeric_signals(
    scope: LearningScope,
    context: LearningContext,
    records: list[LearningRecord],
    policy: LearningPolicy,
    key: str,
    kind: str,
) -> list[RecipeAdjustment]:
    scoped = _records_for(scope, context, records)
    accepted_values: list[float] = []
    rejected_values: list[float] = []
    for item in scoped:
        raw = item.modelSettings.get(key)
        if raw is None and key == "referenceStrength":
            raw = item.referenceStrength
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if item.decision == "accepted":
            accepted_values.append(value)
        else:
            rejected_values.append(value)
    if len(accepted_values) < policy.minSuggest:
        return []
    accepted_values.sort()
    median = accepted_values[len(accepted_values) // 2]
    evidence = len(accepted_values)
    consistency = len(accepted_values) / max(1, len(accepted_values) + len(rejected_values))
    confidence, may_apply, _band = confidence_for(evidence, consistency, policy)
    source = context.source_label(scope)
    pretty = "reference strength" if key == "referenceStrength" else key
    return [
        RecipeAdjustment(
            id=f"set:{key}@{source}",
            kind=kind,  # type: ignore[arg-type]
            value=round(median, 3),
            sourceScope=scope,
            source=source,
            confidence=confidence,
            accepted=len(accepted_values),
            rejected=len(rejected_values),
            evidence=evidence,
            applied=may_apply,
            explanation=(
                f"{pretty.capitalize()} moved toward {median:g} because {evidence} accepted "
                f"{source} candidates performed better around that setting."
            ),
        )
    ]


def collect_signals(
    context: LearningContext,
    records: list[LearningRecord],
    policy: LearningPolicy,
) -> list[RecipeAdjustment]:
    scopes: list[LearningScope] = ["global", "project", "asset_type", "asset"]
    if context.state or context.direction:
        scopes.append("state")
    found: list[RecipeAdjustment] = []
    for scope in scopes:
        found.extend(_fragment_signals(scope, context, records, policy))
        found.extend(_numeric_signals(scope, context, records, policy, "guidance", "guidance"))
        found.extend(_numeric_signals(scope, context, records, policy, "steps", "steps"))
        found.extend(_numeric_signals(scope, context, records, policy, "referenceStrength", "reference_strength"))
    return _prefer_specific(found)


def _prefer_specific(items: list[RecipeAdjustment]) -> list[RecipeAdjustment]:
    """More specific scope wins for the same kind+value. Asset evidence never becomes global."""
    best: dict[tuple[str, str], RecipeAdjustment] = {}
    for item in items:
        key = (item.kind, str(item.value).lower())
        current = best.get(key)
        if current is None or SCOPE_WEIGHT[item.sourceScope] > SCOPE_WEIGHT[current.sourceScope]:
            best[key] = item
    return list(best.values())
