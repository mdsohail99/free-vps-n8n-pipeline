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
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

# ─────────────────────────────────────────────────────────────────────────────
# Detection keywords — stable public output schema
# ─────────────────────────────────────────────────────────────────────────────
# The previous list contained broad single tokens — "student", "startup",
# "discount", "promo" — that substring-matched the *whole scraped page text* of
# full blog indexes (e.g. OpenAI's news RSS) and emitted years-old marketing
# posts as "deals". Those tokens are REMOVED. Every entry below is a phrase or
# context-scoped term that indicates a real, actionable deal/launch/promo
# signal (a coupon, a price cut, free credits, an active offer).
#
# Phrase matches are substring hits against PROMO_KEYWORDS; _PROMO_PATTERNS
# catch near-variants a fixed list cannot enumerate (e.g. "75% off",
# "free $50 credits"). Patterns are reported as their own keyword name.
PROMO_KEYWORDS = [
    "90% off", "95% off", "98% off", "99% off", "launch promotion", "limited time",
    "free credits", "credits multiplier", "token multiplier", "bonus credits",
    "preview pricing", "beta pricing", "early access", "free trial", "extended trial",
    "student", "startup", "enterprise credits", "discount", "coupon", "promo",
    "resource pack", "price drop", "price reduction", "usage multiplier", "off peak",
    "night pricing", "happy hours", "weekend pricing",
]

# Regex variants of the phrases above — reported only when no explicit phrase
# already covered the concept (avoids noisy duplicates like "99% off" + "percent-off").
_PROMO_PATTERNS = []

# Keywords that describe an EVERGREEN offer — a source still advertising them
# is a standing/recurring promo. Items carrying ONLY these survive the freshness
# floor when dated (freshness exemption), matching the spec's "genuine recurring
# promos still marked active". Note: a bare old blog post does NOT carry these —
# the 2024/2025 OpenAI bloat matched "discount"/"student"/"startup"/"promo",
# none of which are here.
RECURRING_PROMO_KEYWORDS = frozenset({
    "free credits", "bonus credits", "credits multiplier", "token multiplier",
    "usage multiplier", "credit boost", "free trial", "extended trial",
    "trial extension", "enterprise credits", "free tier", "free plan",
    "free usage", "free api", "coupon", "coupon code", "promo code", "promo codes",
    "resource pack", "off peak", "night pricing", "happy hours",
    "weekend pricing", "price drop", "price cut", "price reduction",
    "pay as you go", "per token pricing",
})

# Time-bound / actionable offer keywords — presence makes an item an ACTIVE deal
# regardless of age (within the freshness window): expiring offers, coupons,
# launch-day promos, price cuts, free credits/trials.
_ACTIVE_DEAL_KEYWORDS = frozenset({
    "90% off", "95% off", "98% off", "99% off", "launch promotion", "limited time",
    "free credits", "credits multiplier", "token multiplier", "bonus credits",
    "preview pricing", "beta pricing", "early access", "free trial", "extended trial",
    "coupon", "promo", "price drop", "price reduction", "usage multiplier",
})

# Launch-signal keyword names that make a dated item an ACTIVE deal only when it
# falls inside a short "hot" window (launch-day releases). See DEAL_HOT_DAYS.
_LAUNCH_KEYWORDS_FOR_HOT = frozenset({
    "new-model", "new-benchmark", "new-context-window",
    "new-agent-product", "new-ide-integration", "release", "now-available",
})

