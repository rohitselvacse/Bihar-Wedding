#!/usr/bin/env python3
"""Beat, tempo and section mapping for wedding songs and geet.

The brief requires the teaser and trailer to cut on the beat ("all these things
will be a play on the beats... small cuts will be there in the beats wise"), and
requires the master film to be assembled in ritual sequence. Neither is possible
without knowing where the beats actually are, so this module measures them
rather than assuming them.

Produces, per song, `<work>/songs/<name>.json`:

    bpm            estimated tempo
    beats          beat times in seconds
    downbeats      every 4th beat, for bar-level cuts
    sections       energy-derived segment boundaries (intro / build / drop ...)
    duration       song length in seconds

Implementation notes
--------------------
Onsets come from spectral flux over a short-time Fourier transform, tempo from
autocorrelation of the onset envelope, and beat phase from the offset that best
aligns a constant-tempo grid to the onsets. That assumes a roughly steady tempo,
which holds for the film songs and mashups used in wedding edits. Live folk geet
sung by relatives often has no steady tempo at all; for those, cut to phrase
boundaries from the transcript instead, and treat `bpm_confidence` as the signal
for which case you are in.

Depends only on numpy and ffmpeg, both already required by this project, so the
beat grid can be computed anywhere without installing a DSP stack.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import die, work_dir, write_json  # noqa: E402

SAMPLE_RATE = 22050
FRAME = 1024
HOP = 512

# Tempo search range. Indian wedding repertoire runs from slow vidai songs
# around 60 BPM up to fast sangeet and baraat numbers past 170.
MIN_BPM = 55.0
MAX_BPM = 200.0

# Minimum absolute onset strength before we accept that a file has any
# rhythmic events at all. Measured in summed log-magnitude spectral flux.
# Real percussive onsets land around 300 in these units; a sustained tone with
# no attacks peaks near 0.05, because its only variation is FFT phase jitter.
# The normalised envelope cannot tell these apart, since dividing by a tiny
# peak rescales that jitter to look like strong onsets, so the check has to be
# made before normalisation.
MIN_ONSET_STRENGTH = 1.0


def load_audio_mono(path: Path, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Decode any audio or video file to mono float32 PCM via ffmpeg."""
    # NOTE: deliberately not using common.run() here. It decodes stdout as text,
    # which would corrupt raw PCM through a lossy UTF-8 decode. Binary output
    # must be captured as bytes.
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "-"],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        detail = proc.stderr.decode("utf-8", errors="replace")[-300:].strip()
        raise RuntimeError(f"ffmpeg could not decode audio from {path}: {detail}")
    audio = np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32)
    if audio.size == 0:
        raise RuntimeError(f"no audio samples decoded from {path}")
    return audio


def onset_envelope(audio: np.ndarray, frame: int = FRAME, hop: int = HOP) -> tuple[np.ndarray, float]:
    """Spectral-flux onset strength per hop, plus the pre-normalisation peak.

    The raw peak is returned because it is the only reliable way to tell audio
    with no onsets from audio with onsets; see MIN_ONSET_STRENGTH.
    """
    if audio.size < frame:
        return np.zeros(1, dtype=np.float32), 0.0

    n_frames = 1 + (audio.size - frame) // hop
    window = np.hanning(frame).astype(np.float32)

    # Build the magnitude spectrogram frame by frame via a strided view, which
    # avoids materialising a copy of the whole signal per frame.
    idx = np.arange(frame)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = audio[idx] * window
    mag = np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)

    # Log compression keeps loud percussive hits from dominating the envelope.
    mag = np.log1p(mag)

    # Positive spectral difference: energy appearing is an onset, energy
    # decaying is not.
    flux = np.diff(mag, axis=0)
    env = np.maximum(flux, 0.0).sum(axis=1)
    env = np.concatenate([[0.0], env]).astype(np.float32)

    # Remove slow drift so a loud chorus does not swamp a quiet intro.
    if env.size > 9:
        kernel = np.ones(9, dtype=np.float32) / 9.0
        baseline = np.convolve(env, kernel, mode="same")
        env = np.maximum(env - baseline, 0.0)

    peak = float(env.max())
    return (env / peak if peak > 0 else env), peak


def count_onsets(env: np.ndarray, threshold: float = 0.12) -> int:
    """Count distinct onset peaks in the envelope.

    A sustained tone or room tone has almost no onsets, but its normalised
    envelope is mostly noise, and autocorrelating noise can still yield a
    confident-looking periodicity. Counting real peaks separates "no beats
    here" from "a steady beat I measured", so a harmonium drone or ambient
    room tone never receives a phantom beat grid for the planner to cut to.
    """
    if env.size < 3:
        return 0
    peaks = (env[1:-1] >= env[:-2]) & (env[1:-1] > env[2:]) & (env[1:-1] >= threshold)
    return int(np.count_nonzero(peaks))


