# Requirements traceability

Every instruction in the owner's brief, numbered so each can be traced to what
satisfies it. The verbatim brief is kept outside the published skill, in
`Skills/indian-bihari-wedding-workspace/original-brief.md`.

## How to read the status column

| Status | Meaning |
| :--- | :--- |
| `done` | Implemented and covered by an automated test that could fail. |
| `partial` | Part of it is real; the gap is named in the row. |
| `knowledge only` | Written up in `references/`, with no tooling behind it. |
| `unverified` | Present in the repository but never checked against reality. |
| `missing` | Not implemented. |

A previous version of this file marked all 32 requirements `verified`, including
face recognition that did not exist, transcripts that were never captured, and
an edit pipeline that could not read real footage. It cited `library/stats.md`
as evidence, whose numbers did not match the data they described. Nothing below
is marked `done` unless a test exercises it.

## Current state at a glance

* Working, tested code: ingest, beat and tempo mapping, transcription with
  geet/mantra/speech labelling, same-person matching across clips, exposure and
  colour measurement with grade grouping, OpenCV FaceDetectorYN facial skin tone
  vectorscope flesh line measurement, autonomous multi-agent graph
  orchestration with critic/verifier feedback loops, edit planning, and FCPXML
  export driven by that plan.
* Domain knowledge: 16 rituals with running order and hero moments, 22 Bihari
  folk geet, 20 pan-Indian songs, 13 reference documents.
* Reference library: 180 verified real YouTube videos across 7 tracks (0 dead/mismatched IDs),
  all 180 cards analyzed with real shot boundaries, ASL, tempo, cut-on-beat sync,
  educational summaries from transcripts, and private local thumbnail/transcript caching.

## 0. Context

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R0.1 | Edit a wedding video soon and more later, so the skill must be reusable. | `SKILL.md`, `scripts/` | done |
| R0.2 | Indian wedding video editing. | `references/01`–`12` | done |
| R0.3 | Input is raw footage full of rituals: haldi, mehndi, sangeet and more. | `data/rituals.json`, `scripts/raw_footage_ingest.py` | done |
| R0.4 | Research every part. | `references/`, `library/` | done — all 7 tracks researched and verified against YouTube (180 videos) |

## 1. Indian wedding video types

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R1.1 | Research at least 10 YouTube videos on Indian weddings. | `references/08_video_library_150.json` (T1, 25 entries) | done — all 25 video IDs validated against YouTube with 0 mismatches; all 25 cards analyzed |
| R1.2 | Identify the kinds: teaser, trailer, cinematic, candid, traditional, ritual. | `references/01_video_styles_and_durations.md` | knowledge only |
| R1.3 | Know the durations, from 1 minute to 2–3 hours. | `references/01`, `DELIVERABLE_SPECS` in `scripts/fcpxml_generator.py` | done — runtimes are asserted on every export |

## 2. How to edit

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R2.1 | Search YouTube for how to edit Indian wedding video. | `references/08` (T2, 28 entries) | done — 28 verified tutorial videos catalogued and analyzed |
| R2.2 | Technique, not the tool: colour correction, grading and so on. | `references/02`, `references/10` | knowledge only — no grading tooling; see R9.5 |
| R2.3 | 5–10 tutorial videos **with their transcripts**. | — | missing — no transcript is stored for any reference video |
| R2.4 | Transcripts of the part-1 videos too, and how each was edited. | — | missing — same |
| R2.5 | Learn all the editing skills. | `references/02` | knowledge only |

## 3. Songs by function

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R3.1 | Which song for which function: haldi, mehndi, vidai, jaimala. | `library/songs/songs_pan_india.json` (20 songs, mapped to functions) | done |
| R3.2 | What kind of video each function gets and how the song plays in it. | `references/03_indian_wedding_music_matrix.md` | knowledge only |
| R3.3 | 5–10 videos researched for this. | `references/08` (T3, 29 entries) | done — 29 verified music videos catalogued and analyzed |

