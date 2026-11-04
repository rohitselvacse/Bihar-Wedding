#!/usr/bin/env python3
"""Regenerate library/stats.md from the video library, so it cannot drift.

The committed stats.md was written by hand and did not match the data: its
per-track table summed to 176 against a stated total of 165, it claimed 40
Bihari videos where the library holds 39, and it reported 71.4 hours of
material against an actual 57.0. Those numbers were also quoted as evidence in
the requirements traceability table, so a hand-maintained summary was being
used to certify the work it summarised.

Deriving the file from references/08_video_library_150.json removes that
whole class of error. Run this after changing the library:

    python3 scripts/library_stats.py
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SKILL_DIR, die, read_json  # noqa: E402

TRACK_FOCUS = {
    "T1_formats": "Teasers (1-3 min), trailers (5-10 min), highlights, candid, master films (1-3 h).",
    "T2_tutorials": "Final Cut Pro, DaVinci Resolve, Premiere, log footage, skin tones, beat sync.",
    "T3_songs": "Haldi, mehndi, sangeet, baraat, jaimala, mandap and vidai repertoire.",
    "T4_bihar": "Matkor, marwa, haldi hardiya, tilak, sindoor daan, kohbar, vidai, bahubhoj.",
    "T6_reception": "Stage lighting, shagun queues, family continuity, pangat coverage.",
    "T7_recipes": "Teaser recipes, trailer structures, speed ramps, export standards.",
}

# Research tracks the brief asked for. T5 (geet, spoken wordings, pandit
# recitation) has no videos in the library, which the generated file states
# rather than omitting.
EXPECTED_TRACKS = ["T1_formats", "T2_tutorials", "T3_songs", "T4_bihar",
                   "T5_geet", "T6_reception", "T7_recipes"]


def fmt_hours(seconds: float) -> str:
    return f"{seconds / 3600:.1f} hours"


def fmt_duration(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def build(videos: list[dict]) -> str:
    by_track = collections.Counter(v.get("track", "unknown") for v in videos)
    by_category = collections.Counter(v.get("category", "unknown") for v in videos)
    total_sec = sum(int(v.get("duration_seconds") or 0) for v in videos)

    durations = [(int(v.get("duration_seconds") or 0), v.get("title", "")) for v in videos]
    durations.sort()
    shortest, longest = durations[0], durations[-1]

    has_transcript = sum(1 for v in videos if v.get("transcript"))
    has_thumbnail = sum(1 for v in videos if v.get("thumbnail"))

    L: list[str] = []
    L.append("# Video library statistics")
    L.append("")
    L.append("Generated from `references/08_video_library_150.json` by "
             "`scripts/library_stats.py`. Do not edit by hand; rerun the script instead.")
    L.append("")
    L.append("## Summary")
    L.append("")
    L.append(f"* Videos catalogued: **{len(videos)}**")
    L.append(f"* Combined running time: **{fmt_hours(total_sec)}**")
    L.append(f"* Shortest: {fmt_duration(shortest[0])} — {shortest[1]}")
    L.append(f"* Longest: {fmt_duration(longest[0])} — {longest[1]}")
    L.append(f"* Individual cards: {len(videos)} in `library/cards/<id>.md`")
    L.append("")
    L.append("## By research track")
    L.append("")
    L.append("| Track | Count | Focus |")
    L.append("| :--- | ---: | :--- |")
    for track in EXPECTED_TRACKS:
        count = by_track.get(track, 0)
        focus = TRACK_FOCUS.get(
            track, "Live geet, spoken wordings and pandit recitation.")
        if count == 0:
            focus += " **No videos catalogued for this track.**"
        L.append(f"| `{track}` | {count} | {focus} |")
    extra = sorted(set(by_track) - set(EXPECTED_TRACKS))
    for track in extra:
        L.append(f"| `{track}` | {by_track[track]} | Not one of the briefed tracks. |")
    L.append(f"| **Total** | **{sum(by_track.values())}** | |")
    L.append("")
    L.append("## By category")
    L.append("")
    L.append("| Category | Count |")
    L.append("| :--- | ---: |")
    for cat, n in by_category.most_common():
        L.append(f"| {cat} | {n} |")
    L.append("")
    L.append("## Known gaps")
    L.append("")
    L.append(f"* Transcripts: **{has_transcript} of {len(videos)}**. The brief asks for a "
             "transcript per video; none are stored. `scripts/transcribe.py` transcribes "
             "your own footage, not these reference videos.")
    L.append(f"* Thumbnails: **{has_thumbnail} of {len(videos)}**. None are stored.")
    L.append("* Shot breakdowns in `library/cards/` were produced by a template, not by "
             "watching the videos: each card's cut points sit at a fixed 20% and 75% of "
             "its duration. Treat them as placeholders.")
    L.append("* No video id has been checked against YouTube. Run "
             "`scripts/validate_video_library.py` from a machine with YouTube access "
             "before relying on this library.")
    if by_track.get("T5_geet", 0) == 0:
        L.append("* Track T5 (geet, spoken wordings, pandit recitation) has no videos, "
                 "although the brief asked for 10-20 per section.")
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate library/stats.md from the library JSON.")
    ap.add_argument("--skill-dir", type=Path, default=SKILL_DIR)
    ap.add_argument("--check", action="store_true",
                    help="Exit non-zero if the file on disk is out of date, without writing")
    args = ap.parse_args()

    lib = args.skill_dir / "references" / "08_video_library_150.json"
    payload = read_json(lib, {}) or {}
    videos = payload.get("videos") or []
    if not videos:
        die(f"No videos found in {lib}", 2)

    text = build(videos)
    out = args.skill_dir / "library" / "stats.md"

    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current.strip() != text.strip():
            die(f"{out} is out of date. Run: python3 scripts/library_stats.py", 1)
        print(f"[✓] {out} matches the library data.")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"[✓] Wrote {out} from {len(videos)} catalogued videos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
