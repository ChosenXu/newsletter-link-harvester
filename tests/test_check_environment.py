#!/usr/bin/env python3
"""Regression suite for scripts/check_environment.py (stdlib unittest).

Run from the skill root:
    python3 -m unittest discover -s tests -v

Covers the 1.3.0 fix: server matching reads only the name and url fields —
a "gmail" substring buried in an unrelated entry (env, headers, …) must not
read as configured.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import check_environment as ce  # noqa: E402


class MatchServerTests(unittest.TestCase):
    def test_match_on_name(self):
        servers = {"gmail-mcp": {"url": "https://example.com/mcp"}}
        self.assertTrue(ce._match_server(servers, ["gmail"])["configured"])

    def test_match_on_url(self):
        servers = {"remote-bridge": {"url": "https://gmail.bridge.example/mcp"}}
        self.assertTrue(ce._match_server(servers, ["gmail"])["configured"])

    def test_substring_in_unrelated_field_ignored(self):
        # 1.3.0: a match must not be claimed from env/args/other fields
        servers = {
            "other-server": {
                "url": "https://example.com/mcp",
                "env": {"NOTE": "mirrors gmail filters"},
                "args": ["--label", "gmail-import"],
            },
        }
        self.assertFalse(ce._match_server(servers, ["gmail"])["configured"])

    def test_non_dict_entries_skipped(self):
        servers = {"broken": "gmail-mcp string entry"}
        self.assertFalse(ce._match_server(servers, ["gmail"])["configured"])


if __name__ == "__main__":
    unittest.main()
