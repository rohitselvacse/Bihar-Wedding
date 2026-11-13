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


class TestGradeAgentDegradesCleanly(unittest.TestCase):
    """The grade stage must survive a missing optional dependency.

    measure_skin_from_face_patch degrades rather than raising: without OpenCV it
    returns only {"skin_detected": False, "skin_status": "opencv_missing"} and
    the measurement keys are absent. GradeAgent read flesh_line_angle,
    flesh_line_deviation and skin_ire unconditionally, so it raised KeyError and
    took the entire pipeline down on any machine without OpenCV, which is most
    of them since OpenCV is optional. It also reported status READY while doing
    so, claiming an engine that had never loaded.
    """

    def _run_with(self, skin_result):
        import agent_graph_orchestrator as ago

        original = ago.measure_skin_from_face_patch
        ago.measure_skin_from_face_patch = lambda *a, **k: skin_result
        try:
            return ago.GradeAgent().run({})["grade"]
        finally:
            ago.measure_skin_from_face_patch = original

    def test_missing_opencv_does_not_raise(self):
        grade = self._run_with({"skin_detected": False, "skin_status": "opencv_missing"})
        self.assertFalse(grade["skin_detected"])
        self.assertNotEqual(grade["status"], "READY",
                            "a stage whose engine never loaded must not report READY")
        self.assertIn("opencv_missing", grade["status"].lower())
        print("[✓] Grade stage survives missing OpenCV and reports it honestly")

    def test_empty_patch_does_not_raise(self):
        grade = self._run_with({"skin_detected": False, "skin_status": "empty_patch"})
        self.assertNotEqual(grade["status"], "READY")

    def test_successful_measurement_still_reports_ready(self):
        grade = self._run_with({
            "skin_detected": True, "skin_status": "on_flesh_line",
            "flesh_line_angle": 123.4, "flesh_line_deviation": 0.4, "skin_ire": 62.0,
        })
        self.assertEqual(grade["status"], "READY")
        self.assertEqual(grade["flesh_line_angle"], 123.4)
        print("[✓] Grade stage still reports READY on a real measurement")


if __name__ == "__main__":
    unittest.main(verbosity=2)