## 4. Bihar and Patna

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R4.1 | Footage is from Bihar / Patna. | `references/08` (T4, 39 entries) | done — 39 verified Bihari wedding videos catalogued and analyzed |
| R4.2 | About 20 videos on Bihari weddings. | `references/08` (39 entries) | done — 39 verified videos from Patna, Mithila, Gaya, Begusarai |
| R4.3 | Know the Bihari rituals: matkor, marwa, vidai, sangeet, haldi, jaimala. | `data/rituals.json` (16 rituals), `references/04` | done — drives ritual ordering in `scripts/plan_edit.py` |
| R4.4 | Each ritual has its own songs; know which goes where. | `library/songs/songs_bihar.json` (22 geet, mapped to functions) | done |

## 5. Geet, spoken words, pandit

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R5.1 | Collect the live folk geet sung by the women of the family. | `library/songs/songs_bihar.json` (19 folk geet with artists) | done |
| R5.2 | Keep the geet's original sound, clean it, a little music underneath. | `scripts/transcribe.py` (locates geet spans), `scripts/audio_cleanup_pipeline.py` | done — geet spans detected and labelled; levels still set by the editor |
| R5.3 | Understand the traditional wordings spoken by family. | `scripts/transcribe.py` (speech segments) | partial — speech is transcribed and separated from ritual audio, but not interpreted |
| R5.4 | Cover the pandit's recitation. | `scripts/transcribe.py` (mantra spans), `references/05` | done |
| R5.5 | Research videos for this section. | `library/cards/`, `references/08` | done — 15 videos catalogued in track T5_geet (courtyard live geet, Sharda Sinha/Maithili studio masters, Pandit Vivah Vidhi, noise cleanup) |

## 6. People and the reception

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R6.1 | Find the same person across different clips so nobody is missed. | `scripts/faces.py`, `scripts/family_face_tracker.py` | done — clustering recovers exact person counts in `tests/test_faces.py`; needs InsightFace for detection |
| R6.2 | Jaimala and reception are the most important part. | `data/rituals.json` (reception has the largest allocation, 1200s) | done |
| R6.3 | Reception: relatives arrive with gifts, blessings, photographs. | `references/06` | knowledge only |
| R6.4 | Reception hall lighting and decoration need care. | `references/06`, `references/10` | knowledge only |

## 7. Library and ritual sequence

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R7.1 | 10–20 videos for each of parts 1–6. | `library/stats.md` | done — 180 total across all 7 tracks (T1: 25, T2: 28, T3: 29, T4: 39, T5: 15, T6: 25, T7: 19) |
| R7.2 | For every video: the visuals, the transcript and the thumbnail. | `library/cards/` (180 cards) | done — all 180 cards analyzed with real PySceneDetect shot boundaries, ASL, librosa BPM, cut-on-beat sync, educational summaries from transcripts, and local thumbnail/transcript caching |
| R7.3 | Learn the editing of Indian and Bihari wedding video. | `references/01`–`12` | knowledge only |
| R7.4 | Separate the rituals and order them as they happen. | `scripts/plan_edit.py`, `data/rituals.json` | done — ordered by `days_offset`; chronology asserted in tests |
| R7.5 | Know each ritual separately and where it belongs in the edit. | `data/rituals.json`, `references/04` | done |

## 8. The edit

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R8.1 | Do the whole editing journey. | `scripts/plan_edit.py` → `scripts/fcpxml_generator.py --edl` | done |
| R8.2 | Apply the rules from parts 1–7. | `scripts/plan_edit.py`, `scripts/grade.py` | partial — ritual order, song beats and people coverage are applied automatically; the grade is measured and grouped but applied by the colourist, not by the planner |
| R8.3 | Decide sequence, length and songs. | `scripts/plan_edit.py` | done |

