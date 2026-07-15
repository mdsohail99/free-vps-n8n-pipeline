import json
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

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

    results = []
    ql = query.lower()
    for item_id, data in zip(ids, items):
        if data is None:
            continue

        title = data.get("title", "")
        url = data.get("url", f"https://news.ycombinator.com/item?id={item_id}")
        score = data.get("score", 0)
        by = data.get("by", "unknown")

        if ql and not any(w in title.lower() for w in ql.split()):
            continue

        results.append({
            "title": title,
            "url": url,
            "score": score,
            "author": by,
            "source": "HackerNews",
            "summary": f"{score} points by {by}",
        })

    return results
