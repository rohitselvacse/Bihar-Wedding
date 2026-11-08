#!/usr/bin/env python3
"""Measure each clip's exposure and colour, and group clips that need one grade.

The brief calls colour correction, colour grading and lighting "very very
important".

What this does, per clip:
  1. Exposure and cast across the whole frame via ffmpeg signalstats:
     * y_avg, y_min, y_max (exposure, contrast, highlight/shadow clipping)
     * u_avg, v_avg (chroma averages; 128 is neutral on both axes)
     * cast (warm / cool / green / magenta / neutral) and strength
  2. Face region skin tone measurement via OpenCV FaceDetectorYN (YuNet):
     * Finds human face regions in video frames
     * Samples the inner cheek/forehead patch to avoid hair and background
     * Measures skin luma (target: 45–55% IRE for Indian skin tones)
     * Computes vectorscope angle on the (U-128, V-128) plane
     * Evaluates deviation from the canonical Vectorscope Flesh Line (10:30 clock axis)
     * Recommends specific FCPX Hue-vs-Hue adjustments for Haldi yellow or LED magenta spills

Output:
    <work>/grade/measurements.json   per clip
    <work>/grade/plan.json           groups, with a suggested correction each
    <work>/grade/report.md           the same, readable
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import die, load_clips, work_dir, write_json  # noqa: E402

# Rec.709 8-bit. 128 is neutral on both chroma axes; U carries blue-yellow and
# V carries red-cyan.
NEUTRAL = 128.0

# A scene averaging below or above this is likely under or over exposed.
Y_LOW = 70.0
Y_HIGH = 170.0

# Chroma distance from neutral below which a clip is called neutral.
CAST_NEUTRAL = 6.0

# How close two clips must be, in luma and chroma, to share a grade group.
GROUP_Y_TOL = 22.0
GROUP_UV_TOL = 12.0

STATS = ["YAVG", "YMIN", "YMAX", "UAVG", "VAVG", "SATAVG"]

# Vectorscope Flesh Line (I-bar) sits in top-left quadrant at ~10:30 clock face,
# corresponding to ~125 degrees in Cartesian (U-128, V-128) plane.
CANONICAL_FLESH_LINE_DEG = 125.0
FLESH_LINE_TOLERANCE_DEG = 14.0


def load_face_detector(model_path: Path | None = None, score_thresh: float = 0.5):
    """Load OpenCV FaceDetectorYN (YuNet) model for face detection."""
    try:
        import cv2  # type: ignore
    except ImportError:
        return None
    if not hasattr(cv2, "FaceDetectorYN"):
        return None

    candidate_paths = [
        model_path,
        BASE_DIR / "models" / "face_detection_yunet_2023mar.onnx",
        Path.home() / ".cache" / "bihar_wedding" / "models" / "face_detection_yunet_2023mar.onnx",
    ]
    actual_model = None
    for p in candidate_paths:
        if p and Path(p).is_file():
            actual_model = Path(p)
            break
    if not actual_model:
        return None

    try:
        detector = cv2.FaceDetectorYN.create(
            str(actual_model), "", (320, 240), score_thresh, 0.3, 5000
        )
        return detector
    except Exception:
        return None


def measure_skin_from_face_patch(patch_bgr) -> dict:
    """Measure luma, chroma, vectorscope angle, and flesh line deviation from a face patch."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return {"skin_detected": False, "skin_status": "opencv_missing"}

    if patch_bgr is None or patch_bgr.size == 0:
        return {"skin_detected": False, "skin_status": "empty_patch"}

    ycrcb = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2YCrCb)
    y_vals = ycrcb[:, :, 0]
    cr_vals = ycrcb[:, :, 1]  # V (red difference)
    cb_vals = ycrcb[:, :, 2]  # U (blue difference)

    # Filter out hair, specular highlights, and deep shadows:
    # Standard human skin locus in YCrCb: Cr in [128, 190], Cb in [75, 135]
    skin_mask = (cr_vals >= 126) & (cr_vals <= 192) & (cb_vals >= 70) & (cb_vals <= 138) & (y_vals >= 35) & (y_vals <= 235)

    if np.sum(skin_mask) > 10:
        y_avg = float(np.mean(y_vals[skin_mask]))
        v_avg = float(np.mean(cr_vals[skin_mask]))
        u_avg = float(np.mean(cb_vals[skin_mask]))
    else:
        y_avg = float(np.mean(y_vals))
        v_avg = float(np.mean(cr_vals))
        u_avg = float(np.mean(cb_vals))

    du = u_avg - NEUTRAL
    dv = v_avg - NEUTRAL
    angle = math.degrees(math.atan2(dv, du))
    if angle < 0:
        angle += 360.0

    deviation = angle - CANONICAL_FLESH_LINE_DEG
    while deviation > 180:
        deviation -= 360
    while deviation < -180:
        deviation += 360

    if abs(deviation) <= FLESH_LINE_TOLERANCE_DEG:
        status = "on_flesh_line"
        rec = "Skin tones align with vectorscope flesh line. Preserve current balance."
    elif deviation < -FLESH_LINE_TOLERANCE_DEG:
        status = "magenta_tint"
        rec = "Skin tones skew magenta/red (LED spill). In FCPX Hue vs Hue, rotate skin qualifier slightly towards yellow."
    else:
        status = "yellow_tint"
        rec = "Skin tones skew yellow/haldi. In FCPX Hue vs Hue, rotate skin qualifier slightly towards red/orange."

    ire = round((y_avg / 255.0) * 100.0, 1)

    return {
        "skin_detected": True,
        "skin_y_avg": round(y_avg, 2),
        "skin_u_avg": round(u_avg, 2),
        "skin_v_avg": round(v_avg, 2),
        "skin_ire": ire,
        "flesh_line_angle": round(angle, 1),
        "flesh_line_deviation": round(deviation, 1),
        "skin_status": status,
        "fcp_recommendation": rec,
    }


