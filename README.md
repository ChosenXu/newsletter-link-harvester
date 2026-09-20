# Newsletter Link Harvester

English | [简体中文](README.zh-CN.md)

An [Agent Skills](https://agentskills.io)-compatible skill that **harvests links from newsletter emails and files them into a [Raindrop.io](https://raindrop.io/) library — with the author's own introduction attached to every link**. Works with Claude Code, Codex CLI, Gemini CLI, GitHub Copilot, Cursor, and WorkBuddy.

You read a design/tech newsletter once a week; the good links die inside your mailbox. This skill turns each issue into a permanent, searchable bookmark set: every link lands in a per-sender sub-collection, its note carries `via: <newsletter> · <date>` plus a one-sentence summary of *why the author recommended it*.

## What it does

1. **Filter** — searches Gmail by a sender whitelist (primary) and optional subject keywords (secondary), within a look-back window (default 7 days). Explicitly naming an older issue extends the window on demand.
2. **Parse** — two proven channels: Markdown direct links (Quail-style) and plain-text redirect wrappers (SubStack-style `[ url ]` tokens, resolved to their final destinations before anything is saved).
3. **Context** — extracts each link's editorial context: the author's introduction or recommendation, taken from the sentence (or adjacent paragraph) that contains the link. Saved links never lose their "why".
4. **Dedup (3 layers)** — in-batch (URL normalization: www / utm / trailing slash / fragment / case), cross-run (a local state file of processed email IDs), and against your whole Raindrop library.
5. **Confirm → Save** — a full preview with target sub-collection naming; nothing is written without your explicit approval. Bookmarks are batch-created with `via:` + context notes. Promotional entries (self-promotion, social channels, unsubscribe) are flagged and excluded by default.

## Highlights

1. **Zero-context library compare** — the whole Raindrop library is paged straight into a local file over HTTP (9 requests for a 1,300-bookmark library); bookmark payloads never pass through the model conversation. This keeps token cost near zero no matter how large your library grows.
2. **Platform-neutral by design** — the Raindrop token resolves from `RAINDROP_TOKEN`, a `--token-file`, or the first matching MCP config (WorkBuddy / Cursor / Gemini / Claude / project `.mcp.json`); state lives in `~/.config/newsletter-link-harvester/` (prunable with a companion script).
3. **Safety first** — Gmail access is requested read-only (`gmail.readonly` only: search + read, never send/delete/modify — verified against the live tool list); nothing is written without a confirmed preview; emails are never touched.
4. **Faithful notes** — the `via:` line format never changes; the second line is the author's own words. Where two links share one sentence in the original, both bookmarks faithfully carry it.
5. **Trust mode (optional)** — for already-mapped senders, the per-link preview can shrink to a short summary; the confirmation gate before any write is never removed.
6. **Optional Jev pre-classification** — with a TypeSafe API key configured locally, entries are pre-classified before the preview ("clear promotional" / "clear content" Noul judgments, calibrated on real Chinese newsletter entries); without a key the skill behaves identically. Annotations only inform the preview — the confirmation gate is never bypassed.

## Install

This skill follows the open [Agent Skills](https://agentskills.io) standard (`SKILL.md` + `scripts/` + `references/`). Clone this repository into your agent's skills directory:

| Agent | User-level directory | Project-level directory |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| Codex CLI | `~/.agents/skills/` | `.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| GitHub Copilot | `~/.copilot/skills/` | `.github/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` | — |

Tip: `~/.agents/skills/` is the cross-agent directory — Codex CLI, Gemini CLI, GitHub Copilot, and Cursor read it natively, and Claude Code scans it as a fallback too. One install, discovered by multiple agents.

```bash
git clone https://github.com/ChosenXu/newsletter-link-harvester.git \
  ~/.agents/skills/newsletter-link-harvester
```

Or copy the folder manually into any of the directories above.

## Prerequisites

- **Gmail (read-only MCP)** — the email channel. Full step-by-step setup (Google Cloud project, Gmail API, OAuth consent screen, desktop client, one-time browser consent) is in [`references/setup-guide.md`](references/setup-guide.md) (中文) / [`references/setup-guide.en.md`](references/setup-guide.en.md) (English). Request scope `https://www.googleapis.com/auth/gmail.readonly` only — this skill never sends, deletes, or modifies email. Any MCP client exposing Gmail search/read tools works; a local stdio server such as `@klodr/gmail-mcp` is verified working.
- **Raindrop.io** — the destination library. Either register a Raindrop MCP server (official endpoint `https://api.raindrop.io/rest/v2/ai/mcp`) in your agent's MCP config, or just provide an API token via `RAINDROP_TOKEN` / `--token-file` for the library-export channel. Test tokens: [app.raindrop.io/settings/integrations](https://app.raindrop.io/settings/integrations) → For Developers. Never commit tokens anywhere.
- **Python 3.10+** for the helper scripts (stdlib only; no pip installs).
- Run `python3 scripts/check_environment.py` for a read-only readiness check.

## Configuration

Fill `assets/newsletter-rules.json` (a template with `example@newsletter.com` is included):

```json
{
  "senders": ["digest@example-weekly.com"],
  "keywords": [],
  "sender_collection_map": {
    "digest@example-weekly.com": "Example Weekly"
  },
  "settings": {
    "parent_collection": "Newsletter",
    "days_back": 7,
    "max_emails": 20,
    "trust_mode": false
  }
}
```

The skill refuses to run against an unconfigured template — no accidental whole-mailbox scans.

## Usage

Mention your newsletters with an intent like "process my newsletter" / "处理一下我的 newsletter" and the skill drives the full flow (filter → parse → dedup → preview → your confirmation → save → report). You can also name a specific issue to backfill beyond the look-back window ("把 Dine #245 收了"). The execution report states, per run: matched emails, extraction counts, per-layer dedup results, library-export request count, saved/failed, and editorial-context coverage.

## Structure

```
SKILL.md                        # skill definition & workflow
assets/newsletter-rules.json    # sender whitelist & sub-collection mapping (fill this in)
references/setup-guide.md       # Gmail + Raindrop setup, 中文
references/setup-guide.en.md    # setup guide, English
scripts/check_environment.py    # read-only readiness check (multi-config scan)
scripts/dedupe_links.py         # normalization + in-batch dedup
scripts/extract_context.py      # per-link editorial context (Markdown & plain-text modes)
scripts/classify_entries.py     # optional Jev pre-classification (soft dependency)
scripts/fetch_library.py        # zero-context full-library export (token chain)
scripts/check_library.py        # offline library compare (kept/links input)
scripts/prune_state.py          # cross-run state housekeeping (age/cap/dry-run)
```

## Safety

- **Gmail is read-only by construction** — the required scope is `gmail.readonly`; emails are searched and read, never modified, moved, or deleted.
- **No write without a confirmed preview** — sub-collection names, entry lists, and excluded promotional items are all shown first.
- **Tokens stay local** — never printed, logged, or copied into any file this skill writes.
- **State is inspectable** — the cross-run dedup file is plain JSON in `~/.config/newsletter-link-harvester/`; `prune_state.py --dry-run` previews any cleanup.

## Known limitations

- A Google OAuth app in "testing" status expires consent every 7 days (re-running one command re-authorizes); publishing the app to lift this requires a verified domain.
- SubStack-style redirect unwrapping needs network access at run time; a failed resolution is retried once, then saved as-is and flagged in the report.
- When an author puts two links in one sentence, both bookmarks share that sentence as context — faithful to the source, not a bug.

## License

[MIT](LICENSE)
