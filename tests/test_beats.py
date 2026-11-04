#!/usr/bin/env python3
"""Tests for beat, tempo and section detection.

These tests synthesise real audio with ffmpeg and measure what the detector
reports against the tempo the signal was actually built at. Nothing here is
mocked: if the DSP regresses, these fail.

Earlier versions of this project's test suite generated its own mock data and
then asserted against that mock, which cannot fail for the right reasons. The
click tracks below are the opposite: an independent ground truth the detector
has to recover.
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

from beats import MIN_ONSET_STRENGTH, analyse_song, count_onsets, onset_envelope  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None

# Tempi spanning the range of Indian wedding repertoire: slow vidai songs
# through to fast baraat and sangeet numbers.
TEMPI = [70, 85, 100, 110, 128, 140, 150, 175]

# Tolerance for tempo recovery. Measured error across these cases is under 1%;
# 2.5% leaves headroom for platform FFT differences without being so loose that
# an octave error (100% off) or a quantisation regression could slip through.
TEMPO_TOLERANCE_PCT = 2.5


def synth_click_track(path: Path, bpm: float, duration: float = 20.0) -> Path:
    """Render a percussive click track at an exact tempo."""
    period = 60.0 / bpm
    expr = f"0.9*sin(2*PI*300*t)*exp(-60*mod(t,{period}))*lt(mod(t,{period}),0.08)"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         f"aevalsrc='{expr}':s=22050:d={duration}", "-ac", "1", str(path), "-y"],
        check=True, capture_output=True,
    )
    return path


def synth_lavfi(path: Path, source: str, duration: float = 20.0) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"{source}:d={duration}",
         "-ac", "1", str(path), "-y"],
        check=True, capture_output=True,
    )
    return path


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required to synthesise test audio")
class TestTempoDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_recovers_known_tempo(self):
        """The detector must recover the tempo a click track was built at."""
        worst = 0.0
        for bpm in TEMPI:
            path = synth_click_track(self.tmp / f"click_{bpm}.wav", bpm)
            result = analyse_song(path)

            self.assertTrue(result["steady_tempo"],
                            f"{bpm} BPM click track should be detected as having a steady pulse")
            err = abs(result["bpm"] - bpm) / bpm * 100.0
            worst = max(worst, err)
            self.assertLess(
                err, TEMPO_TOLERANCE_PCT,
                f"{bpm} BPM detected as {result['bpm']:.1f} ({err:.1f}% off). "
                f"An error near 50% or 100% means the half/double tempo ambiguity has regressed.",
            )
        print(f"[✓] Tempo recovered for {len(TEMPI)} tempi; worst error {worst:.2f}%")

    def test_beat_grid_spacing_matches_tempo(self):
        """Beat times must be evenly spaced at the detected period."""
        path = synth_click_track(self.tmp / "grid.wav", 120.0)
        result = analyse_song(path)
        beats = result["beats"]
        self.assertGreater(len(beats), 20, "a 20s 120 BPM track should yield ~40 beats")

        gaps = [b - a for a, b in zip(beats[:-1], beats[1:])]
        expected = 60.0 / result["bpm"]
        for g in gaps:
            self.assertAlmostEqual(g, expected, delta=0.02,
                                   msg="beat grid spacing must match the detected tempo")
        # Downbeats are every 4th beat, for bar-level cutting.
        self.assertEqual(result["downbeats"], beats[::4])
        print(f"[✓] Beat grid even at {result['bpm']:.1f} BPM across {len(beats)} beats")

    def test_sustained_tone_has_no_pulse(self):
        """A sustained tone has no onsets and must not get a fabricated beat grid."""
        path = synth_lavfi(self.tmp / "tone.wav", "aevalsrc='0.5*sin(2*PI*440*t)':s=22050")
        result = analyse_song(path)

        self.assertFalse(result["steady_tempo"],
                         "a constant tone must not be reported as having a steady tempo")
        self.assertEqual(result["bpm"], 0.0)
        self.assertEqual(result["beats"], [], "no beats should be emitted for a pulseless signal")
        self.assertLess(result["onset_strength"], MIN_ONSET_STRENGTH)
        print(f"[✓] Sustained tone correctly reports no pulse "
              f"(onset strength {result['onset_strength']:.3f})")

    def test_noise_has_no_steady_tempo(self):
        """Broadband noise is not rhythmic, however much energy it carries."""
        path = synth_lavfi(self.tmp / "noise.wav", "anoisesrc=c=pink:r=22050")
        result = analyse_song(path)
        self.assertFalse(result["steady_tempo"],
                         "pink noise must not be reported as having a steady tempo")
        print(f"[✓] Pink noise correctly reports no steady tempo "
              f"(confidence {result['bpm_confidence']:.3f})")

    def test_sections_detected_on_varying_audio(self):
        """A track that changes level should be split into sections."""
        # Quiet first half, loud second half: one clear boundary.
        expr = "0.9*sin(2*PI*300*t)*exp(-60*mod(t,0.5))*lt(mod(t,0.5),0.08)*if(lt(t,10),0.15,1.0)"
        path = self.tmp / "sections.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             f"aevalsrc='{expr}':s=22050:d=20", "-ac", "1", str(path), "-y"],
            check=True, capture_output=True,
        )
        result = analyse_song(path)
        self.assertGreaterEqual(len(result["sections"]), 2,
                                "a track with a clear level change should yield multiple sections")
        energies = {s["energy"] for s in result["sections"]}
        self.assertTrue(energies, "sections must carry an energy label for the planner")
        print(f"[✓] {len(result['sections'])} sections detected with labels {sorted(energies)}")

    def test_empty_and_tiny_input_are_safe(self):
        """Degenerate input must not raise."""
        import numpy as np
        env, peak = onset_envelope(np.zeros(16, dtype=np.float32))
        self.assertEqual(peak, 0.0)
        self.assertEqual(count_onsets(env), 0)
        print("[✓] Degenerate input handled without raising")


if __name__ == "__main__":
    unittest.main(verbosity=2)
