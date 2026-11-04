#!/usr/bin/env python3
"""Plan the edit: turn ingested footage into a resolved edit decision list.

This is the step the project was missing between knowing what the footage is
and exporting a timeline. The FCPXML generator previously assembled hardcoded
demo shot lists with invented filenames, so there was no path from a real
wedding's rushes to a real edit. It now reads an EDL that this module produces.

Covers points 7, 8 and 9 of the brief:

  7  rituals separated into parts and ordered as they actually happen
  8  the whole edit journey, applying every rule from the earlier parts
  9  three deliverables: teaser, trailer and master film

Inputs, all optional except the clips, so a partial job still plans:

    <work>/clips.jsonl          from raw_footage_ingest.py
    <work>/tags/<clip>.json     from faces.py, or written by hand
    <work>/faces/people.json    from faces.py
    <work>/songs/<name>.json    from beats.py
    data/rituals.json           the 16 Bihari rituals, with running order

Output:

    <work>/edl/<deliverable>.json

Ordering comes from the ritual data, not from guesswork: `days_offset` places
each ritual on the wedding calendar from the tilak fifteen days before to the
reception two days after, and `phase` groups them into the pre-wedding,
wedding-day and post-wedding thirds that give the trailer its three acts.

Why clip choice considers people
--------------------------------
Point 6 of the brief asks that no family member be missed. A planner that
simply took the longest or earliest clip per ritual would reliably drop the
quiet relatives, so selection is greedy on marginal coverage: a clip
containing someone not yet in the cut outranks a technically similar clip of
people already well represented. The plan then reports who still never
appears, rather than leaving it to be discovered at the premiere.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA_DIR, die, load_clips, read_json, snap, work_dir,  # noqa: E402
                    write_json)

DEFAULT_FPS = 25

# Deliverable shapes. Durations match DELIVERABLE_SPECS in fcpxml_generator.
DELIVERABLES = {
    "teaser": {
        "target_sec": 95.0, "min_sec": 60.0, "max_sec": 180.0,
        "shot_sec": (1.8, 4.5),
        "note": "One hero moment per ritual, cut on the beat.",
    },
    "trailer": {
        "target_sec": 360.0, "min_sec": 300.0, "max_sec": 600.0,
        "shot_sec": (4.0, 14.0),
        "note": "Three acts following the wedding's own phases.",
    },
    "master": {
        "target_sec": None, "min_sec": 3600.0, "max_sec": 10800.0,
        "shot_sec": (6.0, 90.0),
        "note": "Full chronological film, each ritual its own chapter.",
    },
}

# Trailer acts, in order, built from the ritual phases in the data.
ACT_PHASES = [
    ("Act1_Roots", ["pre-wedding"]),
    ("Act2_Celebration", ["wedding_day"]),
    ("Act3_Vows_and_Farewell", ["post-wedding"]),
]


# -------------------------------------------------------------------- loading

def load_rituals(data_dir: Path | None = None) -> list[dict]:
    path = (Path(data_dir) if data_dir else DATA_DIR) / "rituals.json"
    payload = read_json(path, {}) or {}
    rituals = payload.get("rituals", [])
    # Chronological: the calendar offset first, then the id, which already
    # encodes the within-day running order (R01 through R16).
    return sorted(rituals, key=lambda r: (r.get("days_offset", 0), r.get("id", "")))


def ritual_key(ritual: dict) -> str:
    """Short tag used to match clips to rituals, e.g. 'haldi_ubtan'."""
    rid = str(ritual.get("id", ""))
    return rid.split("_", 1)[1] if "_" in rid else rid


def load_job(work: Path, data_dir: Path | None = None) -> dict:
    """Gather everything known about this wedding job."""
    work = Path(work)
    clips = load_clips(work, "video")

    tags: dict[str, dict] = {}
    tags_dir = work / "tags"
    if tags_dir.exists():
        for f in sorted(tags_dir.glob("*.json")):
            t = read_json(f, {}) or {}
            if t.get("clip_id"):
                tags[t["clip_id"]] = t

    people = read_json(work / "faces" / "people.json", {}) or {}

    songs = {}
    songs_dir = work / "songs"
    if songs_dir.exists():
        for f in sorted(songs_dir.glob("*.json")):
            songs[f.stem] = read_json(f, {}) or {}

    return {
        "clips": clips,
        "tags": tags,
        "people": people,
        "songs": songs,
        "rituals": load_rituals(data_dir),
    }


def clip_ritual(clip: dict, tags: dict) -> str:
    """Best known ritual for a clip: its tag first, then its ingest guess."""
    tag = tags.get(clip.get("id", ""), {})
    return tag.get("ritual_phase") or clip.get("ritual_phase") or "unknown"


def clip_subjects(clip: dict, tags: dict) -> list[str]:
    return list(tags.get(clip.get("id", ""), {}).get("subjects", []))


def group_by_ritual(job: dict) -> dict[str, list[dict]]:
    """Bucket clips by the ritual they belong to."""
    buckets: dict[str, list[dict]] = {}
    for clip in job["clips"]:
        buckets.setdefault(clip_ritual(clip, job["tags"]), []).append(clip)
    return buckets


def _tokenise(name: str) -> set[str]:
    return {t for t in re.split(r"[_\s-]+", str(name).lower()) if t}


def match_ritual_clips(ritual: dict, buckets: dict[str, list[dict]]) -> list[dict]:
    """Clips belonging to a ritual, matched on whole words rather than substrings.

    Matching must be token-based, not substring-based. An earlier version
    accepted a bucket whose name merely contained a ritual word, which assigned
    all thirteen `kanyadaan` clips to `sindoor_daan` as well, because "daan" is
    a substring of "kanyadaan". The master film would then have shown the
    kanyadaan footage again inside the sindoor daan chapter, and both chapters
    would have been built from the wrong rushes.

    A tag is still allowed to be less specific than the ritual, so a clip
    tagged just "haldi" matches "haldi_ubtan": its tokens are a subset. But
    {"kanyadaan"} is not a subset of {"sindoor", "daan"}, so that no longer
    matches.
    """
    rid = str(ritual.get("id", "")).lower()
    key = ritual_key(ritual).lower()
    english = str(ritual.get("name_english") or "").lower()

    exact = {rid, key}
    if english:
        exact.add(english)
    key_tokens = _tokenise(key)

    out: list[dict] = []
    for bucket_name, clips in buckets.items():
        bn = str(bucket_name).lower()
        if bn in exact:
            out += clips
            continue
        bucket_tokens = _tokenise(bn)
        if not bucket_tokens:
            continue
        if bucket_tokens <= key_tokens or key_tokens <= bucket_tokens:
            out += clips
    return out


# ------------------------------------------------------------------ selection

def coverage_picks(job: dict) -> dict[str, list[dict]]:
    """Smallest practical set of clips that together include every known person.

    Coverage cannot be decided one ritual at a time. A ritual's slice of a
    90-second teaser is only a few seconds, so a greedy choice made inside that
    slice will pass over the one clip containing a grandparent in favour of a
    clip of the couple, and two quiet relatives who happen to be filmed in the
    same ritual will never both survive. Point 6 of the brief is a property of
    the whole film, so it is solved globally first, by greedy set cover over
    all clips, and the result is then forced into each ritual's selection.

    Returns a map of ritual key to the clips that must be included from it.
    """
    known = {p["person_id"] for p in job["people"].get("people", [])}
    if not known:
        return {}

    covered: set[str] = set()
    picks: dict[str, list[dict]] = {}
    remaining = list(job["clips"])

    while True:
        uncovered = known - covered
        if not uncovered or not remaining:
            break

        def gain(clip: dict) -> tuple[int, float]:
            subs = set(clip_subjects(clip, job["tags"]))
            # Prefer the clip covering the most missing people; shorter clips
            # break ties, so a forced inclusion costs the edit as little as
            # possible.
            return (len(subs & uncovered), -float(clip.get("duration", 0.0)))

        best = max(remaining, key=gain)
        if gain(best)[0] == 0:
            # Nobody left can be covered: the remaining people were never
            # filmed. _finalise reports them.
            break
        remaining.remove(best)
        covered |= set(clip_subjects(best, job["tags"]))
        picks.setdefault(clip_ritual(best, job["tags"]), []).append(best)

    return picks


def _pick_with_coverage(candidates: list[dict], job: dict, needed_sec: float,
                        shot_range: tuple[float, float],
                        covered: set[str], fps: Fraction,
                        must_include: list[dict] | None = None) -> list[dict]:
    """Choose clips to fill a time allocation, favouring unseen people.

    Clips in `must_include` are taken first, regardless of budget, because they
    are the ones carrying a person who appears nowhere else. The rest is greedy
    on marginal coverage: the clip bringing the most people not yet in the cut
    wins, with longer clips breaking ties so a ritual is not built from scraps.
    """
    lo, hi = shot_range
    forced = list(must_include or [])
    forced_ids = {c.get("id") for c in forced}
    remaining = forced + [c for c in candidates if c.get("id") not in forced_ids]
    chosen: list[dict] = []
    used = 0.0

    while remaining and (used < needed_sec or forced):
        def rank(c: dict):
            subs = set(clip_subjects(c, job["tags"]))
            new_people = len(subs - covered)
            return (new_people, float(c.get("duration", 0.0)))

        is_forced = bool(forced)
        if is_forced:
            # Take a forced clip now; its person is in no other clip.
            clip = forced.pop(0)
            remaining = [c for c in remaining if c.get("id") != clip.get("id")]
        else:
            remaining.sort(key=rank, reverse=True)
            clip = remaining.pop(0)

        source_dur = float(clip.get("duration", 0.0))
        if source_dur <= 0:
            continue

        budget_left = needed_sec - used
        if is_forced:
            # A forced clip is the only place someone appears, so it gets at
            # least a minimum shot whatever the budget says. Deciding this on
            # remaining budget instead silently dropped such clips: once the
            # allocation was nearly spent, the leftover sliver produced a
            # sub-minimum shot which then failed the length check below and
            # broke out of the loop, losing the relative the clip was forced
            # in to protect.
            take = min(hi, max(lo, min(lo, source_dur)))
        else:
            take = min(hi, max(lo, source_dur), budget_left)
            if take < min(lo, source_dur) * 0.5:
                break
        take = snap(take, fps)
        if take <= 0:
            break

        # Start a little inside the clip: the first moments usually contain the
        # camera settling, and the operator's voice.
        source_in = snap(min(0.5, max(0.0, source_dur - take)), fps)

        chosen.append({
            "clip_id": clip.get("id", ""),
            "path": clip.get("path", ""),
            "source_in": source_in,
            "duration": take,
            "subjects": sorted(clip_subjects(clip, job["tags"])),
        })
        covered |= set(clip_subjects(clip, job["tags"]))
        used += take

    return chosen


def _forced_for(ritual: dict, forced: dict[str, list[dict]]) -> list[dict]:
    """Forced-coverage clips belonging to this ritual."""
    key = ritual_key(ritual).lower()
    rid = str(ritual.get("id", "")).lower()
    out: list[dict] = []
    for bucket, clips in forced.items():
        b = str(bucket).lower()
        if b == key or b == rid or (len(b) > 3 and (b in key or key in b)):
            out += clips
    return out


def _song_for(job: dict, prefer_steady: bool = True) -> dict | None:
    """Pick a song map to cut against, preferring one with a real pulse."""
    songs = [s for s in job["songs"].values() if s]
    if not songs:
        return None
    steady = [s for s in songs if s.get("steady_tempo")]
    if prefer_steady and steady:
        return max(steady, key=lambda s: len(s.get("beats", [])))
    return songs[0]


def snap_to_beats(events: list[dict], song: dict | None, fps: Fraction) -> list[dict]:
    """Stretch each cut so it lands on a beat of the chosen song.

    The brief asks for cuts "on the beats" in the teaser and trailer. Durations
    are nudged to the nearest beat interval rather than recomputed, so the
    planned shape of the edit survives.

    A song with no steady pulse is left alone: live folk geet often has none,
    and forcing a grid onto it would cut against the singing. beats.py reports
    which case applies.

    A cut cannot always be exactly on a beat. At 25 fps a 120 BPM beat is 12.5
    frames, and Final Cut Pro edits on frame boundaries, so the beat and the
    frame grid do not coincide. Frames win, because a non-integral edit point
    is not representable in FCPXML at all, and the residual error is recorded
    per event as `beat_error` so it can be inspected. At 25 fps it is at most
    half a frame, 20 ms, which is far below the ~50 ms at which a listener
    starts to perceive a cut as being off the beat.
    """
    if not song or not song.get("steady_tempo"):
        return events
    bpm = float(song.get("bpm") or 0.0)
    if bpm <= 0:
        return events

    beat = 60.0 / bpm
    for ev in events:
        beats_long = max(1, round(ev["duration"] / beat))
        ideal = beats_long * beat
        ev["duration"] = snap(ideal, fps)
        ev["beats"] = beats_long
        ev["beat_error"] = round(abs(ev["duration"] - ideal), 5)
    return events


# ------------------------------------------------------------------- planners

def plan_master(job: dict, fps: Fraction = Fraction(DEFAULT_FPS)) -> dict:
    """Full chronological film, one chapter per ritual."""
    spec = DELIVERABLES["master"]
    buckets = group_by_ritual(job)
    forced = coverage_picks(job)
    covered: set[str] = set()
    events: list[dict] = []

    for ritual in job["rituals"]:
        candidates = match_ritual_clips(ritual, buckets)
        if not candidates:
            continue
        allocation = float(ritual.get("target_duration_master_sec") or 300.0)
        picked = _pick_with_coverage(candidates, job, allocation,
                                     spec["shot_sec"], covered, fps,
                                     _forced_for(ritual, forced))
        if not picked:
            continue
        # Chapter marker on the ritual's first shot, plus the hero moment the
        # ritual data says must survive the cut.
        picked[0]["markers"] = [{"time_offset": 0.0,
                                 "label": f"CHAPTER: {ritual.get('id')}"}]
        if ritual.get("must_keep_moment"):
            picked[0]["must_keep"] = ritual["must_keep_moment"]
        for ev in picked:
            ev["ritual"] = ritual.get("id")
        events += picked

    return _finalise("master", events, job, fps, song=None)


def plan_teaser(job: dict, fps: Fraction = Fraction(DEFAULT_FPS)) -> dict:
    """One hero moment per ritual, beat-synced, 1 to 3 minutes."""
    spec = DELIVERABLES["teaser"]
    buckets = group_by_ritual(job)
    covered: set[str] = set()
    events: list[dict] = []

    forced = coverage_picks(job)
    rituals_with_clips = [r for r in job["rituals"] if match_ritual_clips(r, buckets)]
    if not rituals_with_clips:
        return _finalise("teaser", [], job, fps, song=None)

    per_ritual = spec["target_sec"] / len(rituals_with_clips)
    for ritual in rituals_with_clips:
        picked = _pick_with_coverage(match_ritual_clips(ritual, buckets), job,
                                     per_ritual, spec["shot_sec"], covered, fps,
                                     _forced_for(ritual, forced))
        for ev in picked:
            ev["ritual"] = ritual.get("id")
        events += picked

    song = _song_for(job)
    events = snap_to_beats(events, song, fps)
    return _finalise("teaser", events, job, fps, song)


def plan_trailer(job: dict, fps: Fraction = Fraction(DEFAULT_FPS)) -> dict:
    """Three acts following the wedding's own phases, 5 to 10 minutes."""
    spec = DELIVERABLES["trailer"]
    buckets = group_by_ritual(job)
    covered: set[str] = set()
    events: list[dict] = []

    forced = coverage_picks(job)
    by_phase: dict[str, list[dict]] = {}
    for ritual in job["rituals"]:
        by_phase.setdefault(str(ritual.get("phase") or "unknown"), []).append(ritual)

    active_acts = [
        (act, [r for ph in phases for r in by_phase.get(ph, [])
               if match_ritual_clips(r, buckets)])
        for act, phases in ACT_PHASES
    ]
    active_acts = [(a, rs) for a, rs in active_acts if rs]
    if not active_acts:
        return _finalise("trailer", [], job, fps, song=None)

    per_act = spec["target_sec"] / len(active_acts)
    for act_name, rituals in active_acts:
        per_ritual = per_act / len(rituals)
        first_in_act = True
        for ritual in rituals:
            picked = _pick_with_coverage(match_ritual_clips(ritual, buckets), job,
                                         per_ritual, spec["shot_sec"], covered, fps,
                                         _forced_for(ritual, forced))
            for ev in picked:
                ev["ritual"] = ritual.get("id")
                ev["act"] = act_name
            if picked and first_in_act:
                picked[0]["markers"] = [{"time_offset": 0.0, "label": act_name}]
                first_in_act = False
            events += picked

    song = _song_for(job)
    events = snap_to_beats(events, song, fps)
    return _finalise("trailer", events, job, fps, song)


