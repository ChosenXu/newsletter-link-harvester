#!/usr/bin/env python3
"""Regression suite for scripts/dedupe_links.py (stdlib unittest, no network).

Run from the skill root:
    python3 -m unittest discover -s tests -v

Covers the 1.3.0 fixes: uppercase schemes kept, empty host rejected,
host-scoped tracking params (si on open.spotify.com only), and the
dedup/normalization rules.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import dedupe_links as dl  # noqa: E402


class SplitUrlTests(unittest.TestCase):
    def test_uppercase_scheme_accepted(self):
        # 1.3.0: "HTTPS://host/path" was previously dropped as non_web
        self.assertIsNotNone(dl.split_url("HTTPS://example.com/page"))
        self.assertEqual(dl.split_url("HTTPS://example.com/page")[0], "https")

    def test_empty_host_rejected(self):
        # 1.3.0: "https:///path" (empty host) is unusable as a bookmark
        self.assertIsNone(dl.split_url("https:///path"))

    def test_non_web_schemes_rejected(self):
        for url in ("ftp://example.com/a", "javascript:void(0)", "mailto:a@b.c", "example.com/page"):
            self.assertIsNone(dl.split_url(url), url)

    def test_fragment_userinfo_default_port_dropped(self):
        parts = dl.split_url("http://user:pw@Example.com:80/p#frag")
        self.assertEqual(parts[0], "http")
        self.assertEqual(parts[1], "example.com")
        self.assertEqual(parts[2], "/p")
        self.assertEqual(parts[3], [])


class TrackingTests(unittest.TestCase):
    def test_si_stripped_on_spotify(self):
        cleaned, _, _ = dl.normalize("https://open.spotify.com/track/x?si=abc")
        self.assertNotIn("si=", cleaned)

    def test_si_kept_elsewhere(self):
        # 1.3.0: TRACKING_HOST whitelist — "si" is only tracking on spotify
        cleaned, _, _ = dl.normalize("https://example.com/page?si=abc")
        self.assertIn("si=abc", cleaned)

    def test_utm_and_exact_list_stripped(self):
        cleaned, _, _ = dl.normalize("https://example.com/p?utm_source=x&fbclid=y&id=7")
        self.assertNotIn("utm_source", cleaned)
        self.assertNotIn("fbclid", cleaned)
        self.assertIn("id=7", cleaned)


class DedupeTests(unittest.TestCase):
    def test_duplicates_collapse_first_wins(self):
        a = {"url": "https://example.com/page?b=2&a=1"}
        b = {"url": "https://www.example.com/page?a=1&b=2"}
        # exercise the batch loop through normalize + dedup key directly
        _, key_a, reason_a = dl.normalize(a["url"])
        _, key_b, reason_b = dl.normalize(b["url"])
        self.assertIsNone(reason_a)
        self.assertIsNone(reason_b)
        self.assertEqual(key_a, key_b)  # www. ignored, query params sorted

    def test_normalize_rejects_non_web(self):
        _, _, reason = dl.normalize("https:///path")
        self.assertEqual(reason, "non_web")


if __name__ == "__main__":
    unittest.main()
