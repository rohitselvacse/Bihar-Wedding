#!/usr/bin/env python3
"""Find the same person across different clips, so no relative is left out.

This is point 6 of the brief: "a same person in the finding in the different
clips and different videos, so you need to take care about that person, that
the person is not getting missed in the video". Until now the project shipped
only an auditor that read tag files which nothing produced, fed by a
generate_mock_tags() helper, so the requirement was entirely unimplemented.

The pipeline here is:

  1. sample frames from every clip with ffmpeg
  2. detect faces and compute an embedding per face (needs InsightFace)
  3. cluster the embeddings so one cluster is one person
  4. write `<work>/faces/people.json`, and tag files naming who is in each clip
  5. audit coverage and report anyone at risk of being missed

Steps 1, 3, 4 and 5 need no machine-learning stack at all. Only step 2 needs
InsightFace, and the clustering works on embeddings from any source, so a
different detector can be substituted without touching the rest.

Scale
-----
The brief describes 500 to 1000 clips and six to seven hours of rushes, which
can yield tens of thousands of faces. An all-pairs distance matrix is not an
option at that size (50k faces would need about 10 GB), so clustering is
incremental against running centroids and then refined, which is linear in the
number of faces and quadratic only in the number of distinct people.

Naming
------
Clusters come out anonymous, as person_001 and so on, ranked by how much screen
time they have: at a wedding the couple and their parents dominate, so the
first few clusters are usually the people who matter most. Map them to real
roles with --name person_001=G01, and the rest of the pipeline, including
family_face_tracker.py, then works in terms of the standard role codes.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import clip_id, die, load_clips, read_json, work_dir, write_json  # noqa: E402

# Cosine similarity above which two ArcFace embeddings are taken to be the same
# person. ArcFace embeddings for one identity typically sit above 0.4 and
# different identities below 0.3. 0.38 is deliberately a little strict: at a
# wedding it is far better to split one person into two clusters, which a human
# merges in seconds, than to merge the bride with her sister and then "prove"
# she had plenty of screen time when she did not.
SAME_PERSON_THRESHOLD = 0.38

# How often to sample frames, in frames per second of source. Faces persist for
# seconds at a time, so two frames a second is ample and keeps a 7-hour rush to
# a manageable number of images.
DEFAULT_SAMPLE_FPS = 2.0


# ----------------------------------------------------------------- sampling

def sample_frames(media: Path, out_dir: Path, sample_fps: float = DEFAULT_SAMPLE_FPS,
                  max_frames: int | None = None) -> list[Path]:
    """Extract frames from a clip at a fixed rate, for face detection."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "f%06d.jpg")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(media),
           "-vf", f"fps={sample_fps}", "-q:v", "3"]
    if max_frames:
        cmd += ["-frames:v", str(max_frames)]
    cmd.append(pattern)

    proc = subprocess.run(cmd, capture_output=True)
    frames = sorted(out_dir.glob("f*.jpg"))
    if proc.returncode != 0 and not frames:
        detail = proc.stderr.decode("utf-8", errors="replace")[-300:].strip()
        raise RuntimeError(f"could not sample frames from {media.name}: {detail}")
    return frames


def frame_time(frame_path: Path, sample_fps: float = DEFAULT_SAMPLE_FPS) -> float:
    """Recover the source timestamp of a sampled frame from its index."""
    idx = int(frame_path.stem.lstrip("f"))
    return max(0.0, (idx - 1) / sample_fps)


# ---------------------------------------------------------------- clustering

def l2_normalise(emb: np.ndarray) -> np.ndarray:
    """Scale embeddings to unit length so a dot product is a cosine similarity."""
    emb = np.asarray(emb, dtype=np.float32)
    if emb.ndim == 1:
        emb = emb[None, :]
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return emb / norms


