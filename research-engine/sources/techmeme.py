import re
from html.parser import HTMLParser
from urllib.request import Request, urlopen

TECHMEME_RSS = "https://techmeme.com/feed.xml?format=xml"

class _TextExtract(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []
    def handle_data(self, data):
        self._text.append(data)
    def text(self):
        return " ".join(self._text)

def _strip_html(html: str) -> str:
    p = _TextExtract()
    p.feed(html)
    return p.text()

def _find_links(text: str) -> list[tuple[str, str]]:
    pattern = r'<a\s+[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
    return re.findall(pattern, text, re.IGNORECASE)

def fetch(query: str, limit: int = 40) -> list[dict]:
    req = Request(TECHMEME_RSS, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=15) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    items = re.findall(r"<item>.*?</item>", raw, re.DOTALL)
    results = []
    for item in items[:limit]:
        title_m = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
        desc_m = re.search(r"<description>(.*?)</description>", item, re.DOTALL)
        link_m = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        date_m = re.search(r"<pubDate>(.*?)</pubDate>", item, re.DOTALL)

        title = _strip_html(title_m.group(1)) if title_m else ""
        desc = _strip_html(desc_m.group(1)) if desc_m else ""
        link = link_m.group(1).strip() if link_m else ""
        pub_date = date_m.group(1).strip() if date_m else ""

        ql = query.lower()
        if ql and not any(w in title.lower() or w in desc.lower() for w in ql.split()):
            continue

        results.append({
            "title": title,
            "url": link,
            "source": "Techmeme",
            "summary": desc[:300] if desc else "",
            "date": pub_date,
        })

    return results
