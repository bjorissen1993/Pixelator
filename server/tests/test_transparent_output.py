"""Generic transparent-output policy, isolation, and validators. No GPU."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import config
from domain.catalog import get_asset
from models.catalog import AssetProfile, GenerationCandidate, GenerationSpec
from processing.isolation import EXTRACTION_VERSION, extract_transparent_asset, isolate_subject
from processing.transparency_quality import assess_transparency
from processing.output_mode import (
    TRANSPARENT_ASSET_TYPES,
    background_mode_for,
    default_background_mode,
    expects_isolated_output,
)
from processing.validators.transparent_output import isolated_reason_messages, transparent_output_warnings
from services.asset_lab import _apply_output_artifacts


def _profile(asset_type: str, background=None, asset_id: str = "demo") -> AssetProfile:
    return AssetProfile(
        projectId="demo",
        assetType=asset_type,  # type: ignore[arg-type]
        assetId=asset_id,
        name="Demo",
        canonicalKind=asset_type,
        canonicalLabel=asset_type,
        generation=GenerationSpec(enabled=False, backgroundMode=background),
    )


def _subject_on_gray(size: int = 64) -> Image.Image:
    image = Image.new("RGB", (size, size), (160, 160, 160))
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 12, 44, 52), fill=(20, 180, 40))
    return image


def _two_subjects() -> Image.Image:
    image = Image.new("RGB", (64, 64), (160, 160, 160))
    draw = ImageDraw.Draw(image)
    draw.rectangle((6, 6, 20, 22), fill=(20, 180, 40))
    draw.rectangle((42, 40, 56, 56), fill=(20, 180, 40))
    return image


def _cropped_subject() -> Image.Image:
    image = Image.new("RGB", (64, 64), (160, 160, 160))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 63, 50), fill=(20, 180, 40))
    return image


class TransparentOutputTests(unittest.TestCase):
    def test_type_defaults_are_generic(self):
        for asset_type in ("character", "portrait", "item", "prop", "ui", "vfx"):
            self.assertEqual(default_background_mode(asset_type), "transparent")
            self.assertTrue(expects_isolated_output(_profile(asset_type)))
        self.assertEqual(default_background_mode("tile"), "solid")
        self.assertFalse(expects_isolated_output(_profile("tile")))
        self.assertEqual(default_background_mode("background"), "scene")
        self.assertFalse(expects_isolated_output(_profile("background")))
        self.assertEqual(TRANSPARENT_ASSET_TYPES, frozenset({"character", "portrait", "item", "prop", "ui", "vfx"}))

    def test_profile_can_override_type_default(self):
        tile_transparent = _profile("tile", "transparent")
        character_scene = _profile("character", "scene")
        self.assertTrue(expects_isolated_output(tile_transparent))
        self.assertEqual(background_mode_for(character_scene), "scene")
        self.assertFalse(expects_isolated_output(character_scene))

    def test_berwynn_uses_generic_transparent_mode_only(self):
        berwynn = get_asset("chimera", "character", "berwynn")
        tile = get_asset("chimera", "tile", "grass")
        self.assertEqual(background_mode_for(berwynn), "transparent")
        self.assertTrue(expects_isolated_output(berwynn))
        self.assertEqual(background_mode_for(tile), "solid")
        self.assertFalse(expects_isolated_output(tile))

    def test_generic_modules_do_not_name_berwynn_or_studio_rembg(self):
        roots = [
            SERVER_DIR / "processing" / "isolation.py",
            SERVER_DIR / "processing" / "output_mode.py",
            SERVER_DIR / "processing" / "validators" / "transparent_output.py",
            SERVER_DIR / "processing" / "transparency_quality.py",
        ]
        for path in roots:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("berwynn", text.lower(), path.name)
            self.assertNotIn("import rembg", text, path.name)
            self.assertNotIn("from rembg", text, path.name)
            self.assertNotIn("remove_background", text, path.name)

    def test_edge_flood_creates_valid_transparent_asset(self):
        isolated, report = isolate_subject(_subject_on_gray())
        warnings = transparent_output_warnings(isolated, report)
        self.assertTrue(report.has_alpha)
        self.assertEqual(report.subject_count, 1)
        self.assertFalse(report.cropped)
        self.assertTrue(report.bbox_reasonable)
        self.assertGreaterEqual(report.transparent_ratio, 0.18)
        self.assertLessEqual(report.remnant_ratio, 0.12)
        self.assertEqual(isolated_reason_messages(warnings), [])

    def test_raw_pixels_are_not_mutated(self):
        raw = _subject_on_gray()
        before = raw.tobytes()
        isolate_subject(raw)
        self.assertEqual(raw.tobytes(), before)

    def test_existing_alpha_is_reused(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 12, 44, 52), fill=(20, 180, 40, 255))
        isolated, report = isolate_subject(image)
        self.assertTrue(any("existing alpha" in note.lower() for note in report.notes))
        self.assertEqual(isolated_reason_messages(transparent_output_warnings(isolated, report)), [])

    def test_validators_catch_multiple_subjects(self):
        isolated, report = isolate_subject(_two_subjects())
        codes = {warning.code for warning in transparent_output_warnings(isolated, report)}
        self.assertIn("isolated_multiple_subjects", codes)

    def test_validators_catch_cropped_subject(self):
        isolated, report = isolate_subject(_cropped_subject())
        codes = {warning.code for warning in transparent_output_warnings(isolated, report)}
        self.assertTrue({"isolated_cropped", "isolated_bbox"} & codes)

    def test_validators_require_alpha(self):
        solid = Image.new("RGB", (64, 64), (20, 180, 40))
        codes = {warning.code for warning in transparent_output_warnings(solid.convert("RGBA"))}
        self.assertIn("isolated_missing_alpha", codes)
        self.assertIn("isolated_low_transparency", codes)

    def test_thin_attached_structure_is_preserved(self):
        image = Image.new("RGB", (64, 64), (160, 160, 160))
        draw = ImageDraw.Draw(image)
        draw.rectangle((24, 16, 40, 48), fill=(20, 180, 40))
        draw.rectangle((40, 28, 58, 31), fill=(148, 148, 154))
        isolated, _report = isolate_subject(image)
        pixels = isolated.load()
        self.assertGreaterEqual(pixels[50, 29][3], 16)
        self.assertEqual(pixels[2, 2][3], 0)

    def test_tiny_interior_holes_are_filled(self):
        image = Image.new("RGB", (64, 64), (160, 160, 160))
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 12, 48, 52), fill=(20, 180, 40))
        draw.rectangle((28, 28, 31, 31), fill=(160, 160, 160))
        isolated, _report = isolate_subject(image)
        self.assertGreaterEqual(isolated.getpixel((29, 29))[3], 16)

    def test_quality_detects_over_removal(self):
        raw = _subject_on_gray()
        isolated, report = isolate_subject(raw)
        damaged = isolated.copy()
        draw = ImageDraw.Draw(damaged)
        draw.rectangle((20, 12, 44, 28), fill=(20, 180, 40, 0))
        quality = assess_transparency(raw, damaged, report)
        self.assertIn(quality.grade, {"warning", "failed"})
        self.assertTrue({"excessive_subject_loss", "alpha_edge_damage"} & set(quality.issues))

    def test_extraction_metadata_is_generic(self):
        result = extract_transparent_asset(_subject_on_gray())
        self.assertEqual(result.version, EXTRACTION_VERSION)
        self.assertEqual(result.method, "edge_flood_refine")
        self.assertTrue(result.settings["binaryAlpha"])
        self.assertIn(result.quality.grade, {"good", "warning", "failed"})

    def test_derived_files_leave_raw_untouched(self):
        raw = _subject_on_gray()
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            previous = config.DATA_DIR
            config.DATA_DIR = data_dir
            try:
                raw_file = (
                    data_dir
                    / "projects"
                    / "demo"
                    / "assets"
                    / "characters"
                    / "hero"
                    / "candidates"
                    / "abc123.png"
                )
                raw_file.parent.mkdir(parents=True, exist_ok=True)
                raw.save(raw_file)
                before = raw_file.read_bytes()
                candidate = GenerationCandidate(
                    id="abc123",
                    projectId="demo",
                    assetType="character",
                    assetId="hero",
                    seed=1,
                    path="projects/demo/assets/characters/hero/candidates/abc123.png",
                    createdAt="2026-09-12T00:00:00+00:00",
                )
                updated = _apply_output_artifacts(_profile("character", asset_id="hero"), candidate, raw_file)
                self.assertEqual(raw_file.read_bytes(), before)
                self.assertEqual(updated.rawPath, "projects/demo/assets/characters/hero/candidates/abc123.png")
                self.assertTrue((raw_file.parent / "abc123.preview.png").is_file())
                self.assertTrue((raw_file.parent / "abc123.isolated.png").is_file())
                self.assertEqual(updated.isolatedStatus, "ok")
                self.assertEqual(updated.backgroundMode, "transparent")
                self.assertIsNotNone(updated.extraction)
                self.assertEqual(updated.extraction.version, EXTRACTION_VERSION)
                self.assertIn(updated.extraction.quality, {"good", "warning", "failed"})
                tile = _apply_output_artifacts(
                    _profile("tile", asset_id="hero"),
                    candidate.model_copy(),
                    raw_file,
                )
                self.assertEqual(tile.isolatedStatus, "skipped")
                self.assertEqual(tile.isolatedPath, "")
            finally:
                config.DATA_DIR = previous


if __name__ == "__main__":
    unittest.main()