# Launch-signal detection: non-promo, high-value intelligence. These fire on the
# title (and summary) of an item, e.g. "Introducing Claude 4", "SWE-bench Pro",
# "1M token context window", "Codex Agent", "VS Code integration".
#
# Precision rules:
#  * proximity windows use `[^.!?\n]{0,N}` — a signal can NEVER span a sentence
#    boundary. The old `.{0,N}` let "Introducing X ... model" match across
#    unrelated sentences on a long scraped blog page (a false-positive source).
#  * "new-model" now requires a concrete model identifier (gpt-*, claude *,
#    gemini *, deepseek *, qwen *, ...) or the word "model" itself next to the
#    launch verb — so "Introducing study mode in ChatGPT" or "Introducing
#    OpenAI Japan" no longer fire.
_LAUNCH_PATTERNS = [
    ("new-model", re.compile(
        r"\b(?:new|introduc\w*|unveil\w*|launch\w*|releas\w*|debut\w*|present\w*|announc\w*)\b"
        r"[^.!?\n]{0,30}\b(?:model|foundation\s+model|gpt[-\w.]*|claude\s*\w+|gemini[-\w.]*|deepseek[-\w.]*|qwen\s*\w+)\b",
        re.I)),
    ("new-model", re.compile(
        r"\b(?:frontier|reasoning|preview|foundation)\s+model\b", re.I)),
    ("new-benchmark", re.compile(
        r"\b(?:new|introduc\w*|releas\w*|launch\w*|unveil\w*|debut\w*)\b[^.!?\n]{0,30}\bbenchmark\b",
        re.I)),
    ("new-context-window", re.compile(
        r"\b(?:new|extended|larger|bigger|expanded|longer|1m|2m|4m|10m)\b[^.!?\n]{0,25}\bcontext\s+(?:window|length)\b",
        re.I)),
    ("new-context-window", re.compile(
        r"\bcontext\s+(?:window|length)\b[^.!?\n]{0,25}\b(?:new|extended|expanded|larger)\b",
        re.I)),
    ("new-agent-product", re.compile(
        r"\b(?:new|introduc\w*|unveil\w*|launch\w*|releas\w*|debut\w*)\b[^.!?\n]{0,30}\bagent\b",
        re.I)),
    ("new-agent-product", re.compile(
        r"\b(?:coding|code|cli)\s+agent\b", re.I)),
    ("new-ide-integration", re.compile(
        r"\b(?:new\s+)?(?:ide|vscode|vs\s*code|visual\s+studio(?:\s+code)?|jetbrains|intellij|pycharm|neovim|emacs)\b"
        r"[^.!?\n]{0,40}\b(?:integration|plugin|extension)\b",
        re.I)),
    ("new-ide-integration", re.compile(
        r"\b(?:integration|plugin|extension)\b[^.!?\n]{0,40}\b(?:ide|vscode|vs\s*code|visual\s+studio(?:\s+code)?|jetbrains|intellij|pycharm)\b",
        re.I)),
    ("release", re.compile(
        r"\brelease[sd]?\b[^.!?\n]{0,12}\bv?\d+(?:\.\d+)+\b", re.I)),
    ("now-available", re.compile(r"\bnow available\b", re.I)),
]


# ─────────────────────────────────────────────────────────────────────────────
# Keyword detection
# ─────────────────────────────────────────────────────────────────────────────
def match_keywords(text):
    """Return promo keywords present in ``text`` (case-insensitive).

    Phrase hits use substring matching against PROMO_KEYWORDS; _PROMO_PATTERNS
    catch near-variants (e.g. "75% off", "free $50 credits") a fixed list cannot
    enumerate. A pattern is reported only when no explicit phrase already
    covered the same concept (no "99% off" + "percent-off" duplication).
    """
    low = (text or "").lower()
    return [k for k in PROMO_KEYWORDS if k in low]


def is_recurring_promo(keywords):
    """True if the matched keywords indicate a still-valid evergreen offer.

    Used to exempt genuine recurring promos from the freshness floor (the spec's
    "EXCEPT ... still marked active"). Keywords like "student"/"discount" alone
    are NOT recurring-evidence, so old marketing posts are not exempted.
    """
    return bool(set(keywords or []) & RECURRING_PROMO_KEYWORDS)


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
# Active-deal flagging (time-bound vs generic news)
# ─────────────────────────────────────────────────────────────────────────────
DEAL_HOT_DAYS = 3  # launch-day / expiring window: a dated launch inside this is active


