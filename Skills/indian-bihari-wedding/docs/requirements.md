# Requirements traceability

Every instruction in the owner's brief, numbered so each one can be traced to the
part of the skill that satisfies it. The verification agents check this table; a
requirement is only `done` when the "Covered in" file exists and actually does it.

Status: `todo` → `draft` → `verified` (checked by an independent critic agent).

## 0. Context

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R0.1 | Edit a wedding (shaadi) video in the near future (1–2 days) and later ones too — the skill must be reusable, not one-off. | SKILL.md | todo |
| R0.2 | It is **Indian** wedding video editing. | all references | todo |
| R0.3 | Input is raw video full of Indian culture and rituals — haldi, mehndi, sangeet and "lots of things". | references/04, 08 | todo |
| R0.4 | Research each and every part. | library/, references/ | todo |

## 1. Indian wedding video types (YouTube research)

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R1.1 | Research at least 10 YouTube videos about Indian weddings. | library/ (track T1) | todo |
| R1.2 | Identify the kinds of wedding videos: teaser, trailer, cinematic, candid, static/traditional, ritual video (and any others found). | references/01 | todo |
| R1.3 | Know the durations: 1, 2, 3 min; 30 min; 1 h; 2 h; up to 2–3 h. | references/01 | todo |

## 2. How to edit (YouTube tutorials + transcripts)

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R2.1 | Search YouTube for how to edit Indian wedding videos. | library/ (track T2) | todo |
| R2.2 | Focus on technique, not the tool: color correction, color grading, etc. | references/02, 10 | todo |
| R2.3 | 5–10 tutorial videos with their transcripts. | library/ (T2 cards) | todo |
| R2.4 | Transcripts of the part-1 videos too, and how each was edited. | library/cards | todo |
| R2.5 | Learn and understand all the editing skills. | references/02 | todo |

## 3. Songs by function (pan-Indian)

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R3.1 | Which song is used in which function: haldi, mehndi, vidai, jaymala/varmala (and others). | references/03, library/songs | todo |
| R3.2 | Which kind of video is made for each function and how the song is played in it. | references/03 | todo |
| R3.3 | 5–10 videos researched for this; learn the skill. | library/ (T3) | todo |

## 4. Bihar / Patna weddings

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R4.1 | Footage is from Bihar / Patna — both keywords used in research. | library/ (T4) | todo |
| R4.2 | About 20 videos on Bihari weddings / weddings in Bihar. | library/ (T4) | todo |
| R4.3 | Know Bihari rituals: matkor, marwa (marba), vidai, sangeet, haldi, jaymala/barmala and everything else. | references/04 | todo |
| R4.4 | Each ritual (marwa, jaymala …) has its own video style and songs — collect all songs and know which goes where (e.g. haldi "hardiya" songs). | references/05, library/songs | todo |

## 5. Geet, spoken words, pandit

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R5.1 | Two kinds of music in Bihari weddings: played songs and **geet** sung live by local women (regional folk). Collect the geet. | references/05, library/geet | todo |
| R5.2 | When geet is in the raw video: keep the original sound, noise-cancel and enhance it, maybe a little background music under it. | references/05, scripts/clean_audio.py | todo |
| R5.3 | Groom / bride / family say traditional wordings and sayings — know which ones and handle them. | references/06 | todo |
| R5.4 | The pandit (priest) performs rituals and mantras — understand and cover them. | references/06 | todo |

## 6. People and the reception

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R6.1 | Track the same person across clips (face recognition / same-person matching) so no family member is missed. | scripts/faces.py, references/07 | todo |
| R6.2 | Jaymala / reception is the most important part. | references/07, 09 | todo |
| R6.3 | Reception: couple sits together, relatives come with gifts/envelopes, bless them, photos are taken — the most critical part to cover. | references/07 | todo |
| R6.4 | Reception hall lighting and decoration must be captured and treated with care. | references/07, 10 | todo |

## 7. Library and ritual sequence

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R7.1 | 10–20 videos for each of parts 1–6. | library/stats.md | todo |
| R7.2 | For every video: how the visuals look, the script/transcript and thumbnail — saved in the skill. | library/ | todo |
| R7.3 | Learn the editing of Indian and Bihari wedding videos. | references/ | todo |
| R7.4 | Separate the rituals into parts and order them (e.g. marwa → haldi → sangeet → tilak → … → vidai → bride arrives at the groom's home → bride–groom games → reception with separate shoots and relatives' photos). | references/08 | todo |
| R7.5 | Know each ritual separately: where it happens and where it goes in the edit. | references/08 | todo |

## 8. The edit

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R8.1 | Do the whole editing journey. | SKILL.md, references/09, scripts/ | todo |
| R8.2 | Apply part 7 and every rule from parts 1–7. | SKILL.md | todo |
| R8.3 | Decide sequence, length and songs, following all rules. | references/09, scripts/plan_edit.py | todo |

## 9. Three deliverables + finishing

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R9.1 | Three outputs: teaser, trailer, master. | references/09 | todo |
| R9.2 | Teaser 1–3 min with the best shots, built from research on Indian and Bihari teasers. | references/09 | todo |
| R9.3 | Trailer 5–10 min (or 5) on one full ~5-min song or a mashup; cuts on the beats. | references/09, scripts/beats.py | todo |
| R9.4 | Master film in ritual sequence, 1–3 h depending on coverage; best shots and songs; final render. | references/09, scripts/build_fcpxml.py | todo |
| R9.5 | Color correction, color grading, lighting, music sync and video sync are critical. | references/10, scripts/grade.py | todo |

## 10. The skill

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| R10.1 | Merge parts 1–9: rituals, songs, sequence, correction, grading, music, geet, sangeet, lighting, reception, haldi, mehndi, every family member, groom, bride, photos. | SKILL.md | todo |
| R10.2 | A library of 100–150 videos, each with transcript, thumbnail and a second-by-second / shot-by-shot description of the visuals. | library/ | todo |
| R10.3 | One skill named "Indian Bihari wedding". | SKILL.md (`indian-bihari-wedding`) | todo |
| R10.4 | Publishable on GitHub, open for anyone to use and edit, crediting Claude. | README.md, LICENSE | todo |
| R10.5 | Handles the owner's real job: 6–7 h of raw video, 100–200 GB, 500–1000 clips. | scripts/ingest.py, references/12 | todo |
| R10.6 | First understand the raw footage, then edit it in Final Cut Pro. | references/11, 12 | todo |

## Execution

| ID | Requirement | Covered in | Status |
|----|-------------|-----------|--------|
| E1 | Multiple agents in a graph: research, transcript, analysis and verification agents. | docs/how-it-was-built.md | todo |
| E2 | Agents loop: research → repeat → test → verify until the skill is strong. | docs/how-it-was-built.md | todo |
| E3 | Claude must understand the skill well enough to use it. | SKILL.md | todo |
| E4 | Fit for public release. | README.md | todo |
| E5 | Nothing in the brief is skipped (this table). | docs/requirements.md | todo |

## Decisions forced by publishing

- **No verbatim transcripts, lyrics or thumbnails in the public repo.** They belong to the
  video and song owners. The library keeps links, factual metadata, our own written
  summaries and our own shot-by-shot descriptions. Raw captions and frames used for the
  analysis stay in a private local cache.
- **Songs are catalogued, not supplied.** Title, film/album, singer, language, ritual, mood
  and how editors use it. The editor supplies licensed audio files for the actual edit.
