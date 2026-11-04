#!/usr/bin/env python3
"""Tests for same-person matching across clips.

The clustering is tested against synthetic embeddings whose true identities are
known, so accuracy is measured rather than asserted. Frame sampling is tested
against video synthesised with ffmpeg.

A note on the synthetic embeddings, because getting this wrong invalidates the
whole test. For e = (base + n)/||base + n|| with n drawn from N(0, s^2 I_D),
the expected cosine similarity between two faces of one identity is about
1/(1 + s^2 D). In 512 dimensions a per-dimension sigma of 0.8 gives noise of
norm ~18 against a signal of norm 1, so every embedding is effectively pure
noise and one-cluster-per-face is the correct answer. sigma must be derived
from the intra-person similarity being targeted, which `sigma_for` does.
Real ArcFace embeddings sit around 0.4-0.7 within an identity and below 0.3
across identities, so 0.6 is the realistic case.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from common import work_dir  # noqa: E402
from faces import (  # noqa: E402
    SAME_PERSON_THRESHOLD, _load_detector, audit_coverage, build_people,
    clip_ritual_map, cluster_embeddings, frame_time, l2_normalise,
    sample_frames, write_clip_tags,
)

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
DIM = 512


def sigma_for(target_cos: float, dim: int = DIM) -> float:
    """Noise sigma that yields a given intra-identity cosine similarity."""
    return float(np.sqrt((1.0 / target_cos - 1.0) / dim))


def synth_identities(n_people: int, per_person: int, intra_cos: float = 0.6,
                     seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Embeddings for n_people distinct identities, with known ground truth."""
    rng = np.random.default_rng(seed)
    s = sigma_for(intra_cos)
    bases = l2_normalise(rng.normal(size=(n_people, DIM)))
    embs, truth = [], []
    for i in range(n_people):
        for _ in range(per_person):
            embs.append(bases[i] + rng.normal(scale=s, size=DIM))
            truth.append(i)
    return l2_normalise(np.array(embs)), np.array(truth)


def purity(truth: np.ndarray, labels: np.ndarray) -> float:
    """Fraction of faces that sit in a cluster dominated by their true identity."""
    total = 0
    for c in set(labels.tolist()):
        members = truth[labels == c]
        total += np.unique(members, return_counts=True)[1].max()
    return total / len(truth)


class TestSyntheticDataIsValid(unittest.TestCase):
    """Guard the test fixture itself, since a bad fixture would hide real bugs."""

    def test_sigma_produces_the_intended_separation(self):
        for target in (0.5, 0.6, 0.7):
            emb, truth = synth_identities(5, 10, target)
            intra, inter = [], []
            for i in range(len(emb)):
                for j in range(i + 1, len(emb)):
                    (intra if truth[i] == truth[j] else inter).append(float(emb[i] @ emb[j]))
            self.assertAlmostEqual(float(np.mean(intra)), target, delta=0.05)
            self.assertLess(abs(float(np.mean(inter))), 0.1,
                            "different identities must be close to orthogonal")
        print("[✓] Synthetic embeddings calibrated to realistic ArcFace separation")


class TestClustering(unittest.TestCase):
    def test_recovers_known_number_of_people(self):
        for n_people, per in [(3, 12), (6, 10), (10, 8), (15, 6)]:
            emb, truth = synth_identities(n_people, per)
            labels = cluster_embeddings(emb)
            found = len(set(labels.tolist()))
            self.assertEqual(found, n_people,
                             f"{n_people} identities should yield {n_people} clusters, got {found}")
            self.assertEqual(purity(truth, labels), 1.0)
        print("[✓] Exact person count recovered for 3, 6, 10 and 15 identities")

    def test_tolerates_looser_and_tighter_identities(self):
        for intra in (0.5, 0.7):
            emb, truth = synth_identities(6, 10, intra)
            labels = cluster_embeddings(emb)
            self.assertEqual(len(set(labels.tolist())), 6)
            self.assertEqual(purity(truth, labels), 1.0)

    def test_result_does_not_depend_on_input_order(self):
        """The same wedding ingested in a different order must give the same people."""
        emb, _ = synth_identities(6, 10)
        rng = np.random.default_rng(1)
        order = rng.permutation(len(emb))

        first = cluster_embeddings(emb)
        second = cluster_embeddings(emb[order])[np.argsort(order)]

        def co_membership(labels):
            return {(i, j) for i in range(len(labels))
                    for j in range(i + 1, len(labels)) if labels[i] == labels[j]}

        a, b = co_membership(first), co_membership(second)
        agreement = len(a & b) / max(1, len(a | b))
        self.assertEqual(agreement, 1.0,
                         "clustering must be order independent after refinement")
        print("[✓] Clustering is order independent (agreement 1.000)")

    def test_distinct_people_are_not_merged(self):
        """Two people must never collapse into one, which would fake coverage."""
        emb, truth = synth_identities(2, 15)
        labels = cluster_embeddings(emb)
        self.assertEqual(len(set(labels.tolist())), 2)
        # Nobody from identity 0 may share a cluster with identity 1.
        for c in set(labels.tolist()):
            self.assertEqual(len(set(truth[labels == c].tolist())), 1)
        print("[✓] Distinct identities never merged")

    def test_empty_input_is_safe(self):
        self.assertEqual(len(cluster_embeddings(np.zeros((0, DIM), dtype=np.float32))), 0)

    def test_single_face_is_one_person(self):
        labels = cluster_embeddings(np.ones((1, DIM), dtype=np.float32))
        self.assertEqual(labels.tolist(), [0])

    def test_threshold_is_conservative_by_design(self):
        """Splitting a person is recoverable; merging two people is not."""
        self.assertLess(SAME_PERSON_THRESHOLD, 0.45)


