#!/usr/bin/env python3
"""Export the full Raindrop bookmark library to a local JSON file.

Data channel for the third dedup layer (library lookup): the export talks to
the Raindrop MCP gateway over HTTP and writes every page straight to a local
file, so bookmark payloads never pass through the model context. The MCP
pagination path costs thousands of tokens per page; this channel costs none —
the caller only sees a one-line summary.

The access token is resolved in this order (first hit wins; the token is
never printed, logged, or copied anywhere else):
  1. environment variable RAINDROP_TOKEN
  2. --token-file PATH (a file whose first line is just the token)
  3. a "raindrop" server entry with a Bearer Authorization header, found in
     the first matching MCP config among: ~/.workbuddy/mcp.json,
     ~/.cursor/mcp.json, ~/.gemini/settings.json, ~/.claude.json,
     ./.mcp.json (current directory)

Protocol details (verified live 2026-09-18):
  endpoint  POST https://api.raindrop.io/rest/v2/ai/mcp
  transport stateless JSON-RPC (no session id); one request per message
  pages     tools/call find_bookmarks {"limit": 150, "page": n}
            n is 1-based; each page returns {"bookmarks": [...], "total": T}
  stop      accumulated >= total, or a page returns fewer items than asked
  rate      gateway rate limit observed at 120 requests/window (8 pages is safe)

Output shape matches check_library.py's expectation:
  {"bookmarks": [{"bookmark_id": ..., "link": "...", "title": "..."}]}
Only the fields needed for comparison are kept.

Options:
  --output PATH   destination file (default: <system tmpdir>/raindrop-library.json)
  --timeout SECS  per-request timeout (default 30)
  --limit         bookmarks per page, 1-150 (default 150)

Exit codes: 0 ok; 2 config/usage problem (token not found, bad JSON in the
config, unusable output path); 1 network/HTTP/tool failure — each page is
retried once before giving up.
"""

import argparse
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request

ENDPOINT = "https://api.raindrop.io/rest/v2/ai/mcp"
CONFIG_CANDIDATES = (
    "~/.workbuddy/mcp.json",
    "~/.cursor/mcp.json",
    "~/.gemini/settings.json",
    "~/.claude.json",
    "./.mcp.json",
)
REQUEST_ID = 900


class ConfigError(Exception):
    """Config/usage problem -> exit code 2."""


class FetchError(Exception):
    """Network/HTTP/tool failure after retry -> exit code 1."""


def _token_from_config_object(config: object) -> str:
    """Find a raindrop server entry with a Bearer header in an MCP config."""
    servers = {}
    if isinstance(config, dict):
        servers = config.get("mcpServers") or config.get("servers") or {}
    if not isinstance(servers, dict):
        return ""
    raindrop = servers.get("raindrop")
    for name, entry in servers.items():
        if "raindrop" in name.lower():
            raindrop = entry
            break
    if not isinstance(raindrop, dict):
        return ""
    auth = (raindrop.get("headers") or {}).get("Authorization", "")
    if isinstance(auth, str) and auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return ""


def load_token(token_file: str = "") -> str:
    """Resolve the Raindrop token: env var, token file, then MCP configs."""
    env_token = os.environ.get("RAINDROP_TOKEN", "").strip()
    if env_token:
        return env_token
    if token_file:
        try:
            with open(os.path.expanduser(token_file), encoding="utf-8") as fh:
                token = fh.readline().strip()
        except OSError as exc:
            raise ConfigError("cannot read token file: " + type(exc).__name__)
        if not token:
            raise ConfigError("token file is empty")
        return token
    for candidate in CONFIG_CANDIDATES:
        path = os.path.expanduser(candidate)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                config = json.load(fh)
        except (OSError, ValueError):
            continue  # unreadable/invalid candidate: try the next one
        token = _token_from_config_object(config)
        if token:
            return token
    raise ConfigError(
        "no Raindrop token found: set RAINDROP_TOKEN, pass --token-file, "
        "or register a raindrop server entry in one of the MCP configs: "
        + ", ".join(CONFIG_CANDIDATES)
    )


def call_gateway(token: str, arguments: dict, timeout: int) -> dict:
    """One JSON-RPC tools/call against the stateless gateway; retry once."""
    global REQUEST_ID
    REQUEST_ID += 1
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": REQUEST_ID,
        "method": "tools/call",
        "params": {"name": "find_bookmarks", "arguments": arguments},
    }).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    last_error = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                payload = json.load(resp)
            if "error" in payload:
                raise RuntimeError("JSON-RPC error: " + str(payload["error"])[:120])
            result = payload.get("result") or {}
            if result.get("isError"):
                raise RuntimeError("tool error: "
                                   + str(result.get("content", ""))[:120])
            return json.loads(result["content"][0]["text"])
        except (urllib.error.URLError, urllib.error.HTTPError,
                ValueError, OSError, RuntimeError, KeyError,
                json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 1:
                time.sleep(1.5)
    raise FetchError("page call failed after retry: " + type(last_error).__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export the Raindrop library to a local JSON file (payloads stay out of context)"
    )
    parser.add_argument("--output", help="destination JSON file")
    parser.add_argument("--timeout", type=int, default=30, help="per-request timeout seconds")
    parser.add_argument("--limit", type=int, default=150, help="bookmarks per page (1-150)")
    parser.add_argument("--token-file", help="file whose first line is the Raindrop token")
    args = parser.parse_args()

    if not 1 <= args.limit <= 150:
        print("limit must be 1-150", file=sys.stderr)
        return 2
    output_path = args.output or os.path.join(
        tempfile.gettempdir(), "raindrop-library.json"
    )

    try:
        token = load_token(args.token_file)
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    bookmarks = []
    total = None
    page = 1
    requests_used = 0
    while True:
        try:
            inner = call_gateway(
                token, {"limit": args.limit, "page": page}, args.timeout
            )
        except FetchError as exc:
            print(str(exc) + " (page " + str(page) + ")", file=sys.stderr)
            return 1
        requests_used += 1
        items = inner.get("bookmarks") or []
        for item in items:
            link = item.get("link")
            if not link:
                continue  # broken record; library compare relies on link
            bookmarks.append({
                "bookmark_id": item.get("bookmark_id"),
                "link": link,
                "title": item.get("title") or "",
            })
        total = inner.get("total") if isinstance(inner.get("total"), int) else total
        if not items or (total is not None and len(bookmarks) >= total):
            break
        page += 1

    try:
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump({"bookmarks": bookmarks}, fh, ensure_ascii=False)
    except OSError as exc:
        print("cannot write output: " + type(exc).__name__, file=sys.stderr)
        return 2

    print(
        "exported " + str(len(bookmarks)) + " bookmarks (total "
        + str(total) + ") in " + str(requests_used)
        + " gateway request(s) -> " + output_path
        + " (payloads kept out of context)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
