#!/usr/bin/env python3
"""Read-only environment check for newsletter-link-harvester.

Checks local MCP registration (gmail, raindrop) across the common MCP
config locations used by different agent clients, Python version, and the
writability of the state directory parent. Never reads credential values,
never writes files, never touches the network.

Exit codes: 0 check completed (see JSON status), 1 internal error.
Statuses: ready | partial | needs_setup | unavailable
"""

import argparse
import json
import os
import sys
from pathlib import Path

MCP_CONFIG_CANDIDATES = (
    "~/.workbuddy/mcp.json",
    "~/.cursor/mcp.json",
    "~/.gemini/settings.json",
    "~/.claude.json",
    "./.mcp.json",
)
STATE_DIR = Path.home() / ".config" / "newsletter-link-harvester"
MIN_PYTHON = (3, 10)

GMAIL_HINTS = ("gmail",)
RAINDROP_HINTS = ("raindrop",)


def _server_kind(entry: dict) -> str:
    if "command" in entry:
        return "local"
    if "url" in entry:
        return "remote"
    return "unknown"


def _match_server(servers: dict, hints) -> dict:
    for name, entry in servers.items():
        lowered = name.lower()
        raw = json.dumps(entry, ensure_ascii=False).lower()
        if any(h in lowered or h in raw for h in hints):
            return {"name": name, "kind": _server_kind(entry), "configured": True}
    return {"name": None, "kind": None, "configured": False}


def check_python() -> dict:
    ok = sys.version_info[:2] >= MIN_PYTHON
    return {
        "id": "python-runtime",
        "ok": ok,
        "detail": "current interpreter "
        + ".".join(str(p) for p in sys.version_info[:3]),
        "recover": "use Python 3.10 or newer" if not ok else "",
    }


def check_mcp() -> dict:
    result = {
        "id": "mcp-registration",
        "gmail": {"configured": False, "name": None, "kind": None},
        "raindrop": {"configured": False, "name": None, "kind": None},
        "raindrop_token_env": bool(os.environ.get("RAINDROP_TOKEN", "").strip()),
        "ok": False,
        "detail": "",
        "recover": "",
    }
    configs = {}
    for candidate in MCP_CONFIG_CANDIDATES:
        path = Path(os.path.expanduser(candidate))
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # unreadable candidate: try the next one
        servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
        if isinstance(servers, dict):
            configs[path] = servers
    if not configs:
        result["detail"] = "no readable MCP config found (searched: " \
            + ", ".join(MCP_CONFIG_CANDIDATES) + ")"
        result["recover"] = ("register gmail and raindrop servers in one of the "
                             "searched configs (or set RAINDROP_TOKEN for the "
                             "library-export channel); see references/setup-guide.md")
        return result
    for path, servers in configs.items():
        g = _match_server(servers, GMAIL_HINTS)
        r = _match_server(servers, RAINDROP_HINTS)
        if g["configured"] and not result["gmail"]["configured"]:
            result["gmail"] = dict(g, config=str(path))
        if r["configured"] and not result["raindrop"]["configured"]:
            result["raindrop"] = dict(r, config=str(path))
    result["ok"] = result["gmail"]["configured"] and (
        result["raindrop"]["configured"] or result["raindrop_token_env"]
    )
    if not result["ok"]:
        missing = []
        if not result["gmail"]["configured"]:
            missing.append("gmail")
        if not result["raindrop"]["configured"] and not result["raindrop_token_env"]:
            missing.append("raindrop")
        result["detail"] = "missing MCP entries: " + ", ".join(missing)
        result["recover"] = "follow references/setup-guide.md for the missing item"
    else:
        result["detail"] = "gmail and raindrop entries found" \
            + (" (raindrop export also covered by RAINDROP_TOKEN)"
               if result["raindrop_token_env"] else "")
    return result


def check_state_dir() -> dict:
    parent = STATE_DIR.parent
    target = "~/.config"
    if not parent.exists():
        parent = Path.home()
        target = "home directory"
    writable = os.access(parent, os.W_OK)
    return {
        "id": "state-directory",
        "ok": writable,
        "detail": "state parent " + target + (" writable" if writable else " not writable"),
        "recover": "check folder permissions for " + str(parent) if not writable else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only pre-run environment check")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON only")
    args = parser.parse_args()

    checks = [check_python(), check_mcp(), check_state_dir()]
    mcp = checks[1]
    if not mcp["ok"] and mcp["detail"].startswith("mcp.json unreadable"):
        overall = "unavailable"
    elif all(c["ok"] for c in checks):
        overall = "ready"
    elif not mcp["gmail"]["configured"] or not mcp["raindrop"]["configured"]:
        overall = "needs_setup"
    else:
        overall = "partial"

    payload = {
        "overall": overall,
        "note": "configured only means registered in a scanned MCP config; verify real tool "
        "availability with a minimal read-only probe in the session",
        "checks": checks,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    lines = ["Overall: " + overall, ""]
    for check in checks:
        mark = "PASS" if check["ok"] else "FAIL"
        lines.append("[" + mark + "] " + check["id"] + " - " + check["detail"])
        if not check["ok"] and check.get("recover"):
            lines.append("       recover: " + check["recover"])
    if mcp["gmail"]["configured"]:
        lines.append(
            "gmail server entry: "
            + str(mcp["gmail"]["name"])
            + " ("
            + str(mcp["gmail"]["kind"])
            + ")"
        )
    if mcp["raindrop"]["configured"]:
        lines.append(
            "raindrop server entry: "
            + str(mcp["raindrop"]["name"])
            + " ("
            + str(mcp["raindrop"]["kind"])
            + ")"
        )
    lines.append("")
    lines.append(payload["note"])
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
