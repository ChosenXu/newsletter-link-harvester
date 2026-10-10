#!/usr/bin/env python3
"""Regression suite for scripts/fetch_library.py (stdlib unittest, no network).

Run from the skill root:
    python3 -m unittest discover -s tests -v

Covers the 1.4.0 fixes: the exact-named "raindrop" entry can no longer be
shadowed by an earlier substring-named entry, and a gateway page that is
valid JSON but not an object is a retryable tool error, not an uncaught
crash.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fetch_library as fl  # noqa: E402


class TokenSelectionTests(unittest.TestCase):
    def test_exact_name_wins_over_earlier_substring_entry(self):
        # 1.4.0: "raindrop-old" (no token) listed first must not shadow "raindrop"
        config = {"mcpServers": {
            "raindrop-old": {"url": "https://x.example", "headers": {}},
            "raindrop": {"headers": {"Authorization": "Bearer good-token"}},
        }}
        self.assertEqual(fl._token_from_config_object(config), "good-token")

    def test_substring_fallback_when_no_exact_name(self):
        config = {"mcpServers": {
            "my-raindrop-bridge": {"headers": {"Authorization": "Bearer tok"}},
        }}
        self.assertEqual(fl._token_from_config_object(config), "tok")

    def test_first_substring_match_used_without_exact_name(self):
        config = {"mcpServers": {
            "a-raindrop": {"headers": {"Authorization": "Bearer first"}},
            "b-raindrop": {"headers": {"Authorization": "Bearer second"}},
        }}
        self.assertEqual(fl._token_from_config_object(config), "first")

    def test_non_bearer_header_rejected(self):
        config = {"mcpServers": {
            "raindrop": {"headers": {"Authorization": "Basic abc"}},
        }}
        self.assertEqual(fl._token_from_config_object(config), "")

    def test_non_dict_entries_ignored(self):
        config = {"mcpServers": {"raindrop": "garbage", "raindrop2": 42}}
        self.assertEqual(fl._token_from_config_object(config), "")


class ParsePageTests(unittest.TestCase):
    def test_object_payload_passes(self):
        self.assertEqual(
            fl.parse_page('{"bookmarks": [], "total": 0}'),
            {"bookmarks": [], "total": 0},
        )

    def test_non_object_payload_is_runtime_error(self):
        # 1.4.0: a JSON array/string page previously crashed with AttributeError
        for text in ("[1, 2]", '"ok"', "null"):
            with self.assertRaises(RuntimeError):
                fl.parse_page(text)

    def test_invalid_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            fl.parse_page("{not json")


if __name__ == "__main__":
    unittest.main()