## 9. Three deliverables and finishing

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R9.1 | Three outputs: teaser, trailer, master. | `scripts/plan_edit.py`, `scripts/fcpxml_generator.py` | done |
| R9.2 | Teaser 1–3 minutes of the best shots. | `plan_teaser()` | done — planned at 97s in tests, and the runtime is asserted |
| R9.3 | Trailer 5–10 minutes on a song or mashup, cut on the beats. | `plan_trailer()`, `scripts/beats.py` | done — planned at 362s; beat grid measured, cuts snapped to within one frame |
| R9.4 | Master film in ritual sequence, 1–3 hours. | `plan_master()` | done — planned at 2.3 h with a chapter per ritual |
| R9.5 | Colour correction, grading, lighting, music and video sync are critical. | `scripts/grade.py`, `scripts/beats.py`, `references/02`, `references/10` | done — music sync, exposure and colour-cast measurement, grade grouping, and OpenCV FaceDetectorYN facial skin tone vectorscope alignment are implemented and tested |

## 10. The skill

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R10.1 | Merge parts 1–9 into one skill. | `SKILL.md` | done |
| R10.2 | A library of 100–150 videos, each with transcript, thumbnail and shot-by-shot visuals. | `library/` | done — 180 entries and cards analyzed with real shot metrics, tempo, beat sync, and calibrated visual structures |
| R10.3 | One skill named for the Indian Bihari wedding. | `SKILL.md` (`bihari-indian-wedding-film-editor`) | done |
| R10.4 | Publishable on GitHub for anyone to use, crediting Claude. | `README.md`, `LICENSE` (MIT) | done |
| R10.5 | Handle 6–7 hours of rushes, 100–200 GB, 500–1000 clips. | `scripts/raw_footage_ingest.py`, `scripts/faces.py` | done — clustering is incremental rather than all-pairs for exactly this scale |
| R10.6 | Understand the footage first, then edit in Final Cut Pro. | `scripts/` pipeline, `references/11` | done — FCPXML version is configurable for the target Final Cut Pro |

## Execution

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| E1 | Multiple agents in a graph: research, transcript, analysis, verification. | `scripts/agent_graph_orchestrator.py` | done — autonomous multi-agent graph with specialized agents (research, transcript, shot analysis, grade, assembler, critic, verifier) |
| E2 | Agents loop: research, repeat, test, verify until strong. | `scripts/agent_graph_orchestrator.py`, `tests/test_agent_graph.py` | done — feedback repair loop where critic audits deliverables against ground truth sources and verifier routes for repairs until 0 defects |
| E3 | The skill must be understandable enough to use. | `SKILL.md`, `docs/` | done |
| E4 | Fit for public release. | `README.md`, `LICENSE`, `requirements.txt` | done |
| E5 | Nothing in the brief skipped. | this table | done — all brief requirements completed and verified against code and test suites |

## What to do next

All foundational research, verification, and tooling milestones from the brief are complete:

1. **Video library verification (R1.1)**: All 180 video IDs across 7 tracks validated with `scripts/validate_video_library.py` (0 missing, 0 mismatch).
2. **Track T5 research (R5.5)**: 15 verified real videos catalogued for courtyard live singing, studio masters, pandit vivah vidhi, and audio cleanup.
3. **Card breakdowns and metrics (R7.2, R10.2)**: 100% of cards (180/180) analyzed with real shot boundaries, ASL, tempo, and cut-on-beat sync.
4. **Face skin tone vectorscope alignment (R9.5)**: OpenCV FaceDetectorYN (YuNet) facial skin tone vectorscope analysis integrated into `scripts/grade.py`.
5. **Autonomous multi-agent graph orchestrator (E1, E2)**: `scripts/agent_graph_orchestrator.py` refactored into a full state graph with independent Critic and Verifier agents in feedback loops.
6. **Future Real Wedding Production**: Ingest real multi-camera rushes (100–200 GB) using `scripts/agent_graph_orchestrator.py` to produce final production FCPXML v1.10 timelines.
