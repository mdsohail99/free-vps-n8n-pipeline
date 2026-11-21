"""feeds.py — official AI vendor blogs and preprint feeds.

Replaces the Reddit source: reddit.com's .rss endpoints answer 404/429/403 to
datacenter IPs, so it contributed nothing but an error line every run.
"""

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from .relevance import is_ai_relevant

FEEDS = [
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI"),
]

USER_AGENT = "Mozilla/5.0 (compatible; free-vps-n8n-pipeline/1.0)"


class _TextExtract(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []

    def handle_data(self, data):
        self._text.append(data)

    def text(self):
        return " ".join(self._text)


def _strip_html(html: str) -> str:
    parser = _TextExtract()
    parser.feed(html or "")
    return " ".join(parser.text().split())


def _tag(block: str, name: str) -> str:
    match = re.search(rf"<{name}[^>]*>(.*?)</{name}>", block, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1)
    value = re.sub(r"^\s*<!\[CDATA\[|\]\]>\s*$", "", value.strip())
    return _strip_html(value)


def _iso_date(raw: str) -> str:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _fetch_feed(label: str, url: str, limit: int) -> list[dict]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    items = re.findall(r"<item>.*?</item>", raw, re.DOTALL)
    results = []
    for item in items[:limit]:
        title = _tag(item, "title")
        if not title:
            continue
        summary = _tag(item, "description")[:300]
        # Vendor blogs are AI by definition; arXiv cs.AI is filtered so the
        # occasional non-LLM paper does not crowd out the briefing.
        if label.startswith("arXiv") and not is_ai_relevant(title, summary):
            continue
        results.append({
            "title": title,
            "url": _tag(item, "link") or _tag(item, "guid"),
            "source": label,
            "summary": summary,
            "date": _iso_date(_tag(item, "pubDate")),
        })
    return results


def fetch(query: str, limit: int = 6) -> list[dict]:
    results = []
    for label, url in FEEDS:
        try:
            results.extend(_fetch_feed(label, url, limit))
        except Exception as e:
            results.append({
                "title": f"ERROR: {label}",
                "url": "",
                "source": label,
                "summary": str(e),
            })
    return results
