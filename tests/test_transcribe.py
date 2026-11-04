#!/usr/bin/env python3
"""Tests for transcription, audio extraction and geet/mantra labelling.

Audio extraction is tested against video files synthesised with ffmpeg and the
result is probed to confirm the format Whisper requires. Labelling is tested on
realistic Devanagari lines of the three kinds the brief distinguishes: folk
geet sung by the family, the pandit's Sanskrit recitation, and ordinary speech.

The Whisper backend itself is not exercised: it downloads a multi-gigabyte
model. Everything around it is, which is the part this project actually wrote.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from transcribe import (  # noqa: E402
    _load_backend, annotate, build_lexicons, classify_segment, extract_audio,
    find_repeated_lines, has_audio_stream, merge_spans, summarise,
)

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def probe(path: Path, entries: str) -> str:
    return subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", entries, "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    ).stdout.strip()


class TestLexicon(unittest.TestCase):
    def test_lexicon_is_built_from_the_song_catalogue(self):
        """Geet vocabulary must come from the project's curated Bihari songs."""
        lx = build_lexicons()
        self.assertGreater(len(lx["mantra"]), 20)
        self.assertGreater(len(lx["geet"]), 50)
        # Terms that can only have come from songs_bihar.json, not the
        # hand-written list, proving the catalogue was actually read.
        self.assertIn("chumawan", lx["geet"])
        self.assertIn("samdaun", lx["geet"])
        print(f"[✓] Lexicon: {len(lx['mantra'])} mantra, {len(lx['geet'])} geet terms")


class TestClassification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lx = build_lexicons()

    def test_pandit_recitation_is_labelled_mantra(self):
        for line in [
            "ॐ अग्नये स्वाहा इदं न मम",
            "ॐ भूर्भुवः स्वः तत्सवितुर्वरेण्यं",
            "अब कन्यादान का संकल्प कीजिए यजमान",
        ]:
            self.assertEqual(classify_segment(line, self.lx)["label"], "mantra", line)
        print("[✓] Pandit recitation labelled mantra")

    def test_folk_geet_is_labelled_geet(self):
        for line in [
            "हरदी हरदिया हो बाबा आंगन में",
            "हरियर बाँस कटइह हो बाबा",
            "सखी हो दुलहिन के कोहबर में",
        ]:
            self.assertEqual(classify_segment(line, self.lx)["label"], "geet", line)
        print("[✓] Folk geet labelled geet")

    def test_ordinary_speech_is_not_mislabelled(self):
        """Crew and family chatter must not be mistaken for ritual audio."""
        for line in [
            "अरे जल्दी आओ फोटो खिंचवाना है",
            "कैमरा इधर रखो लाइट ठीक नहीं है",
            "खाना लग गया है सब लोग आ जाइए",
        ]:
            self.assertEqual(classify_segment(line, self.lx)["label"], "speech", line)
        print("[✓] Ordinary speech not mislabelled")

    def test_decisions_are_auditable(self):
        """Every label carries the terms that produced it, for human review."""
        r = classify_segment("ॐ अग्नये स्वाहा", self.lx)
        self.assertTrue(r["matched"], "a label must report which terms matched")
        self.assertGreater(r["score"], 0.0)

    def test_empty_text_is_unknown_not_speech(self):
        r = classify_segment("   ", self.lx)
        self.assertEqual(r["label"], "unknown")

    def test_repeated_line_detected_as_refrain(self):
        segs = [
            {"start": 0, "end": 4, "text": "हरदी हरदिया हो बाबा आंगन में"},
            {"start": 4, "end": 8, "text": "हरदी हरदिया हो बाबा आंगन में"},
        ]
        self.assertEqual(len(find_repeated_lines(segs)), 1)
        print("[✓] Repeated refrain detected")


class TestSpansAndSummary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lx = build_lexicons()

    def test_adjacent_geet_segments_merge_into_one_span(self):
        """The editor needs continuous ranges, not a list of fragments."""
        segs = [
            {"start": 0, "end": 4, "text": "कैमरा इधर रखो"},
            {"start": 4, "end": 9, "text": "हरदी हरदिया हो बाबा आंगन में"},
            {"start": 9, "end": 14, "text": "सखी हो दुलहिन के कोहबर में"},
            {"start": 40, "end": 46, "text": "ॐ अग्नये स्वाहा इदं न मम"},
        ]
        ann = annotate(segs, self.lx)
        geet = merge_spans(ann, "geet")
        self.assertEqual(len(geet), 1, "contiguous geet should merge to a single span")
        self.assertEqual((geet[0]["start"], geet[0]["end"]), (4.0, 14.0))
        self.assertEqual(geet[0]["duration"], 10.0)

        mantra = merge_spans(ann, "mantra")
        self.assertEqual(len(mantra), 1)

        summary = summarise(ann)
        self.assertEqual(summary["label_seconds"]["geet"], 10.0)
        print(f"[✓] Spans merged: geet {geet[0]['duration']}s, "
              f"mantra {mantra[0]['duration']}s")

    def test_distant_segments_do_not_merge(self):
        segs = [
            {"start": 0, "end": 4, "text": "हरदी हरदिया हो बाबा"},
            {"start": 60, "end": 64, "text": "हरियर बाँस कटइह हो बाबा"},
        ]
        ann = annotate(segs, self.lx)
        self.assertEqual(len(merge_spans(ann, "geet")), 2,
                         "segments a minute apart are separate performances")


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required to synthesise test media")
class TestAudioExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)

        cls.with_audio = cls.tmp / "with_audio.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:d=4",
             "-f", "lavfi", "-i", "sine=frequency=440:r=22050:d=4",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
             str(cls.with_audio), "-y"], check=True, capture_output=True)

        # Drone and action-camera footage is often silent; it must be skipped
        # cleanly rather than crashing a thousand-clip batch.
        cls.silent = cls.tmp / "silent_drone.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:d=4",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cls.silent), "-y"],
            check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_detects_whether_a_clip_has_audio(self):
        self.assertTrue(has_audio_stream(self.with_audio))
        self.assertFalse(has_audio_stream(self.silent))
        print("[✓] Audio stream presence detected correctly")

    def test_extracts_mono_16k_pcm_for_whisper(self):
        """Whisper expects 16 kHz mono PCM; confirm that is what we produce."""
        out = extract_audio(self.with_audio, self.tmp / "out" / "clip.wav")
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 1000)
        self.assertEqual(probe(out, "stream=sample_rate"), "16000")
        self.assertEqual(probe(out, "stream=channels"), "1")
        self.assertEqual(probe(out, "stream=codec_name"), "pcm_s16le")
        print("[✓] Extracted 16 kHz mono pcm_s16le as Whisper requires")

    def test_silent_video_raises_rather_than_writing_garbage(self):
        with self.assertRaises(RuntimeError):
            extract_audio(self.silent, self.tmp / "out" / "silent.wav")
        print("[✓] Silent video raises instead of producing an empty track")


class TestBackendAbsence(unittest.TestCase):
    def test_missing_backend_gives_actionable_instructions(self):
        """With no Whisper installed, the error must say how to install it."""
        try:
            _load_backend("tiny", backend="auto")
        except RuntimeError as e:
            msg = str(e)
            self.assertIn("pip install", msg)
            self.assertIn("faster-whisper", msg)
            print("[✓] Missing backend reports install instructions")
        else:
            self.skipTest("a Whisper backend is installed in this environment")


if __name__ == "__main__":
    unittest.main(verbosity=2)