def compute_active_flag(keywords, date_str, ref_date=None, hot_days=DEAL_HOT_DAYS,
                        expiry_date=None, current_signal=False,
                        freshness_days=14):
    """Return True if an item is a genuinely time-bound / actionable deal.

    An item is an ACTIVE deal when EITHER:
      * it carries a time-bound/actionable offer keyword (coupon, "% off",
        "limited time", "price cut", "free credits", "free trial", ...)
        and is fresh or has an explicit current signal, OR
      * it is a launch signal (new-model / agent / release / now-available)
        dated within ``hot_days`` of ``ref_date`` (launch-day releases).

    Generic news ("new-ide-integration" from a month ago) is not an active deal.
    """
    if ref_date is None:
        ref_date = datetime.now(timezone.utc).date()
    if expiry_date and expiry_date != "Unknown":
        try:
            if date(*[int(x) for x in expiry_date[:10].split("-")]) < ref_date:
                return False
        except Exception:
            pass
    kw = set(keywords or [])
    if kw & _ACTIVE_DEAL_KEYWORDS:
        if current_signal:
            return True
        if not date_str or date_str in ("", "Unknown"):
            return False
        try:
            item_date = date(*[int(x) for x in date_str[:10].split("-")])
        except Exception:
            return False
        return 0 <= (ref_date - item_date).days <= freshness_days
    if not (kw & _LAUNCH_KEYWORDS_FOR_HOT):
        return False
    if not date_str or date_str in ("", "Unknown"):
        return False
    try:
        item_date = date(*[int(x) for x in date_str[:10].split("-")])
    except Exception:
        return False
    days = (ref_date - item_date).days
    return 0 <= days <= hot_days


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


_EXPIRY_PATTERN = re.compile(
    r"\b(?:expires?|ends?|ending|valid\s+through|available\s+through)\s*[:\-]?\s*"
    r"(\d{4}-\d{2}-\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b", re.I
)
_CURRENT_SIGNAL_PATTERN = re.compile(
    r"\b(?:currently\s+available|ongoing|active\s+offer|"
    r"valid\s+until|expires?|ends?|this\s+(?:week|month)|today)\b", re.I
)


def extract_expiry_date(text):
    """Return an explicit offer end date from text, or ``Unknown``."""
    match = _EXPIRY_PATTERN.search(text or "")
    return normalize_date(match.group(1)) if match else "Unknown"


def has_current_signal(text):
    """Return whether text explicitly presents an offer as current."""
    return bool(_CURRENT_SIGNAL_PATTERN.search(text or ""))


# ─────────────────────────────────────────────────────────────────────────────
# Freshness floor (drop stale items; keep fresh + still-active recurring promos)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_FRESHNESS_DAYS = 14


def is_fresh_date(date_str, ref_date, max_age_days=DEFAULT_FRESHNESS_DAYS):
    """True if ``date_str`` (YYYY-MM-DD or 'Unknown') is within the window.

    Unknown / unparseable / missing dates return True (we can't judge staleness,
    so they are kept and sink to the bottom of the ordering). Boundary is
    inclusive: an item exactly ``max_age_days`` old is still fresh.
    """
    if not date_str or date_str in ("", "Unknown", None):
        return True
    try:
        item_date = date(*[int(x) for x in date_str[:10].split("-")])
    except Exception:
        return True
    return (ref_date - item_date).days <= max_age_days


def is_fresh(item, ref_date=None, max_age_days=DEFAULT_FRESHNESS_DAYS):
    """True if an item passes the freshness floor.

    An item marked ``active`` (a still-marked recurring promo / standing offer)
    is exempt from the age drop regardless of date.
    """
    if ref_date is None:
        ref_date = datetime.now(timezone.utc).date()
    expiry = item.get("expiry_date")
    if expiry and expiry != "Unknown":
        try:
            if date(*[int(x) for x in expiry[:10].split("-")]) < ref_date:
                return False
        except Exception:
            pass
    if item.get("active") and item.get("is_active_deal"):
        return True
    return is_fresh_date(item.get("date") or "", ref_date, max_age_days)


def filter_fresh_items(items, ref_date=None, max_age_days=DEFAULT_FRESHNESS_DAYS):
    """Keep only items that pass the freshness floor (order preserved)."""
    if ref_date is None:
        ref_date = datetime.now(timezone.utc).date()
    return [it for it in items if is_fresh(it, ref_date=ref_date, max_age_days=max_age_days)]


