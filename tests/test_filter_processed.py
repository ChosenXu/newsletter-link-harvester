#!/usr/bin/env python3
"""Regression suite for scripts/filter_processed.py (stdlib unittest, offline).

Run from the skill root:
    python3 -m unittest discover -s tests -v

Covers the 1.5.0 zero-context cross-run dedup: state shapes (legacy strings
and object entries), missing state file, malformed state rejection, input
shapes, and the new/processed split.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import filter_processed as fp  # noqa: E402


def run_main(argv):
    buffer = io.StringIO()
    with mock.patch.object(sys, "argv", argv), \
            contextlib.redirect_stdout(buffer):
        code = fp.main()
    return code, buffer.getvalue()


class LoadStateIdsTests(unittest.TestCase):
    def test_legacy_plain_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"processed_email_ids": ["a", "b"]}, fh)
            ids, missing = fp.load_state_ids(path)
        self.assertEqual(ids, {"a", "b"})
        self.assertFalse(missing)

    def test_object_entries_and_mixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"processed_email_ids": [
                    {"id": "x", "processed_at": "2026-10-01", "sender": "s"},
                    "legacy",
                    {"id": ""},  # empty id ignored
                ]}, fh)
            ids, missing = fp.load_state_ids(path)
        self.assertEqual(ids, {"x", "legacy"})
        self.assertFalse(missing)

    def test_missing_file_means_first_run(self):
        ids, missing = fp.load_state_ids("/nonexistent/path/state.json")
        self.assertEqual(ids, set())
        self.assertTrue(missing)

    def test_malformed_state_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "state.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            with self.assertRaises(ValueError):
                fp.load_state_ids(path)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(["not", "an", "object"], fh)
            with self.assertRaises(ValueError):
                fp.load_state_ids(path)


class MainTests(unittest.TestCase):
    def test_split_new_and_processed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids_path = os.path.join(tmp, "ids.json")
            state_path = os.path.join(tmp, "state.json")
            out_path = os.path.join(tmp, "out.json")
            with open(ids_path, "w", encoding="utf-8") as fh:
                json.dump({"ids": ["a", "b", "c"]}, fh)
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"processed_email_ids": [{"id": "b"}]}, fh)
            code, _ = run_main(
                ["filter_processed.py", "--ids", ids_path,
                 "--state", state_path, "--output", out_path])
            with open(out_path, encoding="utf-8") as fh:
                payload = json.load(fh)
        self.assertEqual(code, 0)
        self.assertEqual(payload["new"], ["a", "c"])
        self.assertEqual(payload["processed"], ["b"])
        self.assertEqual(payload["stats"]["input"], 3)

    def test_input_dedup_and_order_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids_path = os.path.join(tmp, "ids.json")
            out_path = os.path.join(tmp, "out.json")
            with open(ids_path, "w", encoding="utf-8") as fh:
                json.dump(["a", "b", "a", " ", ""], fh)
            code, _ = run_main(
                ["filter_processed.py", "--ids", ids_path,
                 "--state", os.path.join(tmp, "absent.json"),
                 "--output", out_path])
            with open(out_path, encoding="utf-8") as fh:
                payload = json.load(fh)
        self.assertEqual(code, 0)
        self.assertEqual(payload["new"], ["a", "b"])
        self.assertTrue(payload["stats"]["state_file_missing"])

    def test_invalid_ids_file_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids_path = os.path.join(tmp, "ids.json")
            with open(ids_path, "w", encoding="utf-8") as fh:
                fh.write("not json")
            code, _ = run_main(
                ["filter_processed.py", "--ids", ids_path,
                 "--state", os.path.join(tmp, "s.json")])
        self.assertEqual(code, 2)

    def test_malformed_state_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids_path = os.path.join(tmp, "ids.json")
            state_path = os.path.join(tmp, "state.json")
            with open(ids_path, "w", encoding="utf-8") as fh:
                json.dump(["a"], fh)
            with open(state_path, "w", encoding="utf-8") as fh:
                fh.write('{"processed_email_ids": "not-a-list"}')
            code, _ = run_main(
                ["filter_processed.py", "--ids", ids_path, "--state", state_path])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