def cluster_embeddings(embeddings: np.ndarray, threshold: float = SAME_PERSON_THRESHOLD,
                       refine_passes: int = 3) -> np.ndarray:
    """Group face embeddings so that one cluster is one person.

    Assigns each face to the nearest existing centroid above `threshold`, or
    starts a new cluster, then alternates centroid recomputation with
    reassignment. The refinement matters: pure single-pass assignment depends on
    the order faces arrive in, so the same wedding ingested in a different order
    would give different people. Refining removes almost all of that.

    Returns an array of cluster labels, one per input embedding.
    """
    emb = l2_normalise(embeddings)
    n = emb.shape[0]
    if n == 0:
        return np.zeros(0, dtype=np.int32)

    # Pass 1: incremental assignment against running centroids.
    centroids = emb[0:1].copy()
    labels = np.zeros(n, dtype=np.int32)
    counts = [1]

    for i in range(1, n):
        sims = centroids @ emb[i]
        best = int(np.argmax(sims))
        if float(sims[best]) >= threshold:
            labels[i] = best
            # Running mean, renormalised so it stays a unit vector.
            c = centroids[best] * counts[best] + emb[i]
            centroids[best] = c / (np.linalg.norm(c) or 1.0)
            counts[best] += 1
        else:
            labels[i] = centroids.shape[0]
            centroids = np.vstack([centroids, emb[i]])
            counts.append(1)

    # Passes 2+: merge centroids that are really the same person, then
    # reassign every face to its nearest centroid.
    for _ in range(max(0, refine_passes)):
        centroids, labels = _merge_close_clusters(centroids, labels, threshold)
        new_labels = np.argmax(emb @ centroids.T, axis=1).astype(np.int32)
        if np.array_equal(new_labels, labels):
            labels = new_labels
            break
        labels = new_labels
        centroids = _recompute_centroids(emb, labels, centroids.shape[0])

    return _compact_labels(labels)


def _recompute_centroids(emb: np.ndarray, labels: np.ndarray, k: int) -> np.ndarray:
    dim = emb.shape[1]
    centroids = np.zeros((k, dim), dtype=np.float32)
    for c in range(k):
        members = emb[labels == c]
        if members.size:
            v = members.mean(axis=0)
            centroids[c] = v / (np.linalg.norm(v) or 1.0)
    # An empty cluster would have a zero centroid, whose similarity to
    # everything is 0; push it away so nothing is assigned to it.
    empty = np.linalg.norm(centroids, axis=1) == 0
    centroids[empty] = -1.0 / np.sqrt(dim)
    return centroids


def _merge_close_clusters(centroids: np.ndarray, labels: np.ndarray,
                          threshold: float) -> tuple[np.ndarray, np.ndarray]:
    """Merge clusters whose centroids are within the same-person threshold."""
    k = centroids.shape[0]
    if k < 2:
        return centroids, labels

    sim = centroids @ centroids.T
    np.fill_diagonal(sim, -1.0)

    parent = list(range(k))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a in range(k):
        for b in range(a + 1, k):
            if sim[a, b] >= threshold:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)

    mapping = {}
    for c in range(k):
        root = find(c)
        mapping.setdefault(root, len(mapping))
    new_labels = np.array([mapping[find(int(l))] for l in labels], dtype=np.int32)
    new_centroids = _recompute_centroids_from_labels(centroids, parent, mapping, k)
    return new_centroids, new_labels


def _recompute_centroids_from_labels(centroids, parent, mapping, k):
    dim = centroids.shape[1]
    out = np.zeros((len(mapping), dim), dtype=np.float32)
    counts = np.zeros(len(mapping), dtype=np.int32)

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    for c in range(k):
        tgt = mapping[find(c)]
        out[tgt] += centroids[c]
        counts[tgt] += 1
    for i in range(out.shape[0]):
        norm = np.linalg.norm(out[i])
        if norm:
            out[i] /= norm
    return out


def _compact_labels(labels: np.ndarray) -> np.ndarray:
    """Renumber labels so they run 0..k-1 with no gaps."""
    uniq = {}
    out = np.zeros_like(labels)
    for i, l in enumerate(labels):
        li = int(l)
        if li not in uniq:
            uniq[li] = len(uniq)
        out[i] = uniq[li]
    return out


# -------------------------------------------------------------------- people

