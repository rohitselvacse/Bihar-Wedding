# Reference 12: Ingestion & Operations Playbook for Massive Raw Footage (100–200 GB, 500–1,000 Clips)

When editing 6 to 7 hours of raw multi-camera wedding footage across 500 to 1,000 individual camera files, systematic pipeline discipline separates broadcast masters from post-production failure.

---

## 1. Physical Media Backup & Verification (3-2-1 Rule)

1. **Card Offload via Checksum**:
   * Never copy camera SD/CFexpress cards via operating system drag-and-drop.
   * Use checksum verification software (ShotPut Pro, Silverstack, or `rsync -avh --progress --checksum`).
   * Primary working SSD: NVMe Thunderbolt 4 drive (read/write > 2,800 MB/s).
   * Secondary on-site backup: High-capacity RAID 0/1 HDD.
   * Off-site archive: Cold cloud storage or second hard drive.

---

## 2. Directory Hierarchy Architecture

```
[2026_Nov_Patna_Rohit_Pooja_Master]
├── 01_Camera_A_Main_FX3/           --> Primary 4K 10-bit 4:2:2 A-roll
├── 02_Camera_B_Candid_A7S3/        --> Telephoto candid b-roll (85mm/135mm)
├── 03_Camera_C_Drone_Air3/         --> Aerial venue & procession sweeps
├── 04_Camera_D_Stage_Lockoff/      --> Static tripod mandap & reception wide
├── 05_Audio_Field_Recorders/       --> Zoom H6 line-outs from DJ/Pandit lavaliers
├── 06_Proxies_ProRes_Proxy/        --> Lightweight editing proxies (540p/1080p)
├── 07_Whisper_Transcripts/         --> Speech-to-text JSON outputs
└── 08_Deliverables_FCPXML/         --> Teaser, Trailer & Master XMLs
```

---

## 3. High-Speed ProRes Proxy Generation

Editing 1,000 raw 4K 10-bit files on laptop hardware will cause timeline stutter. Generate Apple ProRes Proxy (or H.264 Proxy @ 1080p):

```bash
# Automated proxy generation via FFmpeg (50% scale, ProRes Proxy profile 0)
ffmpeg -i raw_4k_clip.mov -vf "scale=1920:1080" -c:v prores_ks -profile:v 0 -c:a pcm_s16le proxy_1080p.mov
```

* In Final Cut Pro: Set **View -> Proxy Only** during rough cutting and beat-matching for 120fps scrubbing.
* Switch to **View -> Optimized/Original** for final color grading and master export.

---

## 4. Multi-Camera Synchronization Protocol

1. **Audio Waveform Alignment**:
   * Synchronize Camera A, Camera B, and the Zoom H6 field recorder using scratch audio waveforms.
   * In FCPX: Select clips -> right-click -> **New Multicam Clip (`Cmd + Option + N`)**.
   * Angle sync setting: *Automatic (Sound Waveform)*.
2. **Angle Switching During Master Cutting**:
   * Open the **Angle Viewer (`Cmd + Shift + 7`)**.
   * Play the timeline and tap keys `1`, `2`, `3`, `4` to live-cut between master wide, bride medium, groom medium, and roaming close-ups without stopping playback.

---

## 5. Automated Speech-to-Text & Mantra Keyword Tagging

Extract 16 kHz mono audio and run Whisper (Hindi / Multilingual model) to identify emotional speech bytes:

### High-Value Detection Keywords:
* **Sanskrit Mantras**: `मङ्गलं` (Mangalam), `कन्यादानं` (Kanyadanam), `सप्तपदी` (Saptapadi), `सिन्दूर` (Sindoor), `स्वाहा` (Swaha).
* **Emotional Parental Vows**: `बेटी` (Beti), `आशीर्वाद` (Ashirwad), `खुश रहो` (Khush Raho), `याद रखना` (Yaad Rakhna).
* **Bihari Folk Phrases**: `माटकोर` (Matkor), `हरदी` (Hardi), `परिछन` (Parichhan), `कोहबर` (Kohbar), `विदाई` (Vidai).

Flag clips containing these keywords with high-priority ratings in your NLE for trailer voiceover placement.
