# Reference 11: Apple Final Cut Pro XML (FCPXML v1.10) Architecture & Automation

This technical manual details the exact XML schema, rational time math, asset cataloging, and timeline assembly mechanics used to generate native Apple Final Cut Pro project interchanges.

---

## 1. FCPXML v1.10 Architectural Hierarchy

```
<fcpxml version="1.10">
  │
  ├── <resources>               --> Formats, Assets, Effects, Generators
  │     ├── <format id="r1" ... />
  │     └── <asset id="r2" src="file:///..." ... />
  │
  └── <library location="file:///...">
        └── <event name="Bihari Wedding Master Event">
              └── <project name="Timeline Name">
                    └── <sequence format="r1" ...>
                          └── <spine>     --> Primary Storyline
                                ├── <asset-clip ...>  --> Video / Multicam
                                ├── <title ...>       --> Lower Thirds / Cards
                                └── <marker ...>      --> Beats / Chapters
```

---

## 2. Rational Time Representation

Final Cut Pro does not use floating-point seconds or drop-frame decimals in FCPXML. All durations, offsets, and start times are represented as **rational fractions** (`numerator/denominator + 's'`) to preserve exact frame-accuracy across broadcast standards:

* **25 fps (PAL / Indian Television & Wedding Standard)**:
  * Frame duration: `1/25s`
  * 1 second: `25/25s` (or `1s`)
  * 3 seconds: `75/25s` (or `3s`)
* **24 fps (Cinema Standard)**:
  * Frame duration: `1/24s`
* **23.976 fps (NTSC Cinema)**:
  * Frame duration: `1001/24000s`
* **50 fps (High Frame Rate Slow Motion)**:
  * Frame duration: `1/50s`

---

## 3. Key FCPXML Elements & Attributes

### `<format>` Element
Defines the canvas resolution and frame rate:
```xml
<format id="r1" name="FFVideoFormat2160p25" frameDuration="1/25s" width="3840" height="2160"/>
```

### `<asset>` Element
Declares a physical media file on disk:
```xml
<asset id="r2" name="Haldi_Splash_120fps.mov" 
       src="file:///Users/username/Movies/Wedding/Haldi_Splash_120fps.mov" 
       start="0s" duration="1500/25s" hasVideo="1" hasAudio="1" format="r1"/>
```

### `<spine>` & `<asset-clip>` Element
The spine represents FCPX's magnetic timeline. Clips placed sequentially inside `<spine>` ripple automatically:
```xml
<spine>
  <asset-clip name="01_Haldi_Smearing" ref="r2" offset="0/25s" duration="125/25s" start="50/25s" format="r1">
    <!-- Chapter or Beat Marker -->
    <marker start="38/25s" duration="1/25s" value="Beat Drop: Haldi Splash" note="Speed ramp to 25%"/>
    <!-- Volume Adjustment -->
    <adjust-volume amount="0dB"/>
  </asset-clip>
</spine>
```

---

## 4. Audio Roles & Multichannel Layout
Assigning Audio Roles enables one-click sub-mix exports and automated ducking in FCPX:
* `dialogue`: Vows, interviews, pandit mantras (`role="dialogue.dialogue-1"`)
* `music`: Master song beds, background mashups (`role="music.music-1"`)
* `effects`: Whooshes, impacts, temple bells (`role="effects.effects-1"`)

---

## 5. Importing into Final Cut Pro
1. Open **Apple Final Cut Pro**.
2. Go to **File -> Import -> XML...** (`Cmd + Shift + I`).
3. Select the generated `.fcpxml` file.
4. FCPX automatically creates an Event housing the imported project with all clip edits, transitions, speed ramps, and chapter markers populated on the magnetic timeline!
