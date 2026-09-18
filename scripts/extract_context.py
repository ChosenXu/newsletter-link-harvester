#!/usr/bin/env python3
"""Extract the author's introduction sentence(s) for each link from the
newsletter email body.

Two body formats are supported (--format):

  markdown (default): links appear as `[anchor](url)`. For every link in the
  input JSON, locate its occurrence in the email Markdown, take the sentence
  (or short paragraph) that contains it, strip Markdown syntax, and store it
  as the link's "context" field. Bare-heading entries fall back to the
  following paragraph.

  text: links appear as `[ url ]` after title text (SubStack-style plain
  text, typically redirect wrappers). Links are matched by their
  `source_url` (the original wrapper) or url, and the context is the
  containing line plus the following line with all `[ ... ]` tokens removed.

Input links JSON shape: {"links": [{...,"url":...,"anchor_text":...}]}
The text format also accepts an optional "source_url" per link (the original
wrapped URL before resolution) — matching uses it first.
Output shape: same, each entry gains "context" (string, possibly empty).

Rules:
  - markdown links are consumed in order; each occurrence is used once
  - context window: the sentence around the link; falls back to the whole
    paragraph (stripped, truncated) when the sentence is too short
  - context is plain text: images removed, [text](url) reduced to text,
    emphasis markers stripped, whitespace collapsed, truncated to max-chars

Exit codes: 0 ok, 2 input file missing/invalid, 1 unexpected error.
Never touches the network, never writes files unless --output is given.
"""

import argparse
import json
import re
import sys

MAX_CHARS_DEFAULT = 160
SENTENCE_END = "。！？；!?"

LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\((https?://[^)\s]+)\)")
IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
EMPH_RE = re.compile(r"[*_`#>]+")


def strip_markdown(fragment: str) -> str:
    fragment = IMG_RE.sub("", fragment)
    fragment = LINK_RE.sub(lambda m: m.group(2), fragment)
    fragment = EMPH_RE.sub("", fragment)
    fragment = re.sub(r"\s+", " ", fragment)
    return fragment.strip()


def sentence_around(paragraph: str, start: int, end: int) -> str:
    left = start
    while left > 0 and paragraph[left - 1] not in SENTENCE_END:
        left -= 1
    right = end
    while right < len(paragraph) and paragraph[right] not in SENTENCE_END:
        right += 1
    return paragraph[left:right]


def find_context(md: str, anchor: str, url: str, max_chars: int) -> str:
    pattern = "[" + anchor + "](" + url + ")"
    pos = md.find(pattern)
    if pos == -1:
        # anchor might differ slightly; fall back to URL-only match
        pos = md.find("(" + url + ")")
        if pos == -1:
            return ""
        pos = md.rfind("[", 0, pos)
        if pos == -1:
            return ""
    # locate containing paragraph (blank-line separated)
    para_start = md.rfind("\n\n", 0, pos)
    para_start = 0 if para_start == -1 else para_start + 2
    para_end = md.find("\n\n", pos)
    para_end = len(md) if para_end == -1 else para_end
    paragraph = md[para_start:para_end]
    local_start = pos - para_start
    local_end = local_start + len(pattern)
    anchor_only = strip_markdown(anchor).strip()
    fragment = sentence_around(paragraph, local_start, local_end)
    stripped = None
    frag_pos = paragraph.find(fragment)
    all_parts = list(re.finditer(r"\s+-\s+", fragment))
    if frag_pos != -1 and all_parts:
        in_frag = local_start - frag_pos
        link_start = in_frag
        link_end = in_frag + len(pattern)
        parts = [
            m for m in all_parts
            if not (m.start() < link_end and m.end() > link_start)
        ]
        if parts:
            bounds = [0] + [m.start() for m in parts] + [len(fragment)]
            segments = [fragment[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]
            link_idx = None
            for si, seg in enumerate(segments):
                off = bounds[si]
                if off <= in_frag <= off + len(seg):
                    link_idx = si
                    break
            if link_idx is not None:
                seg_text = strip_markdown(segments[link_idx]).lstrip("-").strip()
                if seg_text == anchor_only and link_idx + 1 < len(segments):
                    seg_text = (seg_text + " " + strip_markdown(segments[link_idx + 1]).lstrip("-").strip()).strip()
                stripped = seg_text
    if stripped is None:
        stripped = strip_markdown(fragment)
    if len(stripped) < 10 or stripped == anchor_only:
        # heading-only or bare-link entries: take the following paragraph,
        # which holds the author's introduction
        after = md[para_end:].lstrip("\n")
        next_end = after.find("\n\n")
        after = after[: len(after) if next_end == -1 else next_end]
        candidate = strip_markdown(after)
        if len(candidate) >= 10:
            stripped = candidate
    if len(stripped) < 10:
        stripped = strip_markdown(paragraph)
    if len(stripped) > max_chars:
        stripped = stripped[: max_chars - 1].rstrip() + "…"
    return stripped


def find_context_text(md: str, key: str, max_chars: int) -> str:
    """Plain-text channel: context = containing line + next line, `[ url ]`
    tokens removed."""
    if not key:
        return ""
    pos = md.find("[ " + key + " ]")
    if pos == -1:
        pos = md.find(key)
    if pos == -1:
        return ""
    line_start = md.rfind("\n", 0, pos) + 1
    line_end = md.find("\n", pos)
    line_end = len(md) if line_end == -1 else line_end
    nxt_end = md.find("\n", line_end + 1)
    nxt = md[line_end + 1: nxt_end if nxt_end != -1 else len(md)]
    combined = md[line_start:line_end] + " " + nxt
    combined = re.sub(r"\[ ?https?://[^\s\]]+ ?\]", "", combined)
    combined = re.sub(r"\s+", " ", combined).strip()
    if len(combined) > max_chars:
        combined = combined[: max_chars - 1].rstrip() + "…"
    return combined


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract the author's introduction for each newsletter link"
    )
    parser.add_argument("--email", required=True, help="email body file (Markdown)")
    parser.add_argument("--links", required=True, help="links JSON (see module docstring)")
    parser.add_argument("--output", help="write result JSON here; omit to print to stdout")
    parser.add_argument(
        "--max-chars", type=int, default=MAX_CHARS_DEFAULT,
        help="max length of the extracted context"
    )
    parser.add_argument(
        "--format", choices=("markdown", "text"), default="markdown",
        help="body link format: markdown [anchor](url) or plain text [ url ]"
    )
    args = parser.parse_args()

    try:
        md = open(args.email, encoding="utf-8").read()
        data = json.load(open(args.links, encoding="utf-8"))
    except OSError as exc:
        print("cannot read input: " + type(exc).__name__, file=sys.stderr)
        return 2
    except ValueError:
        print("links file is not valid JSON", file=sys.stderr)
        return 2

    links = data.get("links", []) if isinstance(data, dict) else data
    if not isinstance(links, list):
        print("input must contain a links array", file=sys.stderr)
        return 2

    with_context, without = 0, 0
    for item in links:
        if args.format == "text":
            key = (item.get("source_url") or item.get("url") or "").strip()
            context = find_context_text(md, key, args.max_chars)
        else:
            url = item.get("url", "")
            anchor = (item.get("anchor_text") or "").strip()
            context = find_context(md, anchor, url, args.max_chars)
        item["context"] = context
        if context:
            with_context += 1
        else:
            without += 1

    result = {"links": links, "stats": {"total": len(links), "with_context": with_context, "without_context": without}}
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
