import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from .relevance import is_ai_relevant

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"


def _fetch_item(item_id):
    try:
        req = Request(HN_ITEM.format(item_id))
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch(query: str, limit: int = 40) -> list[dict]:
    req = Request(HN_TOP)
    with urlopen(req, timeout=10) as resp:
        ids = json.loads(resp.read().decode("utf-8"))[:limit]

    # Fetch item details concurrently instead of one at a time — same data,
    # same per-request timeout and error handling, just not serialized.
    with ThreadPoolExecutor(max_workers=min(8, len(ids) or 1)) as executor:
        items = list(executor.map(_fetch_item, ids))

    # Word boundaries: the old substring test matched "Nails" and "Airbus"
    # for the query word "ai".
    q_words = re.findall(r"[a-z0-9.]+", query.lower())
    query_is_ai = is_ai_relevant(query)

    results = []
    for item_id, data in zip(ids, items):
        if data is None:
            continue

        title = data.get("title", "")
        url = data.get("url", f"https://news.ycombinator.com/item?id={item_id}")
        score = data.get("score", 0)
        by = data.get("by", "unknown")
        posted = data.get("time")

        if q_words and not any(
            re.search(rf"\b{re.escape(w)}\b", title.lower()) for w in q_words
        ):
            continue
        if query_is_ai and not is_ai_relevant(title):
            continue

        results.append({
            "title": title,
            "url": url,
            "score": score,
            "author": by,
            "source": "HackerNews",
            "summary": f"{score} points by {by}",
            # Date lets the report apply its 14-day freshness gate; HN reposts
            # of old posts were otherwise undated and always included.
            "date": (
                datetime.fromtimestamp(posted, timezone.utc).strftime("%Y-%m-%d")
                if posted else ""
            ),
        })

    return results
