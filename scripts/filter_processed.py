#!/usr/bin/env python3
"""Filter out already-processed email IDs for cross-run dedup (zero context).

Data channel for the second dedup layer (cross-run state): the caller writes
the email IDs collected from the Gmail search to a JSON file and this script
splits them against the state file, so the state file itself (up to 500
entries) never enters the model conversation — the same zero-context design
as the library-export channel.

Supported state shapes (identical to prune_state.py, read transparently):
  {"processed_email_ids": ["id1", "id2"]}                    (legacy)
  {"processed_email_ids": [{"id": "...", "processed_at":
    "YYYY-MM-DD", "sender": "..."}, ...]}                    (current)

Input IDs file shape: {"ids": ["id1", ...]} or a plain array of strings.
A missing state file means the first run: every ID counts as new.

Output shape:
  {"new": [...], "processed": [...],
   "stats": {"input": n, "new": a, "processed": b}}

Exit codes: 0 ok, 2 input/state file missing or invalid (a malformed state
file exits 2 — the caller treats every ID as new and relies on the library
lookup backstop), 1 unexpected error.
Never touches the network, never writes the state file.
"""

import argparse
import json
import os
import sys

DEFAULT_STATE = os.path.join(
    os.path.expanduser("~"), ".config", "newsletter-link-harvester", "state.json"
)


def load_state_ids(state_path: str):
    """Return (ids_set, missing). Malformed state raises ValueError."""
    try:
        with open(state_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return set(), True
    except OSError as exc:
        raise ValueError("cannot read state file: " + type(exc).__name__) from exc
    if not isinstance(data, dict) or not isinstance(
        data.get("processed_email_ids", []), list
    ):
        raise ValueError("state file must be an object with a processed_email_ids list")
    ids = set()
    for item in data["processed_email_ids"]:
        if isinstance(item, dict):
            if item.get("id"):
                ids.add(str(item["id"]))
        elif item:
            ids.add(str(item))
    return ids, False


def load_input_ids(ids_path: str):
    """Return the deduplicated input IDs (order preserved)."""
    try:
        with open(ids_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise ValueError("cannot read ids file: " + type(exc).__name__) from exc
    raw = data.get("ids") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("ids file must be a list or contain an ids array")
    ids, seen = [], set()
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            continue
        item = item.strip()
        if item not in seen:
            seen.add(item)
            ids.append(item)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split email IDs into new vs already-processed (state file stays out of context)"
    )
    parser.add_argument("--ids", required=True,
                        help="JSON file with the email IDs collected this run")
    parser.add_argument("--state", default=DEFAULT_STATE, help="state file path")
    parser.add_argument("--output", help="write result JSON here; omit to print to stdout")
    args = parser.parse_args()

    try:
        ids = load_input_ids(args.ids)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        processed, missing = load_state_ids(args.state)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    fresh = [i for i in ids if i not in processed]
    done = [i for i in ids if i in processed]
    payload = {
        "new": fresh,
        "processed": done,
        "stats": {
            "input": len(ids),
            "new": len(fresh),
            "processed": len(done),
            "state_file_missing": missing,
        },
    }
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
