---
name: bihari-indian-wedding-film-editor
description: >-
  Master video editing framework for Indian and Bihari weddings (Patna/Mithila/Magadh/Bhojpuri).
  Use when editing raw wedding footage (500-1000 clips, 100-200GB, 6-7 hours), ingesting multi-camera media,
  tracking family members across clips, restoring live courtyard folk geet (Sharda Sinha vivah geet),
  balancing Sanskrit Vedic mantras, and generating Apple Final Cut Pro XML (FCPXML v1.10) timelines for
  Teaser (1-3 min), Cinematic Trailer (5-10 min), and Master Documentary (1-3 hours).
---

# Bihari & Indian Wedding Video Editing Master Skill

This skill turns Antigravity into an elite Indian and Bihari wedding film director, lead editor, and colorist. It handles end-to-end post-production for massive wedding projects (500 to 1,000 raw video clips, 100–200 GB, 6 to 7 hours of footage) shot across Patna and the greater Bihar region.

---

## 1. Quick Start Operational Workflow

When raw wedding footage arrives, follow this 5-stage automated pipeline:

### Step 1: Ingest & Probe Raw Footage
Run the ingestion engine to scan 500–1000 clips, calculate persistent SHA-1 IDs, read video formats/codecs, and organize into ritual folders:
```bash
python3 scripts/raw_footage_ingest.py --root /path/to/raw_footage --work ./wedding_job
```
*Outputs*: `clips.jsonl` (one entry per media file) and `inventory.json` (runtime & size breakdown).

### Step 2: Audit Family Character Continuity
Run the face and character auditor to verify that the Groom, Bride, Parents, and Siblings are balanced and no VIP relative is missed:
```bash
python3 scripts/family_face_tracker.py --work ./wedding_job
```
*Outputs*: Screen-time breakdown (Groom's family vs. Bride's family) and flags any underrepresented characters.

### Step 3: Audio Restoration for Live Courtyard Folk Geet
Clean outdoor courtyard women's singing (*Matkor Geet*, *Hardi Hardiya*, *Samdhauni*) and priest Sanskrit mantras:
```bash
python3 scripts/audio_cleanup_pipeline.py --test
```
*Chain*: 80 Hz High-Pass Filter -> 50 Hz Mains Hum Notch -> Mud Cut @ 320 Hz -> Voice Isolation -> -16 dB Adaptive Music Ducking.

### Step 4: Generate Apple Final Cut Pro Timelines (FCPXML v1.10)
Generate broadcast-ready FCPXML files for immediate import into Apple Final Cut Pro:
```bash
python3 scripts/fcpxml_generator.py --type all --out ./wedding_job/out
```
*Outputs*:
* `Bihari_Wedding_Teaser_1080p.fcpxml` (1–3 min fast-paced cuts, speed ramps, beat markers)
* `Bihari_Wedding_Trailer_Cinematic.fcpxml` (5–10 min 3-act narrative, voiceovers, beat-synced mashup)
* `Bihari_Wedding_Master_Documentary.fcpxml` (1–3 hours full chronological documentary with 16 ritual chapters)

### Step 5: Execute Autonomous Multi-Agent Graph Loop
Run the complete multi-agent graph with automated QA verification and correction loops:
```bash
python3 scripts/agent_graph_orchestrator.py --work ./wedding_job
```

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

