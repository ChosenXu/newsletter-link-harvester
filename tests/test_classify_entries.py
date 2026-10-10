#!/usr/bin/env python3
"""Regression suite for scripts/classify_entries.py (stdlib unittest, offline).

Run from the skill root:
    python3 -m unittest discover -s tests -v

The network layer is always mocked; the real TypeSafe API and the real key
file are never contacted. Covers entry state building, --only-new filtering,
the --max-entries cap, the soft-skip exit codes (3 no key, 1 all failed),
and key resolution precedence.
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

import classify_entries as ce  # noqa: E402


def run_main(argv):
    buffer = io.StringIO()
    with mock.patch.object(sys, "argv", argv), \
            contextlib.redirect_stdout(buffer):
        code = ce.main()
    return code, buffer.getvalue()


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return path


def fake_call(state, key):
    return {"is_promotional": 0.95, "meaningful_title": 0.8}


class EntryStateTests(unittest.TestCase):
    def test_state_builds_from_title_url_intro(self):
        entry = {"anchor_text": "A", "url": "https://a.com", "context": "why"}
        state = json.loads(ce._entry_state(entry))
        self.assertEqual(state, {"title": "A", "url": "https://a.com",
                                 "introduction": "why"})

    def test_state_falls_back_to_title_and_intro(self):
        entry = {"title": "T", "url": "https://a.com", "intro": "i"}
        state = json.loads(ce._entry_state(entry))
        self.assertEqual(state["title"], "T")
        self.assertEqual(state["introduction"], "i")


class MainTests(unittest.TestCase):
    def test_only_new_skips_library_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            links_path = write_json(os.path.join(tmp, "in.json"), {"results": [
                {"url": "https://a.com/x", "status": "new"},
                {"url": "https://b.com/y", "status": "exists"},
            ]})
            with mock.patch.object(ce, "load_key", return_value="k"), \
                    mock.patch.object(ce, "call", fake_call):
                code, stdout = run_main(
                    ["classify_entries.py", "--links", links_path, "--only-new"])
            payload = json.loads(stdout)
        self.assertEqual(code, 0)
        # --only-new excludes library entries from the output entirely
        self.assertEqual(len(payload["links"]), 1)
        self.assertEqual(payload["links"][0]["url"], "https://a.com/x")
        self.assertEqual(payload["links"][0]["jev"]["is_promotional"], 0.95)
        self.assertEqual(payload["stats"]["classified"], 1)

    def test_cap_limits_classified_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            links_path = write_json(os.path.join(tmp, "in.json"), {"links": [
                {"url": "https://a.com/%d" % i} for i in range(5)
            ]})
            with mock.patch.object(ce, "load_key", return_value="k"), \
                    mock.patch.object(ce, "call", fake_call):
                code, stdout = run_main(
                    ["classify_entries.py", "--links", links_path,
                     "--max-entries", "2"])
            payload = json.loads(stdout)
        self.assertEqual(code, 0)
        self.assertEqual(payload["stats"]["classified"], 2)
        self.assertEqual(payload["stats"]["skipped_by_cap"], 3)

    def test_no_key_soft_skips_with_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            links_path = write_json(os.path.join(tmp, "in.json"),
                                    {"links": [{"url": "https://a.com"}]})
            with mock.patch.object(ce, "load_key",
                                   side_effect=ce.NotConfigured("no key")):
                code, _ = run_main(["classify_entries.py", "--links", links_path])
        self.assertEqual(code, 3)

    def test_all_failed_exits_1(self):
        def failing_call(state, key):
            raise RuntimeError("down")
        with tempfile.TemporaryDirectory() as tmp:
            links_path = write_json(os.path.join(tmp, "in.json"),
                                    {"links": [{"url": "https://a.com"}]})
            with mock.patch.object(ce, "load_key", return_value="k"), \
                    mock.patch.object(ce, "call", failing_call):
                code, _ = run_main(["classify_entries.py", "--links", links_path])
        self.assertEqual(code, 1)


class LoadKeyTests(unittest.TestCase):
    def test_env_var_wins(self):
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": "env-key"}):
            self.assertEqual(ce.load_key("/nonexistent"), "env-key")

    def test_key_file_first_line(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("TYPESAFE_API_KEY", None)
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "key")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("file-key\nsecond line\n")
                self.assertEqual(ce.load_key(path), "file-key")

    def test_missing_key_file_raises_not_configured(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("TYPESAFE_API_KEY", None)
            with self.assertRaises(ce.NotConfigured):
                ce.load_key("/nonexistent/key/file")

    def test_empty_key_file_raises_not_configured(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("TYPESAFE_API_KEY", None)
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "key")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("\n")
                with self.assertRaises(ce.NotConfigured):
                    ce.load_key(path)


if __name__ == "__main__":
    unittest.main()
