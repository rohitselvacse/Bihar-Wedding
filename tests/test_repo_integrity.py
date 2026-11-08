#!/usr/bin/env python3
"""Checks on the repository itself, not on the pipeline.

Three classes of mistake had already reached a public repository and are easy
to make again, so each gets a test:

  * generated files carrying the operator's own home directory, which leaked a
    username and an employer name across 188 occurrences in 12 files;
  * hand-written summaries disagreeing with the data they summarise, which is
    how library/stats.md came to claim 176 videos in a table totalling 165, and
    71.4 hours of material against an actual 57.0;
  * the traceability table certifying work that does not exist.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

# Shapes of machine-local absolute paths that must never be committed. These
# match the shape rather than any one person's name, so the test keeps working
# for anyone who clones this.
#
# Documentation legitimately shows what such a path looks like, so an explicit
# placeholder in the first path segment is allowed. The point is to catch a
# real account name, not to forbid writing an example.
PLACEHOLDER_USERS = {"username", "user", "youruser", "your-username",
                     "yourname", "me", "example", "USERNAME"}

LOCAL_PATH_PATTERNS = [
    re.compile(r"/Library/CloudStorage/"),
]

HOME_PATH_RE = re.compile(r"file:///(?:Users|home)/([^/\"'\s]+)")

TEXT_SUFFIXES = {".md", ".json", ".py", ".fcpxml", ".txt", ".jsonl", ".yml", ".yaml"}


# This file necessarily contains the path shapes it searches for, so it is
# excluded from its own scan. Any other test that needs such a sample should
# build it at runtime rather than writing one as a literal.
SELF_NAME = Path(__file__).name


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=BASE_DIR,
                         capture_output=True, text=True, check=True)
    return [BASE_DIR / line for line in out.stdout.splitlines()
            if line.strip() and Path(line).name != SELF_NAME]


class TestNoLocalPathsCommitted(unittest.TestCase):
    def test_no_committed_file_contains_a_local_absolute_path(self):
        """The regression that published a username and employer name."""
        offenders: list[str] = []
        for path in tracked_files():
            if path.suffix.lower() not in TEXT_SUFFIXES or not path.exists():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            hit = None
            for pattern in LOCAL_PATH_PATTERNS:
                if pattern.search(text):
                    hit = pattern.pattern
                    break
            if hit is None:
                for user in HOME_PATH_RE.findall(text):
                    if user not in PLACEHOLDER_USERS:
                        hit = f"home path for account {user!r}"
                        break
            if hit:
                offenders.append(f"{path.relative_to(BASE_DIR)}: {hit}")
        self.assertEqual(
            offenders, [],
            "Committed files contain machine-local paths. Regenerate them with "
            "--media-root, or leave the placeholder in place:\n  " + "\n  ".join(offenders))
        print(f"[✓] No local absolute paths in {len(tracked_files())} tracked files")


    def test_the_check_would_catch_a_real_leak(self):
        """Guard the guard: a permissive pattern would make this suite useless.

        The sample account name is assembled at runtime and is deliberately
        fictitious. Writing a real one here as a literal would put it back into
        the repository, which is the exact thing being tested against.
        """
        account = "a" + "cct" + "name"  # not a real account, and not a literal
        real = f'src="file:///Users/{account}/Library/CloudStorage/x.mov"'
        users = [u for u in HOME_PATH_RE.findall(real) if u not in PLACEHOLDER_USERS]
        self.assertTrue(users, "a real account name must still be detected")
        self.assertTrue(any(p.search(real) for p in LOCAL_PATH_PATTERNS))

        documented = 'src="file:///Users/username/Movies/Wedding/Haldi.mov"'
        self.assertEqual(
            [u for u in HOME_PATH_RE.findall(documented) if u not in PLACEHOLDER_USERS], [],
            "a documentation placeholder must not be flagged")
        print("[\u2713] Leak check detects real account names, allows placeholders")


class TestGeneratedStatsMatchData(unittest.TestCase):
    def test_stats_md_is_in_sync_with_the_library(self):
        """stats.md is generated; a stale copy means the numbers are wrong again."""
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "scripts" / "library_stats.py"), "--check"],
            capture_output=True, text=True)
        self.assertEqual(
            result.returncode, 0,
            "library/stats.md does not match the library data. "
            "Run: python3 scripts/library_stats.py\n" + result.stdout + result.stderr)
        print("[✓] library/stats.md matches the library data")

    def test_track_counts_sum_to_the_total(self):
        """The arithmetic error that stood in the committed stats file."""
        lib = json.loads(
            (BASE_DIR / "references" / "08_video_library_150.json").read_text(encoding="utf-8"))
        videos = lib["videos"]
        self.assertEqual(len(videos), lib.get("total_count", len(videos)))

        stats = (BASE_DIR / "library" / "stats.md").read_text(encoding="utf-8")
        rows = re.findall(r"^\| `(T\d_\w+)` \| (\d+) \|", stats, re.MULTILINE)
        self.assertTrue(rows, "no per-track rows found in stats.md")
        self.assertEqual(
            sum(int(n) for _, n in rows), len(videos),
            "per-track counts in stats.md must sum to the number of videos")
        print(f"[✓] Track counts sum to {len(videos)}, matching the library")


class TestRequirementsAreHonest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (BASE_DIR / "docs" / "requirements.md").read_text(encoding="utf-8")

    def test_no_requirement_is_marked_verified(self):
        """Every row was once marked `verified`, including unimplemented work.

        The status vocabulary is now done / partial / knowledge only /
        unverified / missing. A row reading `verified` means the old blanket
        claim has crept back.
        """
        self.assertNotIn("| verified |", self.text)
        print("[✓] No requirement carries the old blanket `verified` status")

    def test_known_gaps_are_recorded_as_gaps(self):
        """Things genuinely not done must not be claimed as done."""
        for rid, expect in [("R2.3", "missing"), ("R2.4", "missing")]:
            row = next((l for l in self.text.splitlines() if l.startswith(f"| {rid} ")), None)
            self.assertIsNotNone(row, f"{rid} is missing from the table")
            self.assertIn(expect, row,
                          f"{rid} should be recorded as {expect}: {row}")
        # R5.5 is now filled with 15 verified videos
        row_r55 = next((l for l in self.text.splitlines() if l.startswith("| R5.5 ")), None)
        self.assertIsNotNone(row_r55)
        self.assertIn("done", row_r55)
        print("[✓] Transcripts and thumbnails recorded as gaps, T5 verified as done")

    def test_face_matching_is_claimed_only_because_it_exists(self):
        row = next(l for l in self.text.splitlines() if l.startswith("| R6.1 "))
        self.assertIn("faces.py", row)
        self.assertTrue((BASE_DIR / "scripts" / "faces.py").exists())

    def test_every_script_referenced_in_the_table_exists(self):
        """A traceability table that cites missing files is not traceability."""
        referenced = set(re.findall(r"`scripts/([A-Za-z0-9_]+\.py)`", self.text))
        self.assertTrue(referenced, "no scripts referenced in requirements.md")
        missing = [s for s in sorted(referenced)
                   if not (BASE_DIR / "scripts" / s).exists()]
        self.assertEqual(missing, [], f"requirements.md cites scripts that do not exist: {missing}")
        print(f"[✓] All {len(referenced)} scripts cited in requirements.md exist")

    def test_every_reference_doc_cited_exists(self):
        cited = set(re.findall(r"`references/(\d+_[A-Za-z0-9_]+\.md)`", self.text))
        missing = [c for c in sorted(cited) if not (BASE_DIR / "references" / c).exists()]
        self.assertEqual(missing, [], f"requirements.md cites missing references: {missing}")


class TestSkillDocumentsRealCommands(unittest.TestCase):
    def test_skill_md_only_references_scripts_that_exist(self):
        """The documented workflow must be runnable."""
        skill = BASE_DIR / ".agents" / "skills" / "bihari-indian-wedding-film-editor" / "SKILL.md"
        self.assertTrue(skill.exists(), "SKILL.md not found")
        text = skill.read_text(encoding="utf-8")
        referenced = set(re.findall(r"python3 scripts/([A-Za-z0-9_]+\.py)", text))
        self.assertTrue(referenced, "SKILL.md documents no commands")
        missing = [s for s in sorted(referenced)
                   if not (BASE_DIR / "scripts" / s).exists()]
        self.assertEqual(missing, [], f"SKILL.md documents missing scripts: {missing}")
        print(f"[✓] All {len(referenced)} scripts documented in SKILL.md exist")

    def test_skill_md_does_not_pin_an_fcpxml_version_in_its_description(self):
        """The schema version is a runtime choice, not a property of the skill."""
        skill = BASE_DIR / ".agents" / "skills" / "bihari-indian-wedding-film-editor" / "SKILL.md"
        frontmatter = skill.read_text(encoding="utf-8").split("---")[1]
        self.assertNotIn("FCPXML v1.10", frontmatter)


if __name__ == "__main__":
    unittest.main(verbosity=2)
