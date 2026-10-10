#!/usr/bin/env python3
"""Regression suite for scripts/check_library.py (stdlib unittest, offline).

Run from the skill root:
    python3 -m unittest discover -s tests -v

Covers normalization-based matching (www / utm / trailing slash / fragment /
case), original-field carry-through, the bookmark_id/id fallback, and input
shape tolerance (kept dict, links dict, plain arrays).
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

import check_library as cl  # noqa: E402


def run_main(argv):
    buffer = io.StringIO()
    with mock.patch.object(sys, "argv", argv), \
            contextlib.redirect_stdout(buffer):
        code = cl.main()
    return code, buffer.getvalue()


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    return path


class CheckLibraryTests(unittest.TestCase):
    def run_compare(self, tmp, links, library):
        links_path = write_json(os.path.join(tmp, "links.json"), links)
        lib_path = write_json(os.path.join(tmp, "library.json"), library)
        code, stdout = run_main(
            ["check_library.py", "--links", links_path, "--library", lib_path])
        return code, (json.loads(stdout) if stdout.strip() else None)

    def test_new_vs_exists_with_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, payload = self.run_compare(
                tmp,
                {"links": [
                    {"url": "https://example.com/post", "anchor_text": "A"},
                    {"url": "https://www.example.com/other/?utm_source=x#frag",
                     "anchor_text": "B"},
                ]},
                {"bookmarks": [
                    {"link": "https://Example.com/post/", "title": "t",
                     "bookmark_id": "bm-1"},
                ]})
        self.assertEqual(code, 0)
        self.assertEqual(payload["stats"], {"total": 2, "new": 1, "exists": 1})
        exists = [r for r in payload["results"] if r["status"] == "exists"]
        self.assertEqual(exists[0]["matched"]["bookmark_id"], "bm-1")

    def test_original_fields_carry_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, payload = self.run_compare(
                tmp,
                {"kept": [{"url": "https://a.com/x", "anchor_text": "A",
                           "context": "why", "sender": "s"}]},
                {"bookmarks": []})
        self.assertEqual(code, 0)
        result = payload["results"][0]
        self.assertEqual(result["status"], "new")
        self.assertEqual(result["anchor_text"], "A")
        self.assertEqual(result["context"], "why")
        self.assertEqual(result["sender"], "s")

    def test_matched_falls_back_to_plain_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, payload = self.run_compare(
                tmp,
                {"links": [{"url": "https://a.com/x"}]},
                {"bookmarks": [{"link": "https://a.com/x", "id": 42}]})
        self.assertEqual(code, 0)
        self.assertEqual(payload["results"][0]["matched"]["bookmark_id"], 42)

    def test_plain_array_library_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, payload = self.run_compare(
                tmp,
                [{"url": "https://a.com/x"}],
                [{"link": "https://a.com/x"}])
        self.assertEqual(code, 0)
        self.assertEqual(payload["stats"]["exists"], 1)

    def test_invalid_input_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            links_path = write_json(os.path.join(tmp, "links.json"), {"kept": []})
            bad_path = os.path.join(tmp, "bad.json")
            with open(bad_path, "w", encoding="utf-8") as fh:
                fh.write("{broken")
            code, _ = run_main(
                ["check_library.py", "--links", links_path, "--library", bad_path])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
