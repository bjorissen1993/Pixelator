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
from learning.quality_first import promoted_quality_records, require_quality_review
from learning.resolver import resolve_learning
from learning.signals import collect_signals
from models.catalog import GenerationCandidate, LearningRecord, QualityReview
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

    def test_bearded_man_quality_helps_berwynn_recipe_without_content_leak(self):
        quality_records: list[LearningRecord] = []
        for index in range(4):
            quality_records.extend(
                [
                    record(
                        record_id=f"bench-sil-{index}",
                        project="pixelator-bench",
                        asset_type="character",
                        asset_id="bearded-man",
                        decision="rejected",
                        manual=["poor silhouette"],
                        scope="asset_type",
                        review_mode="quality_first",
                        state="idle",
                    ),
                    record(
                        record_id=f"bench-tech-{index}",
                        project="pixelator-bench",
                        asset_type="character",
                        asset_id="bearded-man",
                        decision="rejected",
                        manual=["poor technical quality"],
                        scope="global",
                        review_mode="quality_first",
                    ),
                    record(
                        record_id=f"bench-note-{index}",
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
        berwynn = resolve_learning(get_asset("chimera", "character", "berwynn"), quality_records)
        bench = resolve_learning(get_asset("pixelator-bench", "character", "bearded-man"), quality_records)
        trophy = resolve_learning(get_asset("chimera", "item", "old-fishing-trophy"), quality_records)
        berwynn_vals = {str(item.value).lower() for item in berwynn.recommendations}
        bench_vals = {str(item.value).lower() for item in bench.recommendations}
        trophy_vals = {str(item.value).lower() for item in trophy.recommendations}
        self.assertIn("silhouette", berwynn_vals)
        self.assertIn("technical", berwynn_vals)
        self.assertNotIn("beard", berwynn_vals)
        self.assertNotIn("tunic", berwynn_vals)
        self.assertIn("beard", bench_vals)
        self.assertIn("technical", trophy_vals)
        self.assertNotIn("silhouette", trophy_vals)
        self.assertTrue(any(item.learningClass == "global_quality" for item in berwynn.recommendations))
        self.assertTrue(any(item.learningClass == "character_type_quality" for item in berwynn.recommendations))

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
