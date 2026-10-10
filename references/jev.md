# Jev Pre-classification (optional enhancement)

Background for SKILL.md Step 5.6. This step is soft-optional: a run without it behaves exactly like a run without annotations.

## When it runs

Only when BOTH hold:

1. `settings.jev_enabled` is `true` in the rules file (default `false`)
2. a TypeSafe API key is configured (`TYPESAFE_API_KEY` env var, or `~/.typesafe-api-key` whose first line is the key, permission 0600)

A configured key alone must never trigger the step: it sends entry text derived from email content (title, URL, introduction) to the TypeSafe API, so "a key exists" and "this run may use it" are separate decisions.

## What it does

`scripts/classify_entries.py` asks two Noul judgments per entry over one request:

- `is_promotional` — the entry promotes the newsletter's own products or channels (Telegram, social media, subscription nudges) instead of editorially recommending external content
- `meaningful_title` — the anchor text is a concrete name usable as a bookmark title (brand / product / proper noun / descriptive phrase), not a placeholder like "click here"

Requests run in a small thread pool (4 workers, per-worker pacing); `--max-entries` (default 100) caps the classified count — capped entries keep null annotations and are counted as `skipped_by_cap`. With `--only-new`, entries whose `status` is not `new` in the check_library.py output are never classified: they will never be saved, so classifying them would waste API calls.

## Reading the annotations

- noul >= 0.9 → "clear promotional, suggest excluding"
- noul <= 0.3 → "clear content"
- in between → unannotated; goes through human review in the preview as usual

Annotations only inform the preview. The confirmation gate is never changed by them, and the step must never be required.

## Exit codes

| Code | Meaning | Handling |
|---|---|---|
| 0 | ok (partial coverage allowed and reported) | continue; report the coverage counts |
| 2 | usage error (missing/invalid input file) | read stderr, fix the input, retry once |
| 3 | no key configured | expected soft skip — report "Jev pre-classification: off (no key)"; behavior identical to a run without the enhancement |
| 1 | every request failed (service down) | skip annotations, keep the full flow; report "unavailable (service error)" — never retry endlessly |

## Calibration

Calibrated 2026-09-20 on real Chinese newsletter entries: 14/14 correct, self-consistency deviation <= 0.04.
