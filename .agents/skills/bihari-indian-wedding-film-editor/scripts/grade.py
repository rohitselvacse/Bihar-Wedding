#!/usr/bin/env python3
"""Measure each clip's exposure and colour, and group clips that need one grade.

The brief calls colour correction, colour grading and lighting "very very
important". Until now they were documented in references/02 and references/10
and nowhere else, so nothing measured a single frame of the footage.

What this does, per clip, using ffmpeg's signalstats:

    y_avg          average luma, which is exposure
    u_avg, v_avg   chroma averages; 128 is neutral on both axes
    cast           warm / cool / green / magenta / neutral, with a strength
    contrast       luma spread, and whether highlights or shadows are clipped

It then groups clips whose measurements are close, because the useful unit of
grading work is the setup, not the clip: a hundred clips shot in the same
courtyard under the same light want one correction applied to all of them, and
the clip that does not match its neighbours is the one worth looking at.

Output:

    <work>/grade/measurements.json   per clip
    <work>/grade/plan.json           groups, with a suggested correction each
    <work>/grade/report.md           the same, readable

Honest limits
-------------
These are whole-frame averages. A frame that is mostly red lehenga reads warm
whether or not the white balance is wrong, so a cast reading is evidence, not a
verdict, and the suggested corrections are a starting point for the colourist
rather than a grade to apply unseen. Averages are genuinely reliable for the
job they are used for here, which is finding the clips that do not match their
neighbours.

Skin tone is deliberately not judged. Doing it properly means measuring inside
the face rectangles, which faces.py already finds, not across the whole frame;
until that is wired up, references/10 is the guidance to follow.
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import die, load_clips, work_dir, write_json  # noqa: E402

# Rec.709 8-bit. 128 is neutral on both chroma axes; U carries blue-yellow and
# V carries red-cyan.
NEUTRAL = 128.0

# A scene averaging below or above this is likely under or over exposed. Real
# footage varies widely, so these only flag a clip for a look, and a night
# baraat or a bright haldi courtyard will legitimately sit outside them.
Y_LOW = 70.0
Y_HIGH = 170.0

# Chroma distance from neutral below which a clip is called neutral.
CAST_NEUTRAL = 6.0

# How close two clips must be, in luma and chroma, to share a grade group.
GROUP_Y_TOL = 22.0
GROUP_UV_TOL = 12.0

STATS = ["YAVG", "YMIN", "YMAX", "UAVG", "VAVG", "SATAVG"]


def measure_clip(path: Path, max_frames: int = 60) -> dict:
    """Read exposure and chroma statistics from a clip with ffmpeg."""
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

    return {
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
    # 8-bit video legal range is 16-235; beyond it detail is gone, not dark.
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

    # Luma is roughly proportional to light, so a stop is a doubling.
    ev = math.log2(target_y / y) if y > 1 else 0.0
    ev = max(-2.5, min(2.5, ev))

    du, dv = stats["u_offset"], stats["v_offset"]

    gamma = round(2 ** (ev / 2.2), 4)
    filters = [f"eq=gamma={gamma}"]
    if stats["cast"] != "neutral":
        # Nudge chroma back toward neutral. ffmpeg's colorbalance works in
        # shadows/midtones/highlights on an RGB axis; midtones is the safe
        # place for an overall cast.
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
         "## Groups", "",
         "| Group | Clips | Luma | Cast | Strength | Exposure | Preview filter |",
         "| :--- | ---: | ---: | :--- | ---: | ---: | :--- |"]
    for g in groups:
        c = g["correction"]
        L.append(f"| `{g['group_id']}` | {g['clip_count']} | {g['y_avg']:.0f} | {g['cast']} | "
                 f"{g['cast_strength']:.1f} | {c['exposure_ev']:+.2f} EV | "
                 f"`{c['ffmpeg_preview_filter']}` |")

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
        description="Measure exposure and colour, and group clips needing one grade.")
    ap.add_argument("--work", type=Path, required=True, help="Work folder for this wedding job")
    ap.add_argument("inputs", nargs="*", type=Path,
                    help="Media files. Omit to use the work folder's clips.jsonl")
    ap.add_argument("--max-frames", type=int, default=60,
                    help="Frames to sample per clip (default 60)")
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
            m = measure_clip(path, args.max_frames)
        except Exception as e:  # noqa: BLE001
            print(f"[!] {path.name}: {e}")
            failures += 1
            continue
        m["clip_id"] = cid
        measurements.append(m)
        notes = f"  {', '.join(m['exposure_notes'])}" if m["exposure_notes"] else ""
        print(f"[✓] {path.name}: luma {m['y_avg']:.0f}, {m['cast']} "
              f"({m['cast_strength']:.1f}){notes}")

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
