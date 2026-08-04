#!/usr/bin/env python3
"""deals.py — daily AI deals, pricing & launch intelligence scanner.

Scans official sources (changelogs, GitHub releases, RSS/Atom feeds, homepages)
for promo keywords (free credits, discounts, early access, ...) and launch
signals (new models, benchmarks, context windows, agents, IDE integrations).

Designed to be called by n8n via SSH for the AI Daily Briefing workflow:

    python3 /home/ubuntu/research-engine/deals.py --emit=compact \\
        --state-file /home/ubuntu/research-engine/deals_state.json

CLI contract:
    --emit          compact (default) | md | json
    --state-file    path to JSON state dict for day-over-day dedupe (optional)
    --quick         skip slow HTML changelog pages; keep GitHub releases + RSS

Environment:
    GITHUB_TOKEN    optional GitHub Personal Access Token. When set, GitHub API
                    requests (api.github.com ONLY) send `Authorization: Bearer
                    <token>`, raising the unauthenticated rate limit from
                    60 req/hr to 5000 req/hr so model-release announcements are
                    never silently missed. The token is never logged, never
                    written to the state file, and never sent to non-GitHub hosts.

Guarantees:
    * stdlib-only (urllib + xml.etree + json + concurrent.futures), Python 3.12
    * every fetch wrapped in try/except — a failed/empty source never breaks the run
    * always exits 0 and always prints output (even a header + "no items")
    * concurrent fetches (ThreadPoolExecutor) with a ~70s wall-clock cap
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from deals_core import (
    classify,
    dedupe_items,
    github_headers,
    html_to_text,
    load_state,
    make_key,
    merge_state_keys,
    normalize_date,
    parse_feed,
    parse_github_org_repos,
    parse_github_releases,
    save_state,
    truncate,
)
from sources.deals_registry import all_entries

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 10          # seconds per fetch (8-12s window per spec)
RUN_DEADLINE = 70             # wall-clock cap for the whole scan (spec: ~60s target)
SCAN_TEXT_LIMIT = 8000        # chars of visible HTML text scanned per page
QUICK_TYPES = ("github_releases", "github_org_repos", "rss")

# Optional GitHub API token. When set, GitHub API requests (api.github.com only)
# carry `Authorization: Bearer <token>`, raising the unauthenticated rate limit
# from 60 req/hr to 5000 req/hr so model-release announcements are never missed.
# Never logged, never written to state, never sent to non-GitHub hosts.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


# ─────────────────────────────────────────────────────────────────────────────
# Network layer (thin I/O — every call bounded by a hard deadline)
# ─────────────────────────────────────────────────────────────────────────────
def read_url(url, timeout=DEFAULT_TIMEOUT, max_bytes=None, headers=None):
    """Fetch ``url`` with a browser-ish UA and a hard per-fetch deadline.

    ``headers`` is an optional extra-header dict (e.g. a GitHub Bearer token)
    merged on top of the default browser-ish headers — never sent to hosts it
    wasn't explicitly scoped for. Reads in bounded chunks so a trickling server
    can't blow the time budget. Raises on failure; the caller catches and logs
    it as a failed source.
    """
    deadline = time.monotonic() + timeout
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",  # urllib doesn't auto-gunzip
    }
    if headers:
        request_headers.update(headers)
    req = Request(url, headers=request_headers)
    with urlopen(req, timeout=timeout) as resp:
        chunks = []
        total = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"read of {url} exceeded {timeout}s budget")
            if max_bytes is not None and total >= max_bytes:
                break
            chunk = resp.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if max_bytes is not None and total >= max_bytes:
                break
    return b"".join(chunks).decode("utf-8", errors="replace")


def _fetch_html(entry, headers=None):
    """HTML source -> a single candidate (page title + first N chars of text)."""
    raw_html = read_url(
        entry["url"], timeout=entry.get("timeout", DEFAULT_TIMEOUT),
        max_bytes=entry.get("max_bytes"), headers=headers,
    )
    title, text = html_to_text(raw_html)
    scan_text = truncate(f"{title} {text}", SCAN_TEXT_LIMIT)
    return [{
        "title": title or entry["url"],
        "link": entry["url"],
        "date_raw": "",
        "description": scan_text,
    }]


# ─────────────────────────────────────────────────────────────────────────────
# Scanning
# ─────────────────────────────────────────────────────────────────────────────
def _to_item(entry, raw):
    """Turn a raw candidate into a flagged item dict, or None if no signal."""
    title = (raw.get("title") or "").strip()
    if not title:
        return None
    description = raw.get("description") or ""
    promo, launch = classify(title, description)
    keywords = promo + launch
    if not keywords:
        return None
    return {
        "company": entry["company"],
        "title": title,
        "url": raw.get("link") or raw.get("url") or entry["url"],
        "date": normalize_date(raw.get("date_raw")),
        "date_raw": raw.get("date_raw") or "",
        "keywords": keywords,
        "category": entry["category"],
        "source": entry["id"],
        "platform": entry["platform"],
        "priority": entry.get("priority", 2),
        "summary": truncate(description, 400),
        "key": make_key(entry["company"], title),
    }


def scan_source(entry):
    """Fetch + parse + flag one registry entry. Raises on failure."""
    etype = entry["type"]
    timeout = entry.get("timeout", DEFAULT_TIMEOUT)
    # Only api.github.com URLs receive the Bearer token; everything else gets {}.
    extra_headers = github_headers(entry["url"], GITHUB_TOKEN)
    if etype == "github_releases":
        payload = read_url(entry["url"], timeout=timeout,
                           max_bytes=entry.get("max_bytes", 1000000), headers=extra_headers)
        raw_items = parse_github_releases(payload)
    elif etype == "github_org_repos":
        payload = read_url(entry["url"], timeout=timeout,
                           max_bytes=entry.get("max_bytes", 1000000), headers=extra_headers)
        raw_items = parse_github_org_repos(payload)
    elif etype == "rss":
        payload = read_url(entry["url"], timeout=timeout,
                           max_bytes=entry.get("max_bytes", 1000000), headers=extra_headers)
        raw_items = parse_feed(payload)
    elif etype == "html":
        raw_items = _fetch_html(entry, headers=extra_headers)
    else:
        raise ValueError(f"unknown source type: {etype!r}")

    items = []
    for raw in raw_items:
        item = _to_item(entry, raw)
        if item is not None:
            items.append(item)
    return items


def run_scan(entries=None, quick=False, state_file=None, max_workers=10, run_deadline=RUN_DEADLINE):
    """Scan the registry concurrently, dedupe against state, persist state.

    Never raises: per-source failures are recorded and the run always returns a
    result dict (exit code 0 is guaranteed at the CLI layer).
    """
    started = time.monotonic()
    scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if entries is None:
        entries = all_entries()
    if quick:
        entries = [e for e in entries if e["type"] in QUICK_TYPES]

    state = load_state(state_file) if state_file else {"last_run": None, "keys": []}
    known = len(state.get("keys", []))

    items, ok_ids, failed = [], [], {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_source, e): e for e in entries}
        try:
            for future in as_completed(futures, timeout=run_deadline):
                entry = futures[future]
                try:
                    got = future.result()
                    ok_ids.append(entry["id"])
                    items.extend(got)
                except Exception as exc:  # noqa: BLE001 — degrade, never crash
                    failed[entry["id"]] = _exc_message(exc)
        except TimeoutError:
            for future, entry in futures.items():
                if not future.done():
                    failed[entry["id"]] = "run deadline exceeded"

    # Newest first; Unknown dates sink to the bottom.
    items.sort(key=lambda it: (it["date"] == "Unknown", it["date"]), reverse=True)

    new_items, merged_keys = dedupe_items(items, state.get("keys", []))
    state["keys"] = merged_keys
    state["last_run"] = scanned_at
    if state_file:
        try:
            save_state(state_file, state)
        except Exception:  # noqa: BLE001 — a state-write problem must not crash the run
            failed["_state_write"] = "state file could not be written"

    return {
        "scanned_at": scanned_at,
        "entries": len(entries),
        "ok_ids": ok_ids,
        "failed": failed,
        "items": items,
        "new_items": new_items,
        "known": known,
        "state_total": len(merged_keys),
        "elapsed_s": round(time.monotonic() - started, 1),
    }


def _exc_message(exc):
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", exc)
        return f"network error: {reason}"[:120]
    return f"{type(exc).__name__}: {str(exc)[:120]}"


# ─────────────────────────────────────────────────────────────────────────────
# Output formatting
# ─────────────────────────────────────────────────────────────────────────────
def _bullet_compact(item):
    kw = ", ".join(item["keywords"])
    return (f"- **[{item['company']}]** — [matched: {kw}] — "
            f"**{item['title']}** — {item['url']} — {item['date']}")


def _bullet_md(item):
    kw = ", ".join(item["keywords"])
    return (f"- **[{item['company']}]** — [matched: {kw}] — "
            f"[{item['title']}]({item['url']}) — {item['date']}")


def _summary_lines(result):
    lines = []
    failed_txt = ""
    if result["failed"]:
        failed_txt = f" (failed: {', '.join(sorted(result['failed']))})"
    lines.append(f"- Sources OK: {len(result['ok_ids'])}/{result['entries']}{failed_txt}")
    lines.append(
        f"- Items new since last run: {len(result['new_items'])} "
        f"(state file: {result['known']} known, {result['state_total']} total)"
    )
    return lines


def format_compact(result):
    lines = [
        "## 🔥 AI Deals, Pricing & Launch Intelligence",
        f"> Scanned {result['scanned_at']} — {result['entries']} official sources — "
        f"{len(result['items'])} items flagged",
        "",
        "### New This Run (not reported in previous runs)",
    ]
    if result["new_items"]:
        lines.extend(_bullet_compact(it) for it in result["new_items"])
    else:
        lines.append("- No new promotion or launch signals detected in official sources since the last run.")
    lines.append("")
    lines.append("### Signal Summary")
    lines.extend(_summary_lines(result))
    return "\n".join(lines)


def format_md(result):
    lines = [
        "## 🔥 AI Deals, Pricing & Launch Intelligence",
        f"> Scanned {result['scanned_at']} — {result['entries']} official sources — "
        f"{len(result['items'])} items flagged",
        "",
        "### New This Run (not reported in previous runs)",
    ]
    if result["new_items"]:
        lines.extend(_bullet_md(it) for it in result["new_items"])
    else:
        lines.append("- No new promotion or launch signals detected in official sources since the last run.")
    lines.append("")
    lines.append("### Signal Summary")
    lines.extend(_summary_lines(result))
    return "\n".join(lines)


_JSON_ITEM_FIELDS = ("company", "title", "url", "date", "keywords", "category", "source")


def format_json(result):
    payload = {
        "scanned_at": result["scanned_at"],
        "sources_ok": len(result["ok_ids"]),
        "sources_failed": sorted(result["failed"]),
        "items": [
            {k: item[k] for k in _JSON_ITEM_FIELDS}
            for item in result["new_items"]
        ],
        "new_count": len(result["new_items"]),
        "state_total": result["state_total"],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _format_fallback(exc):
    """Minimal output used only if the scan itself explodes — still exit 0."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        "## 🔥 AI Deals, Pricing & Launch Intelligence\n"
        f"> Scanned {ts} — 0 official sources — 0 items flagged\n"
        "\n"
        "### New This Run (not reported in previous runs)\n"
        "- No new promotion or launch signals detected in official sources since the last run.\n"
        "\n"
        "### Signal Summary\n"
        f"- Sources OK: 0/0 (unexpected error: {exc})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="deals.py",
        description="AI deals, pricing & launch intelligence scanner (stdlib-only).",
    )
    parser.add_argument(
        "--emit", choices=["compact", "md", "json"], default="compact",
        help="output format (default: compact)",
    )
    parser.add_argument(
        "--state-file", default=None, metavar="PATH",
        help="JSON state file for day-over-day dedupe; created if missing",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="skip slow HTML changelog pages; keep GitHub releases + RSS",
    )
    args = parser.parse_args(argv)

    # Ensure UTF-8 stdout so emoji/unicode never crash the print (Windows console).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        result = run_scan(quick=args.quick, state_file=args.state_file)
        if args.emit == "json":
            output = format_json(result)
        elif args.emit == "md":
            output = format_md(result)
        else:
            output = format_compact(result)
        print(output)
    except Exception as exc:  # noqa: BLE001 — ALWAYS exit 0, always print output
        print(_format_fallback(exc))

    sys.exit(0)


if __name__ == "__main__":
    main()
