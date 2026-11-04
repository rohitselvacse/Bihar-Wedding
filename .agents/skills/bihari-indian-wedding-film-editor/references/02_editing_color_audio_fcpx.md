# Reference 02: Final Cut Pro (FCPX) Video Editing, Color Grading & Audio Engineering Guide

This technical guide details the exact editing procedures, color science, speed ramping mechanics, and audio mastering protocols required to produce broadcast-quality Indian wedding films in Apple Final Cut Pro (FCPX) and modern NLEs.

---

## 1. Project Setup & Organization in Final Cut Pro

### Library & Event Structure
1. **Library Naming**: `[Groom]_[Bride]_Wedding_[Date]` (e.g., `Rohit_Pooja_Wedding_Nov2026.fcpbundle`).
2. **Events Taxonomy**:
   * `00_Audio_Master_Tracks` (Songs, Mashups, Foley, Mantras, Sound Effects)
   * `01_Cheka_Tilak`
   * `02_Matkor_MatiMangal`
   * `03_Haldi_Haridra`
   * `04_Mehndi_Sangeet`
   * `05_Baraat_DwarPuja`
   * `06_Jaimala_Stage`
   * `07_Mandap_SindoorDaan`
   * `08_Kohbar_Games`
   * `09_Vidai_Farewell`
   * `10_GrihaPravesh`
   * `11_Reception_Bahubhoj`
   * `99_Timelines_Masters` (Teaser, Trailer, Highlights, Master Full Cut)

### Smart Collections & Keyword Collections
* Assign keywords using shortcuts (`Control + 1` to `Control + 9`):
  * `HERO_SHOT`: Spectacular gimbal, drone, or extreme close-up beauty shots.
  * `EMOTIONAL`: Tears, deep smiles, parents embracing, sindoor moment.
  * `FAST_ACTION`: Baraat dancing, dhol jumping, haldi splashes (suited for beat-sync speed ramps).
  * `SPEECH_VOWS`: Pandit mantras, father/mother blessing, groom/bride speech.
  * `FAMILY_VIP`: Key relatives tagged for continuity.

---

## 2. Beat Syncing & Cut-to-the-Beat Workflow

1. **Audio Track Preparation**:
   * Place the master soundtrack on the Primary Storyline (`Timeline`).
   * Listen through with high-fidelity studio monitors or headphones.
   * Tap `M` on every prominent kick drum, snare strike, or transition drop to drop precise timeline **Markers**.
   * Color-code markers: Green for micro-beats (b-roll cut points), Red for heavy drops (impact transitions / pyro / Sindoor Daan).
2. **Magnetic Timeline Snapping (`N`)**:
   * With Snapping enabled (`N`), dragging clip start/end boundaries will automatically latch onto audio beat markers.
3. **Cut-on-Movement & Match Cutting**:
   * Never cut during static dead space. Cut mid-motion (e.g., as a dancer spins, as flower petals leave hands, or as the groom tilts his head).
   * Match cut similar motions across different rituals: e.g., yellow haldi paste being smeared cuts directly into yellow marigold shower on the jaimala stage.

---

## 3. Speed Ramping, Curves & Optical Flow

1. **Frame Rate Conformance**:
   * High-energy footage shot at 60fps or 120fps should be placed into a 24fps or 25fps master timeline.
   * Select clip -> Open Retime Editor (`Cmd + R`).
   * Under Retime menu, set **Video Quality -> Optical Flow** for buttery artifact-free ultra-slow motion.
2. **Speed Ramping Execution**:
   * Use the **Range Selection Tool (`R`)** to highlight the moment right before impact.
   * Speed up the approach to **200% - 400%**, then drop sharply to **25% - 40%** at the emotional apex (e.g., garlanding, sindoor touch, haldi splash).
   * Smooth the transition handle so the curve decelerates gracefully without jarring jerkiness.

---

## 4. Indian Wedding Color Science & Color Grading

Indian weddings present one of the most challenging color environments in cinematography: contrasting skin tones, hyper-saturated fabrics (red, maroon, gold, yellow, magenta), heavy turmeric yellow, and chaotic mixed banquet LED lighting (often harsh blue, green, or magenta).

