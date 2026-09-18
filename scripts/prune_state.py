#!/usr/bin/env python3
"""Prune the cross-run dedup state file so it stays small and useful.

The state file (~/.config/newsletter-link-harvester/state.json) holds
processed email IDs for cross-run dedup. Old entries can be pruned safely:
the Raindrop library lookup (dedup layer 3) backstops duplicates for
anything pruned here.

Supported state shapes (read transparently, written back uniformly):
  {"processed_email_ids": ["id1", "id2"]}                       (legacy)
  {"processed_email_ids": [{"id": "...", "processed_at":
    "YYYY-MM-DD", "sender": "..."}, ...]}                      (current)

Pruning rules:
  - duplicate ids collapse to their last occurrence (newest metadata)
  - entries older than --max-age-days are dropped (undated entries are kept)
  - after ageing, only the newest --max-entries entries are kept
  - any other top-level keys in the state file are preserved

Exit codes: 0 ok (see printed stats), 2 state file missing/invalid,
1 unexpected error. No network, no subprocess, writes only the state file
unless --dry-run.
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta

DEFAULT_STATE = os.path.join(
    os.path.expanduser("~"), ".config", "newsletter-link-harvester", "state.json"
)


def load_entries(raw):
    entries = []
    for item in raw:
        if isinstance(item, dict):
            entries.append({
                "id": str(item.get("id", "")),
                "processed_at": str(item.get("processed_at", "")),
                "sender": str(item.get("sender", "")),
            })
        else:
            entries.append({"id": str(item), "processed_at": "", "sender": ""})
    return [e for e in entries if e["id"]]


def safe_date(value: str):
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prune old entries from the cross-run dedup state file"
    )
    parser.add_argument("--state", default=DEFAULT_STATE, help="state file path")
    parser.add_argument("--max-age-days", type=int, default=180,
                        help="drop entries processed more than this many days ago")
    parser.add_argument("--max-entries", type=int, default=500,
                        help="keep at most this many entries")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be pruned without writing")
    args = parser.parse_args()

    try:
        with open(args.state, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        print("state file not found: nothing to prune")
        return 0
    except OSError as exc:
        print("cannot read state file: " + type(exc).__name__, file=sys.stderr)
        return 2
    except ValueError:
        print("state file is not valid JSON", file=sys.stderr)
        return 2

    raw = data.get("processed_email_ids", [])
    entries = load_entries(raw)
    before = len(entries)

    # collapse duplicate ids, keeping the last occurrence (newest metadata)
    collapsed = {}
    for entry in entries:
        collapsed[entry["id"]] = entry
    entries = list(collapsed.values())

    cutoff = date.today() - timedelta(days=args.max_age_days)
    kept, aged_out = [], 0
    for entry in entries:
        d = safe_date(entry["processed_at"]) if entry["processed_at"] else None
        if d is not None and d < cutoff:
            aged_out += 1
        else:
            kept.append(entry)

    # newest first (undated entries sort last), then cap
    kept.sort(key=lambda e: e["processed_at"], reverse=True)
    if args.max_entries >= 0 and len(kept) > args.max_entries:
        capped_out = len(kept) - args.max_entries
        kept = kept[: args.max_entries]
    else:
        capped_out = 0

    stats = {"before": before, "after": len(kept),
             "pruned_by_age": aged_out, "pruned_by_cap": capped_out}

    if args.dry_run:
        print(json.dumps({"dry_run": True, "stats": stats}, ensure_ascii=False, indent=2))
        return 0

    data["processed_email_ids"] = kept
    try:
        with open(args.state, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    except OSError as exc:
        print("cannot write state file: " + type(exc).__name__, file=sys.stderr)
        return 1
    print(json.dumps({"stats": stats}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
