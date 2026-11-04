#!/usr/bin/env python3
"""Transcribe raw wedding footage and label geet, mantras and speech.

This covers the part of the brief that nothing in this project previously
addressed: point 5, which asks for the live folk *geet* sung by the women of
the family to be found and kept, for the traditional wordings spoken by the
couple and their relatives to be understood, and for the pandit's ritual
recitation to be covered.

What it produces, per clip, in `<work>/transcripts/<clip_id>.json`:

    language       detected spoken language
    segments[]     start, end, text, and a label of geet / mantra / speech
    label_counts   how much of each kind the clip contains
    geet_spans     merged time ranges where singing was detected
    mantra_spans   merged time ranges where ritual recitation was detected

Why the labels matter downstream
--------------------------------
The three kinds of audio must be treated differently in the edit, which is
exactly what the brief asks for:

  geet    keep the original sound, clean it, and lay only a little music under
          it. Folk geet frequently has no steady tempo, so cuts should follow
          phrase boundaries from this transcript rather than a beat grid.
  mantra  preserve and duck the music beneath it, never talk over it.
  speech  the family's own words; worth subtitling and worth protecting from
          music that would bury them.

Honest limits
-------------
The labelling is a lexicon and repetition heuristic, not a trained classifier.
It is built from the Bhojpuri and Maithili geet actually catalogued in
`library/songs/songs_bihar.json` plus a Sanskrit ritual vocabulary, and every
decision carries a score and the terms that matched, so a human can review and
override it. It is meant to point the editor at the right minutes of a seven
hour rush, not to be trusted blindly.

Transcription itself needs a Whisper backend. `faster-whisper` is preferred for
speed, `openai-whisper` works too. Everything else in this module, including
audio extraction and all the labelling, runs without them.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SKILL_DIR, clip_id, die, load_clips, read_json, work_dir, write_json  # noqa: E402

SAMPLE_RATE = 16000

# Sanskrit and ritual vocabulary a pandit uses at a Hindu wedding. Both
# Devanagari and romanised forms appear, because Whisper may output either
# depending on the language it detects.
MANTRA_TERMS = [
    "ॐ", "ओम", "om", "aum",
    "स्वाहा", "swaha", "svaha",
    "नमः", "namah", "namaha",
    "मंत्र", "mantra",
    "अग्नि", "agni",
    "आहुति", "aahuti", "ahuti",
    "यज्ञ", "yagya", "yagna", "हवन", "havan",
    "संकल्प", "sankalp",
    "कन्यादान", "kanyadaan", "kanyadan",
    "सप्तपदी", "saptapadi", "सात फेरे", "saat phere",
    "पाणिग्रहण", "panigrahan",
    "गठबंधन", "gathbandhan",
    "गोत्र", "gotra",
    "विवाह", "vivah", "vivaah",
    "मंगल", "mangal", "शुभ", "shubh",
    "देव", "dev", "देवता", "ब्रह्म", "brahma",
    "वर", "वधू", "vadhu",
    "सिंदूर", "sindoor", "sindur",
    "आशीर्वाद", "ashirvad", "aashirvad",
]

# Kinship and refrain words that pervade Bhojpuri and Maithili wedding geet.
# "हो" in particular is the characteristic line-ending particle of these songs.
GEET_TERMS = [
    "हो", "हे", "रे", "ना",
    "बाबा", "baba", "माई", "mai", "माता",
    "भउजी", "bhauji", "ननद", "nanad", "सखी", "sakhi", "सजनी",
    "दुलहा", "dulha", "दुलहिन", "dulhin", "बाबूजी",
    "हरदी", "hardi", "हरियर", "hariyar",
    "कोहबर", "kohbar", "मड़वा", "marwa", "madwa",
    "मटकोर", "matkor", "विदाई", "vidai", "बिदाई",
    "गीत", "geet", "सोहर", "sohar", "समदाउन", "samdaun",
]


def extract_audio(media: Path, out_wav: Path, sample_rate: int = SAMPLE_RATE) -> Path:
    """Decode a clip's audio to the mono 16 kHz WAV that Whisper expects."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(media),
         "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(out_wav)],
        capture_output=True,
    )
    if proc.returncode != 0 or not out_wav.exists():
        detail = proc.stderr.decode("utf-8", errors="replace")[-300:].strip()
        raise RuntimeError(f"could not extract audio from {media.name}: {detail}")
    return out_wav