### A. Technical Correction (The Foundation)
1. **Color Space & Gamut**:
   * For Log footage (Sony S-Log3/S-Gamut3.Cine, Canon C-Log3, DJI D-Log M):
     * Apply Camera LUT or Color Space Transform (CST) to convert from Log to **Rec.709**.
   * Turn on **Video Scopes (`Cmd + 7`)**:
     * **Waveform (Luma)**: Ensure deep blacks sit around 0–5 IRE (never crushed to -5), and lehenga gold/jewelry highlights peak between 90–95 IRE without blown-out flat clipping.
     * **Vectorscope**: The master reference for Indian skin tones.

### B. Protecting Indian Skin Tones (Vectorscope Flesh Line)
1. **The Skin Tone Line**:
   * Indian skin tones naturally carry a rich melanin spectrum from warm olive to deep bronze. Regardless of skin shade, human hemoglobin ensures that skin tones must fall precisely along the **Skin Tone Line** (between the Yellow and Red axes on the vectorscope, approximately at 10:30 on the clock face).
2. **Hue / Saturation Curves**:
   * Open **Hue vs Hue**: Sample skin tone. Shift any unnatural green or magenta cast back onto the neutral warm line.
   * Open **Hue vs Sat**: If banquet LED pars cast an unnatural orange glow, gently pull down the orange saturation node while leaving overall luminance intact.

### C. Specific Ritual Color Schemes

| Ritual | Dominant Palette | Color Grading Strategy |
| :--- | :--- | :--- |
| **Haldi (Haridra)** | Deep Turmeric Yellow, Mustard, Marigold Orange | Boost Yellow Luminance slightly; pull yellow saturation back by 5-10% to prevent "nuclear clipping". Enhance contrast in midtones so water/paste droplets glisten. |
| **Mehndi** | Henna Green, Floral Pastels, Terracotta | Enhance greens with a rich organic earthy warmth (push Green Hue slightly toward warm emerald, avoiding cold cyan). |
| **Sangeet** | Neon, Stage Lights, Sparklers | Tame blown-out banquet LED highlights with a soft highlight roll-off curve. Lift shadows slightly to reveal audience reactions. |
| **Jaimala & Mandap** | Crimson Red, Maroon, Royal Gold | Red lehengas can oversaturate easily. Lower Red Saturation by 8%, but lift Red Luminance to reveal intricate zardozi embroidery and gold threadwork. |
| **Sindoor Daan** | Sacred Vermilion (Blood Red / Orange-Red) | Isolate the Sindoor color vector; give it a rich, royal crimson tone with a subtle glow or halation effect to make it visually divine. |

---

## 5. Audio Engineering, Live Geet & Noise Cleanup

Live wedding environments in India are notoriously noisy: ceiling fans, diesel generator hums, distant traffic, echoing banquet halls, crying toddlers, and wind gusts.

### A. Raw Vocal Folk Geet (Lokgeet) Restoration
When elder women sing traditional folk songs in the courtyard during Matkor or Haldi:
1. **High-Pass / Low-Cut Filter**: Set a steep 24dB/octave high-pass filter at **80 Hz** to eliminate heavy generator thrum and table bumps.
2. **Spectral De-Noise / Dialogue Isolation**:
   * In FCPX, enable **Voice Isolation** set to **45% – 65%**. Do not push to 100% to avoid watery metallic phase artifacts.
   * If using iZotope RX or external VST plugins: Apply Spectral Denoise (learn ambient room tone) + De-reverb for echoey courtyards.
3. **Parametric EQ**:
   * Dip **250 Hz - 400 Hz** by 2-3 dB to clean up "mud" and "boxiness".
   * Gentle boost at **3.5 kHz - 5 kHz** by 2 dB to give elder women's voices vocal clarity and presence.
4. **Gentle Background Acoustic Sweetening**:
   * Layer a very subtle, low-volume (-22 dB) acoustic Indian instrumental under the live singing (soft bamboo bansuri flute, tanpura drone, or acoustic acoustic dholak) to fill in room dead air seamlessly.

### B. Speech, Vows & Pandit Mantras
* Apply **Adaptive Audio Ducking**: When the Pandit chants Sanskrit mantras or the father speaks emotional words, the background cinematic score must automatically duck down by **-14 dB to -18 dB** with a 400ms smooth release.
* Limiter on Master Voice track set to **-1.5 dB True Peak** to avoid distortion during loud megaphone/microphone cheers.
