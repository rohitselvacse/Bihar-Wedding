#!/usr/bin/env python3
"""Tests for the multi-agent graph orchestrator and feedback repair loop."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from agent_graph_orchestrator import (
    WeddingEditGraphOrchestrator,
    CriticAgent,
    VerifierAgent,
)


class TestAgentGraph(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_graph_executes_and_passes(self):
        orchestrator = WeddingEditGraphOrchestrator(self.tmp, max_loops=2)
        success = orchestrator.execute_graph_pipeline()
        self.assertTrue(success)
        self.assertGreaterEqual(len(orchestrator.state["history"]), 1)
        self.assertTrue(orchestrator.state["history"][0]["passed"])
        print("[✓] Multi-agent graph pipeline executed and verified successfully")

    def test_critic_catches_unbalanced_family_and_rejects_signoff(self):
        critic = CriticAgent()
        verifier = VerifierAgent()

        state = {
            "work_dir": self.tmp,
            "research": {"required_phases": ["matkor", "sindoor_daan"]},
            "shot_analysis": {
                "family_balance": {
                    "groom_family_percentage": 75.0,
                    "bride_family_percentage": 25.0,  # 50% deviation!
                },
                "missing_characters": [{"name": "Dada Ji", "role": "paternal-grandfather"}],
                "reception_stage_verified": False,
            },
            "assembler": {},
        }

        critic.run(state)
        self.assertFalse(state["critic"]["pass_verdict"])
        self.assertGreater(len(state["critic"]["findings"]), 0)

        passed = verifier.run(state)
        self.assertFalse(passed)
        self.assertEqual(state["verifier"]["status"], "RETRY_REQUIRED")
        print("[✓] Critic agent successfully flagged unbalanced family & rejected signoff")


if __name__ == "__main__":
    unittest.main(verbosity=2)