def has_audio_stream(media: Path) -> bool:
    """True when the file carries at least one audio stream."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(media)],
        capture_output=True, text=True,
    )
    return bool(proc.stdout.strip())


def build_lexicons(skill_dir: Path | None = None) -> dict:
    """Assemble match terms, drawing geet vocabulary from the song catalogue.

    The catalogue is the project's own curated list of Bihari wedding geet, so
    its titles are a better source of real vocabulary than anything invented
    here. Terms from it are added to the hand-written refrain and kinship words.
    """
    base = Path(skill_dir) if skill_dir else SKILL_DIR
    geet = set(GEET_TERMS)

    catalogue = read_json(base / "library" / "songs" / "songs_bihar.json", {}) or {}
    for song in catalogue.get("songs", []):
        if song.get("kind") != "folk-geet":
            continue
        for field in ("title", "title_devanagari"):
            for token in re.split(r"[\s|(),/-]+", str(song.get(field) or "")):
                token = token.strip().lower()
                # Single characters and very short particles add noise, and the
                # useful short particles are already listed explicitly.
                if len(token) >= 3:
                    geet.add(token)
        for fn in song.get("functions", []):
            if len(str(fn)) >= 4:
                geet.add(str(fn).lower())

    return {
        "mantra": {t.lower() for t in MANTRA_TERMS},
        "geet": geet,
    }


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^\wऀ-ॿ]+", text.lower()) if t]


def classify_segment(text: str, lexicons: dict, repeated: bool = False) -> dict:
    """Label one transcript segment as geet, mantra or speech.

    Returns the label, a score, and the terms that matched, so the decision can
    be audited rather than taken on trust.
    """
    toks = _tokens(text)
    if not toks:
        return {"label": "unknown", "score": 0.0, "matched": []}

    tokset = set(toks)
    mantra_hits = sorted(tokset & lexicons["mantra"])
    geet_hits = sorted(tokset & lexicons["geet"])

    # Normalise by length so a long sentence containing one ritual word is not
    # ranked above a short line that is almost entirely ritual vocabulary.
    mantra_score = len(mantra_hits) / max(1, len(tokset)) * 2.0
    geet_score = len(geet_hits) / max(1, len(tokset))

    # A line sung again is almost always a refrain, which is the single
    # strongest signal that a segment is geet rather than conversation.
    if repeated:
        geet_score += 0.5

    if mantra_score >= geet_score and mantra_hits:
        return {"label": "mantra", "score": round(mantra_score, 3), "matched": mantra_hits}
    if geet_hits and geet_score > 0.12:
        return {"label": "geet", "score": round(geet_score, 3), "matched": geet_hits}
    return {"label": "speech", "score": round(max(mantra_score, geet_score), 3),
            "matched": mantra_hits + geet_hits}


def find_repeated_lines(segments: list[dict], min_len: int = 8) -> set[str]:
    """Normalised segment texts that occur more than once (likely refrains)."""
    seen: dict[str, int] = {}
    for seg in segments:
        key = " ".join(_tokens(str(seg.get("text", ""))))
        if len(key) >= min_len:
            seen[key] = seen.get(key, 0) + 1
    return {k for k, n in seen.items() if n > 1}


def merge_spans(segments: list[dict], label: str, gap: float = 2.0) -> list[dict]:
    """Merge adjacent segments of one label into continuous time ranges."""
    spans: list[dict] = []
    for seg in segments:
        if seg.get("label") != label:
            continue
        start, end = float(seg["start"]), float(seg["end"])
        if spans and start - spans[-1]["end"] <= gap:
            spans[-1]["end"] = end
            spans[-1]["segments"] += 1
        else:
            spans.append({"start": start, "end": end, "segments": 1})
    for s in spans:
        s["start"] = round(s["start"], 2)
        s["end"] = round(s["end"], 2)
        s["duration"] = round(s["end"] - s["start"], 2)
    return spans


def annotate(segments: list[dict], lexicons: dict) -> list[dict]:
    """Attach a label to every transcript segment."""
    repeats = find_repeated_lines(segments)
    out = []
    for seg in segments:
        key = " ".join(_tokens(str(seg.get("text", ""))))
        verdict = classify_segment(str(seg.get("text", "")), lexicons, repeated=key in repeats)
        out.append({
            "start": round(float(seg.get("start", 0.0)), 2),
            "end": round(float(seg.get("end", 0.0)), 2),
            "text": str(seg.get("text", "")).strip(),
            **verdict,
        })
    return out


def summarise(segments: list[dict]) -> dict:
    counts: dict[str, int] = {}
    seconds: dict[str, float] = {}
    for seg in segments:
        lbl = seg["label"]
        counts[lbl] = counts.get(lbl, 0) + 1
        seconds[lbl] = round(seconds.get(lbl, 0.0) + (seg["end"] - seg["start"]), 2)
    return {"label_counts": counts, "label_seconds": seconds}


# ------------------------------------------------------------------ backends

def _load_backend(model_size: str, backend: str = "auto"):
    """Return a callable(wav_path) -> (language, segments), or raise."""
    errors = []

    if backend in ("auto", "faster-whisper"):
        try:
            from faster_whisper import WhisperModel  # type: ignore

            model = WhisperModel(model_size, device="auto", compute_type="int8")

            def run_fw(wav: Path):
                segs, info = model.transcribe(str(wav), vad_filter=True)
                return info.language, [
                    {"start": s.start, "end": s.end, "text": s.text} for s in segs
                ]

            return run_fw
        except Exception as e:  # noqa: BLE001
            errors.append(f"faster-whisper: {e}")

    if backend in ("auto", "whisper"):
        try:
            import whisper  # type: ignore

            model = whisper.load_model(model_size)

            def run_w(wav: Path):
                res = model.transcribe(str(wav))
                return res.get("language", ""), [
                    {"start": s["start"], "end": s["end"], "text": s["text"]}
                    for s in res.get("segments", [])
                ]

            return run_w
        except Exception as e:  # noqa: BLE001
            errors.append(f"openai-whisper: {e}")

    raise RuntimeError(
        "No Whisper backend available. Install one of:\n"
        "    pip install faster-whisper      (recommended, much faster on CPU)\n"
        "    pip install openai-whisper\n"
        "Audio extraction and geet/mantra labelling work without it; only the\n"
        "speech-to-text step needs it.\n"
        "Tried:\n  " + "\n  ".join(errors)
    )


def transcribe_clip(media: Path, work: Path, lexicons: dict, runner,
                    cid: str | None = None) -> dict:
    """Extract audio, transcribe it, and label every segment."""
    cid = cid or clip_id(media.name)
    wav = work / "audio16k" / f"{cid}.wav"
    if not wav.exists():
        extract_audio(media, wav)

    language, raw_segments = runner(wav)
    segments = annotate(raw_segments, lexicons)

    result = {
        "clip_id": cid,
        "source": media.name,
        "language": language,
        "segment_count": len(segments),
        **summarise(segments),
        "geet_spans": merge_spans(segments, "geet"),
        "mantra_spans": merge_spans(segments, "mantra"),
        "segments": segments,
    }
    write_json(work / "transcripts" / f"{cid}.json", result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Transcribe wedding footage and label geet, mantras and speech.")
    ap.add_argument("--work", type=Path, required=True, help="Work folder for this wedding job")
    ap.add_argument("inputs", nargs="*", type=Path,
                    help="Media files. Omit to use every video clip in the work folder's clips.jsonl")
    ap.add_argument("--model", default="small",
                    help="Whisper model size (tiny, base, small, medium, large-v3). Default small.")
    ap.add_argument("--backend", default="auto", choices=["auto", "faster-whisper", "whisper"])
    ap.add_argument("--extract-only", action="store_true",
                    help="Only extract 16 kHz audio; skip transcription (needs no Whisper backend)")
    args = ap.parse_args()

    work = work_dir(args.work)
    lexicons = build_lexicons()

    media_files = list(args.inputs)
    if not media_files:
        media_files = [Path(c["path"]) for c in load_clips(work, "video")]
    if not media_files:
        die("No input files given and no video clips found in the work folder. "
            "Run raw_footage_ingest.py first, or pass files directly.", 2)

    if args.extract_only:
        for m in media_files:
            if not has_audio_stream(m):
                print(f"[-] {m.name}: no audio stream, skipped")
                continue
            cid = clip_id(m.name)
            out = extract_audio(m, work / "audio16k" / f"{cid}.wav")
            print(f"[✓] {m.name} -> {out}")
        return 0

    try:
        runner = _load_backend(args.model, args.backend)
    except RuntimeError as e:
        die(str(e), 3)

    failures = 0
    for m in media_files:
        if not m.exists():
            print(f"[!] missing: {m}")
            failures += 1
            continue
        if not has_audio_stream(m):
            print(f"[-] {m.name}: no audio stream, skipped")
            continue
        try:
            r = transcribe_clip(m, work, lexicons, runner)
        except Exception as e:  # noqa: BLE001 - one bad clip must not stop a 1000-clip run
            print(f"[!] {m.name}: {e}")
            failures += 1
            continue
        counts = r["label_counts"]
        print(f"[✓] {m.name} [{r['language']}]: {r['segment_count']} segments "
              f"(geet {counts.get('geet', 0)}, mantra {counts.get('mantra', 0)}, "
              f"speech {counts.get('speech', 0)})")

    if failures:
        die(f"{failures} clip(s) failed.", 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
