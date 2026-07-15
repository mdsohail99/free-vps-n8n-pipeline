import re
from urllib.request import Request, urlopen

def fetch_page(url: str, timeout: int = 15) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return raw

def fetch(query: str) -> list[dict]:
    if not query.startswith("http://") and not query.startswith("https://"):
        return [{"title": "web source needs a URL, not a query", "url": "", "source": "Web", "summary": "Pass a URL or use --source hn,reddit,techmeme instead"}]
    try:
        text = fetch_page(query)
        m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        title = m.group(1).strip() if m else "Fetched page"
        clean = re.sub(r"<[^>]+>", "", text)
        snippet = " ".join(clean.split())[:500].strip()
        return [{"title": title, "url": query, "source": "Web", "summary": snippet}]
    except Exception as e:
        return [{"title": f"ERROR fetching {query}", "url": query, "source": "Web", "summary": str(e)}]