def build_people(faces: list[dict], labels: np.ndarray,
                 name_map: dict[str, str] | None = None) -> dict:
    """Summarise clusters into people, ranked by how much they appear.

    `faces` is one record per detected face with at least clip_id and time.
    """
    name_map = name_map or {}
    by_cluster: dict[int, list[dict]] = {}
    for face, label in zip(faces, labels):
        by_cluster.setdefault(int(label), []).append(face)

    # Rank by appearance count: at a wedding the couple and parents dominate,
    # so the biggest clusters are the people most likely to matter.
    order = sorted(by_cluster.items(), key=lambda kv: -len(kv[1]))

    people = []
    for rank, (cluster, members) in enumerate(order, start=1):
        auto_id = f"person_{rank:03d}"
        clips = sorted({m["clip_id"] for m in members})
        rituals = sorted({m.get("ritual_phase", "unknown") for m in members})
        people.append({
            "person_id": name_map.get(auto_id, auto_id),
            "auto_id": auto_id,
            "cluster": cluster,
            "face_count": len(members),
            "clip_count": len(clips),
            "clips": clips,
            "rituals": rituals,
            "first_seen": {
                "clip_id": members[0]["clip_id"],
                "time": round(float(members[0].get("time", 0.0)), 2),
            },
        })

    return {
        "total_faces": len(faces),
        "total_people": len(people),
        "same_person_threshold": SAME_PERSON_THRESHOLD,
        "people": people,
    }


def clip_ritual_map(faces: list[dict]) -> dict[str, str]:
    """Most common ritual phase seen per clip, for tagging."""
    tally: dict[str, dict[str, int]] = {}
    for f in faces:
        cid = f["clip_id"]
        phase = f.get("ritual_phase") or "unknown"
        tally.setdefault(cid, {})
        tally[cid][phase] = tally[cid].get(phase, 0) + 1
    return {cid: max(counts, key=counts.get) for cid, counts in tally.items()}


def write_clip_tags(work: Path, people: dict,
                    clip_rituals: dict[str, str] | None = None) -> int:
    """Write per-clip tag files naming who appears, for the continuity auditor.

    family_face_tracker.py reads `<work>/tags/<clip_id>.json` and previously had
    no producer except mock data. This closes that loop with real detections.

    Note that the auditor reports against the standard role codes (G01, B01,
    GF01 and so on), so clusters still carrying auto ids contribute nothing to
    its per-role statistics. Map them with --name before relying on that audit;
    an anonymous cluster cannot be checked against a role nobody assigned it.
    """
    clip_rituals = clip_rituals or {}
    by_clip: dict[str, set[str]] = {}
    for person in people["people"]:
        for cid in person["clips"]:
            by_clip.setdefault(cid, set()).add(person["person_id"])

    tags_dir = work / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)
    for cid, subjects in by_clip.items():
        path = tags_dir / f"{cid}.json"
        existing = read_json(path, {}) or {}
        existing.update({
            "clip_id": cid,
            "subjects": sorted(subjects),
            "subjects_source": "faces.py",
        })
        ritual = clip_rituals.get(cid)
        if ritual:
            existing["ritual_phase"] = ritual
        else:
            existing.setdefault("ritual_phase", "unknown")
        existing.setdefault("duration", 5.0)
        write_json(path, existing)
    return len(by_clip)


def audit_coverage(people: dict, min_clips: int = 2) -> dict:
    """Flag people who barely appear, so nobody is quietly left out."""
    at_risk = [
        {"person_id": p["person_id"], "clip_count": p["clip_count"],
         "face_count": p["face_count"]}
        for p in people["people"] if p["clip_count"] < min_clips
    ]
    return {
        "total_people": people["total_people"],
        "at_risk_count": len(at_risk),
        "at_risk": at_risk,
        "note": ("People seen in fewer than "
                 f"{min_clips} clips risk being cut entirely. Review these before "
                 "locking the edit; a guest who appears once may still be an "
                 "important relative."),
    }


# ------------------------------------------------------------------ detector

