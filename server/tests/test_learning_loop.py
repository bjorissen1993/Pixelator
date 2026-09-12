"""Learning Loop V1 isolation and policy tests. No GPU, no weight training."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domain.catalog import get_asset
from learning.context import LearningContext, record_matches
from learning.policy import DEFAULT_POLICY, confidence_for
from learning.recipes import build_next_recipe, plan_candidate_recipes
from learning.resolver import apply_controls, resolve_learning
from learning.scoring import recipe_fingerprint, recipe_score, score_recipes
from learning.signals import collect_signals, tokens_from_reason
from models.catalog import LearningRecord
from models.learning import GenerationRecipe, LearningControls, LearningPolicy, RecipeAdjustment


def record(
    *,
    record_id: str,
    project: str,
    asset_type: str,
    asset_id: str,
    decision: str,
    reasons: list[str] | None = None,
    scope: str = "asset",
    guidance: float = 7.5,
    steps: int = 30,
    reference_strength: float | None = None,
    fingerprint: str = "",
    rating: int | None = None,
    created: str = "2026-09-12T00:00:00+00:00",
    state: str | None = None,
    seed: int = 1,
    valid: bool = False,
) -> LearningRecord:
    return LearningRecord(
        id=record_id,
        createdAt=created,
        projectId=project,
        assetType=asset_type,  # type: ignore[arg-type]
        assetId=asset_id,
        state=state,
        decision=decision,  # type: ignore[arg-type]
        rejectionReasons=reasons or [],
        scope=scope,  # type: ignore[arg-type]
        modelSettings={"guidance": guidance, "steps": steps},
        referenceStrength=reference_strength,
        recipeFingerprint=fingerprint,
        manualRating=rating,
        seed=seed,
        validationResults={"ok": valid, "validForBase": valid},
    )


class LearningLoopTests(unittest.TestCase):
    def test_tokens_come_from_recorded_reasons_only(self):
        tokens = tokens_from_reason("Rejected: armor or shoulder pieces are visible")
        self.assertIn("armor", tokens)
        self.assertNotIn("rejected", tokens)

    def test_one_rejection_is_record_only(self):
        policy = DEFAULT_POLICY
        confidence, apply, band = confidence_for(1, 1.0, policy)
        self.assertEqual(band, "record")
        self.assertFalse(apply)
        self.assertEqual(confidence, 0.0)

    def test_three_decisions_are_suggestions(self):
        confidence, apply, band = confidence_for(3, 1.0, DEFAULT_POLICY)
        self.assertEqual(band, "suggest")
        self.assertFalse(apply)
        self.assertGreater(confidence, 0)

    def test_four_decisions_may_apply(self):
        _confidence, apply, band = confidence_for(4, 1.0, DEFAULT_POLICY)
        self.assertEqual(band, "apply")
        self.assertTrue(apply)

    def test_berwynn_armor_does_not_leak(self):
        records = [
            record(
                record_id=f"berwynn-armor-{index}",
                project="chimera",
                asset_type="character",
                asset_id="berwynn",
                decision="rejected",
                reasons=["Rejected: armor or shoulder pieces are visible"],
                state="idle",
            )
            for index in range(6)
        ]
        records.extend(
            [
                record(
                    record_id=f"trophy-{index}",
                    project="chimera",
                    asset_type="item",
                    asset_id="old-fishing-trophy",
                    decision="rejected",
                    reasons=["Rejected: subject is not isolated"],
                )
                for index in range(6)
            ]
        )
        records.extend(
            [
                record(
                    record_id=f"tile-{index}",
                    project="chimera",
                    asset_type="tile",
                    asset_id="mossy-stone-floor",
                    decision="accepted",
                    reasons=[],
                    valid=True,
                )
                for index in range(2)
            ]
        )
        records.extend(
            [
                record(
                    record_id=f"vfx-{index}",
                    project="another-game",
                    asset_type="vfx",
                    asset_id="fireball-impact",
                    decision="rejected",
                    reasons=["Rejected: burst is unreadable"],
                    scope="asset",
                )
                for index in range(6)
            ]
        )
        records.append(
            record(
                record_id="chimera-sat-1",
                project="chimera",
                asset_type="character",
                asset_id="style",
                decision="accepted",
                reasons=[],
                scope="project",
                guidance=6.5,
                valid=True,
            )
        )
        for index in range(4):
            records.append(
                record(
                    record_id=f"chimera-sat-{index + 2}",
                    project="chimera",
                    asset_type="item",
                    asset_id="style",
                    decision="accepted",
                    reasons=[],
                    scope="project",
                    guidance=6.5,
                    valid=True,
                )
            )
        for index in range(5):
            records.append(
                record(
                    record_id=f"global-bg-{index}",
                    project="none",
                    asset_type="character",
                    asset_id="none",
                    decision="rejected",
                    reasons=["Rejected: background is busy"],
                    scope="global",
                )
            )

        berwynn = resolve_learning(get_asset("chimera", "character", "berwynn"), records)
        trophy = resolve_learning(get_asset("chimera", "item", "old-fishing-trophy"), records)
        tile = resolve_learning(get_asset("chimera", "tile", "mossy-stone-floor"), records)
        vfx = resolve_learning(get_asset("another-game", "vfx", "fireball-impact"), records)

        berwynn_vals = {str(item.value).lower() for item in berwynn.recommendations}
        trophy_vals = {str(item.value).lower() for item in trophy.recommendations}
        tile_vals = {str(item.value).lower() for item in tile.recommendations}
        vfx_vals = {str(item.value).lower() for item in vfx.recommendations}

        self.assertIn("armor", berwynn_vals)
        self.assertNotIn("armor", trophy_vals)
        self.assertNotIn("armor", tile_vals)
        self.assertNotIn("armor", vfx_vals)
        self.assertIn("isolated", trophy_vals)
        self.assertNotIn("isolated", tile_vals)
        self.assertNotIn("isolated", berwynn_vals)
        self.assertIn("background", berwynn_vals)
        self.assertIn("background", vfx_vals)
        self.assertTrue(any(item.kind == "guidance" and item.sourceScope == "project" for item in berwynn.recommendations))
        self.assertFalse(any(item.kind == "guidance" and item.sourceScope == "project" for item in vfx.recommendations))
        self.assertTrue(any(item.sourceScope == "global" and str(item.value) == "background" for item in vfx.recommendations))

    def test_specificity_prefers_asset_over_type(self):
        records = [
            record(
                record_id="type-armor",
                project="chimera",
                asset_type="character",
                asset_id="other",
                decision="rejected",
                reasons=["Rejected: armor"],
                scope="asset_type",
            )
            for _ in range(6)
        ]
        records.extend(
            [
                record(
                    record_id=f"asset-crop-{index}",
                    project="chimera",
                    asset_type="character",
                    asset_id="berwynn",
                    decision="rejected",
                    reasons=["Rejected: subject is cropped"],
                )
                for index in range(6)
            ]
        )
        found = collect_signals(
            LearningContext("chimera", "character", "berwynn", "idle", "S"),
            records,
            DEFAULT_POLICY,
        )
        armor = next(item for item in found if str(item.value) == "armor")
        crop = next(item for item in found if str(item.value) == "cropped")
        self.assertEqual(armor.sourceScope, "asset_type")
        self.assertEqual(crop.sourceScope, "asset")

    def test_asset_records_do_not_match_global_scope(self):
        item = record(
            record_id="only-asset",
            project="chimera",
            asset_type="character",
            asset_id="berwynn",
            decision="rejected",
            reasons=["Rejected: armor"],
        )
        context = LearningContext("chimera", "character", "berwynn")
        self.assertTrue(record_matches(item, context, "asset"))
        self.assertFalse(record_matches(item, context, "global"))
        self.assertFalse(record_matches(item, context, "project"))
        self.assertFalse(record_matches(item, context, "asset_type"))

    def test_seed_is_not_in_fingerprint(self):
        first = GenerationRecipe(modelId="m", guidance=7.5, steps=30, seed=11)
        second = GenerationRecipe(modelId="m", guidance=7.5, steps=30, seed=99)
        self.assertEqual(recipe_fingerprint(first), recipe_fingerprint(second))

    def test_recipe_score_is_transparent_and_smoothed(self):
        weak = recipe_score(1, 0, 1, 0, 0)
        strong = recipe_score(8, 1, 8, 20, 4)
        self.assertLess(weak, 0.7)
        self.assertGreater(strong, weak)

    def test_score_recipes_groups_by_fingerprint(self):
        records = [
            record(record_id="a1", project="chimera", asset_type="item", asset_id="old-fishing-trophy", decision="accepted", fingerprint="aaa", valid=True),
            record(record_id="a2", project="chimera", asset_type="item", asset_id="old-fishing-trophy", decision="rejected", fingerprint="aaa", reasons=["x"]),
            record(record_id="b1", project="chimera", asset_type="item", asset_id="old-fishing-trophy", decision="accepted", fingerprint="bbb", valid=True, rating=5),
        ]
        scores = {item.fingerprint: item for item in score_recipes(records)}
        self.assertEqual(scores["aaa"].attempts, 2)
        self.assertEqual(scores["aaa"].accepts, 1)
        self.assertEqual(scores["bbb"].averageRating, 5)

    def test_exploration_stays_bounded(self):
        asset = get_asset("chimera", "character", "berwynn")
        policy = LearningPolicy(exploitRatio=0.75, exploreGuidanceDelta=0.5, exploreStepsDelta=2)
        planned = plan_candidate_recipes(asset, [], policy, 4)
        self.assertEqual([item.mode for item in planned], ["exploit", "exploit", "exploit", "explore"])
        explore = planned[-1]
        exploit = planned[0]
        self.assertAlmostEqual(explore.guidance - exploit.guidance, 0.5)
        self.assertEqual(explore.steps - exploit.steps, 2)
        self.assertLessEqual(explore.guidance, policy.maxGuidance)
        self.assertGreaterEqual(explore.guidance, policy.minGuidance)
        self.assertNotEqual(exploit.modelId, "")
        self.assertEqual(explore.modelId, exploit.modelId)

    def test_prompt_fragments_keep_identity_and_provenance(self):
        asset = get_asset("chimera", "character", "berwynn")
        rec = RecipeAdjustment(
            id="neg:armor@asset:chimera/character/berwynn",
            kind="negative_fragment",
            value="armor",
            sourceScope="asset",
            source="asset:chimera/character/berwynn",
            confidence=0.84,
            accepted=1,
            rejected=7,
            evidence=7,
            applied=True,
            explanation="Added negative fragment 'armor' because 7 asset:chimera/character/berwynn candidates were rejected for recorded reasons mentioning it.",
        )
        recipe = build_next_recipe(asset, [rec], DEFAULT_POLICY)
        self.assertIn(asset.generation.prompt, recipe.prompt)
        self.assertIn("armor", recipe.negativePrompt)
        self.assertTrue(any(item.source.endswith("berwynn") for item in recipe.adjustments))
        self.assertIn("armor", " ".join(recipe.why))

    def test_pinned_settings_cannot_be_overridden(self):
        asset = get_asset("chimera", "character", "berwynn")
        rec = RecipeAdjustment(
            id="set:guidance@asset:x",
            kind="guidance",
            value=10.0,
            sourceScope="asset",
            source="asset:x",
            confidence=0.9,
            evidence=8,
            applied=True,
        )
        controls = LearningControls(pinnedSettings={"guidance": 7.5})
        applied = apply_controls([rec], controls)
        recipe = build_next_recipe(asset, applied, DEFAULT_POLICY, controls)
        self.assertEqual(recipe.guidance, 7.5)
        self.assertTrue(applied[0].pinned)
        self.assertFalse(applied[0].applied)

    def test_disabled_recommendations_stay_disabled(self):
        asset = get_asset("chimera", "item", "old-fishing-trophy")
        rec = RecipeAdjustment(
            id="neg:isolated@asset:x",
            kind="negative_fragment",
            value="isolated",
            sourceScope="asset",
            source="asset:x",
            confidence=0.8,
            evidence=6,
            applied=True,
        )
        controls = LearningControls(disabledIds=["neg:isolated@asset:x"])
        applied = apply_controls([rec], controls)
        recipe = build_next_recipe(asset, applied, DEFAULT_POLICY, controls)
        self.assertTrue(applied[0].disabled)
        self.assertNotIn("isolated", recipe.negativePrompt)

    def test_reset_marker_ignores_old_asset_evidence(self):
        records = [
            record(
                record_id=f"old-{index}",
                project="chimera",
                asset_type="character",
                asset_id="berwynn",
                decision="rejected",
                reasons=["Rejected: armor"],
                created="2026-01-01T00:00:00+00:00",
            )
            for index in range(6)
        ]
        controls = LearningControls(resetAfter={"asset": "2026-06-01T00:00:00+00:00"})
        snapshot = resolve_learning(get_asset("chimera", "character", "berwynn"), records, controls)
        self.assertFalse(any(str(item.value) == "armor" for item in snapshot.recommendations))


if __name__ == "__main__":
    unittest.main()
