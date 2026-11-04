#!/usr/bin/env python3
"""Tests for edit planning and EDL-driven FCPXML export.

A synthetic wedding job is built on disk (clips, tags, people, a song map) and
the planner is run against it, so these tests exercise the real code path from
ingested footage through to an FCPXML document Final Cut Pro can open.

The assertions that matter most are the ones the previous suite never made:
that each deliverable lands inside the runtime the brief requires, that the
rituals come out in the order they actually happen, that nobody known to the
job is left out of the cut, and that no generated file carries a local machine
path.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from common import work_dir, write_json, write_jsonl  # noqa: E402
from fcpxml_generator import (DeliverableSpecError, build_from_edl,  # noqa: E402
                              check_deliverable_duration)
from plan_edit import (load_job, load_rituals, plan_master, plan_teaser,  # noqa: E402
                       plan_trailer, snap_to_beats, validate_edl)

ROLES = ["G01", "B01", "GF01", "GM01", "BF01", "BM01",
         "B_SIB01", "G_SIB01", "B_DADA", "G_DADI"]


def build_job(root: Path, clips_per_ritual: int = 13, seed: int = 11,
              rare_people: tuple[str, ...] = ("G_DADI", "B_DADA"),
              unfilmed_person: str | None = None,
              with_song: bool = True) -> Path:
    """Synthesise a wedding job: clips across every ritual, tags, people, song.

    Everyone in `rare_people` is placed in exactly one clip each, to check that
    the planner's coverage logic keeps a barely-filmed relative in the edit.

    `unfilmed_person` is added to people.json but to no clip at all, which is a
    genuinely different case: they cannot be included, and the planner is
    expected to report them rather than quietly omit them.
    """
    import random

    rng = random.Random(seed)
    work = work_dir(root)
    rituals = load_rituals()

    clips = []
    n = 0
    # Place each rare person in one clip, spaced apart so they land in
    # different rituals.
    rare_slots = {5 + i * 7: person for i, person in enumerate(rare_people)}
    for ritual in rituals:
        key = ritual["id"].split("_", 1)[1]
        for _ in range(clips_per_ritual):
            n += 1
            cid = f"c{n:04d}"
            dur = round(rng.uniform(40.0, 260.0), 2)
            clips.append({
                "id": cid, "kind": "video", "duration": dur,
                "path": f"/Volumes/WEDDING_MEDIA/{key}/{cid}.mov",
                "ritual_phase": key,
            })
            subs = set()
            if rng.random() < 0.7:
                subs.add("G01")
            if rng.random() < 0.7:
                subs.add("B01")
            for role in ROLES[2:8]:
                if rng.random() < 0.3:
                    subs.add(role)
            if n in rare_slots:
                subs.add(rare_slots[n])
            write_json(work / "tags" / f"{cid}.json", {
                "clip_id": cid, "subjects": sorted(subs),
                "ritual_phase": key, "duration": dur,
            })

    write_jsonl(work / "clips.jsonl", clips)

    roles = [r for r in ROLES if r in set(ROLES[:8]) or r in rare_people]
    if unfilmed_person:
        roles.append(unfilmed_person)
    write_json(work / "faces" / "people.json", {
        "total_people": len(roles),
        "people": [{"person_id": r, "face_count": 10, "clip_count": 3,
                    "clips": [], "rituals": []} for r in roles],
    })

    if with_song:
        bpm = 128.0
        beat = 60.0 / bpm
        write_json(work / "songs" / "sangeet_mashup.json", {
            "source": "sangeet_mashup.wav", "duration": 400.0, "bpm": bpm,
            "bpm_confidence": 0.8, "steady_tempo": True,
            "beats": [round(i * beat, 4) for i in range(int(400 / beat))],
            "downbeats": [], "sections": [],
        })
    return work


class TestRitualOrdering(unittest.TestCase):
    def test_rituals_are_in_calendar_order(self):
        """The running order comes from the data, not from guesswork."""
        rituals = load_rituals()
        self.assertEqual(len(rituals), 16)
        offsets = [r["days_offset"] for r in rituals]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(rituals[0]["id"], "R01_cheka_tilak")
        self.assertEqual(rituals[-1]["id"], "R16_reception_bahubhoj")
        print(f"[✓] 16 rituals ordered from day {offsets[0]} to day {offsets[-1]}")


class TestRitualMatching(unittest.TestCase):
    """Clips must land in the right ritual, matched on words not substrings."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.work = build_job(Path(cls._tmp.name) / "job")
        cls.job = load_job(cls.work)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_no_clip_belongs_to_two_rituals(self):
        """"daan" is a substring of "kanyadaan", which must not create a match.

        Substring matching assigned every kanyadaan clip to sindoor_daan too,
        so both chapters of the master film were built from the wrong rushes.
        """
        from plan_edit import group_by_ritual, match_ritual_clips

        buckets = group_by_ritual(self.job)
        owners: dict[str, list[str]] = {}
        for ritual in self.job["rituals"]:
            for clip in match_ritual_clips(ritual, buckets):
                owners.setdefault(clip["id"], []).append(ritual["id"])
        clashes = {cid: rs for cid, rs in owners.items() if len(rs) > 1}
        self.assertEqual(clashes, {},
                         f"clips claimed by more than one ritual: {list(clashes.items())[:3]}")
        print(f"[\u2713] All {len(owners)} matched clips belong to exactly one ritual")

    def test_less_specific_tag_still_matches(self):
        """A clip tagged just "haldi" belongs to the ritual "haldi_ubtan"."""
        from plan_edit import match_ritual_clips

        ritual = next(r for r in self.job["rituals"] if r["id"] == "R05_haldi_ubtan")
        matched = match_ritual_clips(ritual, {"haldi": [{"id": "x", "duration": 10.0}]})
        self.assertEqual(len(matched), 1)

    def test_unrelated_tag_does_not_match(self):
        from plan_edit import match_ritual_clips

        ritual = next(r for r in self.job["rituals"] if r["id"] == "R11_sindoor_daan")
        self.assertEqual(
            match_ritual_clips(ritual, {"kanyadaan": [{"id": "y", "duration": 10.0}]}), [])


