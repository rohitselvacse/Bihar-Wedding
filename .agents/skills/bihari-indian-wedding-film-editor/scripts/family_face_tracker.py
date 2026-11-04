#!/usr/bin/env python3
"""Family Member Tracking & Character Continuity Auditor.

Tracks presence of key characters across 500-1000 raw clips:
- Groom (G01) & Bride (B01)
- Bride's Father (BF01) & Bride's Mother (BM01)
- Groom's Father (GF01) & Groom's Mother (GM01)
- Siblings, Grandparents, and VIP guests.

Audits family screen-time balance, detects missing relatives, and verifies
reception/jaimala stage coverage so NO family member is accidentally omitted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

STANDARD_ROLES = {
    "G01": {"name": "Groom", "side": "groom", "min_shots_trailer": 10, "min_shots_master": 50},
    "B01": {"name": "Bride", "side": "bride", "min_shots_trailer": 10, "min_shots_master": 50},
    "GF01": {"name": "Groom's Father", "side": "groom", "min_shots_trailer": 3, "min_shots_master": 15},
    "GM01": {"name": "Groom's Mother", "side": "groom", "min_shots_trailer": 3, "min_shots_master": 15},
    "BF01": {"name": "Bride's Father", "side": "bride", "min_shots_trailer": 3, "min_shots_master": 15},
    "BM01": {"name": "Bride's Mother", "side": "bride", "min_shots_trailer": 3, "min_shots_master": 15},
    "B_SIB01": {"name": "Bride's Sister", "side": "bride", "min_shots_trailer": 2, "min_shots_master": 8},
    "G_SIB01": {"name": "Groom's Brother", "side": "groom", "min_shots_trailer": 2, "min_shots_master": 8},
    "B_DADA": {"name": "Bride's Grandfather", "side": "bride", "min_shots_trailer": 1, "min_shots_master": 5},
    "G_DADI": {"name": "Groom's Grandmother", "side": "groom", "min_shots_trailer": 1, "min_shots_master": 5},
}


def audit_character_continuity(tags_dir: Path, deliverables_plan: dict | None = None) -> dict:
    """Analyze all clip character tags and verify against minimum thresholds."""
    character_appearances = defaultdict(list)
    side_durations = {"groom": 0.0, "bride": 0.0, "joint": 0.0}
    total_tagged_clips = 0

    if tags_dir.exists():
        for tag_file in tags_dir.glob("*.json"):
            try:
                with open(tag_file, encoding="utf-8") as fp:
                    data = json.load(fp)
                    cid = data.get("clip_id")
                    dur = float(data.get("duration", 5.0))
                    subjects = data.get("subjects", [])
                    has_groom_side = any(STANDARD_ROLES.get(s, {}).get("side") == "groom" for s in subjects)
                    has_bride_side = any(STANDARD_ROLES.get(s, {}).get("side") == "bride" for s in subjects)

                    if has_groom_side and has_bride_side:
                        side_durations["joint"] += dur
                    elif has_groom_side:
                        side_durations["groom"] += dur
                    elif has_bride_side:
                        side_durations["bride"] += dur

                    for s in subjects:
                        character_appearances[s].append({
                            "clip_id": cid,
                            "ritual": data.get("ritual_phase", "general"),
                            "duration": dur,
                            "emotion": data.get("emotion", "neutral")
                        })
                    total_tagged_clips += 1
            except Exception as e:
                continue

    audit_results = {
        "total_tagged_clips": total_tagged_clips,
        "character_stats": {},
        "missing_characters": [],
        "family_balance": {},
        "is_balanced": True,
        "reception_stage_verified": False
    }

    # Verify each key role
    for role_id, info in STANDARD_ROLES.items():
        shots = character_appearances.get(role_id, [])
        total_time = sum(s["duration"] for s in shots)
        rituals_present = list(set(s["ritual"] for s in shots))
        
        status = "OK"
        if len(shots) < info["min_shots_trailer"]:
            status = "WARNING_UNDERREPRESENTED"
        if len(shots) == 0:
            status = "CRITICAL_MISSING"
            audit_results["missing_characters"].append({
                "role_id": role_id,
                "name": info["name"],
                "side": info["side"],
                "required_min": info["min_shots_trailer"]
            })

        audit_results["character_stats"][role_id] = {
            "name": info["name"],
            "side": info["side"],
            "total_shots": len(shots),
            "total_duration_sec": round(total_time, 2),
            "rituals_covered": rituals_present,
            "status": status
        }

    # Verify family screen-time balance
    tot_side_time = side_durations["groom"] + side_durations["bride"]
    groom_pct = round((side_durations["groom"] / tot_side_time * 100), 1) if tot_side_time > 0 else 50.0
    bride_pct = round((side_durations["bride"] / tot_side_time * 100), 1) if tot_side_time > 0 else 50.0

    audit_results["family_balance"] = {
        "groom_family_percentage": groom_pct,
        "bride_family_percentage": bride_pct,
        "joint_couple_duration_sec": round(side_durations["joint"], 2)
    }

    # Strict check: Neither family side should receive less than 35% of non-joint screen time
    if groom_pct < 35.0 or bride_pct < 35.0:
        audit_results["is_balanced"] = False

    # Verify reception / jaimala stage coverage
    reception_shots = [
        s for shots in character_appearances.values()
        for s in shots if "reception" in s["ritual"] or "jaimala" in s["ritual"]
    ]
    audit_results["reception_stage_verified"] = len(reception_shots) >= 15

    return audit_results


def generate_mock_tags(work_dir: Path, count: int = 120):
    """Generate realistic character tags for simulation and testing."""
    tags_dir = work_dir / "tags"
    tags_dir.mkdir(parents=True, exist_ok=True)
    
    rituals = [
        "01_cheka_tilak", "02_matkor", "03_marava", "04_haldi",
        "05_mehndi", "06_sangeet", "07_baraat_dwarpuja", "08_jaimala",
        "09_mandap_phere", "10_sindoor_daan", "11_kohbar_games",
        "12_vidai", "13_griha_pravesh", "14_reception"
    ]
    
    role_keys = list(STANDARD_ROLES.keys())
    for i in range(count):
        r_phase = rituals[i % len(rituals)]
        cid = f"clip_{i:04d}"
        
        # Determine natural subjects based on ritual
        if "haldi" in r_phase:
            subs = ["B01", "BM01", "B_SIB01"] if i % 2 == 0 else ["G01", "GM01", "G_SIB01"]
        elif "sindoor" in r_phase or "jaimala" in r_phase:
            subs = ["G01", "B01", "BM01", "BF01", "GM01", "GF01"]
        elif "reception" in r_phase:
            subs = ["G01", "B01", role_keys[i % len(role_keys)]]
        elif "vidai" in r_phase:
            subs = ["B01", "BF01", "BM01", "B_SIB01", "B_DADA"]
        else:
            subs = ["G01", "B01"]
            
        data = {
            "clip_id": cid,
            "ritual_phase": r_phase,
            "duration": round(6.5 + (i % 7), 2),
            "subjects": subs,
            "emotion": "joyful" if "haldi" in r_phase or "sangeet" in r_phase else "tearful" if "vidai" in r_phase else "sacred"
        }
        with open(tags_dir / f"{cid}.json", "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit character presence & family balance.")
    parser.add_argument("--work", type=str, default="./work_output", help="Job work directory")
    parser.add_argument("--mock", action="store_true", help="Generate mock tags for testing")
    args = parser.parse_args()

    wdir = Path(args.work)
    if args.mock:
        generate_mock_tags(wdir, 150)
        print("[✓] Generated 150 mock tagged clips for character testing.")

    audit = audit_character_continuity(wdir / "tags")
    print(json.dumps(audit, indent=2))

