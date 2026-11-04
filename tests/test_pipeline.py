#!/usr/bin/env python3
"""Automated Test Suite for Indian & Bihari Wedding Video Editing Pipeline.

Verifies:
1. Rituals database integrity (16 rituals in data/rituals.json)
2. Song matrices integrity (Pan-India and Bihari catalogs)
3. 165 Video cards in library/cards/
4. Character continuity and screen-time auditor
5. DSP audio filtergraph & ducking calculations
6. FCPXML v1.10 XML schema generation for Teaser, Trailer, and Master Cut
7. Multi-Agent Graph Orchestrator execution loop
"""

import json
import os
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

# Ensure scripts dir is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from raw_footage_ingest import compute_clip_id, guess_ritual_phase
from family_face_tracker import audit_character_continuity, generate_mock_tags
from audio_cleanup_pipeline import build_ffmpeg_audio_filter, calculate_ducking_keyframes
from fcpxml_generator import build_teaser_timeline, build_trailer_timeline, build_master_documentary_timeline
from agent_graph_orchestrator import WeddingEditGraphOrchestrator


class TestWeddingPipeline(unittest.TestCase):
    def setUp(self):
        self.base_dir = BASE_DIR
        self.test_work = self.base_dir / "test_pipeline_run"
        self.test_work.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Keep artifacts or clean up if needed
        pass

    def test_01_rituals_database(self):
        rit_path = self.base_dir / "data" / "rituals.json"
        self.assertTrue(rit_path.exists(), "data/rituals.json must exist")
        with open(rit_path, encoding="utf-8") as fp:
            data = json.load(fp)
        rituals = data.get("rituals", [])
        self.assertEqual(len(rituals), 16, "Must define exactly 16 Bihari rituals")
        # Verify essential ritual IDs exist
        r_ids = {r["id"] for r in rituals}
        self.assertIn("R02_matkor", r_ids)
        self.assertIn("R05_haldi_ubtan", r_ids)
        self.assertIn("R11_sindoor_daan", r_ids)
        self.assertIn("R14_vidai_samdhauni", r_ids)
        print("[✓] Test 01: Rituals database verified (16 rituals).")

    def test_02_songs_catalogs(self):
        pan_india = self.base_dir / "library" / "songs" / "songs_pan_india.json"
        bihar = self.base_dir / "library" / "songs" / "songs_bihar.json"
        self.assertTrue(pan_india.exists(), "songs_pan_india.json must exist")
        self.assertTrue(bihar.exists(), "songs_bihar.json must exist")

        with open(pan_india, encoding="utf-8") as fp:
            p_data = json.load(fp)
        with open(bihar, encoding="utf-8") as fp:
            b_data = json.load(fp)

        self.assertGreaterEqual(len(p_data.get("songs", [])), 15)
        self.assertGreaterEqual(len(b_data.get("songs", [])), 20)
        print(f"[✓] Test 02: Song catalogs verified ({len(p_data['songs'])} Pan-India, {len(b_data['songs'])} Bihari).")

    def test_03_video_cards_count(self):
        cards_dir = self.base_dir / "library" / "cards"
        self.assertTrue(cards_dir.exists(), "library/cards/ directory must exist")
        card_files = list(cards_dir.glob("*.md"))
        self.assertEqual(len(card_files), 165, "Must generate exactly 165 video cards")
        # Verify random sample card content
        sample = card_files[0].read_text(encoding="utf-8")
        self.assertIn("# Video Card:", sample)
        self.assertIn("YouTube ID", sample)
        self.assertIn("Key Takeaways for Final Cut Pro", sample)
        print("[✓] Test 03: 165 individual video cards verified in library/cards/.")

    def test_04_character_continuity_audit(self):
        generate_mock_tags(self.test_work, count=150)
        audit = audit_character_continuity(self.test_work / "tags")
        self.assertEqual(audit["total_tagged_clips"], 150)
        self.assertIn("groom_family_percentage", audit["family_balance"])
        self.assertIn("bride_family_percentage", audit["family_balance"])
        self.assertTrue(audit["is_balanced"], "Screen-time balance should pass threshold")
        self.assertTrue(audit["reception_stage_verified"], "Reception stage must be covered")
        print("[✓] Test 04: Family character continuity audit verified.")

    def test_05_audio_dsp_and_ducking(self):
        filter_str = build_ffmpeg_audio_filter(has_dialogue=True, is_folk_geet=True)
        self.assertIn("highpass=f=80", filter_str)
        self.assertIn("equalizer=f=50", filter_str)
        self.assertIn("equalizer=f=320", filter_str)

        speech = [(5.0, 15.0), (30.0, 45.0)]
        keyframes = calculate_ducking_keyframes(speech, 60.0)
        self.assertGreater(len(keyframes), 0)
        self.assertEqual(keyframes[1]["gain_db"], -16.0)
        print("[✓] Test 05: Audio DSP filtergraph and -16dB ducking verified.")

    def test_06_fcpxml_generation(self):
        out_dir = self.test_work / "fcpxml_test_out"
        teaser = build_teaser_timeline(out_dir / "Teaser.fcpxml")
        trailer = build_trailer_timeline(out_dir / "Trailer.fcpxml")
        master = build_master_documentary_timeline(out_dir / "Master.fcpxml")

        for fpath in [teaser, trailer, master]:
            self.assertTrue(fpath.exists(), f"{fpath.name} must exist")
            # Parse XML
            tree = ET.parse(fpath)
            root = tree.getroot()
            self.assertEqual(root.tag, "fcpxml")
            self.assertEqual(root.attrib.get("version"), "1.10")
            spine = root.find(".//spine")
            self.assertIsNotNone(spine, "FCPXML must contain a <spine>")
            clips = spine.findall("asset-clip")
            self.assertGreater(len(clips), 0, "Spine must contain clips")

        print("[✓] Test 06: FCPXML v1.10 generation verified for Teaser, Trailer, and Master.")

    def test_07_agent_graph_orchestrator(self):
        orchestrator = WeddingEditGraphOrchestrator(self.test_work, max_loops=2)
        success = orchestrator.execute_graph_pipeline()
        self.assertTrue(success, "Multi-agent graph loop should succeed and pass QA")
        print("[✓] Test 07: Multi-Agent Graph loop verified with 100% QA pass.")


if __name__ == "__main__":
    unittest.main()
