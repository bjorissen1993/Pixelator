"""Quality-first benchmark isolation. No GPU."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domain.catalog import all_projects, get_asset
from learning.context import LearningContext, record_matches
from learning.policy import DEFAULT_POLICY
from learning.content_map import fragments_for_reason
from learning.quality_first import promoted_quality_records, require_quality_review
from learning.recipes import plan_candidate_recipes
from learning.resolver import resolve_learning
from learning.signals import collect_signals
from models.catalog import GenerationCandidate, LearningRecord, QualityReview
from models.learning import LearningPolicy
from processing.validators.review_reasons import reasons_for_asset
from tests.test_learning_loop import record


def _review(**overrides: str) -> QualityReview:
    payload = {
        "technicalQuality": "good",
        "silhouette": "good",
        "proportions": "good",
        "pixelReadability": "good",
        "transparencyExtraction": "good",
        **overrides,
    }
    return QualityReview(**payload)  # type: ignore[arg-type]


def _candidate() -> GenerationCandidate:
    return GenerationCandidate(
        id="bench1",
        projectId="pixelator-bench",
        assetType="character",
        assetId="bearded-man",
        seed=11,
        path="projects/pixelator-bench/assets/characters/bearded-man/candidates/bench1.png",
        createdAt="2026-09-12T00:00:00+00:00",
        modelSettings={"guidance": 8.0, "steps": 32},
        recipeFingerprint="bench-recipe",
    )


class QualityFirstTests(unittest.TestCase):
    def test_catalog_registers_generic_benchmark_asset(self):
        ids = {item.id for item in all_projects()}
        self.assertIn("pixelator-bench", ids)
        asset = get_asset("pixelator-bench", "character", "bearded-man")
        self.assertEqual(asset.reviewMode, "quality_first")
        self.assertTrue(asset.generation.enabled)
        self.assertIn("bearded man", asset.generation.prompt)
        self.assertEqual(asset.generation.backgroundMode, "transparent")
        self.assertFalse(asset.flags.spiritForm)

    def test_quality_first_omits_identity_review_reasons(self):
        bench = get_asset("pixelator-bench", "character", "bearded-man")
        berwynn = get_asset("chimera", "character", "berwynn")
        bench_ids = {item.id for item in reasons_for_asset(bench)}
        berwynn_ids = {item.id for item in reasons_for_asset(berwynn)}
        self.assertNotIn("wrong_hair_beard", bench_ids)
        self.assertNotIn("wrong_clothing", bench_ids)
        self.assertNotIn("visible_legs", bench_ids)
        self.assertIn("wrong_silhouette", bench_ids)
        self.assertIn("wrong_hair_beard", berwynn_ids)
        self.assertIn("visible_legs", berwynn_ids)

    def test_quality_ratings_are_required(self):
        with self.assertRaises(ValueError):
            require_quality_review(None)
        with self.assertRaises(ValueError):
            require_quality_review(QualityReview(technicalQuality="good"))

    def test_promoted_records_are_generic_and_cross_project(self):
        asset = get_asset("pixelator-bench", "character", "bearded-man")
        review = _review(silhouette="bad", technicalQuality="bad", transparencyExtraction="bad")
        records = promoted_quality_records(
            asset,
            _candidate(),
            review,
            created_at="2026-09-12T00:00:00+00:00",
            record_id_prefix="bench1-quality",
        )
        generation = [item for item in records if item.feedbackChannel == "generation"]
        global_bad = next(item for item in generation if item.scope == "global" and item.decision == "rejected")
        type_bad = next(item for item in generation if item.scope == "asset_type" and item.decision == "rejected")
        self.assertEqual(global_bad.manualRejectionReasons, ["poor technical quality"])
        self.assertEqual(type_bad.manualRejectionReasons, ["poor silhouette"])
        self.assertEqual(global_bad.prompt, "")
        self.assertTrue(all(item.reviewMode == "quality_first" for item in records))
        extraction = next(item for item in records if item.feedbackChannel == "extraction")
        self.assertEqual(extraction.scope, "asset")
        berwynn_ctx = LearningContext("chimera", "character", "berwynn", "idle", "S")
        self.assertTrue(record_matches(global_bad, berwynn_ctx, "global"))
        self.assertTrue(record_matches(type_bad, berwynn_ctx, "asset_type"))
        self.assertFalse(record_matches(type_bad, berwynn_ctx, "asset"))

    def _quality_cluster_records(self, *, good_guidance: float, good_steps: int, bad_guidance: float, bad_steps: int) -> list[LearningRecord]:
        records: list[LearningRecord] = []
        for index in range(4):
            records.extend(
                [
                    record(
                        record_id=f"good-tech-{good_guidance}-{index}",
                        project="pixelator-bench",
                        asset_type="character",
                        asset_id="bearded-man",
                        decision="accepted",
                        scope="global",
                        review_mode="quality_first",
                        dimension="technicalQuality",
                        guidance=good_guidance,
                        steps=good_steps,
                    ),
                    record(
                        record_id=f"bad-tech-{bad_guidance}-{index}",
                        project="pixelator-bench",
                        asset_type="character",
                        asset_id="bearded-man",
                        decision="rejected",
                        manual=["poor technical quality"],
                        scope="global",
                        review_mode="quality_first",
                        dimension="technicalQuality",
                        guidance=bad_guidance,
                        steps=bad_steps,
                    ),
                    record(
                        record_id=f"good-read-{good_guidance}-{index}",
                        project="pixelator-bench",
                        asset_type="character",
                        asset_id="bearded-man",
                        decision="accepted",
                        scope="global",
                        review_mode="quality_first",
                        dimension="pixelReadability",
                        guidance=good_guidance,
                        steps=good_steps,
                    ),
                    record(
                        record_id=f"bad-read-{bad_guidance}-{index}",
                        project="pixelator-bench",
                        asset_type="character",
                        asset_id="bearded-man",
                        decision="rejected",
                        manual=["poor pixel readability"],
                        scope="global",
                        review_mode="quality_first",
                        dimension="pixelReadability",
                        guidance=bad_guidance,
                        steps=bad_steps,
                    ),
                    record(
                        record_id=f"good-sil-{good_guidance}-{index}",
                        project="pixelator-bench",
                        asset_type="character",
                        asset_id="bearded-man",
                        decision="accepted",
                        scope="asset_type",
                        review_mode="quality_first",
                        dimension="silhouette",
                        state="idle",
                        guidance=good_guidance,
                        steps=good_steps,
                    ),
                    record(
                        record_id=f"note-{index}",
                        project="pixelator-bench",
                        asset_type="character",
                        asset_id="bearded-man",
                        decision="rejected",
                        manual=["beard is too thin and the tunic is wrong"],
                        scope="asset",
                        state="idle",
                    ),
                ]
            )
        return records

    def test_quality_labels_never_become_prompt_fragments(self):
        self.assertEqual(fragments_for_reason("poor pixel readability"), [])
        self.assertEqual(fragments_for_reason("poor technical quality"), [])
        records = self._quality_cluster_records(good_guidance=6.5, good_steps=28, bad_guidance=8.5, bad_steps=34)
        berwynn = resolve_learning(get_asset("chimera", "character", "berwynn"), records)
        bench = resolve_learning(get_asset("pixelator-bench", "character", "bearded-man"), records)
        trophy = resolve_learning(get_asset("chimera", "item", "old-fishing-trophy"), records)
        review_words = {"pixel", "readability", "technical", "quality", "silhouette", "proportions", "beard", "tunic"}
        for snapshot in (berwynn, bench, trophy):
            values = {str(item.value).lower() for item in snapshot.recommendations}
            self.assertFalse(review_words & values)
            self.assertNotIn("pixel", (snapshot.nextRecipe.negativePrompt if snapshot.nextRecipe else "").lower())

    def test_rejected_candidate_good_ratings_still_count(self):
        records = self._quality_cluster_records(good_guidance=6.5, good_steps=28, bad_guidance=8.5, bad_steps=34)
        bench = resolve_learning(get_asset("pixelator-bench", "character", "bearded-man"), records)
        tech = next(item for item in bench.qualityLearning if item.id == "technicalQuality")
        self.assertEqual(tech.good, 4)
        self.assertEqual(tech.bad, 4)
        self.assertTrue(any(item.kind == "guidance" and float(item.value) == 6.5 for item in bench.recommendations if item.applied))

    def test_quality_dimensions_stay_independent(self):
        records: list[LearningRecord] = []
        for index in range(4):
            records.append(
                record(
                    record_id=f"sil-good-{index}",
                    project="pixelator-bench",
                    asset_type="character",
                    asset_id="bearded-man",
                    decision="accepted",
                    scope="asset_type",
                    review_mode="quality_first",
                    dimension="silhouette",
                    state="idle",
                    guidance=6.8,
                    steps=28,
                )
            )
            records.append(
                record(
                    record_id=f"prop-bad-{index}",
                    project="pixelator-bench",
                    asset_type="character",
                    asset_id="bearded-man",
                    decision="rejected",
                    manual=["poor proportions"],
                    scope="asset_type",
                    review_mode="quality_first",
                    dimension="proportions",
                    state="idle",
                    guidance=6.8,
                    steps=28,
                )
            )
        bench = resolve_learning(get_asset("pixelator-bench", "character", "bearded-man"), records)
        silhouette = next(item for item in bench.qualityLearning if item.id == "silhouette")
        proportions = next(item for item in bench.qualityLearning if item.id == "proportions")
        self.assertEqual(silhouette.good, 4)
        self.assertEqual(silhouette.bad, 0)
        self.assertEqual(proportions.good, 0)
        self.assertEqual(proportions.bad, 4)

    def test_content_reasons_still_map_to_semantic_constraints(self):
        records = [
            record(
                record_id=f"legs-{index}",
                project="chimera",
                asset_type="character",
                asset_id="berwynn",
                decision="rejected",
                manual=["visible legs"],
                state="idle",
            )
            for index in range(4)
        ]
        berwynn = resolve_learning(get_asset("chimera", "character", "berwynn"), records)
        values = {str(item.value).lower() for item in berwynn.recommendations}
        self.assertIn("legs", values)
        self.assertIn("boots", values)
        self.assertIn("legs", (berwynn.nextRecipe.negativePrompt if berwynn.nextRecipe else "").lower())

    def test_recipe_selection_shifts_only_after_sufficient_evidence(self):
        weak = [
            record(
                record_id="weak-good-0",
                project="pixelator-bench",
                asset_type="character",
                asset_id="bearded-man",
                decision="accepted",
                scope="global",
                review_mode="quality_first",
                dimension="technicalQuality",
                guidance=6.5,
                steps=28,
            ),
            record(
                record_id="weak-bad-0",
                project="pixelator-bench",
                asset_type="character",
                asset_id="bearded-man",
                decision="rejected",
                manual=["poor technical quality"],
                scope="global",
                review_mode="quality_first",
                dimension="technicalQuality",
                guidance=8.5,
                steps=34,
            ),
        ]
        weak_snap = resolve_learning(get_asset("pixelator-bench", "character", "bearded-man"), weak)
        self.assertFalse(any(item.kind == "guidance" and item.applied for item in weak_snap.recommendations))
        strong = self._quality_cluster_records(good_guidance=6.5, good_steps=28, bad_guidance=8.5, bad_steps=34)
        strong_snap = resolve_learning(get_asset("pixelator-bench", "character", "bearded-man"), strong)
        self.assertTrue(any(item.kind == "guidance" and item.applied and float(item.value) == 6.5 for item in strong_snap.recommendations))

    def test_character_type_quality_does_not_affect_items(self):
        records = self._quality_cluster_records(good_guidance=6.5, good_steps=28, bad_guidance=8.5, bad_steps=34)
        trophy = resolve_learning(get_asset("chimera", "item", "old-fishing-trophy"), records)
        tile = resolve_learning(get_asset("chimera", "tile", "mossy-stone-floor"), records)
        sil = next(item for item in trophy.qualityLearning if item.id == "silhouette")
        self.assertFalse(sil.applies)
        self.assertTrue(any(item.kind == "guidance" and float(item.value) == 6.5 for item in trophy.recommendations))
        self.assertTrue(any(item.learningClass == "global_quality" for item in trophy.recommendations if item.applied))
        self.assertIsNotNone(tile.nextRecipe)

    def test_quality_first_explores_distinct_setting_clusters(self):
        asset = get_asset("pixelator-bench", "character", "bearded-man")
        planned = plan_candidate_recipes(asset, [], LearningPolicy(qualityExploitRatio=0.5), 4)
        self.assertEqual([item.mode for item in planned], ["exploit", "exploit", "explore", "explore"])
        explores = [item for item in planned if item.mode == "explore"]
        self.assertEqual(len({(item.guidance, item.steps) for item in explores}), 2)
        self.assertTrue(all("Explore" in " ".join(item.why) for item in explores))
        self.assertEqual({item.modelId for item in planned}, {asset.generation.modelId})

    def test_extraction_quality_is_not_generation_learning(self):
        records = [
            record(
                record_id=f"extract-{index}",
                project="pixelator-bench",
                asset_type="character",
                asset_id="bearded-man",
                decision="rejected",
                manual=["transparency extraction failed"],
                feedback_channel="extraction",
                review_mode="quality_first",
            )
            for index in range(4)
        ]
        found = collect_signals(
            LearningContext("chimera", "character", "berwynn"),
            records,
            DEFAULT_POLICY,
        )
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