def measure_clip_skin_tone(path: Path, max_samples: int = 5, detector=None) -> dict:
    """Sample video frames, detect faces with FaceDetectorYN, and measure skin tone."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return {"faces_detected": 0, "skin_status": "opencv_missing"}

    if detector is None:
        detector = load_face_detector()
    if detector is None:
        return {"faces_detected": 0, "skin_status": "detector_unavailable"}

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {"faces_detected": 0, "skin_status": "unreadable_clip"}

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
    step = max(1, total_frames // (max_samples + 1))

    face_patches = []
    for i in range(1, max_samples + 1):
        frame_idx = i * step
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        h, w = frame.shape[:2]
        detector.setInputSize((w, h))
        try:
            _, faces = detector.detect(frame)
        except Exception:
            continue

        if faces is not None and len(faces) > 0:
            for f in faces:
                if f[-1] < 0.5:
                    continue
                fx, fy, fw, fh = f[:4].astype(int)
                # Crop inner 60% of face box
                cx = max(0, int(fx + fw * 0.2))
                cy = max(0, int(fy + fh * 0.2))
                cw = min(w - cx, int(fw * 0.6))
                ch = min(h - cy, int(fh * 0.6))
                if cw > 5 and ch > 5:
                    face_patches.append(frame[cy:cy+ch, cx:cx+cw])

    cap.release()

    if not face_patches:
        return {
            "faces_detected": 0,
            "skin_status": "no_faces_detected",
            "note": "Non-character shot or profile angles; grade by whole-frame exposure."
        }

    # Aggregate skin measurements across all face patches
    all_y, all_u, all_v, all_dev = [], [], [], []
    for patch in face_patches:
        m = measure_skin_from_face_patch(patch)
        if m.get("skin_detected"):
            all_y.append(m["skin_y_avg"])
            all_u.append(m["skin_u_avg"])
            all_v.append(m["skin_v_avg"])
            all_dev.append(m["flesh_line_deviation"])

    if not all_y:
        return {"faces_detected": len(face_patches), "skin_status": "no_skin_pixels"}

    avg_y = sum(all_y) / len(all_y)
    avg_u = sum(all_u) / len(all_u)
    avg_v = sum(all_v) / len(all_v)
    avg_dev = sum(all_dev) / len(all_dev)

    du = avg_u - NEUTRAL
    dv = avg_v - NEUTRAL
    angle = math.degrees(math.atan2(dv, du))
    if angle < 0:
        angle += 360.0

    if abs(avg_dev) <= FLESH_LINE_TOLERANCE_DEG:
        status = "on_flesh_line"
        rec = "Skin tones align with vectorscope flesh line. Preserve current balance."
    elif avg_dev < -FLESH_LINE_TOLERANCE_DEG:
        status = "magenta_tint"
        rec = "Skin tones skew magenta/red (LED spill). In FCPX Hue vs Hue, rotate skin qualifier slightly towards yellow."
    else:
        status = "yellow_tint"
        rec = "Skin tones skew yellow/haldi. In FCPX Hue vs Hue, rotate skin qualifier slightly towards red/orange."

    return {
        "faces_detected": len(face_patches),
        "skin_y_avg": round(avg_y, 2),
        "skin_u_avg": round(avg_u, 2),
        "skin_v_avg": round(avg_v, 2),
        "skin_ire": round((avg_y / 255.0) * 100.0, 1),
        "flesh_line_angle": round(angle, 1),
        "flesh_line_deviation": round(avg_dev, 1),
        "skin_status": status,
        "fcp_recommendation": rec,
    }


def measure_clip(path: Path, max_frames: int = 60, measure_skin: bool = True) -> dict:
    """Read exposure and chroma statistics from a clip with ffmpeg, and skin tone via FaceDetectorYN."""
    entries = ",".join(f"lavfi.signalstats.{s}" for s in STATS)
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-f", "lavfi",
         f"movie={path},signalstats",
         "-show_entries", f"frame_tags={entries}",
         "-of", "csv=p=0", "-read_intervals", f"%+#{max_frames}"],
        capture_output=True, text=True,
    )
    rows = [r for r in proc.stdout.strip().splitlines() if r.strip()]
    if not rows:
        detail = proc.stderr.strip()[-200:]
        raise RuntimeError(f"could not measure {path.name}: {detail}")

    acc = {s: [] for s in STATS}
    for row in rows:
        parts = row.split(",")
        for key, value in zip(STATS, parts):
            try:
                acc[key].append(float(value))
            except (TypeError, ValueError):
                continue

    def mean(key: str) -> float:
        vals = acc[key]
        return sum(vals) / len(vals) if vals else 0.0

    y_avg, u_avg, v_avg = mean("YAVG"), mean("UAVG"), mean("VAVG")
    y_min, y_max = mean("YMIN"), mean("YMAX")

    res = {
        "source": path.name,
        "frames_measured": len(rows),
        "y_avg": round(y_avg, 2),
        "y_min": round(y_min, 2),
        "y_max": round(y_max, 2),
        "u_avg": round(u_avg, 2),
        "v_avg": round(v_avg, 2),
        "sat_avg": round(mean("SATAVG"), 2),
        "contrast": round(y_max - y_min, 2),
        **classify_cast(u_avg, v_avg),
        **classify_exposure(y_avg, y_min, y_max),
    }

    if measure_skin:
        try:
            res["skin_tone"] = measure_clip_skin_tone(path)
        except Exception:
            res["skin_tone"] = {"faces_detected": 0, "skin_status": "measurement_error"}

    return res


def classify_cast(u_avg: float, v_avg: float) -> dict:
    """Name the colour cast from the chroma averages.

    U above neutral is blue and below it is yellow; V above neutral is red and
    below it is cyan. A warm cast therefore shows as low U with high V, which
    is how tungsten light and a sunlit haldi courtyard both read.
    """
    du, dv = u_avg - NEUTRAL, v_avg - NEUTRAL
    strength = math.hypot(du, dv)

    if strength < CAST_NEUTRAL:
        cast = "neutral"
    elif du < 0 and dv > 0:
        cast = "warm"
    elif du > 0 and dv < 0:
        cast = "cool"
    elif du < 0 and dv < 0:
        cast = "green"
    else:
        cast = "magenta"

    return {"cast": cast, "cast_strength": round(strength, 2),
            "u_offset": round(du, 2), "v_offset": round(dv, 2)}


def classify_exposure(y_avg: float, y_min: float, y_max: float) -> dict:
    """Flag exposure problems and clipping."""
    notes = []
    if y_avg < Y_LOW:
        notes.append("under-exposed")
    elif y_avg > Y_HIGH:
        notes.append("over-exposed")
    if y_max >= 250:
        notes.append("highlights clipped")
    if y_min <= 4:
        notes.append("shadows crushed")
    if (y_max - y_min) < 40:
        notes.append("very low contrast (flat or log footage)")
    return {"exposure_notes": notes}


def suggest_correction(stats: dict) -> dict:
    """A starting correction for a clip or group, as values and an ffmpeg filter.

    Exposure is expressed in stops, since that is how a colourist thinks and
    how Final Cut Pro's exposure control behaves. Chroma is expressed as the
    offset to remove.
    """
    y = stats["y_avg"]
    target_y = 110.0  # a reasonable mid for a graded Rec.709 scene average

    ev = math.log2(target_y / y) if y > 1 else 0.0
    ev = max(-2.5, min(2.5, ev))

    du, dv = stats["u_offset"], stats["v_offset"]

    gamma = round(2 ** (ev / 2.2), 4)
    filters = [f"eq=gamma={gamma}"]
    if stats["cast"] != "neutral":
        rs = round(-dv / 255.0, 4)
        bs = round(-du / 255.0, 4)
        filters.append(f"colorbalance=rm={rs}:bm={bs}")

    return {
        "exposure_ev": round(ev, 2),
        "remove_u_offset": round(-du, 2),
        "remove_v_offset": round(-dv, 2),
        "ffmpeg_preview_filter": ",".join(filters),
        "note": ("Starting point only. Whole-frame averages cannot tell a wrong "
                 "white balance from a red lehenga filling the frame."),
    }


def group_clips(measurements: list[dict]) -> list[dict]:
    """Group clips whose look is close enough to share one correction."""
    groups: list[dict] = []
    for m in measurements:
        placed = False
        for g in groups:
            if (abs(m["y_avg"] - g["y_avg"]) <= GROUP_Y_TOL
                    and abs(m["u_avg"] - g["u_avg"]) <= GROUP_UV_TOL
                    and abs(m["v_avg"] - g["v_avg"]) <= GROUP_UV_TOL):
                n = len(g["clips"])
                for key in ("y_avg", "u_avg", "v_avg"):
                    g[key] = (g[key] * n + m[key]) / (n + 1)
                g["clips"].append(m.get("clip_id") or m["source"])
                placed = True
                break
        if not placed:
            groups.append({
                "group_id": f"grade_{len(groups) + 1:02d}",
                "y_avg": m["y_avg"], "u_avg": m["u_avg"], "v_avg": m["v_avg"],
                "clips": [m.get("clip_id") or m["source"]],
            })

    for g in groups:
        rounded = {"y_avg": round(g["y_avg"], 2),
                   "u_avg": round(g["u_avg"], 2), "v_avg": round(g["v_avg"], 2)}
        g.update(rounded)
        g.update(classify_cast(g["u_avg"], g["v_avg"]))
        g["clip_count"] = len(g["clips"])
        g["correction"] = suggest_correction({**rounded, **classify_cast(g["u_avg"], g["v_avg"])})

    groups.sort(key=lambda g: -g["clip_count"])
    return groups


def write_report(path: Path, measurements: list[dict], groups: list[dict]) -> None:
    L = ["# Grade plan", "",
         f"Measured {len(measurements)} clips with ffmpeg signalstats and grouped them "
         f"into {len(groups)} looks.", "",
         "Whole-frame averages: treat a cast reading as evidence, not a verdict. "
         "The useful signal here is which clips do not match their neighbours.", "",
         "## Grade groups", "",
         "| Group | Clips | Luma | Cast | Strength | Push (EV) | ffmpeg preview |",
         "| :--- | ---: | ---: | :--- | ---: | ---: | :--- |"]
    for g in groups:
        c = g["correction"]
        L.append(f"| `{g['group_id']}` | {g['clip_count']} | {g['y_avg']:.0f} | {g['cast']} | "
                 f"{g['cast_strength']:.1f} | {c['exposure_ev']:+.2f} EV | "
                 f"`{c['ffmpeg_preview_filter']}` |")

    # Skin Tone Analysis section
    skin_clips = [m for m in measurements if m.get("skin_tone", {}).get("faces_detected", 0) > 0]
    L += ["", "## Skin tone & Vectorscope alignment", ""]
    if skin_clips:
        L.append("| Clip | Faces | Skin IRE | Vectorscope Angle | Deviation | Status | FCP Recommendation |")
        L.append("| :--- | ---: | ---: | ---: | ---: | :--- | :--- |")
        for m in skin_clips:
            st = m["skin_tone"]
            L.append(f"| {m['source']} | {st['faces_detected']} | {st.get('skin_ire', 0):.1f}% | "
                     f"{st.get('flesh_line_angle', 0):.1f}° | {st.get('flesh_line_deviation', 0):+.1f}° | "
                     f"`{st.get('skin_status', 'unknown')}` | {st.get('fcp_recommendation', '—')} |")
    else:
        L.append("No human faces were detected in the sampled clips.")

    flagged = [m for m in measurements if m["exposure_notes"]]
    L += ["", "## Clips to look at", ""]
    if flagged:
        L.append("| Clip | Luma | Cast | Notes |")
        L.append("| :--- | ---: | :--- | :--- |")
        for m in sorted(flagged, key=lambda x: x["y_avg"]):
            L.append(f"| {m['source']} | {m['y_avg']:.0f} | {m['cast']} | "
                     f"{', '.join(m['exposure_notes'])} |")
    else:
        L.append("No clip was flagged for exposure or clipping.")
    L += ["", "## Preview a correction", "",
          "```bash",
          "ffmpeg -i <clip> -vf \"<preview filter from the table>\" -t 10 preview.mp4",
          "```", "",
          "These filters are for judging the correction, not for delivery. Apply the "
          "equivalent in Final Cut Pro so the grade stays non-destructive.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Measure exposure, colour, and face skin tones, and group clips needing one grade.")
    ap.add_argument("--work", type=Path, required=True, help="Work folder for this wedding job")
    ap.add_argument("inputs", nargs="*", type=Path,
                    help="Media files. Omit to use the work folder's clips.jsonl")
    ap.add_argument("--max-frames", type=int, default=60,
                    help="Frames to sample per clip (default 60)")
    ap.add_argument("--no-skin", action="store_true",
                    help="Skip facial skin tone detection")
    args = ap.parse_args()

    work = work_dir(args.work)

    media: list[tuple[str, Path]] = []
    if args.inputs:
        media = [(p.stem, p) for p in args.inputs]
    else:
        media = [(c["id"], Path(c["path"])) for c in load_clips(work, "video")]
    if not media:
        die("No inputs given and no video clips in the work folder. "
            "Run raw_footage_ingest.py first, or pass files directly.", 2)

    measurements: list[dict] = []
    failures = 0
    for cid, path in media:
        if not path.exists():
            print(f"[!] missing: {path}")
            failures += 1
            continue
        try:
            m = measure_clip(path, args.max_frames, measure_skin=not args.no_skin)
        except Exception as e:  # noqa: BLE001
            print(f"[!] {path.name}: {e}")
            failures += 1
            continue
        m["clip_id"] = cid
        measurements.append(m)
        notes = f"  {', '.join(m['exposure_notes'])}" if m["exposure_notes"] else ""
        skin_info = ""
        if "skin_tone" in m and m["skin_tone"].get("faces_detected", 0) > 0:
            st = m["skin_tone"]
            skin_info = f" | skin IRE {st.get('skin_ire', 0):.0f}%, {st.get('skin_status')}"
        print(f"[✓] {path.name}: luma {m['y_avg']:.0f}, {m['cast']} "
              f"({m['cast_strength']:.1f}){skin_info}{notes}")

    if not measurements:
        die("Nothing could be measured.", 1)

    groups = group_clips(measurements)
    write_json(work / "grade" / "measurements.json",
               {"clip_count": len(measurements), "clips": measurements})
    write_json(work / "grade" / "plan.json",
               {"group_count": len(groups), "groups": groups})
    write_report(work / "grade" / "report.md", measurements, groups)

    print(f"\n[✓] {len(measurements)} clips in {len(groups)} grade group(s)")
    for g in groups:
        print(f"    {g['group_id']}  {g['clip_count']:>4} clips  luma {g['y_avg']:>5.0f}  "
              f"{g['cast']:<8} {g['correction']['exposure_ev']:+.2f} EV")
    print(f"[✓] {work / 'grade' / 'report.md'}")

    if failures:
        print(f"[!] {failures} clip(s) could not be measured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
