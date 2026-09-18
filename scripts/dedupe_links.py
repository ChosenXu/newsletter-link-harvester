#!/usr/bin/env python3
"""Normalize and de-duplicate extracted newsletter links.

Input JSON shape:
  {"links": [{"url": "...", "sender": "...", "email_subject": "...",
              "email_date": "...", "anchor_text": "...", "email_id": "..."}]}

Processing:
  1. keep only http/https links (others reported as removed, reason non_web)
  2. lowercase scheme and host, drop default ports, drop userinfo and fragment
  3. drop tracking query params (utm_* prefix plus a fixed list)
  4. strip trailing slash on non-root paths
  5. de-duplicate inside the batch; key ignores the leading www. and sorts
     remaining query params; the first occurrence wins

URL handling is plain string parsing only: no network access, no urllib,
no subprocess, no credential reading.

Output JSON shape:
  {"kept": [...], "removed": [{"url": ..., "reason": ...}], "stats": {...}}

Exit codes: 0 ok, 2 input file missing or invalid JSON, 1 unexpected error.
Never touches the network, never writes files unless --output is given.
"""

import argparse
import json
import sys

TRACKING_EXACT = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid",
    "si", "ref_src", "ref_url", "_hsenc", "_hsmi", "vero_id", "wickedid",
    "ttclid", "li_fat_id", "twclid", "s_kwcid", "yclid",
}


def split_url(url: str):
    """Return (scheme, host, path, query_pairs) or None when not http/https."""
    rest = url.strip()
    for scheme in ("https://", "http://"):
        if rest.startswith(scheme):
            used = scheme[:-3]
            break
    else:
        return None
    rest = rest[len(used) + 3:]
    rest = rest.split("#", 1)[0]
    if "?" in rest:
        path_part, query = rest.split("?", 1)
    else:
        path_part, query = rest, ""
    netloc, _, path = path_part.partition("/")
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]
    host = netloc.lower()
    if ":" in host:
        hostname, _, port = host.partition(":")
        if (used == "http" and port == "80") or (used == "https" and port == "443"):
            host = hostname
    pairs = []
    if query:
        for chunk in query.split("&"):
            if not chunk:
                continue
            key, sep, value = chunk.partition("=")
            pairs.append((key, value if sep else ""))
    return used, host, "/" + path if path else "", pairs


def join_url(scheme: str, host: str, path: str, pairs) -> str:
    query = "&".join(k + "=" + v if v else k for k, v in pairs)
    return scheme + "://" + host + path + ("?" + query if query else "")


def is_tracking(key: str) -> bool:
    lowered = key.lower()
    return lowered in TRACKING_EXACT or lowered.startswith("utm_")


def normalize(url: str):
    """Return (cleaned_url, dedup_key, remove_reason)."""
    parts = split_url(url)
    if parts is None:
        return None, None, "non_web"
    scheme, host, path, pairs = parts
    kept_pairs = [(k, v) for k, v in pairs if not is_tracking(k)]
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    cleaned = join_url(scheme, host, path, kept_pairs)
    key_host = host[4:] if host.startswith("www.") else host
    key = join_url(scheme, key_host, path, sorted((k.lower(), v) for k, v in kept_pairs))
    return cleaned, key, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize and de-duplicate extracted newsletter links"
    )
    parser.add_argument("input", help="JSON file with a links array, see module docstring")
    parser.add_argument("--output", help="write result JSON here; omit to print to stdout")
    args = parser.parse_args()

    try:
        with open(args.input, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        print("cannot read input file: " + type(exc).__name__, file=sys.stderr)
        return 2
    except ValueError:
        print("input file is not valid JSON", file=sys.stderr)
        return 2

    links = data.get("links", []) if isinstance(data, dict) else data
    if not isinstance(links, list):
        print("input must contain a links array", file=sys.stderr)
        return 2

    kept, removed, seen = [], [], {}
    stats = {"input": len(links), "kept": 0, "removed_non_web": 0, "removed_duplicate": 0}

    for item in links:
        raw_url = item.get("url", "") if isinstance(item, dict) else ""
        cleaned, key, reason = normalize(raw_url)
        if reason == "non_web":
            stats["removed_non_web"] += 1
            removed.append({"url": raw_url, "reason": "non_web"})
            continue
        if key in seen:
            stats["removed_duplicate"] += 1
            removed.append({"url": raw_url, "reason": "duplicate_of:" + seen[key]})
            continue
        seen[key] = cleaned
        entry = dict(item)
        entry["url"] = cleaned
        kept.append(entry)
        stats["kept"] += 1

    result = {"kept": kept, "removed": removed, "stats": stats}
    text = json.dumps(result, ensure_ascii=False, indent=2)
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
