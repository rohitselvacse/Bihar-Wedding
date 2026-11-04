# Reference 10: Color Correction, Grading & LUT Mastery for Indian Weddings

This technical guide provides the definitive color science protocol for Indian and Bihari weddings, detailing exact software operations for Apple Final Cut Pro (FCPX) and FFmpeg headless rendering.

---

## 1. Color Science Fundamentals for Indian Weddings

Indian weddings are visually defined by high-saturation cultural palettes:
* **Indian Skin Tones**: Fitzpatrick Types III, IV, and V. High melanin levels require warm golden-bronze reproduction without unnatural orange, yellow, or olive casts.
* **Turmeric Yellow (*Haldi*)**: Extreme luminance and saturation around 580 nm. Western LUTs cause clipping and severe jaundiced skin bounce.
* **Vermilion Red (*Sindoor*) & Bridal Zari**: High-intensity cadmium red fabrics that easily clip the red channel on digital sensors (especially Sony S-Log3 and Canon C-Log).
* **Banquet Hall RGB LEDs**: Uncalibrated 100W stage LED floods casting toxic magenta, electric cyan, or deep purple spills across human faces.

---

## 2. The 6-Step Color Pipeline in Final Cut Pro

Apply color effects in strict sequence to preserve 10-bit dynamic range:

```
[1. Camera Log Transform / CST] ➔ Rec.709 Base (Sony S-Gamut3.Cine / Canon Cinema Gamut)
       │
       ▼
[2. Primary Exposure & Contrast] ➔ Waveform Luma: Blacks @ 2-5 IRE, Highlights @ 90-95 IRE
       │
       ▼
[3. White Balance & Temperature] ➔ Neutralize room tint; keep Kelvin accurate
       │
       ▼
[4. Secondary HSL Qualifiers]    ➔ Lock skin tone to Vectorscope Flesh Line (10:30 axis)
       │
       ▼
[5. Cultural Palette Balancing]  ➔ Tame Haldi yellow, lehenga red & banquet LED spill
       │
       ▼
[6. Creative Film Look / LUT]    ➔ 35-50% mix opacity + soft highlight roll-off + film grain
```

### Step-by-Step FCPX Adjustments:
1. **Exposure & Contrast (Color Wheels / Curves)**:
   * Shadows: Keep resting between 0% and 5% IRE. Do not crush below 0% to avoid losing intricate fabric textures in dark sherwanis and suits.
   * Midtones: Lift to 45%–55% IRE to ensure brown/melanin skin has radiant presence.
   * Highlights: Soft-knee roll-off at 90%–95% IRE to prevent blown-out gold jewelry and chandelier clipping.
2. **Vectorscope Skin Tone Protection**:
   * Turn on **Video Scopes (`Cmd + 7`)** -> select **Vectorscope**.
   * Indian skin must align precisely along the **Flesh Line** (between Yellow and Red axes).
   * Open **Hue vs Hue**: Sample cheeks and forehead. Rotate qualifier until the vectorscope trace aligns directly on the line.
   * Open **Hue vs Sat**: Restrict skin saturation to 28%–40%.
3. **Turmeric (*Haldi*) Yellow Management**:
   * In **Hue vs Hue**: Shift yellow vector by +10° away from green toward warm amber.
   * In **Hue vs Sat**: Pull yellow saturation down by 15%–20% to prevent flat nuclear clipping.
   * In **Hue vs Luma**: Slightly lower yellow brightness to reveal floral petal textures and paste droplets.
4. **Vermilion (*Sindoor*) Red Management**:
   * Monitor the **RGB Parade**. If the Red channel flattens against the 100 IRE ceiling, pull Red Saturation down by 15%–22% in Hue vs Sat.
   * Lift Red Luminance by +5% to reveal metallic gold zari threads (*Zardozi*).
5. **Banquet LED Cast Neutralization (Magenta / Cyan / Blue)**:
   * Add a secondary **Color Wheels** effect with a tracked **Shape Mask** around the couple's faces.
   * Shift midtone wheel toward complementary green-yellow to cancel magenta flood.
   * Globally pull down magenta and cyan saturation in Hue vs Sat by 50% without affecting the warm skin axis.

---

## 3. Headless FFmpeg Filter Equivalent

For automated pipeline rendering or proxy grading, use this FFmpeg filtergraph:

```bash
ffmpeg -i raw_clip.mov -vf "
  eq=contrast=1.12:brightness=-0.02:saturation=1.05,
  colorbalance=rs=0.04:gs=-0.02:bs=-0.05:rm=0.03:gm=-0.01:bm=-0.04,
  curves=m='0/0 0.25/0.20 0.75/0.82 1/0.95':r='0/0 0.5/0.52 1/0.96':b='0/0 0.5/0.46 1/0.92'
" -c:v prores_ks -profile:v 3 -c:a copy graded_clip.mov
```

* `colorbalance`: Adds subtle warmth in shadows and midtones while pulling blue down.
* `curves`: Softens shadow crush and rolls off extreme highlight glare.

