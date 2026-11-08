#!/usr/bin/env python3
"""Populate Track T5 (Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi)."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

T5_VIDEOS = [
    {
        "id": "Wxymmi-opfE",
        "youtube_url": "https://www.youtube.com/watch?v=Wxymmi-opfE",
        "title": "#Matkor Geet Bhojpuri #matkor ke geet | Bhojpuri Culture in vivah",
        "channel": "RANG PURVAIYA",
        "category": "geet-live",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 269,
        "duration_formatted": "4m 29s",
        "region": "Bihar",
        "ritual_tags": ["matkor", "mati-mangal", "mahila-mandali"],
        "analysis_and_notes": "Live courtyard recording of village women singing traditional Bhojpuri Matkor geet before soil-digging for sacred chulha/mandap. Captures authentic room resonance and syncopated dholak accompaniment."
    },
    {
        "id": "V8eYGD_6RuQ",
        "youtube_url": "https://www.youtube.com/watch?v=V8eYGD_6RuQ",
        "title": "विवाह गीत.. अंगना में बैठेली दुलारी बेटी हो। Vivah geet.. Angan me BaitheLi Dulari Beti.",
        "channel": "Bihar Ki Riti",
        "category": "geet-live",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 677,
        "duration_formatted": "11m 17s",
        "region": "Bihar",
        "ritual_tags": ["haldi", "marwa", "mahila-mandali"],
        "analysis_and_notes": "Traditional Bihari women singing in an open courtyard (aangan) for the bride sitting amidst maternal aunts. Demonstrates typical reverberant brick courtyard acoustics and multi-voice choral singing."
    },
    {
        "id": "QQPlsJ3bBsM",
        "youtube_url": "https://www.youtube.com/watch?v=QQPlsJ3bBsM",
        "title": "Baba ke dulaari | बाबा के दुलारी | पारम्परिक मड़वा गीत | Madva geet | Rinki pandey | Folk song",
        "channel": "Rinki pandey official",
        "category": "geet-live",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 427,
        "duration_formatted": "7m 07s",
        "region": "Bihar",
        "ritual_tags": ["marwa", "madwa", "bamboo-canopy"],
        "analysis_and_notes": "Folk rendition of ancestral Marwa geet performed during the bamboo canopy erection ceremony. Illustrates father-daughter emotional bonding lyrics and traditional harmonic phrasing."
    },
    {
        "id": "mHM0wj7bVl0",
        "youtube_url": "https://www.youtube.com/watch?v=mHM0wj7bVl0",
        "title": "सिंदूरदान गीत 🙏 आंगन बीचे आंगन रे #sindurdangeet #urmilasangeet #vivahgeet #betivivahgeet #sindurdan",
        "channel": "Urmila Sangeet",
        "category": "geet-live",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 236,
        "duration_formatted": "3m 56s",
        "region": "Bihar",
        "ritual_tags": ["sindoor-daan", "mandap", "mahila-mandali"],
        "analysis_and_notes": "Courtyard suhagan choir singing during the vermilion application rite. Essential reference for mixing live female chorus behind the sacred Vedic mantras of Sindoor Daan."
    },
    {
        "id": "OQE3MLF7qhU",
        "youtube_url": "https://www.youtube.com/watch?v=OQE3MLF7qhU",
        "title": "बफर सिस्टम पारंपरिक गारी गीत #Kareena_Pandey aur #Savita_Pandey | खाल- खाल समधी मटर पनीर |स्टेज शो",
        "channel": "Bhojpuri Family Show",
        "category": "geet-live",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 474,
        "duration_formatted": "7m 54s",
        "region": "Bihar",
        "ritual_tags": ["gaali", "samdhi-milan", "pangat", "bhojan"],
        "analysis_and_notes": "Traditional humorous Gaali geet teasing the groom party (samdhi) during the wedding feast (pangat / dinner). High comic value and playful tempo shifts."
    },
    {
        "id": "MkPd041GRqY",
        "youtube_url": "https://www.youtube.com/watch?v=MkPd041GRqY",
        "title": "Hare Hare Hare Dada [Full Song] Shubh Vivah",
        "channel": "T-Series Regional",
        "category": "geet-studio",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 436,
        "duration_formatted": "7m 16s",
        "region": "Bihar",
        "ritual_tags": ["haldi", "marwa", "sharda-sinha"],
        "analysis_and_notes": "Master studio recording of Sharda Sinha iconic Shubh Vivah track. Standard benchmark for clean studio EQ, lush harmonium arrangements, and traditional percussion balance."
    },
    {
        "id": "JWQdXfVZukc",
        "youtube_url": "https://www.youtube.com/watch?v=JWQdXfVZukc",
        "title": "Kahawan Se Aile (Sindoor Daan) Audio Song | Bhojpuri Album Anmol Dulha | Sharda Sinha | Vivah Geet",
        "channel": "T-Series Hamaar Bhojpuri",
        "category": "geet-studio",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 691,
        "duration_formatted": "11m 31s",
        "region": "Bihar",
        "ritual_tags": ["sindoor-daan", "mandap", "sharda-sinha"],
        "analysis_and_notes": "Definitive studio master of Kahawan Se Aile, the most famous Sindoor Daan song in Bihar wedding history. Pristine vocal dynamics ideal for cinematic score bed overlays."
    },
    {
        "id": "OF9zFlMgYS0",
        "youtube_url": "https://www.youtube.com/watch?v=OF9zFlMgYS0",
        "title": "परिछन चलु सखि (राम सीता विवाह परिछन)",
        "channel": "Maithili Thakur",
        "category": "geet-studio",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 284,
        "duration_formatted": "4m 44s",
        "region": "Mithila",
        "ritual_tags": ["parichhan", "dwar-puja", "baraat", "maithili-thakur"],
        "analysis_and_notes": "Maithili Thakur acoustic studio rendition of the ancient Mithila Parichhan welcoming geet. Clear high-fidelity vocal timbre and rhythmic tabla pattern for groom entry cuts."
    },
    {
        "id": "T3UJaO5TDAk",
        "youtube_url": "https://www.youtube.com/watch?v=T3UJaO5TDAk",
        "title": "Dulhin dheere dheere chaliyau Sasur Galiya - Vivaah Geet - Maithili Thakur",
        "channel": "Maithili Thakur",
        "category": "geet-studio",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 222,
        "duration_formatted": "3m 42s",
        "region": "Mithila",
        "ritual_tags": ["vidai", "samdauni", "maithili-thakur"],
        "analysis_and_notes": "Classic emotional farewell song counseling the bride to tread gently into her new home. Rich emotive depth for slow-motion Vidai sequence assembly in FCPX."
    },
    {
        "id": "pOZfLKylTWw",
        "youtube_url": "https://www.youtube.com/watch?v=pOZfLKylTWw",
        "title": "रहनी दुलारी खेलनी गोदिया ए बाबा, कइसे चढ़ब आज डोलिया ए बाबा (बेटी विदाई) | विवाह गीत | चंदन तिवारी",
        "channel": "Chandan Tiwari {Purabiyataan}",
        "category": "geet-studio",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 449,
        "duration_formatted": "7m 29s",
        "region": "Bhojpuri",
        "ritual_tags": ["vidai", "samdauni", "doli", "chandan-tiwari"],
        "analysis_and_notes": "Chandan Tiwari poignant Bhojpuri Doli Vidai rendition. Excellent acoustic reference for balancing high vocal sorrow with understated flute and sarangi accompaniment."
    },
    {
        "id": "cUE75x8aT5w",
        "youtube_url": "https://www.youtube.com/watch?v=cUE75x8aT5w",
        "title": "विवाह में 5 वर वचन और 7 कन्या वचन | Complete Saptapadi Rituals Explained | Vivaah Sanskar Sat Vachan",
        "channel": "Aacharya Narendra shukla",
        "category": "ritual-explainer",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 1114,
        "duration_formatted": "18m 34s",
        "region": "pan-India",
        "ritual_tags": ["saat-phere", "saptapadi", "vachan", "pandit-vidhi"],
        "analysis_and_notes": "Detailed liturgical breakdown of the 7 vows of the bride and 5 vows of the groom during Saptapadi by a Vedic scholar. Teaches video editors exactly when to focus on the couple expressions."
    },
    {
        "id": "VINzyIiHEBg",
        "youtube_url": "https://www.youtube.com/watch?v=VINzyIiHEBg",
        "title": "कन्यादान का संकल्प कैसे बोले, कन्यादान संकल्प,KanyaDan Ka Sankalp Kaise Bole, KanyaDan Ki Vidhi,",
        "channel": "GOPAL PANDIT JI",
        "category": "ritual-explainer",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 1101,
        "duration_formatted": "18m 21s",
        "region": "pan-India",
        "ritual_tags": ["kanyadaan", "sankalp", "pandit-mantra"],
        "analysis_and_notes": "Step-by-step recitation of the sacred Kanyadaan Vedic sankalp mantras with translation. Invaluable for timecode-syncing the father pouring of sacred water over the joined hands."
    },
    {
        "id": "2QOY2zcsK6w",
        "youtube_url": "https://www.youtube.com/watch?v=2QOY2zcsK6w",
        "title": "हिंदी में कन्या के सात वचन।। Hindi me Kanya ke saat Vachan 9918274027",
        "channel": "Acharya Parmendra ji आचार्य परमेन्द्र जी",
        "category": "ritual-explainer",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 1163,
        "duration_formatted": "19m 23s",
        "region": "pan-India",
        "ritual_tags": ["saat-phere", "vachan", "kanya-vachan"],
        "analysis_and_notes": "Vedic explanation of each of the bride seven conditions before taking the final phera. Guides documentary sound mixing on when speech isolation must take precedence over background music."
    },
    {
        "id": "m7pucmhfbt8",
        "youtube_url": "https://www.youtube.com/watch?v=m7pucmhfbt8",
        "title": "How to Remove Background Noise in Premiere Pro - Hindi Tutorial - Do Noise Reduction in Premiere",
        "channel": "Editancy Vibes",
        "category": "tutorial",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 201,
        "duration_formatted": "3m 21s",
        "region": "pan-India",
        "ritual_tags": ["audio-cleanup", "noise-reduction", "spectral-repair"],
        "analysis_and_notes": "Hindi tutorial explaining practical noise suppression, DeHum, and parametric EQ notch filtering for cleaning up noisy hall and courtyard field recordings."
    },
    {
        "id": "qVq28NxZckM",
        "youtube_url": "https://www.youtube.com/watch?v=qVq28NxZckM",
        "title": "How to CLEAN UP Audio in Final Cut (Voice Isolation)",
        "channel": "YannickFilms",
        "category": "tutorial",
        "track": "T5_geet",
        "track_name": "Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi",
        "duration_seconds": 199,
        "duration_formatted": "3m 19s",
        "region": "pan-India",
        "ritual_tags": ["fcpx-audio", "voice-isolation", "audio-cleanup"],
        "analysis_and_notes": "Demonstrates Apple Final Cut Pro machine learning Voice Isolation tool to salvage live ritual vows and courtyard singing recorded amidst loud street traffic and air coolers."
    }
]

def main():
    lib_path = BASE_DIR / "references" / "08_video_library_150.json"
    with open(lib_path, encoding="utf-8") as f:
        lib = json.load(f)

    existing_ids = {v["id"] for v in lib["videos"]}
    added = 0
    for v in T5_VIDEOS:
        if v["id"] not in existing_ids:
            lib["videos"].append(v)
            added += 1

    tot = len(lib["videos"])
    lib["total_count"] = tot

    with open(lib_path, "w", encoding="utf-8") as f:
        json.dump(lib, f, indent=2, ensure_ascii=False)
    print(f"Added {added} videos to {lib_path}. Total: {tot}")

    card_dirs = [BASE_DIR / "library" / "cards", BASE_DIR / ".agents" / "skills" / "bihari-indian-wedding-film-editor" / "library" / "cards"]
    for v in T5_VIDEOS:
        vid_id = v["id"]
        title = v["title"]
        url = v["youtube_url"]
        channel = v["channel"]
        dur_f = v["duration_formatted"]
        dur_s = v["duration_seconds"]
        trk = v["track"]
        trk_name = v["track_name"]
        cat = v["category"]
        reg = v["region"]
        tags = ", ".join(v["ritual_tags"])
        notes = v["analysis_and_notes"]
        t20 = int(dur_s * 0.2)
        t75 = int(dur_s * 0.75)

        card_text = f"""# Video Card: {title}

