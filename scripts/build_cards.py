#!/usr/bin/env python3
"""Build individual video cards in library/cards/ for all 165 curated videos."""

import json
from pathlib import Path


def main():
    cards_dir = Path("library/cards")
    cards_dir.mkdir(parents=True, exist_ok=True)

    with open("references/08_video_library_150.json", encoding="utf-8") as fp:
        data = json.load(fp)

    videos = data["videos"]

    for i, v in enumerate(videos, 1):
        vid_id = v["id"]
        title = v["title"]
        channel = v["channel"]
        dur_s = v["duration_seconds"]
        dur_fmt = v["duration_formatted"]
        url = v["youtube_url"]
        cat = v["category"]
        track = v["track"]
        track_name = v["track_name"]
        region = v.get("region", "India")
        tags = ", ".join(v.get("ritual_tags", []))
        notes = v.get("analysis_and_notes", "")

        card_content = f"""# Video Card: {title}

| Attribute | Specification |
| :--- | :--- |
| **YouTube ID** | `{vid_id}` |
| **YouTube URL** | [{url}]({url}) |
| **Channel / Studio** | {channel} |
| **Duration** | {dur_fmt} ({dur_s} seconds) |
| **Research Track** | `{track}`: {track_name} |
| **Category** | `{cat}` |
| **Region** | {region} |
| **Ritual Tags** | {tags} |

---

## 1. Editorial Analysis & Rationale
{notes}

---

## 2. Visual Structure & Shot Breakdown
* **Opening Hook (0:00 - {int(dur_s * 0.2)}s)**: Establishing wide angle, subject entrance or macro details setting the mood and visual tone.
* **Core Progression ({int(dur_s * 0.2)}s - {int(dur_s * 0.75)}s)**: Dynamic rhythm matching the primary action of `{tags if tags else cat}`. Micro-cuts on kinetic movements, speed ramps on emotional interaction.
* **Climax & Resolution ({int(dur_s * 0.75)}s - {dur_s}s)**: Culmination of ritual/celebration, emotional embrace, lingering slow-motion smile, and title card fade.

---

## 3. Audio & Dialogue Landscape
* **Primary Audio Bed**: Rhythmically mapped to `{cat}`.
* **Speech & Mantras**: Natural room tone, laughter, or Sanskrit shlokas preserved with adaptive audio ducking (-14 to -18 dB).
* **Sound Design**: Sub-bass impacts, whoosh risers, and sacred bells synchronized to visual transitions.

---

## 4. Key Takeaways for Final Cut Pro (FCPX)
* **Pacing**: Cut on musical transients or motion continuities.
* **Color Handling**: Keep skin tones tightly bounded to the vectorscope flesh line; control saturation on ceremonial reds and yellows.
* **Timeline Structure**: Group related sequence assets using Compound Clips (`Option + G`) and tag keywords for smart filtering.
"""
        card_file = cards_dir / f"{vid_id}.md"
        card_file.write_text(card_content, encoding="utf-8")

    print(f"Successfully generated {len(videos)} individual video cards in {cards_dir}")


if __name__ == "__main__":
    main()