class TestPlanning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.work = build_job(Path(cls._tmp.name) / "job")
        cls.job = load_job(cls.work)
        cls.fps = Fraction(25)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_job_loaded(self):
        self.assertGreater(len(self.job["clips"]), 100)
        self.assertEqual(len(self.job["tags"]), len(self.job["clips"]))
        self.assertEqual(len(self.job["people"]["people"]), len(ROLES))

    def _check(self, edl, label):
        lo, hi = edl["spec"]["min_sec"], edl["spec"]["max_sec"]
        self.assertGreaterEqual(
            edl["duration"], lo,
            f"{label} is {edl['duration']:.1f}s, under the {lo:.0f}s the brief requires")
        self.assertLessEqual(
            edl["duration"], hi,
            f"{label} is {edl['duration']:.1f}s, over the {hi:.0f}s the brief allows")
        self.assertEqual(edl["issues"], [], f"{label} reported issues: {edl['issues']}")
        return edl

    def test_teaser_is_one_to_three_minutes(self):
        edl = self._check(plan_teaser(self.job, self.fps), "teaser")
        print(f"[✓] Teaser {edl['duration']:.1f}s ({edl['duration']/60:.1f} min), "
              f"{edl['event_count']} shots")

    def test_trailer_is_five_to_ten_minutes(self):
        """The shipped trailer was 175s against a 5-10 minute requirement."""
        edl = self._check(plan_trailer(self.job, self.fps), "trailer")
        self.assertGreaterEqual(edl["duration"], 300.0)
        print(f"[✓] Trailer {edl['duration']:.1f}s ({edl['duration']/60:.1f} min), "
              f"{edl['event_count']} shots")

    def test_master_is_one_to_three_hours(self):
        edl = self._check(plan_master(self.job, self.fps), "master")
        print(f"[✓] Master {edl['duration']/3600:.2f} h, {edl['event_count']} shots")

    def test_every_deliverable_covers_every_ritual(self):
        for name, fn in [("teaser", plan_teaser), ("trailer", plan_trailer),
                         ("master", plan_master)]:
            edl = fn(self.job, self.fps)
            self.assertEqual(len(edl["rituals_covered"]), 16,
                             f"{name} should touch all 16 rituals")
        print("[✓] All three deliverables cover all 16 rituals")

    def test_rituals_appear_in_chronological_order(self):
        """Point 7: the rituals must run in the order they actually happen."""
        order = [r["id"] for r in load_rituals()]
        for name, fn in [("teaser", plan_teaser), ("trailer", plan_trailer),
                         ("master", plan_master)]:
            edl = fn(self.job, self.fps)
            seen = []
            for ev in edl["events"]:
                r = ev.get("ritual")
                if r and (not seen or seen[-1] != r):
                    seen.append(r)
            expected = [r for r in order if r in set(seen)]
            self.assertEqual(seen, expected, f"{name} is out of ritual order")
        print("[✓] Ritual order is chronological in all three deliverables")

    def test_barely_filmed_relative_is_not_dropped(self):
        """Point 6: a relative in a single clip must still make the cut."""
        for name, fn in [("teaser", plan_teaser), ("trailer", plan_trailer),
                         ("master", plan_master)]:
            edl = fn(self.job, self.fps)
            self.assertIn("G_DADI", edl["people_in_cut"],
                          f"{name} dropped the relative who appears in only one clip")
            self.assertEqual(edl["people_missing"], [], f"{name} left people out")
        print("[✓] Relative appearing in one clip kept in all three deliverables")

    def test_teaser_and_trailer_are_beat_synced_but_master_is_not(self):
        """Cuts land on beats for the short forms; the master follows rituals."""
        self.assertEqual(plan_teaser(self.job, self.fps)["bpm"], 128.0)
        self.assertEqual(plan_trailer(self.job, self.fps)["bpm"], 128.0)
        self.assertIsNone(plan_master(self.job, self.fps)["bpm"])
        print("[✓] Teaser and trailer beat-synced at 128 BPM, master is not")

    def test_trailer_has_three_acts(self):
        edl = plan_trailer(self.job, self.fps)
        acts = sorted({ev["act"] for ev in edl["events"] if ev.get("act")})
        self.assertEqual(len(acts), 3, f"expected three acts, got {acts}")
        print(f"[✓] Trailer built in three acts: {acts}")

    def test_master_marks_a_chapter_per_ritual(self):
        edl = plan_master(self.job, self.fps)
        chapters = [m["label"] for ev in edl["events"] for m in ev.get("markers", [])
                    if m["label"].startswith("CHAPTER:")]
        self.assertEqual(len(chapters), 16)
        print(f"[✓] Master carries {len(chapters)} chapter markers")


