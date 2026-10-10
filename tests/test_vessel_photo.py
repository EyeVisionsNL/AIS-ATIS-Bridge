#!/usr/bin/env python3
"""Regression tests for ship-photo filtering; no external network needed."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
from ais_atis_bridge import vessel_photo as photo


def candidate(title, description="", categories="", thumb=True, mmsi="", imo="", eni=""):
    more = " ".join(filter(None, [description, ("MMSI " + mmsi) if mmsi else "", ("IMO " + imo) if imo else "", ("ENI " + eni) if eni else ""]))
    return {
        "title": "File:" + title,
        "imageinfo": [{
            "thumburl": "https://upload.wikimedia.org/wikipedia/commons/a/a1/example.jpg" if thumb else "",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example",
            "extmetadata": {
                "ImageDescription": {"value": more},
                "Categories": {"value": categories},
                "Artist": {"value": "Ship photographer"},
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
            },
        }],
    }


class VesselPhotoValidation(unittest.TestCase):
    def score(self, page, name="TOURMALINE", imo="", eni="", mmsi="244700498"):
        return photo._score(page, mmsi=mmsi, shipname=name, imo=imo, eni=eni)

    def test_mineral_from_screenshot_is_rejected(self):
        self.assertLess(self.score(candidate(".Tourmaline - Tourmali.jpg",
                                              "Tourmaline mineral sample, quartz", "Minerals")), 0)

    def test_name_alone_cannot_qualify(self):
        self.assertLess(self.score(candidate("Tourmaline.jpg", "Tourmaline gemstone")), 0)

    def test_art_is_rejected(self):
        self.assertLess(self.score(candidate("Motor tanker Tourmaline painting.jpg",
                                              "Illustration of a motor tanker")), 0)

    def test_military_namesake_is_rejected(self):
        self.assertLess(self.score(candidate("USS Tourmaline PY-20.jpg",
                                              "USS Tourmaline patrol vessel", "US Navy ships")), 0)

    def test_ship_in_filename_without_matching_identifier_is_rejected(self):
        self.assertLess(self.score(candidate("Motor tanker TOURMALINE.jpg", "Motor tanker Tourmaline")), 0)

    def test_ship_in_description_without_matching_identifier_is_rejected(self):
        self.assertLess(self.score(candidate("Tourmaline.jpg",
                                              "De motortanker Tourmaline bij Vlaardingen")), 0)

    def test_name_as_credit_is_not_vessel_identity(self):
        self.assertLess(self.score(candidate("MV Ocean Blue.jpg",
                                              "Ships photographed by someone called Tourmaline")), 0)

    def test_ship_name_must_be_exact(self):
        self.assertLess(self.score(candidate("Motor tanker Tourmalines.jpg", "Motortanker Tourmalines")), 0)

    def test_correct_mmsi_is_accepted(self):
        self.assertGreaterEqual(self.score(candidate("Boat harbour.jpg", "Vessel photographed", mmsi="244700498")), 200)

    def test_wrong_mmsi_is_rejected(self):
        self.assertLess(self.score(candidate("Motor tanker Tourmaline.jpg", "Motor tanker Tourmaline",
                                              mmsi="123456789")), 0)

    def test_wrong_imo_is_rejected(self):
        self.assertLess(self.score(candidate("Motor tanker Tourmaline.jpg",
                                              "Motor tanker Tourmaline", imo="7654321"), imo="1234567"), 0)

    def test_correct_eni_is_accepted(self):
        page = candidate("Unnamed vessel.jpg", "Inland vessel at Rotterdam", eni="02321028")
        self.assertGreaterEqual(self.score(page, eni="02321028"), 210)

    def test_wikimedia_query_includes_eni(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            original_file, original_cache = photo.CACHE_FILE, photo._cache
            try:
                photo.CACHE_FILE = Path(cache_dir) / "cache.json"
                photo._cache = {}
                with patch.object(photo, "_spotter_lookup", return_value=None), \
                     patch.object(photo, "_binnenvaart_lookup", return_value=None), \
                     patch.object(photo, "_mark_lookup", return_value=None), \
                     patch.object(photo, "_commons_search", return_value=[]) as search:
                    photo.lookup("244700498", "TOURMALINE", eni="02321028")
                queries = [call.args[0] for call in search.call_args_list]
                self.assertIn('"ENI 02321028"', queries)
            finally:
                photo.CACHE_FILE = original_file
                photo._cache = original_cache

    def test_wrong_eni_is_rejected(self):
        page = candidate("Motor tanker Tourmaline.jpg", "Motor tanker Tourmaline", eni="02311111")
        self.assertLess(self.score(page, eni="02321028"), 0)

    def test_no_thumbnail_is_rejected(self):
        self.assertLess(self.score(candidate("Motor tanker Tourmaline.jpg", thumb=False)), 0)

    def test_mineral_name_requires_matching_vessel_identity(self):
        page = candidate("Motor tanker CRYSTAL.jpg", "Motor tanker Crystal", mmsi="244700498")
        self.assertGreaterEqual(self.score(page, name="CRYSTAL"), 220)

    def test_lookup_skips_mineral_and_uses_vessel(self):
        bad = candidate("Tourmaline mineral.jpg", "Tourmaline crystal")
        good = candidate("Motor tanker TOURMALINE.jpg", "Motor tanker Tourmaline", mmsi="244700498")
        with tempfile.TemporaryDirectory() as cache_dir:
            original_file, original_cache = photo.CACHE_FILE, photo._cache
            try:
                photo.CACHE_FILE = Path(cache_dir) / "cache.json"
                photo._cache = {}
                with patch.object(photo, "_mark_lookup", return_value=None), \
                     patch.object(photo, "_commons_search", return_value=[bad, good]):
                    result = photo.lookup("244700498", "TOURMALINE")
                self.assertTrue(result["ok"])
                self.assertEqual(result["title"], "Motor tanker TOURMALINE.jpg")
                self.assertFalse(result["cached"])
                self.assertEqual(result["source"], "Wikimedia Commons")
            finally:
                photo.CACHE_FILE = original_file
                photo._cache = original_cache

    def test_old_photo_cache_is_not_reused(self):
        self.assertEqual(photo.PHOTO_POLICY_VERSION, 8)
        old_key = "7|244700498|TOURMALINE|"
        with tempfile.TemporaryDirectory() as cache_dir:
            original_file, original_cache = photo.CACHE_FILE, photo._cache
            try:
                photo.CACHE_FILE = Path(cache_dir) / "cache.json"
                photo._cache = {old_key: {"ok": True, "image_url": "https://example.com/mineral.jpg", "cached_at": 1e20}}
                with patch.object(photo, "_mark_lookup", return_value=None), \
                     patch.object(photo, "_commons_search", return_value=[]):
                    result = photo.lookup("244700498", "TOURMALINE")
                self.assertFalse(result["ok"])
                self.assertFalse(result["cached"])
            finally:
                photo.CACHE_FILE = original_file
                photo._cache = original_cache


if __name__ == "__main__":
    unittest.main()
