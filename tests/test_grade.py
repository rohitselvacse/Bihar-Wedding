#!/usr/bin/env python3
"""Tests for exposure and colour measurement, and grade grouping.

Clips are synthesised at known colours and exposures with ffmpeg, so the
measurements are checked against a ground truth rather than against
themselves. Colour is the one area of the brief that had no code behind it at
all, so these assertions are about whether the numbers mean anything.
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

from grade import (NEUTRAL, classify_cast, classify_exposure, group_clips,  # noqa: E402
                   measure_clip, suggest_correction, write_report)

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def synth_colour(path: Path, hex_colour: str, duration: float = 2.0) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi",
         f"-i", f"color=c={hex_colour}:s=320x240:r=25:d={duration}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path), "-y"],
        check=True, capture_output=True)
    return path


class TestCastClassification(unittest.TestCase):
    """U carries blue-yellow and V carries red-cyan, 128 neutral on both."""

    def test_neutral(self):
        self.assertEqual(classify_cast(NEUTRAL, NEUTRAL)["cast"], "neutral")
        self.assertEqual(classify_cast(130, 126)["cast"], "neutral")

    def test_warm_is_low_u_high_v(self):
        """Tungsten light and a sunlit haldi courtyard both read this way."""
        self.assertEqual(classify_cast(86, 170)["cast"], "warm")

    def test_cool_is_high_u_low_v(self):
        self.assertEqual(classify_cast(175, 92)["cast"], "cool")

    def test_green_and_magenta(self):
        self.assertEqual(classify_cast(110, 110)["cast"], "green")
        self.assertEqual(classify_cast(150, 150)["cast"], "magenta")

    def test_strength_grows_with_distance_from_neutral(self):
        weak = classify_cast(120, 136)["cast_strength"]
        strong = classify_cast(86, 170)["cast_strength"]
        self.assertLess(weak, strong)
        print("[✓] Cast classification correct on all four chroma quadrants")


class TestExposureClassification(unittest.TestCase):
    def test_under_and_over_exposure(self):
        self.assertIn("under-exposed", classify_exposure(40, 10, 90)["exposure_notes"])
        self.assertIn("over-exposed", classify_exposure(200, 150, 240)["exposure_notes"])
        self.assertEqual(classify_exposure(110, 16, 235)["exposure_notes"], [])

    def test_clipping_is_detected(self):
        self.assertIn("highlights clipped", classify_exposure(150, 20, 255)["exposure_notes"])
        self.assertIn("shadows crushed", classify_exposure(90, 0, 200)["exposure_notes"])
        print("[✓] Exposure and clipping flags correct")

    def test_flat_footage_flagged(self):
        self.assertIn("very low contrast (flat or log footage)",
                      classify_exposure(110, 100, 130)["exposure_notes"])


class TestCorrectionSuggestion(unittest.TestCase):
    def test_dark_clip_gets_a_positive_exposure_push(self):
        dark = {"y_avg": 50.0, **classify_cast(NEUTRAL, NEUTRAL)}
        self.assertGreater(suggest_correction(dark)["exposure_ev"], 0.5)

    def test_bright_clip_gets_a_negative_exposure_push(self):
        bright = {"y_avg": 210.0, **classify_cast(NEUTRAL, NEUTRAL)}
        self.assertLess(suggest_correction(bright)["exposure_ev"], -0.5)

    def test_correction_removes_the_measured_cast(self):
        """A warm clip must be corrected toward neutral, not further warm."""
        warm = {"y_avg": 110.0, **classify_cast(86, 170)}
        c = suggest_correction(warm)
        # u_offset was negative, so the removal must be positive, and vice versa.
        self.assertGreater(c["remove_u_offset"], 0)
        self.assertLess(c["remove_v_offset"], 0)
        self.assertIn("colorbalance", c["ffmpeg_preview_filter"])
        print(f"[✓] Warm cast corrected toward neutral: {c['ffmpeg_preview_filter']}")

    def test_neutral_clip_gets_no_colour_balance(self):
        neutral = {"y_avg": 110.0, **classify_cast(NEUTRAL, NEUTRAL)}
        self.assertNotIn("colorbalance", suggest_correction(neutral)["ffmpeg_preview_filter"])

    def test_exposure_push_is_bounded(self):
        """A wild measurement must not produce an absurd correction."""
        for y in (2.0, 1.0, 254.0):
            ev = suggest_correction({"y_avg": y, **classify_cast(NEUTRAL, NEUTRAL)})["exposure_ev"]
            self.assertLessEqual(abs(ev), 2.5)

    def test_correction_states_its_own_limits(self):
        c = suggest_correction({"y_avg": 110.0, **classify_cast(86, 170)})
        self.assertIn("Starting point only", c["note"])


class TestGrouping(unittest.TestCase):
    """The unit of grading work is the setup, not the clip."""

    def _m(self, cid, y, u, v):
        return {"clip_id": cid, "source": f"{cid}.mov", "y_avg": y, "u_avg": u, "v_avg": v}

    def test_similar_clips_share_one_group(self):
        groups = group_clips([
            self._m("a", 110, 128, 128),
            self._m("b", 115, 130, 126),
            self._m("c", 108, 127, 131),
        ])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["clip_count"], 3)
        print("[✓] Three clips of one setup grouped together")

    def test_different_looks_are_separated(self):
        groups = group_clips([
            self._m("warm1", 133, 86, 170),
            self._m("warm2", 130, 90, 166),
            self._m("cool1", 109, 175, 92),
            self._m("dark1", 43, 128, 128),
        ])
        self.assertEqual(len(groups), 3, "warm pair, cool, dark")
        biggest = groups[0]
        self.assertEqual(biggest["clip_count"], 2)
        self.assertEqual(biggest["cast"], "warm")
        print(f"[✓] Four clips separated into {len(groups)} looks, "
              f"largest is the {biggest['cast']} pair")

    def test_groups_are_ordered_by_size(self):
        groups = group_clips([
            self._m("x", 43, 128, 128),
            self._m("a", 110, 128, 128), self._m("b", 112, 129, 127),
            self._m("c", 109, 127, 129),
        ])
        counts = [g["clip_count"] for g in groups]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_each_group_carries_a_correction(self):
        groups = group_clips([self._m("a", 60, 100, 160)])
        self.assertIn("correction", groups[0])
        self.assertIn("ffmpeg_preview_filter", groups[0]["correction"])

    def test_empty_input(self):
        self.assertEqual(group_clips([]), [])


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required to synthesise test clips")
class TestMeasurementAgainstRealClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.clips = {
            "warm": synth_colour(cls.tmp / "warm.mp4", "0xCC7733"),
            "cool": synth_colour(cls.tmp / "cool.mp4", "0x3377CC"),
            "dark": synth_colour(cls.tmp / "dark.mp4", "0x202020"),
            "bright": synth_colour(cls.tmp / "bright.mp4", "0xE8E8E8"),
        }

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_measures_a_warm_clip_as_warm(self):
        m = measure_clip(self.clips["warm"])
        self.assertEqual(m["cast"], "warm")
        self.assertGreater(m["frames_measured"], 0)
        print(f"[✓] Orange clip measured warm (luma {m['y_avg']:.0f}, "
              f"strength {m['cast_strength']:.1f})")

    def test_measures_a_cool_clip_as_cool(self):
        self.assertEqual(measure_clip(self.clips["cool"])["cast"], "cool")

    def test_measures_exposure_in_the_right_direction(self):
        dark = measure_clip(self.clips["dark"])
        bright = measure_clip(self.clips["bright"])
        self.assertLess(dark["y_avg"], bright["y_avg"])
        self.assertIn("under-exposed", dark["exposure_notes"])
        self.assertIn("over-exposed", bright["exposure_notes"])
        self.assertGreater(suggest_correction(dark)["exposure_ev"], 0)
        self.assertLess(suggest_correction(bright)["exposure_ev"], 0)
        print(f"[✓] Dark clip luma {dark['y_avg']:.0f} -> "
              f"{suggest_correction(dark)['exposure_ev']:+.2f} EV, bright "
              f"{bright['y_avg']:.0f} -> {suggest_correction(bright)['exposure_ev']:+.2f} EV")

    def test_grey_clips_read_as_neutral(self):
        """A grey frame has no cast; if it reads as one the chroma maths is wrong."""
        for name in ("dark", "bright"):
            self.assertEqual(measure_clip(self.clips[name])["cast"], "neutral")
        print("[✓] Grey clips read neutral, so the chroma axes are not skewed")

    def test_missing_file_raises(self):
        with self.assertRaises(RuntimeError):
            measure_clip(self.tmp / "nope.mp4")

    def test_report_is_written(self):
        measurements = [measure_clip(p) for p in self.clips.values()]
        for m, cid in zip(measurements, self.clips):
            m["clip_id"] = cid
        groups = group_clips(measurements)
        out = self.tmp / "report.md"
        write_report(out, measurements, groups)
        text = out.read_text(encoding="utf-8")
        self.assertIn("# Grade plan", text)
        self.assertIn("Clips to look at", text)
        self.assertIn("evidence, not a verdict", text,
                      "the report must state the limits of frame averages")
        print(f"[✓] Grade report written for {len(groups)} groups")


if __name__ == "__main__":
    unittest.main(verbosity=2)