class TestBeatSnapping(unittest.TestCase):
    def test_durations_land_on_beats_within_one_frame(self):
        """Cuts fall on beats as closely as the frame grid permits.

        Exact beat alignment is not always possible: at 25 fps a 120 BPM beat
        is 12.5 frames, and an edit point has to be a whole frame. The frame
        grid wins, because a fractional frame is not representable in FCPXML,
        so the guarantee is a whole number of beats to within one frame, with
        the residual recorded per event as beat_error.
        """
        fps = 25
        frame = 1.0 / fps
        beat = 0.5  # 120 BPM
        snapped = snap_to_beats([{"duration": 2.3}, {"duration": 3.9},
                                 {"duration": 0.7}],
                                {"steady_tempo": True, "bpm": 120.0}, Fraction(fps))
        for ev in snapped:
            self.assertGreaterEqual(ev["beats"], 1)
            self.assertAlmostEqual(ev["duration"], ev["beats"] * beat, delta=frame)
            self.assertLessEqual(ev["beat_error"], frame / 2 + 1e-9)
            # The cut must sit exactly on a frame boundary.
            self.assertAlmostEqual(ev["duration"] * fps, round(ev["duration"] * fps),
                                   places=6)
        worst = max(ev["beat_error"] for ev in snapped)
        print(f"[✓] Cuts on beats within one frame "
              f"(worst error {worst*1000:.1f} ms, frame is {frame*1000:.0f} ms)")

    def test_beat_alignment_is_exact_when_grids_coincide(self):
        """At 120 BPM and 24 fps a beat is exactly 12 frames, so error is zero."""
        snapped = snap_to_beats([{"duration": 2.3}],
                                {"steady_tempo": True, "bpm": 120.0}, Fraction(24))
        self.assertEqual(snapped[0]["beat_error"], 0.0)
        print("[✓] Zero beat error when beat and frame grids coincide")

    def test_geet_without_steady_tempo_is_left_alone(self):
        """Live folk geet has no grid; forcing one would cut against the singing."""
        original = [{"duration": 2.3}, {"duration": 3.9}]
        snapped = snap_to_beats([dict(e) for e in original],
                                {"steady_tempo": False, "bpm": 0.0}, Fraction(25))
        self.assertEqual([e["duration"] for e in snapped],
                         [e["duration"] for e in original])
        print("[✓] Pulseless geet left unsnapped")


