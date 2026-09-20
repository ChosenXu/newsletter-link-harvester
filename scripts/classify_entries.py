#!/usr/bin/env python3
"""Optional Jev (TypeSafe System One) pre-classification for newsletter entries.

Soft-optional enhancement: when no TypeSafe API key is configured the script
exits with code 3 and the skill continues exactly as before — results are
annotations for the preview stage only and never affect the confirmation
gate. No key is ever printed or logged.

For every entry it asks two Noul questions over one state (title, url,
introduction) in a single request, evaluated in parallel by the API:

  is_promotional   — the entry promotes the newsletter's own products or
                     channels (Telegram, social media, subscription nudges)
                     rather than editorially recommending external content
  meaningful_title — the anchor text is a concrete name usable as a bookmark
                     title (brand / product / proper noun / descriptive
                     phrase), not a placeholder like "click here"

Threshold guidance (calibrated 2026-09-20 on real Chinese newsletter
entries, 14/14 correct with clean separation): noul >= 0.9 marks "clear
promotional (suggest excluding)", <= 0.3 marks "clear content"; values in
between stay for human review in the preview.

Token resolution (first hit wins):
  1. TYPESAFE_API_KEY environment variable
  2. ~/.typesafe-api-key (first line is the key)

Input shape:  {"links": [{"anchor_text"|"title", "url", "context"|"intro", ...}]}
Output shape: same entries; each gains "jev": {"is_promotional": float|null,
"meaningful_title": float|null} plus "stats" describing coverage.

Exit codes: 0 ok (partial coverage allowed and reported); 2 usage error;
3 key not configured (expected soft skip — callers treat this as "enhancement
off"); 1 every request failed (network/service down).
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.typesafe.ai/v1/systemone"
KEY_FILE = os.path.expanduser("~/.typesafe-api-key")
REQUEST_TIMEOUT = 30

QUESTIONS = {
    "is_promotional": {
        "type": "noul",
        "instructions": "这条条目是 newsletter 作者在推广自己的产品、自家渠道（Telegram、小红书、Instagram 等）或寻求订阅关注，而不是以编辑视角推荐值得收藏的外部内容。",
    },
    "meaningful_title": {
        "type": "noul",
        "instructions": "这段锚文本是一个有具体指向的名称（品牌名、产品名、专有名词或描述性短语），可以原样用作收藏书签的标题；而不是「这里」「点击」「查看更多」这类没有任何信息量的占位词。",
    },
}


class NotConfigured(Exception):
    """No API key available -> exit code 3 (soft skip)."""


def load_key(key_file: str = "") -> str:
    env_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if env_key:
        return env_key
    path = os.path.expanduser(key_file) if key_file else KEY_FILE
    if not os.path.isfile(path):
        raise NotConfigured("no TypeSafe API key: set TYPESAFE_API_KEY or create " + KEY_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            key = fh.readline().strip()
    except OSError as exc:
        raise NotConfigured("cannot read key file: " + type(exc).__name__)
    if not key:
        raise NotConfigured("key file is empty: " + path)
    return key


def call(state: str, key: str) -> dict:
    body = json.dumps({"state": state, "model": "jev-latest",
                       "questions": QUESTIONS}).encode("utf-8")
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    })
    last_error = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                payload = json.load(resp)
            answers = payload.get("answers") or {}
            promo = answers.get("is_promotional") or {}
            title = answers.get("meaningful_title") or {}
            return {"is_promotional": promo.get("noul"),
                    "meaningful_title": title.get("noul")}
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
            last_error = exc
            if attempt == 1:
                time.sleep(1.5)
    raise RuntimeError("Jev call failed after retry: " + type(last_error).__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Optional Jev pre-classification of newsletter entries (soft dependency)"
    )
    parser.add_argument("--links", required=True,
                        help="links JSON (deduped/checked output; keys anchor_text|title, url, context|intro)")
    parser.add_argument("--output", help="write annotated JSON here; omit to print to stdout")
    parser.add_argument("--key-file", help="custom key file (first line is the key)")
    args = parser.parse_args()

    try:
        links_data = json.load(open(args.links, encoding="utf-8"))
    except OSError as exc:
        print("cannot read links file: " + type(exc).__name__, file=sys.stderr)
        return 2
    except ValueError:
        print("links file is not valid JSON", file=sys.stderr)
        return 2
    links = links_data.get("links", links_data.get("kept")) \
        if isinstance(links_data, dict) else links_data
    if not isinstance(links, list):
        print("links must be a list or contain links/kept", file=sys.stderr)
        return 2

    try:
        key = load_key(args.key_file)
    except NotConfigured as exc:
        print(str(exc), file=sys.stderr)
        return 3  # expected soft skip: enhancement off, flow unchanged

    classified = failed = 0
    for entry in links:
        if not isinstance(entry, dict):
            continue
        title = (entry.get("anchor_text") or entry.get("title") or "").strip()
        url = (entry.get("url") or "").strip()
        intro = (entry.get("context") or entry.get("intro") or "").strip()
        if not url:
            entry["jev"] = {"is_promotional": None, "meaningful_title": None}
            continue
        state = json.dumps({"title": title, "url": url, "introduction": intro},
                           ensure_ascii=False)
        try:
            entry["jev"] = call(state, key)
            classified += 1
        except RuntimeError:
            entry["jev"] = {"is_promotional": None, "meaningful_title": None}
            failed += 1
        time.sleep(0.1)

    result = {"links": links, "stats": {
        "total": len(links), "classified": classified, "failed": failed,
        "note": "noul >= 0.9 clear promotional; <= 0.3 clear content; "
                "between -> human review. Annotations only; confirmation gate unchanged.",
    }}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError as exc:
            print("cannot write output: " + type(exc).__name__, file=sys.stderr)
            return 2
    else:
        print(text)
    if failed and not classified:
        print("all Jev calls failed; entries left unclassified", file=sys.stderr)
        return 1
    print(f"classified {classified}/{len(links)} ({failed} failed) — annotations only",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