def estimate_tempo(env: np.ndarray, sample_rate: int = SAMPLE_RATE, hop: int = HOP) -> tuple[float, float]:
    """Estimate BPM by autocorrelating the onset envelope.

    Returns (bpm, confidence) where confidence is the normalised strength of the
    winning lag, in 0..1. Low confidence means the track has no steady pulse,
    which is common for live geet.
    """
    if env.size < 16:
        return 0.0, 0.0

    # A beat period is rarely a whole number of analysis hops (140 BPM is 18.46
    # hops at this hop size), so successive onsets land at different offsets
    # inside their frame and their energy splits across neighbours. That makes
    # the true-period correlation weaker than the double-period one and flips
    # the estimate to half tempo. Smoothing the envelope first re-merges that
    # split energy. Only tempo estimation uses the smoothed copy; beat phase is
    # tracked on the sharp envelope so cut points stay precise.
    smooth_kernel = np.array([0.25, 0.5, 0.25], dtype=np.float32)
    env_s = np.convolve(env, smooth_kernel, mode="same")

    env_s = env_s - env_s.mean()
    ac = np.correlate(env_s, env_s, mode="full")[env_s.size - 1:]
    if ac[0] <= 0:
        return 0.0, 0.0
    ac = ac / ac[0]

    fps = sample_rate / hop
    min_lag = max(1, int(round(fps * 60.0 / MAX_BPM)))
    max_lag = min(ac.size - 1, int(round(fps * 60.0 / MIN_BPM)))
    if max_lag <= min_lag:
        return 0.0, 0.0

    lags = np.arange(min_lag, max_lag + 1)
    window = ac[min_lag:max_lag + 1]
    candidate_bpm = 60.0 * fps / lags

    # Autocorrelation cannot tell a tempo from half or double that tempo: a grid
    # at 60 BPM fits a 120 BPM track just as well, and hop quantisation plus
    # musical backbeat emphasis often make the wrong octave score higher. Weight
    # candidates by a log-normal prior centred on 120 BPM, roughly an octave
    # wide, which is the usual resolution for this ambiguity. Without it this
    # detector reported 120 BPM click tracks as 60 BPM.
    prior = np.exp(-0.5 * (np.log2(candidate_bpm / 120.0) / 0.75) ** 2)
    scored = window * prior

    best_i = int(np.argmax(scored))

    # Refine to sub-hop precision with a parabola through the winning lag and
    # its neighbours. Without this the tempo is quantised to whole hops, which
    # at this hop size is a ~2% error, enough for a beat grid to drift audibly
    # across a five-minute song.
    abs_lag = lags[best_i]
    if 0 < abs_lag < ac.size - 1:
        y0, y1, y2 = float(ac[abs_lag - 1]), float(ac[abs_lag]), float(ac[abs_lag + 1])
        denom = y0 - 2.0 * y1 + y2
        delta = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-12 else 0.0
        delta = max(-0.5, min(0.5, delta))
        refined_lag = abs_lag + delta
    else:
        refined_lag = float(abs_lag)

    bpm = float(60.0 * fps / refined_lag) if refined_lag > 0 else 0.0
    # Report the unweighted correlation, so confidence reflects how periodic the
    # signal actually is rather than how much the prior liked the answer.
    return bpm, float(max(0.0, window[best_i]))


def track_beats(env: np.ndarray, bpm: float, sample_rate: int = SAMPLE_RATE, hop: int = HOP) -> list[float]:
    """Place a constant-tempo beat grid at the phase that best fits the onsets."""
    if bpm <= 0 or env.size == 0:
        return []

    fps = sample_rate / hop
    period = fps * 60.0 / bpm
    if period < 1:
        return []

    # Try every phase within one beat period and keep the grid that collects the
    # most onset energy.
    best_phase, best_score = 0.0, -1.0
    for phase in np.arange(0.0, period, max(0.5, period / 32.0)):
        positions = np.arange(phase, env.size, period)
        score = float(env[positions.astype(int)].sum())
        if score > best_score:
            best_phase, best_score = float(phase), score

    positions = np.arange(best_phase, env.size, period)
    return [round(float(p) / fps, 4) for p in positions]