class TestPeopleAndTags(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _scenario(self):
        """Four people across three clips, one of them in a single clip only."""
        rng = np.random.default_rng(7)
        s = sigma_for(0.6)
        bases = l2_normalise(rng.normal(size=(4, DIM)))
        plan = [
            (0, "cA", "haldi", 8), (0, "cB", "jaimala", 6), (0, "cC", "reception", 5),
            (1, "cA", "haldi", 6), (1, "cB", "jaimala", 4),
            (2, "cB", "jaimala", 5), (2, "cC", "reception", 4),
            (3, "cC", "reception", 2),
        ]
        faces, embs = [], []
        for pid, cid, ritual, n in plan:
            for k in range(n):
                embs.append(bases[pid] + rng.normal(scale=s, size=DIM))
                faces.append({"clip_id": cid, "time": float(k), "ritual_phase": ritual})
        labels = cluster_embeddings(l2_normalise(np.array(embs)))
        return faces, labels

    def test_people_ranked_by_appearance(self):
        """The couple and parents dominate a wedding, so rank by screen presence."""
        faces, labels = self._scenario()
        people = build_people(faces, labels)
        self.assertEqual(people["total_people"], 4)
        counts = [p["face_count"] for p in people["people"]]
        self.assertEqual(counts, sorted(counts, reverse=True))
        top = people["people"][0]
        self.assertEqual(top["clip_count"], 3)
        self.assertEqual(top["rituals"], ["haldi", "jaimala", "reception"])
        print(f"[✓] {people['total_people']} people ranked by appearance")

    def test_auto_ids_can_be_mapped_to_roles(self):
        faces, labels = self._scenario()
        people = build_people(faces, labels, {"person_001": "B01"})
        self.assertEqual(people["people"][0]["person_id"], "B01")
        self.assertEqual(people["people"][0]["auto_id"], "person_001")

    def test_person_in_one_clip_is_flagged_at_risk(self):
        """The whole point of point 6: nobody quietly dropped from the film."""
        faces, labels = self._scenario()
        people = build_people(faces, labels)
        audit = audit_coverage(people)
        self.assertEqual(audit["at_risk_count"], 1)
        self.assertEqual(audit["at_risk"][0]["clip_count"], 1)
        print(f"[✓] At-risk relative flagged: {audit['at_risk'][0]['person_id']}")

    def test_tags_are_written_for_the_continuity_auditor(self):
        """faces.py must produce the tag files family_face_tracker.py reads."""
        import json

        faces, labels = self._scenario()
        people = build_people(faces, labels)
        work = work_dir(self.tmp / "job")
        written = write_clip_tags(work, people, clip_ritual_map(faces))

        self.assertEqual(written, 3)
        tag = json.loads((work / "tags" / "cB.json").read_text())
        self.assertEqual(tag["clip_id"], "cB")
        self.assertEqual(tag["ritual_phase"], "jaimala",
                         "the clip's ritual must be carried into its tag file")
        self.assertEqual(tag["subjects_source"], "faces.py")
        self.assertEqual(len(tag["subjects"]), 3)
        print(f"[✓] Real tag files written for {written} clips")

    def test_clip_ritual_map_takes_the_dominant_phase(self):
        faces = [
            {"clip_id": "x", "ritual_phase": "haldi"},
            {"clip_id": "x", "ritual_phase": "haldi"},
            {"clip_id": "x", "ritual_phase": "sangeet"},
        ]
        self.assertEqual(clip_ritual_map(faces), {"x": "haldi"})


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg is required to synthesise test media")
class TestFrameSampling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.clip = cls.tmp / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:d=6",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cls.clip), "-y"],
            check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_samples_at_the_requested_rate(self):
        frames = sample_frames(self.clip, self.tmp / "f2", sample_fps=2.0)
        self.assertGreaterEqual(len(frames), 11)
        self.assertLessEqual(len(frames), 13)
        print(f"[✓] 6s clip at 2 fps produced {len(frames)} frames")

    def test_frame_index_maps_back_to_source_time(self):
        frames = sample_frames(self.clip, self.tmp / "f1", sample_fps=2.0)
        self.assertEqual(frame_time(frames[0], 2.0), 0.0)
        self.assertAlmostEqual(frame_time(frames[-1], 2.0), (len(frames) - 1) / 2.0, places=3)
        print("[✓] Frame timestamps recovered correctly")

    def test_missing_file_raises(self):
        with self.assertRaises(RuntimeError):
            sample_frames(self.tmp / "nope.mp4", self.tmp / "f3")


class TestDetectorAbsence(unittest.TestCase):
    def test_missing_insightface_gives_actionable_instructions(self):
        try:
            _load_detector()
        except RuntimeError as e:
            msg = str(e)
            self.assertIn("pip install", msg)
            self.assertIn("insightface", msg)
            print("[✓] Missing detector reports install instructions")
        else:
            self.skipTest("InsightFace is installed in this environment")


if __name__ == "__main__":
    unittest.main(verbosity=2)