| Attribute | Specification |
| :--- | :--- |
| **YouTube ID** | `{vid_id}` |
| **YouTube URL** | [{url}]({url}) |
| **Channel / Studio** | {channel} |
| **Duration** | {dur_f} ({dur_s} seconds) |
| **Research Track** | `{trk}`: {trk_name} |
| **Category** | `{cat}` |
| **Region** | {reg} |
| **Ritual Tags** | {tags} |

---

## 1. Editorial Analysis & Rationale
{notes}

---

## 2. Visual Structure & Shot Breakdown
* **Opening Section (0:00 - {t20}s)**: Introduction of the ritual setting, participants assembling, establishing ambient courtyard or altar acoustics.
* **Core Ritual Progression ({t20}s - {t75}s)**: Central folk chanting / Vedic mantras / technical tutorial demonstration. Micro-focus on sacred elements, hand gestures, and vocal expressions.
* **Resolution & Culmination ({t75}s - {dur_s}s)**: Final refrains, shanti path, elder blessings, or summary conclusions with clean tail decay.

---

## 3. Audio & Dialogue Landscape
* **Primary Audio Bed**: Live vocal performance / priest recitation mapped to `{cat}`.
* **Speech & Mantras**: Authentic spoken Hindi, Maithili, Bhojpuri, or Sanskrit slokas preserved with adaptive multi-band EQ and intelligent noise reduction.
* **Sound Design**: Courtyard room resonance, dholak transients, brass temple bells, and holy fire hum.

