"""deals_core.py — pure, stdlib-only logic for the deal-intelligence scanner.

Everything in this module is deliberately side-effect free (or tiny thin-I/O)
so it can be unit-tested without a network connection:

* keyword matching (promo + launch-signal categories)
* HTML / RSS / Atom / GitHub-releases parsing
* date normalization
* dedupe-key generation and state-file merge/cap logic

The network fetch layer lives in deals.py; this module never touches urllib.
"""

import hashlib
import html as _html
import json
import os
import re
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# ─────────────────────────────────────────────────────────────────────────────
# Detection keywords — EXACT list from the spec (case-insensitive substring match)
# ─────────────────────────────────────────────────────────────────────────────
PROMO_KEYWORDS = [
    "90% off", "95% off", "98% off", "99% off", "launch promotion", "limited time",
    "free credits", "credits multiplier", "token multiplier", "bonus credits",
    "preview pricing", "beta pricing", "early access", "free trial", "extended trial",
    "student", "startup", "enterprise credits", "discount", "coupon", "promo",
    "resource pack", "price drop", "price reduction", "usage multiplier",
    "off peak", "night pricing", "happy hours", "weekend pricing",
]

# Launch-signal detection: non-promo, high-value intelligence. These fire on the
# title (and summary) of an item, e.g. "Introducing Claude 4", "SWE-bench Pro",
# "1M token context window", "Codex Agent", "VS Code integration".
_LAUNCH_PATTERNS = [
    ("new-model", re.compile(
        r"\b(?:new|introduc\w*|unveil\w*|launch\w*|releas\w*|debut\w*|present\w*|announc\w*)\b.{0,40}\bmodel\b",
        re.I)),
    ("new-model", re.compile(
        r"\b(?:frontier|reasoning|preview|foundation)\s+model\b", re.I)),
    ("new-benchmark", re.compile(
        r"\b(?:new|introduc\w*|releas\w*|launch\w*|unveil\w*|debut\w*)\b.{0,40}\bbenchmark\b",
        re.I)),
    ("new-context-window", re.compile(
        r"\b(?:new|extended|larger|bigger|expanded|longer|1m|2m|4m|10m)\b.{0,25}\bcontext\s+(?:window|length)\b",
        re.I)),
    ("new-context-window", re.compile(
        r"\bcontext\s+(?:window|length)\b.{0,25}\b(?:new|extended|expanded|larger)\b",
        re.I)),
    ("new-agent-product", re.compile(
        r"\b(?:new|introduc\w*|unveil\w*|launch\w*|releas\w*|debut\w*)\b.{0,40}\bagent\b",
        re.I)),
    ("new-agent-product", re.compile(
        r"\b(?:coding|code|cli)\s+agent\b", re.I)),
    ("new-ide-integration", re.compile(
        r"\b(?:new\s+)?(?:ide|vscode|vs\s*code|visual\s+studio(?:\s+code)?|jetbrains|intellij|pycharm|neovim|emacs)\b.{0,40}\b(?:integration|plugin|extension)\b",
        re.I)),
    ("new-ide-integration", re.compile(
        r"\b(?:integration|plugin|extension)\b.{0,40}\b(?:ide|vscode|vs\s*code|visual\s+studio(?:\s+code)?|jetbrains|intellij|pycharm)\b",
        re.I)),
]


# ─────────────────────────────────────────────────────────────────────────────
# Keyword detection
# ─────────────────────────────────────────────────────────────────────────────
def match_keywords(text):
    """Return promo keywords present in ``text`` (case-insensitive substring match)."""
    low = (text or "").lower()
    return [k for k in PROMO_KEYWORDS if k in low]


def detect_launch_keywords(text):
    """Return launch-signal keywords present in ``text`` (deduplicated)."""
    low = (text or "").lower()
    found = []
    seen = set()
    for kw, pattern in _LAUNCH_PATTERNS:
        if pattern.search(low) and kw not in seen:
            seen.add(kw)
            found.append(kw)
    return found


def classify(title, summary=""):
    """Return (promo_keywords, launch_keywords) for an item's title + summary."""
    return match_keywords(title + " " + (summary or "")), detect_launch_keywords(title + " " + (summary or ""))


def is_flagged(title, summary=""):
    """True if the item carries any promo or launch signal."""
    promo, launch = classify(title, summary)
    return bool(promo or launch)


# ─────────────────────────────────────────────────────────────────────────────
# Text helpers
# ─────────────────────────────────────────────────────────────────────────────
def truncate(text, n):
    """Truncate ``text`` to at most ``n`` characters."""
    text = text or ""
    return text if len(text) <= n else text[:n]


def normalize_title(title):
    """Lowercase + collapse whitespace on a title (used for dedupe keys)."""
    return " ".join((title or "").lower().split())


# ─────────────────────────────────────────────────────────────────────────────
# Auth headers
# ─────────────────────────────────────────────────────────────────────────────
_GITHUB_API_HOST = "api.github.com"


def github_headers(url, token):
    """Return extra request headers for a URL, given an optional GitHub token.

    Pure helper: returns {} for non-GitHub-API URLs, or when ``token`` is empty/
    None. For api.github.com URLs with a token it returns a Bearer Authorization
    header (raises the unauthenticated GitHub rate limit from 60 to 5000 req/hr).

    The token is never logged, written to state, or sent to non-GitHub hosts.
    """
    if not token or not token.strip() or not url:
        return {}
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return {}
    if host != _GITHUB_API_HOST:
        return {}
    return {"Authorization": f"Bearer {token.strip()}"}


