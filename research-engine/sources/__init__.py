from . import hackernews, techmeme, reddit, web

SOURCES = {
    "hn": hackernews,
    "hackernews": hackernews,
    "techmeme": techmeme,
    "reddit": reddit,
    "web": web,
}

SOURCE_NAMES = {
    "hn": "HackerNews",
    "techmeme": "Techmeme",
    "reddit": "Reddit",
    "web": "Web Fetch",
}

def fetch_all(query: str, enabled: list[str] | None = None) -> dict[str, list[dict]]:
    if enabled is None:
        enabled = ["hn", "techmeme", "reddit"]
    results = {}
    for name in enabled:
        mod = SOURCES.get(name)
        if mod is None:
            continue
        try:
            items = mod.fetch(query)
            results[name] = items
        except Exception as e:
            results[name] = [{"title": f"ERROR fetching {name}", "url": "", "summary": str(e)}]
    return results