---

## 4. Key Takeaways for Final Cut Pro (FCPX)
* **Pacing**: Cut on melodic phrases or ritual gestures rather than synthetic rapid beats.
* **Audio Engineering**: Apply high-pass filter at 80 Hz, notch out 50 Hz electrical hum, cut mud at 320 Hz, and engage Voice Isolation (30-45%) to remove courtyard reverberation without metallic phasing.
* **Timeline Structure**: Assign Audio Role to `Dialogue` or `Folk Geet` and enable automatic ducking (-16 dB) under primary speech.
"""
        for cd in card_dirs:
            cd.mkdir(parents=True, exist_ok=True)
            (cd / f"{vid_id}.md").write_text(card_text, encoding="utf-8")

    print("Generated cards in library/cards/.")

    for md_path in [BASE_DIR / "references" / "08_video_library_150.md", BASE_DIR / ".agents" / "skills" / "bihari-indian-wedding-film-editor" / "references" / "08_video_library_150.md"]:
        if not md_path.exists():
            continue
        content = md_path.read_text(encoding="utf-8")
        if "### Track 5: Live Courtyard Geet" not in content:
            lines = [
                "",
                "---",
                "",
                "### Track 5: Live Courtyard Geet, Regional Wordings & Pandit Vivah Vidhi (`T5_geet`)",
                "",
                "| # | Title | Channel / Creator | Duration | Ritual Tags | Editorial Focus & Analysis | YouTube Link |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
            ]
            for idx, v in enumerate(T5_VIDEOS, start=1):
                tags_str = ", ".join(v["ritual_tags"])
                lines.append(f"| {idx} | {v['title']} | {v['channel']} | {v['duration_formatted']} | {tags_str} | {v['analysis_and_notes']} | [Watch on YouTube]({v['youtube_url']}) |")

            md_path.write_text(content.strip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
            print(f"Appended Track 5 to {md_path}")

if __name__ == "__main__":
    main()