def strip_html(raw_html):
    """Remove script/style/tags from HTML and collapse whitespace."""
    if not raw_html:
        return ""
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.I | re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    return _html.unescape(" ".join(body.split()))


def html_to_text(raw_html):
    """Return (page_title, visible_text) for an HTML document."""
    title_m = re.search(r"<title[^>]*>(.*?)</title>", raw_html or "", re.I | re.S)
    title = _html.unescape(title_m.group(1)).strip() if title_m else ""
    return title, strip_html(raw_html)


# ─────────────────────────────────────────────────────────────────────────────
# Feed / release parsing (pure: text in, items out)
# ─────────────────────────────────────────────────────────────────────────────
def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _findtext(node, name):
    for child in node:
        if _local(child.tag) == name:
            return "".join(child.itertext()).strip()
    return ""


def _find_link(node):
    for child in node:
        if _local(child.tag) == "link":
            if child.text and child.text.strip():
                return child.text.strip()
            href = child.attrib.get("href")
            if href:
                return href
    return ""


def parse_feed(xml_text):
    """Parse RSS 2.0 or Atom XML into item dicts (title/link/date_raw/description)."""
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    nodes = []
    if _local(root.tag) == "feed":  # Atom
        nodes = [c for c in root if _local(c.tag) == "entry"]
    else:  # RSS: rss > channel > item
        channel = next((c for c in root if _local(c.tag) == "channel"), None)
        if channel is not None:
            nodes = [c for c in channel if _local(c.tag) == "item"]

    out = []
    for node in nodes:
        title = _findtext(node, "title")
        if not title:
            continue
        desc = (
            _findtext(node, "description")
            or _findtext(node, "summary")
            or _findtext(node, "content")
            or ""
        )
        date_raw = (
            _findtext(node, "pubDate")
            or _findtext(node, "published")
            or _findtext(node, "updated")
            or ""
        )
        out.append({
            "title": title,
            "link": _find_link(node),
            "date_raw": date_raw,
            "description": truncate(strip_html(desc), 1500),
        })
    return out


def parse_github_releases(payload):
    """Parse a GitHub releases API JSON payload into item dicts."""
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("GitHub releases: expected a JSON array")
    out = []
    for rel in data:
        if not isinstance(rel, dict):
            continue
        tag = rel.get("tag_name") or ""
        name = rel.get("name") or tag
        title = f"{tag} - {name}" if (tag and name and name != tag) else (tag or name or "Untitled release")
        out.append({
            "title": title,
            "link": rel.get("html_url") or "",
            "date_raw": rel.get("published_at") or "",
            "description": truncate(strip_html(rel.get("body") or ""), 1500),
        })
    return out


def parse_github_org_repos(payload):
    """Parse a GitHub org-repos JSON payload (sorted by pushed) into item dicts."""
    data = json.loads(payload)
    if not isinstance(data, list):
        raise ValueError("GitHub org repos: expected a JSON array")
    out = []
    for repo in data:
        if not isinstance(repo, dict):
            continue
        name = repo.get("full_name") or repo.get("name") or ""
        if not name:
            continue
        out.append({
            "title": name,
            "link": repo.get("html_url") or "",
            "date_raw": repo.get("pushed_at") or "",
            "description": truncate(strip_html(repo.get("description") or ""), 1500),
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Dates
# ─────────────────────────────────────────────────────────────────────────────
def normalize_date(raw):
    """Normalize a raw date string to YYYY-MM-DD, or 'Unknown'."""
    if not raw:
        return "Unknown"
    raw = raw.strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return m.group(1)
    try:
        dt = parsedate_to_datetime(raw)
        if dt is not None:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return "Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Dedupe keys + state file
# ─────────────────────────────────────────────────────────────────────────────
def make_key(company, title):
    """Deterministic dedupe key: hash of '(company)::<first 120 chars of title>'."""
    norm = normalize_title(title)[:120]
    raw = f"{str(company or '').strip().lower()}::{norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def merge_state_keys(existing, added, cap=2000):
    """Merge existing+added key lists (order-preserving, deduped), capped newest-last."""
    seen = set()
    combined = []
    for key in list(existing) + list(added):
        if not key:
            continue
        if key not in seen:
            seen.add(key)
            combined.append(key)
    return combined[-cap:]


def dedupe_items(items, known_keys):
    """Split flagged items into (new_items, merged_key_list).

    Only items whose dedupe key is NOT already in ``known_keys`` count as new;
    ALL items' keys are added to the merged list for the next run.
    """
    known = set(known_keys or [])
    new_items = [it for it in items if it.get("key") and it["key"] not in known]
    merged = merge_state_keys(list(known), [it.get("key") for it in items if it.get("key")])
    return new_items, merged


def load_state(path):
    """Load a state dict {'last_run', 'keys': [...]} from a JSON file.

    Missing/corrupt files degrade to a fresh state — never raise.
    """
    if not path:
        return {"last_run": None, "keys": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        keys = data.get("keys", [])
        if isinstance(keys, list) and all(isinstance(k, str) for k in keys):
            return {"last_run": data.get("last_run"), "keys": keys}
    except Exception:
        pass
    return {"last_run": None, "keys": []}


def save_state(path, state):
    """Atomically write the state dict back to ``path`` (tmp file + os.replace)."""
    payload = {
        "last_run": state.get("last_run"),
        "keys": list(state.get("keys", [])),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, path)
