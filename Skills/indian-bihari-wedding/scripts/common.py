"""Shared helpers for the indian-bihari-wedding pipeline.

Work-folder layout (one folder per wedding job, never inside the raw-footage folder):

    <work>/clips.jsonl            one line per media file (ingest.py)
    <work>/inventory.md           human summary of the footage (ingest.py)
    <work>/analysis/<id>.json     per-clip picture + sound measurements (analyze.py)
    <work>/sheets/<id>.jpg        labelled contact sheet per clip (analyze.py)
    <work>/audio16k/<id>.wav      16 kHz mono audio for Whisper + audio analysis
    <work>/faces/                 face detections + embeddings (analyze.py), people.json (faces.py)
    <work>/transcripts/<id>.json  Whisper output (transcribe.py)
    <work>/tags/<id>.json         ritual / moment tags written by Claude (see references/12)
    <work>/songs/<name>.json      beat + section map of each song (beats.py)
    <work>/plans/<deliverable>.json   story plan (plan_edit.py auto, then refined)
    <work>/edl/<deliverable>.json     resolved, frame-accurate timeline (plan_edit.py resolve)
    <work>/grade/                 LUTs and grade groups (grade.py)
    <work>/out/                   FCPXML, renders, reports
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SKILL_DIR / "data"
VENV_PY = Path.home() / "video-env" / "bin" / "python"

VIDEO_EXT = {".mp4", ".mov", ".mts", ".m2ts", ".mxf", ".avi", ".mkv", ".m4v", ".3gp", ".mpg", ".mpeg", ".wmv", ".webm"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".aif", ".aiff", ".ogg", ".wma"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".dng", ".rw2"}
SKIP_EXT = {".lrv", ".thm", ".xml", ".xmp", ".bim", ".cpi", ".bdm", ".mpl", ".ind", ".bup", ".ifo", ".db", ".ds_store", ".srt", ".txt"}


# ---------------------------------------------------------------- paths / io

def work_dir(path: str | Path) -> Path:
    w = Path(path).expanduser().resolve()
    for sub in ("analysis", "sheets", "audio16k", "faces", "transcripts", "tags", "songs", "plans", "edl", "grade", "out"):
        (w / sub).mkdir(parents=True, exist_ok=True)
    return w


def clip_id(rel_path: str) -> str:
    """Stable id from the path relative to the footage root (survives re-ingest)."""
    return "c" + hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:10]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def read_json(path: Path, default=None):
    if not Path(path).exists():
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def load_clips(work: Path, kind: str | None = "video") -> list[dict]:
    rows = read_jsonl(work / "clips.jsonl")
    return [r for r in rows if kind is None or r.get("kind") == kind]


def clips_by_id(work: Path) -> dict[str, dict]:
    return {c["id"]: c for c in load_clips(work, None)}


def load_rituals() -> list[dict]:
    return read_json(DATA_DIR / "rituals.json", [])["rituals"]


# ---------------------------------------------------------------- processes

def run(cmd: list[str], check: bool = True, timeout: float | None = None, quiet: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed ({p.returncode}): {p.stderr[-800:]}")
    if not quiet and p.stderr:
        sys.stderr.write(p.stderr)
    return p


def ffprobe(path: Path) -> dict:
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)], check=False)
    try:
        return json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        return {}


def n_workers(default_cap: int = 6) -> int:
    return max(1, min(default_cap, (os.cpu_count() or 4) - 2))


# ---------------------------------------------------------------- time

def parse_rate(r: str | None) -> Fraction | None:
    if not r or r in ("0/0", "0"):
        return None
    try:
        f = Fraction(r)
    except (ValueError, ZeroDivisionError):
        return None
    return f if f > 0 else None


def tc(sec: float) -> str:
    sec = max(0.0, float(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}" if h >= 1 else f"{int(m)}:{s:05.2f}"


def fcp_time(sec: float, fps: Fraction) -> str:
    """Seconds -> FCPXML rational time snapped to whole frames of `fps`."""
    frames = round(Fraction(sec).limit_denominator(10**6) * fps)
    t = Fraction(frames) / fps
    return "0s" if t == 0 else f"{t.numerator}/{t.denominator}s"


def snap(sec: float, fps: Fraction) -> float:
    return float(round(Fraction(sec).limit_denominator(10**6) * fps) / fps)


# ---------------------------------------------------------------- misc

def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def die(msg: str, code: int = 1):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)
