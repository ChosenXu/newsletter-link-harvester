#!/usr/bin/env python3
"""Regression suite for scripts/prune_state.py (stdlib unittest, no network).

Run from the skill root:
    python3 -m unittest discover -s tests -v

Covers the 1.3.0 fixes: malformed state rejected with exit 2, atomic write
(temp + os.replace, no .tmp residue), legacy shape handling, and the
collapse/cap rules.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "prune_state.py"
)


def run_prune(state_path, *extra):
    return subprocess.run(
        [sys.executable, SCRIPT, "--state", state_path, *extra],
        capture_output=True, text=True,
    )


class PruneStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.tmp.name, "state.json")

    def tearDown(self):
        self.tmp.cleanup()

    def write_state(self, data):
        with open(self.state, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def test_malformed_root_rejected(self):
        # 1.3.0: a non-object root must exit 2, not crash
        with open(self.state, "w", encoding="utf-8") as fh:
            fh.write('["not", "an", "object"]')
        result = run_prune(self.state)
        self.assertEqual(result.returncode, 2)
        self.assertIn("JSON object", result.stderr)

    def test_non_list_ids_rejected(self):
        # 1.3.0: processed_email_ids must be a list
        self.write_state({"processed_email_ids": "oops"})
        result = run_prune(self.state)
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be a list", result.stderr)

    def test_atomic_write_no_tmp_residue(self):
        # 1.3.0: write via temp file + os.replace; no .tmp left behind
        self.write_state({"processed_email_ids": ["a", "b"], "other_key": 1})
        result = run_prune(self.state)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(self.state + ".tmp"))
        with open(self.state, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(sorted(e["id"] for e in data["processed_email_ids"]), ["a", "b"])
        self.assertEqual(data["other_key"], 1)  # unrelated keys preserved

    def test_duplicates_collapse_to_last(self):
        self.write_state({"processed_email_ids": [
            {"id": "x", "processed_at": "2026-10-01", "sender": "old"},
            {"id": "x", "processed_at": "2026-10-05", "sender": "new"},
        ]})
        run_prune(self.state)
        with open(self.state, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(len(data["processed_email_ids"]), 1)
        self.assertEqual(data["processed_email_ids"][0]["sender"], "new")

    def test_cap_keeps_newest(self):
        self.write_state({"processed_email_ids": [
            {"id": "old", "processed_at": "2026-09-01"},
            {"id": "new", "processed_at": "2026-10-01"},
        ]})
        result = run_prune(self.state, "--max-entries", "1")
        self.assertEqual(result.returncode, 0)
        with open(self.state, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual([e["id"] for e in data["processed_email_ids"]], ["new"])

    def test_legacy_string_shape_accepted(self):
        self.write_state({"processed_email_ids": ["a", "b"]})
        result = run_prune(self.state, "--dry-run")
        self.assertEqual(result.returncode, 0)
        self.assertIn('"after": 2', result.stdout)


if __name__ == "__main__":
    unittest.main()