class TestValidation(unittest.TestCase):
    def test_short_plan_is_reported(self):
        edl = {"duration": 30.0, "spec": {"min_sec": 60.0, "max_sec": 180.0},
               "events": [{"path": "x", "clip_id": "c1"}], "people_missing": []}
        issues = validate_edl(edl)
        self.assertTrue(any("Too short" in i for i in issues))

    def test_long_plan_is_reported(self):
        edl = {"duration": 900.0, "spec": {"min_sec": 60.0, "max_sec": 180.0},
               "events": [{"path": "x", "clip_id": "c1"}], "people_missing": []}
        self.assertTrue(any("Too long" in i for i in validate_edl(edl)))

    def test_missing_people_are_reported(self):
        edl = {"duration": 90.0, "spec": {"min_sec": 60.0, "max_sec": 180.0},
               "events": [{"path": "x", "clip_id": "c1"}],
               "people_missing": ["B_DADA", "G_DADI"]}
        self.assertTrue(any("never appear" in i for i in validate_edl(edl)))

    def test_empty_plan_explains_itself(self):
        edl = {"duration": 0.0, "spec": {"min_sec": 60.0, "max_sec": 180.0},
               "events": [], "people_missing": []}
        issues = validate_edl(edl)
        self.assertTrue(any("No events" in i for i in issues))
        self.assertTrue(any("tagging" in i for i in issues))
        print("[✓] Empty plan explains the likely cause")

    def test_untagged_job_does_not_silently_produce_an_edit(self):
        """With no clips matching rituals, say so rather than exporting nothing."""
        with tempfile.TemporaryDirectory() as td:
            work = work_dir(Path(td) / "job")
            write_jsonl(work / "clips.jsonl", [
                {"id": "c1", "kind": "video", "duration": 30.0,
                 "path": "/m/c1.mov", "ritual_phase": "no_such_ritual"},
            ])
            edl = plan_teaser(load_job(work), Fraction(25))
            self.assertEqual(edl["event_count"], 0)
            self.assertTrue(edl["issues"])
            print("[✓] Untagged job reports the problem instead of faking a cut")

    def test_duration_spec_checker(self):
        ok, msg = check_deliverable_duration("teaser", 97.0)
        self.assertTrue(ok)
        ok, msg = check_deliverable_duration("trailer", 175.0)
        self.assertFalse(ok, "175s must not pass the 5-10 minute trailer spec")
        self.assertIn("short of", msg)
        with self.assertRaises(DeliverableSpecError):
            check_deliverable_duration("trailer", 175.0, strict=True)
        print("[✓] Runtime spec checker rejects the old 175s trailer")


