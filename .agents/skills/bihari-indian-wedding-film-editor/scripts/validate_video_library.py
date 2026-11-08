#!/usr/bin/env python3
"""Validate every YouTube video in the research library actually exists.

WHY THIS EXISTS
---------------
`references/08_video_library_150.json` claims 165 researched YouTube videos, and
`library/cards/<id>.md` carries one card per video. None of that was ever checked
against YouTube itself, and the cards were produced by a template rather than by
watching the videos. If an ID was hallucinated, its card is worthless and so is
anything built on top of it. Run this first, before investing in transcripts,
thumbnails or shot analysis.

WHAT IT CHECKS
--------------
For each video ID:
  * Does the video exist on YouTube at all?
  * Does the real title match the title recorded in the library?
  * Does the real channel match the channel recorded in the library?

Two endpoints are used, neither of which needs an API key:
  1. oEmbed  -> authoritative title + channel when the video allows embedding.
  2. Thumbnail -> cheap existence check for videos that block embedding, so a
     private or embed-disabled video is not mistaken for a fabricated ID.

RESULT STATUSES
---------------
  OK                 Video exists and the recorded title matches.
  TITLE_MISMATCH     Video exists but the recorded title is wrong.
  CHANNEL_MISMATCH   Title matches, recorded channel does not.
  EXISTS_UNVERIFIED  Video exists but blocks embedding, so the title could not
                     be confirmed. Not a failure.
  MISSING            YouTube has no such video. Either removed or never existed.
  ERROR              Network or parsing problem. Re-run these.

USAGE
-----
    python3 scripts/validate_video_library.py                  # check all 165
    python3 scripts/validate_video_library.py --limit 10       # quick smoke test
    python3 scripts/validate_video_library.py --workers 4      # be gentler

Needs only the Python standard library. Run it from a machine that can reach
youtube.com; sandboxed CI environments often cannot.

Exit code is 1 if any video is MISSING or mismatched, so this can gate CI.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_LIBRARY = BASE_DIR / "references" / "08_video_library_150.json"

OEMBED = "https://www.youtube.com/oembed?url={watch}&format=json"
THUMBNAIL = "https://img.youtube.com/vi/{vid}/mqdefault.jpg"
WATCH = "https://www.youtube.com/watch?v={vid}"

USER_AGENT = "bihari-wedding-skill-library-validator/1.0"
TIMEOUT = 20

# Statuses that mean the library entry is wrong and needs human attention.
FAILING = {"MISSING", "TITLE_MISMATCH", "CHANNEL_MISMATCH"}


def _norm(text: str) -> set[str]:
    """Reduce a title to a set of comparable word tokens.

    Preserves letters and combining vowel marks across Indic scripts (Devanagari,
    Bengali, etc.) so Hindi and regional language titles compare accurately.
    """
    text = text.lower()
    # Strip quality/format noise that uploaders and researchers record differently.
    text = re.sub(r"\b(4k|1080p|720p|hd|full hd|official|video|part[- ]?\d+)\b", " ", text)
    # Replace punctuation and symbols (P*, S*) with spaces, keeping letters, numbers, and marks
    text = "".join(" " if unicodedata.category(c).startswith(("P", "S")) else c for c in text)
    return {t for t in text.split() if len(t) >= 2}


def titles_match(claimed: str, actual: str, threshold: float = 0.45) -> bool:
    """True when two titles share enough distinctive words.

    Exact string equality is too strict: uploaders rename videos and researchers
    abbreviate. Token overlap tolerates that while still catching a title that
    describes an entirely different video.
    """
    a, b = _norm(claimed), _norm(actual)
    if not a or not b:
        return False
    overlap = len(a & b) / min(len(a), len(b))
    return overlap >= threshold


def _get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""


def _exists_via_thumbnail(vid: str) -> bool:
    """YouTube serves no thumbnail for an ID that never existed."""
    try:
        status, _ = _get(THUMBNAIL.format(vid=vid))
        return status == 200
    except Exception:
        return False


def check_video(entry: dict, retries: int = 2) -> dict:
    """Resolve one library entry against YouTube."""
    vid = entry.get("id", "")
    claimed_title = (entry.get("title") or "").strip()
    claimed_channel = (entry.get("channel") or "").strip()
    result = {
        "id": vid,
        "track": entry.get("track", ""),
        "claimed_title": claimed_title,
        "claimed_channel": claimed_channel,
        "actual_title": None,
        "actual_channel": None,
        "status": "ERROR",
        "detail": "",
        "url": WATCH.format(vid=vid),
    }

    watch = urllib.parse.quote(WATCH.format(vid=vid), safe="")
    last_err = ""

    for attempt in range(retries + 1):
        try:
            status, body = _get(OEMBED.format(watch=watch))

            if status == 200:
                data = json.loads(body)
                actual_title = (data.get("title") or "").strip()
                actual_channel = (data.get("author_name") or "").strip()
                result["actual_title"] = actual_title
                result["actual_channel"] = actual_channel

                if not titles_match(claimed_title, actual_title):
                    result["status"] = "TITLE_MISMATCH"
                    result["detail"] = "Recorded title does not describe this video."
                elif claimed_channel and not titles_match(claimed_channel, actual_channel, 0.34):
                    result["status"] = "CHANNEL_MISMATCH"
                    result["detail"] = "Title matches but the recorded channel does not."
                else:
                    result["status"] = "OK"
                return result

            if status == 404:
                # oEmbed 404 is ambiguous, so confirm against the thumbnail CDN
                # before calling an ID fabricated.
                if _exists_via_thumbnail(vid):
                    result["status"] = "EXISTS_UNVERIFIED"
                    result["detail"] = "Exists but oEmbed returned 404; title unverified."
                else:
                    result["status"] = "MISSING"
                    result["detail"] = "No such video on YouTube (no oEmbed, no thumbnail)."
                return result

            if status in (401, 403):
                result["status"] = "EXISTS_UNVERIFIED"
                result["detail"] = f"Embedding disabled or private (HTTP {status}); title unverified."
                return result

            last_err = f"HTTP {status}"

        except Exception as e:  # noqa: BLE001 - reported per entry, never fatal
            last_err = f"{type(e).__name__}: {e}"

        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))

    result["detail"] = last_err or "unknown error"
    return result


def load_entries(library_path: Path) -> list[dict]:
    with open(library_path, encoding="utf-8") as fp:
        data = json.load(fp)
    entries = data.get("videos") or []
    if not entries:
        raise SystemExit(f"No 'videos' array found in {library_path}")
    return entries


def write_reports(results: list[dict], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    json_path = out_dir / "video_library_validation.json"
    json_path.write_text(
        json.dumps({"total": len(results), "counts": counts, "results": results},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# Video Library Validation Report",
        "",
        f"Checked **{len(results)}** videos from the research library against YouTube.",
        "",
        "| Status | Count | Meaning |",
        "| :--- | ---: | :--- |",
    ]
    meanings = {
        "OK": "Exists, recorded title matches.",
        "EXISTS_UNVERIFIED": "Exists but blocks embedding; title unconfirmed.",
        "TITLE_MISMATCH": "Exists, but the recorded title is wrong.",
        "CHANNEL_MISMATCH": "Title matches, recorded channel does not.",
        "MISSING": "**No such video on YouTube.**",
        "ERROR": "Network error; re-run these.",
    }
    for status in ["OK", "EXISTS_UNVERIFIED", "TITLE_MISMATCH", "CHANNEL_MISMATCH", "MISSING", "ERROR"]:
        if counts.get(status):
            lines.append(f"| `{status}` | {counts[status]} | {meanings[status]} |")

    problems = [r for r in results if r["status"] in FAILING]
    if problems:
        lines += ["", "## Entries needing attention", ""]
        for r in sorted(problems, key=lambda x: x["status"]):
            lines.append(f"### `{r['id']}` — {r['status']}")
            lines.append(f"* Track: `{r['track']}`")
            lines.append(f"* Recorded: {r['claimed_title'] or '(none)'} — {r['claimed_channel'] or '(none)'}")
            if r["actual_title"]:
                lines.append(f"* Actual: {r['actual_title']} — {r['actual_channel']}")
            lines.append(f"* {r['detail']}")
            lines.append(f"* {r['url']}")
            lines.append("")
    else:
        lines += ["", "No fabricated or mislabelled entries found.", ""]

    md_path = out_dir / "video_library_validation.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the YouTube research library against YouTube.")
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY, help="Path to 08_video_library_150.json")
    parser.add_argument("--out", type=Path, default=BASE_DIR / "validation", help="Report output directory")
    parser.add_argument("--limit", type=int, default=0, help="Check only the first N entries (0 = all)")
    parser.add_argument("--workers", type=int, default=6, help="Parallel requests (keep low to stay polite)")
    args = parser.parse_args()

    entries = load_entries(args.library)
    if args.limit:
        entries = entries[: args.limit]

    print(f"Validating {len(entries)} videos against YouTube with {args.workers} workers...\n")

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(check_video, e): e for e in entries}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            results.append(r)
            flag = "!!" if r["status"] in FAILING else ("??" if r["status"] != "OK" else "ok")
            print(f"[{i:>3}/{len(entries)}] {flag} {r['status']:<18} {r['id']}  {r['claimed_title'][:52]}")

    results.sort(key=lambda r: (r["track"], r["id"]))
    json_path, md_path = write_reports(results, args.out)

    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print("\n" + "=" * 62)
    for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {status:<20} {n}")
    print("=" * 62)
    print(f"\nReports written:\n  {json_path}\n  {md_path}")

    failed = sum(counts.get(s, 0) for s in FAILING)
    errors = counts.get("ERROR", 0)
    confirmed = counts.get("OK", 0) + counts.get("EXISTS_UNVERIFIED", 0)

    if failed:
        print(f"\n{failed} entry/entries are fabricated or mislabelled. "
              f"Their cards in library/cards/ cannot be trusted.")
        return 1

    # Nothing reached YouTube at all: that is an inconclusive run, not a pass.
    # Reporting it as success would be worse than reporting nothing.
    if confirmed == 0 and errors:
        print(f"\nInconclusive: all {errors} request(s) failed, so nothing was verified. "
              f"Check network access to youtube.com and re-run.")
        return 2

    if errors:
        print(f"\n{confirmed} video(s) confirmed to exist; {errors} could not be reached. "
              f"Re-run to retry the failures before trusting this result.")
        return 2

    unverified = counts.get("EXISTS_UNVERIFIED", 0)
    if unverified:
        print(f"\nAll {confirmed} videos exist. {unverified} block embedding, "
              f"so their titles could not be confirmed.")
    else:
        print(f"\nAll {confirmed} videos exist and all titles match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
