# Fetch Instruction — Collect Launch Comments from a Real Browser

You are the **fetch stage** of the Launch Intelligence pipeline. Your only job is to read a launch's post URLs, open each one in a **real, logged-in browser**, extract every visible comment, and write a single JSON array to disk. This stage is **fetch-only**: you never create accounts, never post, never comment, never like, and never follow. You only read.

## Before you start

1. Confirm Node.js is available: `node --version`.
2. Confirm the launch directory exists: `runtime/launches/<launch-id>/`.
3. Confirm `runtime/launches/<launch-id>/launch_config.json` exists. It is a JSON array of launch posts:
   ```json
   [
     {
       "id": "post_1",
       "platform": "twitter",
       "url": "https://x.com/username/status/1234567890",
       "title": "Initial tweet sharing the launch",
       "published_at": "2026-07-15"
     }
   ]
   ```
4. You will use a **Browser tab you are already logged into** (via Chrome DevTools, a browser MCP, or your agent's browser tool). Do not log in, do not attempt alternate accounts, and do not accept "manage anyway" prompts.

Wherever `<launch-id>` appears below, substitute the actual folder name.

## Step 1 — Read the launch config

Read `runtime/launches/<launch-id>/launch_config.json`. You will process **every** entry in the array, in order. If the array is empty, report that and stop. Keep a working list of `(id, platform, url)` triples, and track progress — e.g. `[1/3] twitter post_1 → https://x.com/...`.

## Step 2 — Open each URL in the real browser

For each entry:

1. Open the entry's `url` in a new browser tab.
2. Wait for the page to render. If you see a **login wall** (a login prompt, an interstitial, or a "sign in to continue" that you cannot dismiss with the logged-in session), record it in your log as `skipped: login wall` for that post and move on. Do **not** create an account, do **not** attempt credentials.
3. If the page loads, proceed to Step 3 on this tab.

## Step 3 — Scroll to load all comments

Comment threads load lazily. On the open tab:

1. Scroll to the comments section. On platforms that collapse comments (Reddit, Hacker News, X), expand any "view more comments", "load more", "show replies", "more replies" controls you find.
2. Scroll to the bottom of the comment area, then scroll back and forth until both of these are true:
   - the page reached its natural bottom and the scroll stopped growing the comment list, **and**
   - a second full scroll pass yields **zero new comments** (the DOM comment count no longer changes).
3. Only then extract comments.

## Step 4 — Extract each comment

For each comment you find, capture **exactly**:

- `id` — a unique, stable string you generate for this comment (e.g. `<post_id>_c001`, `<post_id>_c002`). The same comment must always get the same `id` within this run, and a `c` prefix for "comment".
- `author` — the display name or handle.
- `text` — the full comment body, exactly as written (clean up only line-break artifacts, never reword).
- `url` — the **permalink** of this comment (a deep link to the specific comment, not the post). If a platform exposes no stable per-comment link, fall back to the post URL and set `fallback_url: true` for that entry.
- `platform` — lowercase slug: `twitter` / `linkedin` / `reddit` / `hackernews` / `devto` / `medium` / `other`.
- `post_id` — the `id` of the launch post this comment belongs to (from `launch_config.json`).
- `collected_at` — current timestamp in ISO 8601 UTC (e.g. `2026-07-15T10:15:00Z`).

Do not invent, guess, or "improve" any field. Do not summarize comment text — the analysis stage needs the verbatim text.

## Step 5 — Write raw_comments.json

When every URL is processed, write a **single JSON array** to:

```text
runtime/launches/<launch-id>/raw_comments.json
```

```json
[
  {
    "id": "post_1_c_01",
    "author": "display name",
    "text": "full verbatim comment body",
    "url": "https://x.com/.../comment/permalink",
    "platform": "twitter",
    "post_id": "post_1",
    "collected_at": "2026-07-15T10:15:00Z"
  }
]
```

Rules for the file:

- It is a **bare JSON array** — no wrapping object, no comments, no markdown fences around it.
- It must contain **only** comments you actually saw rendered in the browser we see.
- Empty comment threads → still write the file as `[]`.
- If the file already exists, **overwrite** it only after confirming the previous run completed; otherwise report the conflict and do not lose existing data.

Also print a short progress report at the end: total posts found, total comments captured, per-platform counts, and any URLs skipped (`skipped: <url> — reason`). Do not drop skipped URLs silently.

## Step 6 — Normalize and dedupe

The raw comments are not yet the analysis input. Run the pipeline's ingest step so duplicates are removed against the post ledger:

```bash
node workflows/launch-intelligence/scripts/comment_manager.mjs ingest runtime/launches/<launch-id>
```

The exact flag names and positional arguments are defined by the script — if unsure, run `node workflows/launch-intelligence/scripts/comment_manager.mjs --help` first. The ingest command reads `raw_comments.json`, deduplicates against `history.json`, and writes `comments.json`. Confirm `comments.json` was written before finishing. If the script reports errors, correct the input and rerun; do not manually edit `comments.json`.

## Hard rules

- **Never** create an account. Do **not** plant demo comments.
- **Never** post, reply, like, or follow. This stage is fetch-only.
- **Never** run any script that posts on your behalf.
- **Never** fabricate comments, authors, or permalinks. If content cannot be read, report it as skipped/unsupported — do not roll it up.
- **Never** modify `history.json` directly.