class TestEdlToFcpxml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.work = build_job(cls.tmp / "job")
        cls.job = load_job(cls.work)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _export(self, kind, planner, **kw):
        edl = planner(self.job, Fraction(25))
        edl_path = self.work / "edl" / f"{kind}.json"
        write_json(edl_path, edl)
        out = build_from_edl(edl_path, self.tmp / "out" / f"{kind}.fcpxml", **kw)
        return edl, out

    def test_exports_valid_fcpxml_for_each_deliverable(self):
        for kind, planner in [("teaser", plan_teaser), ("trailer", plan_trailer),
                              ("master", plan_master)]:
            edl, out = self._export(kind, planner)
            self.assertTrue(out.exists())
            root = ET.parse(out).getroot()
            self.assertEqual(root.tag, "fcpxml")
            spine = root.find(".//spine")
            self.assertIsNotNone(spine)
            clips = spine.findall("asset-clip")
            self.assertEqual(len(clips), edl["event_count"],
                             f"{kind}: every planned event must reach the timeline")
        print("[✓] Valid FCPXML exported for teaser, trailer and master")

    def test_exported_files_contain_no_local_machine_paths(self):
        """The regression that leaked a username and employer into a public repo."""
        for kind, planner in [("teaser", plan_teaser), ("master", plan_master)]:
            _, out = self._export(kind, planner)
            text = out.read_text(encoding="utf-8")
            self.assertNotIn("/Users/", text)
            self.assertNotIn("/home/", text)
            self.assertNotIn("CloudStorage", text)
        print("[✓] No local machine paths in exported FCPXML")

    def test_media_root_resolves_relative_paths(self):
        """Relative clip paths resolve against media_root; absolute ones stand.

        An EDL from a real ingest carries absolute paths, which must be used
        exactly as recorded, so media_root only applies to relative ones.
        """
        edl = {
            "deliverable": "teaser", "fps": 25,
            "events": [{"clip_id": "rel", "path": "haldi/c1.mov",
                        "source_in": 0.0, "duration": 50.0},
                       {"clip_id": "abs", "path": "/Volumes/ALREADY/c2.mov",
                        "source_in": 0.0, "duration": 50.0}],
            "issues": [],
        }
        edl_path = self.tmp / "roots.json"
        write_json(edl_path, edl)
        out = build_from_edl(edl_path, self.tmp / "out" / "roots.fcpxml",
                             media_root="/Volumes/SHOOT2026")
        srcs = [a.get("src") for a in ET.parse(out).getroot().findall(".//asset")]
        self.assertTrue(any("/Volumes/SHOOT2026/haldi/c1.mov" in s for s in srcs),
                        "relative path should resolve against media_root")
        self.assertTrue(any("/Volumes/ALREADY/c2.mov" in s for s in srcs),
                        "absolute path must be preserved as recorded")
        print("[\u2713] media_root resolves relative paths, absolute paths preserved")

    def test_fcpxml_version_is_configurable(self):
        _, out = self._export("teaser", plan_teaser, fcpxml_version="1.13")
        self.assertEqual(ET.parse(out).getroot().get("version"), "1.13")
        print("[✓] FCPXML schema version configurable for newer Final Cut Pro")

    def test_asset_urls_are_percent_encoded(self):
        """Paths with spaces are not valid in a file:// URL unencoded."""
        edl = {
            "deliverable": "teaser", "fps": 25,
            "events": [{"clip_id": "c1", "path": "Media/Haldi Day One/shot 01.mov",
                        "source_in": 0.0, "duration": 90.0}],
            "issues": [],
        }
        edl_path = self.tmp / "spaces.json"
        write_json(edl_path, edl)
        out = build_from_edl(edl_path, self.tmp / "out" / "spaces.fcpxml")
        src = ET.parse(out).getroot().find(".//asset").get("src")
        self.assertNotIn(" ", src)
        self.assertIn("%20", src)
        print(f"[✓] Asset URL percent-encoded: ...{src[-34:]}")

    def test_empty_edl_raises_instead_of_writing_an_empty_timeline(self):
        edl_path = self.tmp / "empty.json"
        write_json(edl_path, {"deliverable": "teaser", "fps": 25, "events": [], "issues": []})
        with self.assertRaises(ValueError):
            build_from_edl(edl_path, self.tmp / "out" / "empty.fcpxml")
        print("[✓] Empty EDL raises rather than exporting a hollow timeline")

    def test_strict_mode_rejects_out_of_spec_timeline(self):
        edl = {
            "deliverable": "trailer", "fps": 25,
            "events": [{"clip_id": "c1", "path": "/m/a.mov",
                        "source_in": 0.0, "duration": 30.0}],
            "issues": [],
        }
        edl_path = self.tmp / "shorttrailer.json"
        write_json(edl_path, edl)
        with self.assertRaises(DeliverableSpecError):
            build_from_edl(edl_path, self.tmp / "out" / "short.fcpxml", strict=True)
        print("[✓] Strict mode refuses a 30s trailer")


if __name__ == "__main__":
    unittest.main(verbosity=2)