# ─────────────────────────────────────────────────────────────────────────────
# Per-source crawl cap (limit blog-index bloat) + ordering
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_SOURCE_CAP = 10


def cap_items_per_source(items, cap=DEFAULT_SOURCE_CAP):
    """Keep at most ``cap`` items per source, newest first (Unknown dates last).

    Applied AFTER the freshness floor so a full blog index only contributes its
    most recent qualifying items per run.
    """
    if cap is None or cap <= 0:
        return list(items)
    grouped = {}
    for item in items:
        grouped.setdefault(item.get("source") or "", []).append(item)
    out = []
    for group in grouped.values():
        ordered = sorted(group, key=lambda it: (
            1 if it.get("active") or it.get("is_active_deal") else 0,
            0 if (it.get("date") or "") in ("", "Unknown") else 1,
            it.get("date") or "",
            -(it.get("priority") or 2),
            it.get("key") or "",
        ), reverse=True)
        out.extend(ordered[:cap])
    return out


def order_items(items):
    """Rank items: active deals first, then newest date, then priority tier.

    Ordering intent (all descending on the sort key):
      1. active deal (is_active_deal) ahead of generic news;
      2. dated items ahead of Unknown-date items;
      3. newest date first;
      4. priority tier: 1 (coding platforms) before 2 (model providers).
    """
    def sort_key(it):
        d = it.get("date") or ""
        unknown = d in ("", "Unknown")
        return (
            1 if it.get("is_active_deal") else 0,   # active first
            0 if unknown else 1,                    # dated before Unknown
            d,                                      # newest date first (desc lexicographic)
            2 - (it.get("priority") or 2),          # priority 1 before 2
        )
    return sorted(items, key=sort_key, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# Dedupe keys + state file
# ─────────────────────────────────────────────────────────────────────────────
def make_key(company, title):
    """Deterministic dedupe key: hash of '(company)::<first 120 chars of title>'."""
    norm = normalize_title(title)[:120]
    raw = f"{str(company or '').strip().lower()}::{norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Tracking params stripped so the same article via different affiliate/referral
# links still dedupes to a single item.
_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid", "spm",
})


def make_url_key(url):
    """Deterministic dedupe key from a normalized URL (host+path, tracking stripped).

    Used for cross-source dedupe: the same item mirrored under a different
    company label (e.g. "OpenAI" vs "OpenAI (API)") still has the same URL key
    and is emitted once. Returns None for an unusable URL.
    """
    if not url:
        return None
    try:
        p = urlparse(url)
    except ValueError:
        return None
    host = (p.netloc or "").lower().rstrip(".")
    path = (p.path or "").rstrip("/")
    keep = []
    for pair in (p.query or "").split("&"):
        if not pair:
            continue
        name = pair.split("=", 1)[0].lower()
        if name not in _TRACKING_PARAMS:
            keep.append(pair)
    raw = f"{host}{path}"
    q = "&".join(sorted(keep))
    if q:
        raw += f"?{q}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def dedupe_items_within_run(items):
    """Drop duplicates within a single run: same dedupe key OR same URL key.

    Keeps the first occurrence (input order = per-source, pre-sort order) so
    deterministic. Both title/company key and normalized-URL key are consulted,
    covering the "same title across sources" and "same URL under two company
    labels" cases.
    """
    def winner_key(it):
        d = it.get("date") or ""
        known_date = d not in ("", "Unknown")
        return (
            1 if it.get("active") or it.get("is_active_deal") else 0,
            1 if (it.get("priority") or 2) == 1 else 0,
            1 if known_date else 0,
            d,
            str(it.get("key") or ""),
            str(it.get("url_key") or ""),
        )

    # Sorting before selection makes async source completion order irrelevant.
    candidates = sorted(items, key=winner_key, reverse=True)
    seen_keys, seen_urls = set(), set()
    out = []
    for it in candidates:
        key = it.get("key")
        url_key = it.get("url_key")
        if key and key in seen_keys:
            continue
        if url_key and url_key in seen_urls:
            continue
        if key:
            seen_keys.add(key)
        if url_key:
            seen_urls.add(url_key)
        out.append(it)
    return out


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
