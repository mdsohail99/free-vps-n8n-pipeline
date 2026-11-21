from . import hackernews, techmeme, feeds

SOURCES = {
    "hn": hackernews,
    "hackernews": hackernews,
    "techmeme": techmeme,
    "feeds": feeds,
}

SOURCE_NAMES = {
    "hn": "HackerNews",
    "techmeme": "Techmeme",
    "feeds": "Official AI Blogs & Preprints",
}

def fetch_all(query: str, enabled: list[str] | None = None) -> dict[str, list[dict]]:
    if enabled is None:
        enabled = ["hn", "techmeme", "feeds"]
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