def _load_detector(det_size: int = 640):
    """Return a callable(image_path) -> list of (embedding, bbox, score)."""
    try:
        import insightface  # type: ignore
        from insightface.app import FaceAnalysis  # type: ignore

        app = FaceAnalysis(name="buffalo_l")
        app.prepare(ctx_id=-1, det_size=(det_size, det_size))

        def detect(image_path: Path):
            import cv2  # type: ignore

            img = cv2.imread(str(image_path))
            if img is None:
                return []
            return [
                (f.normed_embedding, [float(v) for v in f.bbox], float(f.det_score))
                for f in app.get(img)
            ]

        return detect
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "Face detection needs InsightFace. Install it with:\n"
            "    pip install insightface onnxruntime opencv-python-headless\n"
            "Frame sampling, clustering, people.json, tag writing and the\n"
            "coverage audit all work without it, on embeddings from any source.\n"
            f"Import failed: {e}"
        ) from e


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Match the same person across clips so no relative is missed.")
    ap.add_argument("--work", type=Path, required=True, help="Work folder for this wedding job")
    ap.add_argument("inputs", nargs="*", type=Path,
                    help="Media files. Omit to use the work folder's clips.jsonl")
    ap.add_argument("--sample-fps", type=float, default=DEFAULT_SAMPLE_FPS)
    ap.add_argument("--threshold", type=float, default=SAME_PERSON_THRESHOLD,
                    help="Cosine similarity above which two faces are the same person")
    ap.add_argument("--max-frames-per-clip", type=int, default=None)
    ap.add_argument("--name", action="append", default=[], metavar="AUTO=ROLE",
                    help="Map an auto id to a role, e.g. --name person_001=G01")
    ap.add_argument("--sample-only", action="store_true",
                    help="Only sample frames; skip detection (needs no InsightFace)")
    args = ap.parse_args()

    work = work_dir(args.work)
    name_map = {}
    for pair in args.name:
        if "=" in pair:
            k, v = pair.split("=", 1)
            name_map[k.strip()] = v.strip()

    media_files = list(args.inputs)
    clip_meta = {}
    if not media_files:
        for c in load_clips(work, "video"):
            media_files.append(Path(c["path"]))
            clip_meta[Path(c["path"]).name] = c
    if not media_files:
        die("No inputs given and no video clips in the work folder. "
            "Run raw_footage_ingest.py first, or pass files directly.", 2)

    frames_root = work / "faces" / "frames"
    sampled: list[tuple[str, Path]] = []
    for m in media_files:
        if not m.exists():
            print(f"[!] missing: {m}")
            continue
        cid = clip_meta.get(m.name, {}).get("id") or clip_id(m.name)
        frames = sample_frames(m, frames_root / cid, args.sample_fps,
                               args.max_frames_per_clip)
        sampled += [(cid, f) for f in frames]
        print(f"[✓] {m.name}: {len(frames)} frames sampled")

    if args.sample_only:
        print(f"\n{len(sampled)} frames under {frames_root}")
        return 0

    try:
        detect = _load_detector()
    except RuntimeError as e:
        die(str(e), 3)

    faces: list[dict] = []
    embeddings: list[np.ndarray] = []
    for cid, frame in sampled:
        for emb, bbox, score in detect(frame):
            faces.append({
                "clip_id": cid,
                "time": frame_time(frame, args.sample_fps),
                "bbox": bbox,
                "det_score": score,
                "frame": frame.name,
                "ritual_phase": clip_meta.get(cid, {}).get("ritual_phase", "unknown"),
            })
            embeddings.append(np.asarray(emb, dtype=np.float32))

    if not faces:
        die("No faces detected in the sampled frames.", 1)

    labels = cluster_embeddings(np.vstack(embeddings), threshold=args.threshold)
    people = build_people(faces, labels, name_map)
    write_json(work / "faces" / "people.json", people)
    np.save(work / "faces" / "embeddings.npy", np.vstack(embeddings))

    tagged = write_clip_tags(work, people, clip_ritual_map(faces))
    audit = audit_coverage(people)
    write_json(work / "faces" / "coverage_audit.json", audit)

    print(f"\n[✓] {people['total_faces']} faces -> {people['total_people']} people")
    for p in people["people"][:10]:
        print(f"    {p['person_id']:<12} {p['face_count']:>5} faces  "
              f"{p['clip_count']:>4} clips")
    print(f"[✓] Wrote tags for {tagged} clips -> {work / 'tags'}")
    if audit["at_risk_count"]:
        print(f"[!] {audit['at_risk_count']} person(s) appear in fewer than 2 clips "
              f"and risk being cut entirely.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
