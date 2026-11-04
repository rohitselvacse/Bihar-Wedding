---
name: bihari-indian-wedding-film-editor
description: >-
  Master video editing framework for Indian and Bihari weddings (Patna/Mithila/Magadh/Bhojpuri).
  Use when editing raw wedding footage (500-1000 clips, 100-200GB, 6-7 hours), ingesting multi-camera media,
  tracking family members across clips, restoring live courtyard folk geet (Sharda Sinha vivah geet),
  balancing Sanskrit Vedic mantras, and generating Apple Final Cut Pro XML timelines for
  Teaser (1-3 min), Cinematic Trailer (5-10 min), and Master Documentary (1-3 hours).
---

# Bihari & Indian Wedding Video Editing Master Skill

This skill turns Antigravity into an elite Indian and Bihari wedding film director, lead editor, and colorist. It handles end-to-end post-production for massive wedding projects (500 to 1,000 raw video clips, 100–200 GB, 6 to 7 hours of footage) shot across Patna and the greater Bihar region.

---

## 1. Operational workflow

Each stage writes into one job folder and reads what the stage before it wrote,
so you can stop after any stage and inspect the result. Every script takes the
same `--work` path.

### Step 1 - Ingest the rushes

Scan the footage, assign each file a stable id from its path, and read its real
format with ffprobe.

```bash
python3 scripts/raw_footage_ingest.py --root /path/to/raw_footage --work ./wedding_job
```

Writes `clips.jsonl`, one line per media file.

### Step 2 - Transcribe, and find the geet and the mantras

Extracts 16 kHz audio, transcribes it, and labels every segment as geet, mantra
or speech, so you know which minutes of a seven-hour rush hold the family's
singing and the pandit's recitation.

```bash
python3 scripts/transcribe.py --work ./wedding_job --model small
```

Writes `transcripts/<clip>.json` with `geet_spans` and `mantra_spans`. Needs
`pip install faster-whisper`. Use `--extract-only` to prepare the audio without
transcribing.

### Step 3 - Match people across clips

Samples frames, embeds faces, and clusters them so one cluster is one person.
Clusters come out anonymous and ranked by screen presence; name the ones you
recognise and rerun, and the rest of the pipeline then works in role codes.

```bash
python3 scripts/faces.py --work ./wedding_job
python3 scripts/faces.py --work ./wedding_job --name person_001=B01 --name person_002=G01
```

Writes `faces/people.json`, the per-clip tag files the auditor reads, and
`faces/coverage_audit.json` flagging anyone at risk of being cut. Needs
`pip install insightface onnxruntime opencv-python-headless`. Use
`--sample-only` to extract frames without detection.

### Step 4 - Map the songs

Measures tempo, a beat grid and energy sections for each song you plan to cut
against.

```bash
python3 scripts/beats.py /path/to/songs/*.mp3 --work ./wedding_job
```

Writes `songs/<name>.json`. It reports `steady_tempo: false` for live geet with
no regular pulse; those are cut to transcript phrases instead of a beat grid.

### Step 5 - Check who might be left out

```bash
python3 scripts/family_face_tracker.py --work ./wedding_job
```

Reports screen time per role. It audits the tag files written in step 3, so run
that first; with no tags it correctly reports everybody as missing.

### Step 6 - Clean the audio

```bash
python3 scripts/audio_cleanup_pipeline.py --test
```

Chain: 80 Hz high-pass, 50 Hz mains notch, 320 Hz mud cut, presence lift, and
-16 dB ducking under speech and mantras.

### Step 6b - Measure exposure and colour

Reads each clip's luma and chroma with ffmpeg and groups clips that need the
same correction, because the unit of grading work is the setup rather than the
clip.

```bash
python3 scripts/grade.py --work ./wedding_job
```

Writes `grade/measurements.json`, `grade/plan.json` and a readable
`grade/report.md` listing each look, a starting correction in stops, and an
ffmpeg filter for previewing it. The clips worth your attention are the ones
that do not match their neighbours.

These are whole-frame averages, so a frame full of red lehenga reads warm
whether or not the white balance is wrong. Treat a cast reading as evidence,
not a verdict, and apply the grade in Final Cut Pro so it stays
non-destructive. Skin tone is not judged here; follow `references/10`.

### Step 7 - Plan the edit

Turns everything above into an edit decision list for each deliverable: rituals
in calendar order, cuts on the beat, and every known person kept in the cut.

```bash
python3 scripts/plan_edit.py --work ./wedding_job --type all
```

Writes `edl/teaser.json`, `edl/trailer.json` and `edl/master.json`. It prints
any problem it finds rather than planning around it: a deliverable outside its
required runtime, a person who never appears, clips that matched no ritual. Add
`--strict` to fail instead of warn.

### Step 8 - Export for Final Cut Pro

```bash
python3 scripts/fcpxml_generator.py --edl ./wedding_job/edl/master.json \
    --out ./wedding_job/out --media-root /Volumes/WEDDING_MEDIA
```