def detect_sections(env: np.ndarray, audio: np.ndarray, sample_rate: int = SAMPLE_RATE,
                    hop: int = HOP, min_section_sec: float = 8.0) -> list[dict]:
    """Segment the song by sustained changes in loudness.

    Wedding edits need to know where a song lifts (so the jaimala or the drop
    lands with it) and where it falls away (so a vidai can breathe). Short-time
    RMS, smoothed and differenced, locates those turns well enough to plan from.
    """
    if audio.size < sample_rate:
        return []

    win = int(sample_rate * 0.5)
    n = audio.size // win
    if n < 3:
        return []
    rms = np.sqrt((audio[: n * win].reshape(n, win) ** 2).mean(axis=1) + 1e-12)
    rms_db = 20.0 * np.log10(rms / (rms.max() + 1e-12) + 1e-12)

    k = max(3, int(round(4.0 / 0.5)))  # ~4 second smoothing
    smooth = np.convolve(rms_db, np.ones(k) / k, mode="same")
    change = np.abs(np.diff(smooth))
    if change.size == 0:
        return []

    threshold = float(change.mean() + 1.2 * change.std())
    min_gap = int(round(min_section_sec / 0.5))

    boundaries = [0]
    for i, c in enumerate(change):
        if c >= threshold and (i - boundaries[-1]) >= min_gap:
            boundaries.append(i)
    boundaries.append(n)

    sections = []
    for a, b in zip(boundaries[:-1], boundaries[1:]):
        if b - a < 2:
            continue
        level = float(smooth[a:b].mean())
        sections.append({
            "start": round(a * 0.5, 3),
            "end": round(b * 0.5, 3),
            "mean_level_db": round(level, 2),
        })

    # Label sections by relative loudness so a planner can ask for "the loudest
    # section" without re-deriving it.
    if sections:
        levels = sorted(s["mean_level_db"] for s in sections)
        quiet_cut = levels[max(0, len(levels) // 3 - 1)]
        loud_cut = levels[min(len(levels) - 1, (2 * len(levels)) // 3)]
        for s in sections:
            lvl = s["mean_level_db"]
            s["energy"] = "low" if lvl <= quiet_cut else ("high" if lvl >= loud_cut else "mid")
    return sections


def analyse_song(path: Path) -> dict:
    """Full beat and section map for one song or geet recording."""
    audio = load_audio_mono(path)
    duration = audio.size / SAMPLE_RATE

    env, raw_peak = onset_envelope(audio)
    bpm, confidence = estimate_tempo(env)
    onsets = count_onsets(env)

    # Require a real rhythmic event roughly every two seconds before claiming a
    # steady tempo, so sustained audio with no attacks is reported honestly as
    # having no pulse rather than being handed a fabricated grid.
    min_onsets = max(8, int(duration / 2.0))
    has_onsets = raw_peak >= MIN_ONSET_STRENGTH
    has_pulse = bool(has_onsets and confidence >= 0.15 and bpm > 0 and onsets >= min_onsets)

    beats = track_beats(env, bpm) if has_pulse else []
    beats = [b for b in beats if b <= duration]
    sections = detect_sections(env, audio)

    return {
        "source": path.name,
        "duration": round(duration, 3),
        "bpm": round(bpm, 2) if has_pulse else 0.0,
        "bpm_confidence": round(confidence, 4),
        "onset_count": onsets if has_onsets else 0,
        "onset_strength": round(raw_peak, 4),
        "steady_tempo": has_pulse,
        "beat_count": len(beats),
        "beats": beats,
        "downbeats": beats[::4],
        "sections": sections,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Map beats, tempo and sections of wedding songs.")
    ap.add_argument("inputs", nargs="+", type=Path, help="Audio or video files to analyse")
    ap.add_argument("--work", type=Path, required=True, help="Work folder for this wedding job")
    args = ap.parse_args()

    work = work_dir(args.work)
    failures = 0

    for src in args.inputs:
        if not src.exists():
            print(f"[!] missing: {src}")
            failures += 1
            continue
        try:
            result = analyse_song(src)
        except Exception as e:  # noqa: BLE001 - one bad file must not stop the batch
            print(f"[!] {src.name}: {e}")
            failures += 1
            continue

        out = work / "songs" / f"{src.stem}.json"
        write_json(out, result)
        pulse = "steady" if result["steady_tempo"] else "no steady pulse (cut to phrases)"
        print(f"[✓] {src.name}: {result['bpm']:.1f} BPM, {result['beat_count']} beats, "
              f"{len(result['sections'])} sections, {pulse}")
        print(f"    -> {out}")

    if failures:
        die(f"{failures} file(s) could not be analysed.", 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
