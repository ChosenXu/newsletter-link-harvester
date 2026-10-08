#!/usr/bin/env python3
"""Regression suite for scripts/extract_context.py (stdlib unittest, no network).

Run from the skill root:
    python3 -m unittest discover -s tests -v

Covers the 1.3.0 fixes: sentence boundaries ignore decimals and abbreviations,
the --max-chars floor of 10 (no negative slicing), non-dict link entries are
skipped, and the URL-only fallback measures the actually matched text.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import extract_context as ec  # noqa: E402

SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "extract_context.py"
)

MD = (
    "Intro line before.\n\n"
    "It adds 3.5 features [Tool A](https://a.example/x) in total. Next sentence here.\n\n"
    "[Tool B](https://b.example/y)\n\n"
    "Real body for B that follows the bare heading and is long enough.\n\n"
    "Wrong anchor usage: [Real Anchor](https://c.example/z) trailing text.\n\n"
    "U.S. markets opened flat. Then [Tool D](https://d.example/w) appears.\n"
)


class SentenceBoundaryTests(unittest.TestCase):
    def test_decimal_point_does_not_end_sentence(self):
        # 1.3.0: "3.5" must not split the sentence containing the link
        para = "It adds 3.5 features [T](https://a.example/x) in total. Then more."
        ctx = ec.find_context(para, "T", "https://a.example/x", 160)
        self.assertIn("3.5 features", ctx)

    def test_abbreviations_do_not_end_sentence(self):
        # 1.3.0: e.g. / etc. / U.S. tails must not split
        self.assertFalse(ec._ends_sentence("see e.g. the guide", 9))
        self.assertFalse(ec._ends_sentence("U.S. markets", 3))
        self.assertTrue(ec._ends_sentence("done. Next", 4))


class ClampTests(unittest.TestCase):
    def test_max_chars_floor(self):
        # 1.3.0: --max-chars is clamped to MIN_CHARS=10 (no negative slicing)
        self.assertEqual(ec.MIN_CHARS, 10)

    def test_small_max_chars_via_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            email_path = os.path.join(tmp, "email.md")
            links_path = os.path.join(tmp, "links.json")
            with open(email_path, "w", encoding="utf-8") as fh:
                fh.write(MD)
            with open(links_path, "w", encoding="utf-8") as fh:
                json.dump({"links": [{"url": "https://a.example/x", "anchor_text": "Tool A"}]}, fh)
            result = subprocess.run(
                [sys.executable, SCRIPT, "--email", email_path,
                 "--links", links_path, "--max-chars", "3"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = json.loads(result.stdout)
            ctx = out["links"][0]["context"]
            self.assertGreaterEqual(len(ctx), 10)  # clamped, not negative-sliced


class FallbackTests(unittest.TestCase):
    def test_non_dict_entries_skipped(self):
        # 1.3.0: non-dict entries in the links array are counted, not crashing
        links = [1, "junk", {"url": "https://a.example/x", "anchor_text": "Tool A"}]
        with tempfile.TemporaryDirectory() as tmp:
            email_path = os.path.join(tmp, "email.md")
            links_path = os.path.join(tmp, "links.json")
            with open(email_path, "w", encoding="utf-8") as fh:
                fh.write(MD)
            with open(links_path, "w", encoding="utf-8") as fh:
                json.dump({"links": links}, fh)
            result = subprocess.run(
                [sys.executable, SCRIPT, "--email", email_path, "--links", links_path],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = json.loads(result.stdout)
            self.assertEqual(out["stats"]["without_context"], 2)
            # the valid dict entry after the junk ones is still processed
            self.assertIn("3.5 features", out["links"][2]["context"])

    def test_url_fallback_uses_matched_text(self):
        # 1.3.0: anchor mismatch falls back to URL-only match and measures
        # the actually matched text, so the context is still found
        ctx = ec.find_context(MD, "wrong-anchor", "https://c.example/z", 160)
        self.assertTrue(ctx)
        self.assertIn("Real Anchor", ctx or "")
        self.assertIn("Wrong anchor usage", ctx)

    def test_bare_heading_falls_to_next_paragraph(self):
        # heading-only entry: context comes from the following paragraph
        ctx = ec.find_context(MD, "Tool B", "https://b.example/y", 160)
        self.assertTrue(ctx.startswith("Real body for B"))


if __name__ == "__main__":
    unittest.main()