# ------------------------------------------------------------------ finishing

def _finalise(kind: str, events: list[dict], job: dict,
              fps: Fraction, song: dict | None) -> dict:
    total = sum(float(e["duration"]) for e in events)

    known_people = {p["person_id"] for p in job["people"].get("people", [])}
    in_cut: set[str] = set()
    for e in events:
        in_cut |= set(e.get("subjects", []))

    edl = {
        "deliverable": kind,
        "note": DELIVERABLES[kind]["note"],
        "fps": int(fps),
        "event_count": len(events),
        "duration": round(total, 3),
        "spec": {"min_sec": DELIVERABLES[kind]["min_sec"],
                 "max_sec": DELIVERABLES[kind]["max_sec"]},
        "song": song.get("source") if song else None,
        "bpm": song.get("bpm") if song else None,
        "people_in_cut": sorted(in_cut),
        "people_missing": sorted(known_people - in_cut),
        "rituals_covered": sorted({e["ritual"] for e in events if e.get("ritual")}),
        "events": events,
    }
    edl["issues"] = validate_edl(edl)
    return edl


def validate_edl(edl: dict) -> list[str]:
    """Report everything wrong with a plan, rather than exporting it silently."""
    issues: list[str] = []
    spec = edl["spec"]
    dur = edl["duration"]

    if not edl["events"]:
        issues.append("No events: no clips matched any ritual. Check clip tagging.")
        return issues

    if dur < spec["min_sec"]:
        issues.append(
            f"Too short: {dur:.1f}s against a {spec['min_sec']:.0f}s minimum. "
            f"Not enough usable footage matched the rituals.")
    elif dur > spec["max_sec"]:
        issues.append(
            f"Too long: {dur:.1f}s against a {spec['max_sec']:.0f}s maximum.")

    if edl["people_missing"]:
        issues.append(
            f"{len(edl['people_missing'])} known {'person' if len(edl['people_missing']) == 1 else 'people'} "
            f"never appear: {', '.join(edl['people_missing'][:8])}"
            + (" ..." if len(edl["people_missing"]) > 8 else ""))

    for ev in edl["events"]:
        if not ev.get("path"):
            issues.append(f"Event for clip {ev.get('clip_id')} has no media path.")
            break

    return issues