`--media-root` is where your footage lives; relative clip paths resolve against
it. Without it a machine-neutral placeholder is written and Final Cut Pro asks
you to relink, which is deliberate: generated files must never carry your own
home directory into a shared repository.

Confirm the schema version your Final Cut Pro writes, and pass it if it differs
from the default:

```bash
head -3 /path/to/any-export-from-your-fcp.fcpxml
python3 scripts/fcpxml_generator.py --edl ... --fcpxml-version 1.13
```

Run without `--edl` to produce demo timelines from built-in shot lists. Those
are for checking the FCPXML shape only; they are not an edit of anybody's
wedding.

### Optional - run the stages in sequence

```bash
python3 scripts/agent_graph_orchestrator.py --work ./wedding_job
```

A convenience runner over the stages above. Its QA step checks data produced
earlier in the same run, so treat its result as a smoke test, not verification.

### Checking the reference library

The 165 reference videos in `references/` and `library/cards/` have never been
checked against YouTube. Before relying on them:

```bash
python3 scripts/validate_video_library.py
```

See `docs/requirements.md` for what is implemented, what is documentation only,
and what is still missing.

---

## 2. The 16 Bihari Ritual Sequence (Master Chronology)

When assembling timelines, strictly adhere to the cultural sequence:

1. **Cheka & Tilak**: Formal engagement; bride's father applies sandalwood/vermilion tilak, gifts yellow pitambar and silver shagun.
2. **Matkor / Mati Mangal**: Women march to riverbank/field with brass pots; sacred clay excavated to build mandap base and chulha.
3. **Marava / Madwa**: Bamboo poles (*Hariyer Baans*) and mango leaves erected into canopy; clay chulha installed.
4. **Silpohka & Imrit Chhawana**: Mother and maternal aunts grind urad dal on stone silbatta; sacred sweets fried on chulha.
5. **Haldi / Haridra & Ubtan**: Turmeric roots crushed; yellow paste applied with green doob grass; 120fps water splashes.
6. **Mehndi & Sangeet Gala**: Intimate henna patterns on palms; high-octane family dance competition.
7. **Baraat Aagman, Dwar Puja & Parichan**: Groom arrives with brass band; mother-in-law performs aarti and playfully catches groom's nose!
8. **Jaymala / Varmala**: Grand stage exchange of flower garlands under fireworks and flower petal cannons.
9. **Kanyadaan & Panigrahana**: Father pours holy water over joined palms of bride and groom; reciting lineage sankalpa.
10. **Gathbandhan & Saat Phere**: Groom's stole tied to bride's red chunari; seven sacred vows around agni kund.
11. **Sindoor Daan (The Climax)**: Groom traces vibrant vermilion in a continuous stroke from the very TIP of bride's nose to the crown of her maang with a silver rupee coin.
12. **Chumawan**: Relatives touch sacred grass and yellow rice to couple's knees, shoulders, and heads.
13. **Kohbar Chamber & Traditional Games**: Couple enters Madhubani-painted chamber (lotus, fish, bamboo); race to find gold ring in milk platter (*Angoothi Chupana*).
14. **Vidai / Samdhauni**: Bride tosses raw puffed rice (*Dhan*) backward over head into mother's pallu; heartbreaking farewell.
15. **Vadhu Pravesh / Griha Pravesh**: Bride knocks over rice kalash with right toe; steps into red alta leaving divine Lakshmi footprints.
16. **Bahubhoj / Grand Reception**: Opulent banquet; stage greeting queue (3-cut rhythm: Wide -> Gift/Envelope -> Candid laugh).

---

## 3. Reference Library Navigation

Detailed reference manuals are available in `references/`:
* [01_video_styles_and_durations.md](./references/01_video_styles_and_durations.md) — Teaser (1-3m), Trailer (5-10m), Master (1-3h) visual grammar.
* [02_editing_color_audio_fcpx.md](./references/02_editing_color_audio_fcpx.md) — FCPX editing mechanics, speed ramping, Indian skin tone vectorscope alignment, and color grading.
* [03_indian_wedding_music_matrix.md](./references/03_indian_wedding_music_matrix.md) — Bollywood & fusion music matrix across all wedding ceremonies.
* [04_bihari_rituals_complete_guide.md](./references/04_bihari_rituals_complete_guide.md) — Comprehensive cultural blueprint for Bihari & Patna weddings.
* [05_bihari_folk_geet_and_mantras.md](./references/05_bihari_folk_geet_and_mantras.md) — 29 traditional Maithili/Bhojpuri folk geet (Sharda Sinha) and Sanskrit mantras.
* [06_family_tracking_and_reception_guide.md](./references/06_family_tracking_and_reception_guide.md) — Multi-character tracking and reception stage 3-cut rhythm.
* [07_chronological_assembly_pipeline.md](./references/07_chronological_assembly_pipeline.md) — Storage directory hierarchy and 5-phase editing assembly.
* [08_video_library_150.md](./references/08_video_library_150.md) — Curated master library of 165 analyzed YouTube wedding films and tutorials.
* [09_agent_graph_architecture.md](./references/09_agent_graph_architecture.md) — Graph topology, node roles, and QA verification loops.

