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
from learning.policy import ALLOWED_BATCH_SIZES, DEFAULT_POLICY, confidence_for, parse_batch_size
from learning.recipes import allocate_batch, build_next_recipe, plan_candidate_recipes
from models.catalog import AssetLabGenerateRequest
from learning.resolver import apply_controls, resolve_learning
from learning.scoring import recipe_fingerprint, recipe_score, score_recipes
from learning.signals import collect_signals, split_rejection_reasons, tokens_from_reason
from models.catalog import LearningRecord
from processing.validators.review_reasons import reasons_for_asset, resolve_manual_reasons
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
    automatic: list[str] | None = None,
    manual: list[str] | None = None,
    validator_feedback: str | None = None,
    feedback_channel: str = "generation",
    review_mode: str = "standard",
) -> LearningRecord:
    automatic_reasons = automatic if automatic is not None else ([] if manual else reasons or [])
    manual_reasons = manual or []
    return LearningRecord(
        id=record_id,
        createdAt=created,
        projectId=project,
        assetType=asset_type,  # type: ignore[arg-type]
        assetId=asset_id,
        state=state,
        decision=decision,  # type: ignore[arg-type]
        rejectionReasons=[*(automatic_reasons or reasons or []), *manual_reasons],
        automaticRejectionReasons=automatic_reasons,
        manualRejectionReasons=manual_reasons,
        validatorFeedback=validator_feedback,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        modelSettings={"guidance": guidance, "steps": steps},
        referenceStrength=reference_strength,
        recipeFingerprint=fingerprint,
        manualRating=rating,
        seed=seed,
        validationResults={"ok": valid, "validForBase": valid},
        feedbackChannel=feedback_channel,  # type: ignore[arg-type]
        reviewMode=review_mode,  # type: ignore[arg-type]
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

    def test_recipe_score_is_weighted_normalized_rates(self):
        none = recipe_score(0, 0, 0, 0, 0)
        accept_only = recipe_score(1, 0, 0, 0, 0)
        accept_and_valid = recipe_score(1, 0, 1, 0, 0)
        strong = recipe_score(8, 1, 8, 20, 4)
        self.assertEqual(none, 0.0)
        self.assertAlmostEqual(accept_only, 0.6)
        self.assertAlmostEqual(accept_and_valid, 0.85)
        expected_strong = 0.6 * (8 / 9) + 0.25 * (8 / 9) + 0.15 * 1.0
        self.assertAlmostEqual(strong, round(expected_strong, 4))
        self.assertGreater(strong, accept_only)

    def test_recipe_scores_stay_in_unit_interval(self):
        cases = [
            (0, 0, 0, 0, 0),
            (10, 0, 10, 50, 10),
            (10, 0, 10, 0, 0),
            (10, 0, 100, 999, 10),
            (0, 10, 0, 0, 0),
            (3, 7, 2, 12, 4),
        ]
        for args in cases:
            score = recipe_score(*args)
            self.assertGreaterEqual(score, 0.0, args)
            self.assertLessEqual(score, 1.0, args)
        perfect = recipe_score(10, 0, 10, 50, 10)
        self.assertEqual(perfect, 1.0)
        inflated = LearningPolicy(scoreWeightAccept=3, scoreWeightValidator=1, scoreWeightRating=1)
        self.assertEqual(recipe_score(10, 0, 10, 50, 10, inflated), 1.0)

    def test_confidence_stays_in_unit_interval(self):
        default_strong, _apply, band = confidence_for(10, 1.0, DEFAULT_POLICY)
        self.assertEqual(band, "strong")
        self.assertEqual(default_strong, 0.85)
        overflow_consistency, _, _ = confidence_for(10, 2.0, DEFAULT_POLICY)
        self.assertEqual(overflow_consistency, 0.85)
        wild = LearningPolicy(suggestConfidence=2.0, applyConfidence=3.0, strongConfidence=4.0)
        overflow_band, _, _ = confidence_for(10, 1.0, wild)
        self.assertEqual(overflow_band, 1.0)
        for evidence in range(0, 12):
            for consistency in (0.0, 0.5, 1.0, 1.5, 2.0):
                confidence, _, _ = confidence_for(evidence, consistency, DEFAULT_POLICY)
                self.assertGreaterEqual(confidence, 0.0)
                self.assertLessEqual(confidence, 1.0)
                wild_confidence, _, _ = confidence_for(evidence, consistency, wild)
                self.assertGreaterEqual(wild_confidence, 0.0)
                self.assertLessEqual(wild_confidence, 1.0)

    def test_batch_allocation_reports_requested_vs_actual(self):
        self.assertEqual(allocate_batch(4, 0.8), (3, 1))
        self.assertEqual(allocate_batch(5, 0.8), (4, 1))
        self.assertEqual(allocate_batch(8, 0.8), (6, 2))
        self.assertEqual(allocate_batch(10, 0.8), (8, 2))
        self.assertEqual(allocate_batch(12, 0.8), (10, 2))
        self.assertEqual(allocate_batch(20, 0.8), (16, 4))
        self.assertEqual(allocate_batch(0, 0.8), (0, 0))
        snapshot = resolve_learning(get_asset("chimera", "character", "berwynn"), [])
        self.assertAlmostEqual(snapshot.requestedExploitRatio, 0.8)
        self.assertAlmostEqual(snapshot.requestedExploreRatio, 0.2)
        self.assertAlmostEqual(snapshot.exploitRatio, 0.8)
        self.assertEqual(snapshot.allocationBatchSize, 4)
        self.assertEqual(snapshot.allocatedExploit, 3)
        self.assertEqual(snapshot.allocatedExplore, 1)
        self.assertAlmostEqual(snapshot.allocatedExploitRatio, 0.75)
        self.assertAlmostEqual(snapshot.allocatedExploreRatio, 0.25)
        for size, exploit, explore in ((8, 6, 2), (12, 10, 2), (20, 16, 4)):
            sized = resolve_learning(get_asset("chimera", "character", "berwynn"), [], batch_size=size)
            self.assertEqual(sized.allocationBatchSize, size)
            self.assertEqual(sized.allocatedExploit, exploit)
            self.assertEqual(sized.allocatedExplore, explore)
            self.assertAlmostEqual(sized.requestedExploitRatio, 0.8)
            self.assertAlmostEqual(sized.requestedExploreRatio, 0.2)

    def test_asset_lab_batch_size_is_validated(self):
        self.assertEqual(tuple(ALLOWED_BATCH_SIZES), (4, 8, 12, 20))
        self.assertEqual(parse_batch_size(None), 4)
        for size in ALLOWED_BATCH_SIZES:
            self.assertEqual(parse_batch_size(size), size)
        with self.assertRaises(ValueError):
            parse_batch_size(5)
        with self.assertRaises(ValueError):
            parse_batch_size(16)
        self.assertEqual(AssetLabGenerateRequest(batchSize=12).resolved_batch_size(), 12)
        self.assertEqual(AssetLabGenerateRequest(count=8).resolved_batch_size(), 8)
        self.assertEqual(AssetLabGenerateRequest().resolved_batch_size(), 4)
        with self.assertRaises(ValueError):
            AssetLabGenerateRequest(batchSize=3).resolved_batch_size()
        planned = plan_candidate_recipes(get_asset("chimera", "character", "berwynn"), [], DEFAULT_POLICY, 12)
        self.assertEqual(len(planned), 12)
        self.assertEqual([item.mode for item in planned], ["exploit"] * 10 + ["explore"] * 2)

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

    def test_berwynn_manual_reasons_come_from_profile_not_global_registry(self):
        berwynn = get_asset("chimera", "character", "berwynn")
        trophy = get_asset("chimera", "item", "old-fishing-trophy")
        tile = get_asset("chimera", "tile", "mossy-stone-floor")
        vfx = get_asset("another-game", "vfx", "fireball-impact")
        berwynn_ids = {item.id for item in reasons_for_asset(berwynn)}
        trophy_ids = {item.id for item in reasons_for_asset(trophy)}
        tile_ids = {item.id for item in reasons_for_asset(tile)}
        vfx_ids = {item.id for item in reasons_for_asset(vfx)}
        for reason_id in ("visible_legs", "missing_spectral_tail", "armor_shoulder"):
            self.assertIn(reason_id, berwynn_ids)
            self.assertNotIn(reason_id, trophy_ids)
            self.assertNotIn(reason_id, tile_ids)
            self.assertNotIn(reason_id, vfx_ids)
        self.assertIn("wrong_hair_beard", berwynn_ids)
        self.assertNotIn("wrong_hair_beard", trophy_ids)
        self.assertIn("not_isolated", trophy_ids)
        self.assertNotIn("not_isolated", berwynn_ids)
        labels = resolve_manual_reasons(berwynn, ["visible_legs", "armor_shoulder"])
        self.assertEqual(labels, ["visible legs", "armor / shoulder armor"])
        with self.assertRaises(ValueError):
            resolve_manual_reasons(trophy, ["visible_legs"])

    def test_manual_berwynn_reasons_do_not_leak_to_other_assets(self):
        records = [
            record(
                record_id=f"berwynn-manual-legs-{index}",
                project="chimera",
                asset_type="character",
                asset_id="berwynn",
                decision="rejected",
                manual=["visible legs", "missing spectral lower body / ghost tail"],
                state="idle",
            )
            for index in range(6)
        ]
        records.extend(
            [
                record(
                    record_id=f"trophy-manual-{index}",
                    project="chimera",
                    asset_type="item",
                    asset_id="old-fishing-trophy",
                    decision="rejected",
                    manual=["subject is not isolated"],
                )
                for index in range(6)
            ]
        )
        berwynn = resolve_learning(get_asset("chimera", "character", "berwynn"), records)
        trophy = resolve_learning(get_asset("chimera", "item", "old-fishing-trophy"), records)
        tile = resolve_learning(get_asset("chimera", "tile", "mossy-stone-floor"), records)
        vfx = resolve_learning(get_asset("another-game", "vfx", "fireball-impact"), records)
        berwynn_vals = {str(item.value).lower() for item in berwynn.recommendations}
        trophy_vals = {str(item.value).lower() for item in trophy.recommendations}
        tile_vals = {str(item.value).lower() for item in tile.recommendations}
        vfx_vals = {str(item.value).lower() for item in vfx.recommendations}
        self.assertIn("legs", berwynn_vals)
        self.assertIn("ghost", berwynn_vals)
        self.assertNotIn("legs", trophy_vals)
        self.assertNotIn("ghost", trophy_vals)
        self.assertNotIn("legs", tile_vals)
        self.assertNotIn("ghost", tile_vals)
        self.assertNotIn("legs", vfx_vals)
        self.assertIn("isolated", trophy_vals)
        self.assertNotIn("isolated", berwynn_vals)
        self.assertTrue(berwynn.stats.topManualReasons)
        self.assertFalse(trophy.stats.topAutomaticReasons)

    def test_manual_evidence_outweighs_automatic_evidence(self):
        automatic = [
            record(
                record_id=f"auto-armor-{index}",
                project="chimera",
                asset_type="character",
                asset_id="berwynn",
                decision="rejected",
                automatic=["Rejected: armor or shoulder pieces are visible"],
                state="idle",
            )
            for index in range(3)
        ]
        auto_only = collect_signals(
            LearningContext("chimera", "character", "berwynn", "idle", "S"),
            automatic,
            DEFAULT_POLICY,
        )
        self.assertFalse(any(str(item.value) == "armor" for item in auto_only))
        manual = automatic + [
            record(
                record_id=f"manual-armor-{index}",
                project="chimera",
                asset_type="character",
                asset_id="berwynn",
                decision="rejected",
                manual=["armor / shoulder armor"],
                state="idle",
            )
            for index in range(3)
        ]
        mixed = collect_signals(
            LearningContext("chimera", "character", "berwynn", "idle", "S"),
            manual,
            DEFAULT_POLICY,
        )
        armor = next(item for item in mixed if str(item.value) == "armor")
        self.assertGreaterEqual(armor.manualEvidence, 3)
        self.assertLess(armor.automaticEvidence, armor.manualEvidence)
        self.assertGreaterEqual(armor.evidence, DEFAULT_POLICY.minSuggest)

    def test_incorrect_validator_detection_is_not_used_as_learning_evidence(self):
        records = [
            record(
                record_id=f"false-legs-{index}",
                project="chimera",
                asset_type="character",
                asset_id="berwynn",
                decision="rejected",
                automatic=["Rejected: legs are visible; this asset needs a spectral ghost tail"],
                manual=["wrong clothing"],
                validator_feedback="incorrect_detection",
                state="idle",
            )
            for index in range(6)
        ]
        automatic, manual = split_rejection_reasons(records[0])
        self.assertEqual(automatic, [])
        self.assertEqual(manual, ["wrong clothing"])
        found = collect_signals(
            LearningContext("chimera", "character", "berwynn", "idle", "S"),
            records,
            DEFAULT_POLICY,
        )
        values = {str(item.value).lower() for item in found}
        self.assertIn("clothing", values)
        self.assertNotIn("legs", values)

    def test_extraction_feedback_is_not_generation_learning(self):
        records = [
            record(
                record_id=f"extract-arm-{index}",
                project="chimera",
                asset_type="character",
                asset_id="berwynn",
                decision="rejected",
                manual=["arm cut off by alpha mask"],
                feedback_channel="extraction",
                state="idle",
            )
            for index in range(6)
        ]
        found = collect_signals(
            LearningContext("chimera", "character", "berwynn", "idle", "S"),
            records,
            DEFAULT_POLICY,
        )
        values = {str(item.value).lower() for item in found}
        self.assertNotIn("arm", values)
        self.assertNotIn("alpha", values)
        self.assertNotIn("mask", values)
        generation = record(
            record_id="gen-legs-0",
            project="chimera",
            asset_type="character",
            asset_id="berwynn",
            decision="rejected",
            manual=["visible legs"],
            state="idle",
        )
        mixed = collect_signals(
            LearningContext("chimera", "character", "berwynn", "idle", "S"),
            [*records, generation],
            DEFAULT_POLICY,
        )
        mixed_vals = {str(item.value).lower() for item in mixed}
        self.assertIn("legs", mixed_vals)
        self.assertNotIn("arm", mixed_vals)


if __name__ == "__main__":
    unittest.main()