def plan_all(job: dict, fps: Fraction = Fraction(DEFAULT_FPS)) -> dict[str, dict]:
    return {
        "teaser": plan_teaser(job, fps),
        "trailer": plan_trailer(job, fps),
        "master": plan_master(job, fps),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Plan teaser, trailer and master edits from ingested footage.")
    ap.add_argument("--work", type=Path, required=True, help="Work folder for this wedding job")
    ap.add_argument("--type", choices=["teaser", "trailer", "master", "all"], default="all")
    ap.add_argument("--fps", type=int, default=DEFAULT_FPS)
    ap.add_argument("--data-dir", type=Path, default=None,
                    help="Override the rituals data directory")
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any plan has issues")
    args = ap.parse_args()

    work = work_dir(args.work)
    job = load_job(work, args.data_dir)

    if not job["clips"]:
        die("No video clips found. Run raw_footage_ingest.py against your footage first.", 2)

    print(f"Job: {len(job['clips'])} clips, {len(job['tags'])} tagged, "
          f"{len(job['people'].get('people', []))} people, {len(job['songs'])} song maps")

    fps = Fraction(args.fps)
    wanted = ["teaser", "trailer", "master"] if args.type == "all" else [args.type]
    planners = {"teaser": plan_teaser, "trailer": plan_trailer, "master": plan_master}

    any_issues = False
    for kind in wanted:
        edl = planners[kind](job, fps)
        out = work / "edl" / f"{kind}.json"
        write_json(out, edl)

        mins = edl["duration"] / 60.0
        print(f"\n[{kind}] {edl['event_count']} events, {edl['duration']:.1f}s ({mins:.1f} min), "
              f"{len(edl['rituals_covered'])} rituals")
        if edl.get("bpm"):
            print(f"    cut to {edl['song']} at {edl['bpm']:.1f} BPM")
        for issue in edl["issues"]:
            any_issues = True
            print(f"    [!] {issue}")
        if not edl["issues"]:
            print("    [✓] within spec, every known person appears")
        print(f"    -> {out}")

    if any_issues and args.strict:
        die("\nPlans have issues and --strict was given.", 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
