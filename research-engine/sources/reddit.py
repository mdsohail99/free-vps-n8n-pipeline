from html.parser import HTMLParser
from time import sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

REDDITS = [
    ("r/artificial", "r/artificial"),
    ("r/artificialintelligence", "r/artificialintelligence"),
    ("r/LocalLLaMA", "r/LocalLLaMA"),
    ("r/MachineLearning", "r/MachineLearning"),
]

ATOM = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "free-vps-n8n-pipeline/1.0 (public RSS reader)"


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


def _child_text(entry, name: str) -> str:
    child = entry.find(f"{ATOM}{name}")
    return child.text.strip() if child is not None and child.text else ""


def _entry_url(entry) -> str:
    for link in entry.findall(f"{ATOM}link"):
        href = link.attrib.get("href", "")
        rel = link.attrib.get("rel", "alternate")
        if href and rel == "alternate":
            return href
    return ""


def _entry_author(entry) -> str:
    author = entry.find(f"{ATOM}author")
    if author is None:
        return ""
    name = author.find(f"{ATOM}name")
    return name.text.strip() if name is not None and name.text else ""


def fetch_reddit(sub: str, label: str, query: str, limit: int = 8) -> list[dict]:
    url = f"https://www.reddit.com/{sub}/hot/.rss?limit={limit}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        try:
            with urlopen(req, timeout=15) as resp:
                raw = resp.read()
        except HTTPError as e:
            if e.code != 429:
                raise
            sleep(3)
            try:
                with urlopen(req, timeout=15) as resp:
                    raw = resp.read()
            except HTTPError as retry_err:
                if retry_err.code == 429:
                    return []
                raise
    except Exception as e:
        return [{"title": f"ERROR: {label}", "url": "", "source": "Reddit", "summary": str(e)}]

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return [{"title": f"ERROR: {label}", "url": "", "source": "Reddit", "summary": f"RSS parse failed: {e}"}]

    results = []
    q_words = [w for w in query.lower().split() if w]
    for entry in root.findall(f"{ATOM}entry"):
        title = _child_text(entry, "title")
        summary = _strip_html(_child_text(entry, "content"))[:200]
        haystack = f"{title} {summary}".lower()
        if q_words and not any(word in haystack for word in q_words):
            continue
        results.append({
            "title": title,
            "url": _entry_url(entry),
            "author": _entry_author(entry),
            "source": f"Reddit/{label}",
            "summary": summary,
            "date": _child_text(entry, "updated"),
        })
    return results


def fetch(query: str) -> list[dict]:
    all_results = []
    for index, (sub, label) in enumerate(REDDITS):
        if index:
            sleep(1)
        all_results.extend(fetch_reddit(sub, label, query))
    return all_results
