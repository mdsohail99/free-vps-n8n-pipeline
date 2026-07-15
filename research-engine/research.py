#!/usr/bin/env python3
"""research.py — lightweight research engine for AI news gathering.

Fetches from public sources (HackerNews, Techmeme, Reddit) with no API keys
required. Designed to be called by n8n via SSH for the AI Daily Briefing workflow.

Usage:
    python3 research.py "AI LLM models news" --emit=compact --quick
    python3 research.py "OpenAI" --sources=hn,reddit
    python3 research.py --list-sources
"""

import argparse
import sys
from datetime import datetime, timezone
from sources import fetch_all, SOURCE_NAMES


def format_compact(results: dict[str, list[dict]]) -> str:
    lines = []
    lines.append(f"# Research Results — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    total = sum(len(items) for items in results.values())
    if total == 0:
        lines.append("No results found matching your query.")
        lines.append("")
        return "\n".join(lines)

    for source_name, items in results.items():
        if not items:
            continue
        display = SOURCE_NAMES.get(source_name, source_name)
        lines.append(f"## {display}")
        for item in items:
            title = item.get("title", "Untitled")
            url = item.get("url", "")
            summary = item.get("summary", "")
            score = item.get("score")
            author = item.get("author", "")
            date = item.get("date", "")
            parts = []
            parts.append(f"  - **{title}**")
            if url:
                parts.append(f"    URL: {url}")
            if summary:
                clean = summary.replace("\n", " ").strip()[:200]
                parts.append(f"    {clean}")
            meta = []
            if score is not None:
                meta.append(f"score: {score}")
            if author:
                meta.append(f"by: {author}")
            if date:
                meta.append(date)
            if meta:
                parts.append(f"    ({'; '.join(meta)})")
            lines.append("\n".join(parts))
        lines.append("")

    return "\n".join(lines)


def format_json(results: dict[str, list[dict]]) -> str:
    import json
    return json.dumps(results, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="AI research engine")
    parser.add_argument("query", nargs="?", default="", help="Search query")
    parser.add_argument("--emit", choices=["compact", "json", "md"], default="compact",
                        help="Output format")
    parser.add_argument("--quick", action="store_true",
                        help="Skip slower sources (web fetches)")
    parser.add_argument("--sources", default="hn,techmeme,reddit",
                        help="Comma-separated sources: hn,techmeme,reddit,web")
    parser.add_argument("--list-sources", action="store_true",
                        help="List available sources and exit")

    args = parser.parse_args()

    if args.list_sources:
        print("Available sources:")
        for key, name in SOURCE_NAMES.items():
            print(f"  {key}: {name}")
        sys.exit(0)

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    if args.quick:
        sources = [s for s in sources if s != "web"]

    results = fetch_all(args.query, enabled=sources)

    if args.emit == "json":
        print(format_json(results))
    else:
        print(format_compact(results))


if __name__ == "__main__":
    main()
