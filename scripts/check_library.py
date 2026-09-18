#!/usr/bin/env python3
"""Compare deduplicated newsletter links against a Raindrop library export.

Third dedup layer, done locally: instead of querying Raindrop once per link,
the caller fetches the library bookmarks (paginated, e.g. 150 per call) into
a JSON file and this script compares them offline.

Input shapes:
  links file:   {"links": [{"url": "...", ...}]} (deduped.json)
  library file: {"bookmarks": [{"link": "...", ...}]}
                or a plain array of the same objects

Both sides are normalized with the same rules as dedupe_links.py (lowercase
host, drop fragment, drop utm_*/tracking params, strip trailing slash,
ignore leading www.), so a bookmark saved as
`https://www.example.com/post/?utm_source=x` matches a new link
`https://example.com/post`.

Output shape:
  {"results": [{"url": ..., "status": "new"|"exists", "matched": ...}, ...],
   "stats": {"total": n, "new": a, "exists": b}}

Exit codes: 0 ok, 2 input file missing/invalid, 1 unexpected error.
Never touches the network, never writes files unless --output is given.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedupe_links import normalize  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare newsletter links against a Raindrop library export"
    )
    parser.add_argument("--links", required=True, help="deduped links JSON (see module docstring)")
    parser.add_argument("--library", required=True, help="library bookmarks JSON (see module docstring)")
    parser.add_argument("--output", help="write result JSON here; omit to print to stdout")
    args = parser.parse_args()

    try:
        links_data = json.load(open(args.links, encoding="utf-8"))
        library_data = json.load(open(args.library, encoding="utf-8"))
    except OSError as exc:
        print("cannot read input: " + type(exc).__name__, file=sys.stderr)
        return 2
    except ValueError:
        print("input file is not valid JSON", file=sys.stderr)
        return 2

    # dedupe_links.py outputs {"kept": ...}; accept "links" too for raw lists
    links = None
    if isinstance(links_data, dict):
        links = links_data.get("links", links_data.get("kept"))
    elif isinstance(links_data, list):
        links = links_data
    bookmarks = library_data.get("bookmarks", []) if isinstance(library_data, dict) else library_data
    if not isinstance(links, list) or not isinstance(bookmarks, list):
        print("links must be a list and library must be a list or contain a bookmarks list",
              file=sys.stderr)
        return 2

    library_keys = {}
    for bm in bookmarks:
        if not isinstance(bm, dict):
            continue
        bm_url = bm.get("link", "")
        if not bm_url:
            continue
        _, key, _ = normalize(bm_url)
        if key:
            library_keys[key] = bm

    results = []
    new = exists = 0
    for item in links:
        url = item.get("url", "") if isinstance(item, dict) else ""
        _, key, _ = normalize(url)
        if key and key in library_keys:
            matched = library_keys[key]
            results.append({
                "url": url,
                "status": "exists",
                "matched": {"link": matched.get("link"),
                            "title": matched.get("title"),
                            "bookmark_id": matched.get("bookmark_id")
                            or matched.get("id")},
            })
            exists += 1
        else:
            results.append({"url": url, "status": "new", "matched": None})
            new += 1

    payload = {"results": results, "stats": {"total": len(results), "new": new, "exists": exists}}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except OSError as exc:
            print("cannot write output file: " + type(exc).__name__, file=sys.stderr)
            return 1
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
