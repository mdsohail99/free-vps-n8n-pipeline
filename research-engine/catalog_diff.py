#!/usr/bin/env python3
"""Computed sections for the weekly AI report.

Every number here is calculated from files on disk, so the model that writes the
prose around it cannot invent one. The model only writes Story Trends and
Recommendations; everything else is pasted verbatim into the Notion page.

Usage:
  python3 catalog_diff.py --emit=weekly
  python3 catalog_diff.py --self-check

Snapshots are written by `free_models.py --snapshot` into ./catalog/. The diff
compares the newest snapshot against the newest one at least 7 days older, so
the snapshot filename's timezone never matters.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_DIR = os.path.join(HERE, "catalog")
REPORTS_DIR = "/home/ubuntu/reports"
STATE_FILE = os.path.join(HERE, "deals_state.json")

SECTIONS_SEP = "===WEEKLY_SECTIONS==="
BODIES_SEP = "===WEEKLY_BODIES==="


def snapshot_days():
    if not os.path.isdir(CATALOG_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(CATALOG_DIR) if f.endswith(".json"))


def load_snapshot(day):
    with open(os.path.join(CATALOG_DIR, day + ".json"), encoding="utf-8") as f:
        return (json.load(f) or {}).get("models") or {}


def pick_pair(days):
    """(latest, baseline). Baseline is the newest snapshot >= 7 days older than latest."""
    if not days:
        return None, None
    latest = days[-1]
    target = (date.fromisoformat(latest) - timedelta(days=7)).isoformat()
    older = [d for d in days if d <= target]
    return latest, (older[-1] if older else None)


def _price(m):
    return float(m.get("prompt") or 0), float(m.get("completion") or 0)


def diff(old, new):
    """(added ids, removed ids, [(id, old_price, new_price)])."""
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = []
    for mid in sorted(set(old) & set(new)):
        a, b = _price(old[mid]), _price(new[mid])
        if abs(a[0] - b[0]) > 1e-9 or abs(a[1] - b[1]) > 1e-9:
            changed.append((mid, a, b))
    return added, removed, changed


def money(v):
    return "$%.2f" % (v * 1e6)


def report_files(n=7):
    if not os.path.isdir(REPORTS_DIR):
        return []
    return sorted(f for f in os.listdir(REPORTS_DIR) if f.endswith(".md"))[-n:]


def read_capped(path, cap):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()[:cap]
    except OSError:
        return ""


def glance(days, latest, baseline, snap, old, added, removed, changed, files):
    free = [mid for mid, m in snap.items() if _price(m) == (0.0, 0.0)]
    out = ["## Week at a Glance", ""]
    out.append("- Daily briefings in window: %d (%s)" % (len(files), ", ".join(f[:-3] for f in files) or "none"))
    out.append("- Models in catalog: %d" % len(snap))
    if old is None:
        out.append("- Week-over-week deltas: baseline starts %s, first real diff lands 7 days later" % (latest or "today"))
    else:
        out.append("- Catalog change %s to %s: +%d added, -%d removed, %d price changes"
                   % (baseline, latest, len(added), len(removed), len(changed)))
    out.append("- Free text models available: %d" % len(free))
    out.append("- Snapshots on disk: %d" % len(days))
    out.append("")
    return out


def delta(latest, baseline, added, removed, changed, snap):
    out = ["## Catalog Delta", ""]
    if baseline is None:
        out.append("No baseline snapshot is old enough yet. This section reports exact week-over-week "
                   "price and catalog changes from the first Sunday after %s." % (latest or "today"))
        out.append("")
        return out
    out.append("Comparing %s against %s." % (latest, baseline))
    out.append("")
    if changed:
        out.append("### Price changes")
        for mid, a, b in changed:
            pct = "" if a[0] == 0 else " (%.0f%%)" % ((b[0] - a[0]) / a[0] * 100)
            out.append("- **%s** - input %s to %s%s, output %s to %s"
                       % (mid, money(a[0]), money(b[0]), pct, money(a[1]), money(b[1])))
        out.append("")
    if added:
        out.append("### Added to the catalog")
        for mid in added[:20]:
            m = snap.get(mid) or {}
            out.append("- **%s** - %s input / %s output - %sK ctx"
                       % (mid, money(_price(m)[0]), money(_price(m)[1]), round((m.get("ctx") or 0) / 1000)))
        out.append("")
    if removed:
        out.append("### Removed from the catalog")
        for mid in removed[:20]:
            out.append("- **%s**" % mid)
        out.append("")
    if not (changed or added or removed):
        out.append("No catalog changes this week.")
        out.append("")
    return out


def free_watch(snap):
    free = sorted(((mid, m) for mid, m in snap.items() if _price(m) == (0.0, 0.0)),
                  key=lambda kv: -(kv[1].get("ctx") or 0))
    stealth = [mid for mid, _ in free if not mid.endswith(":free") and mid != "openrouter/free"]
    out = ["## Free & Stealth Watch", ""]
    out.append("- Free text models in catalog: %d" % len(free))
    out.append("- Stealth (zero-price, not tagged ':free'): %s" % (", ".join(stealth) if stealth else "none today"))
    out.append("")
    for mid, m in free[:12]:
        out.append("- **%s** - %sK ctx" % (mid, round((m.get("ctx") or 0) / 1000)))
    out.append("")
    return out


def deal_ledger():
    out = ["## Deal Ledger", ""]
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f) or {}
    except (OSError, ValueError):
        out.append("Deal state file unreadable this run.")
        out.append("")
        return out
    out.append("- Tracked promotion and launch signals: %d" % len(state.get("keys") or []))
    out.append("- Last scan: %s" % (state.get("last_run") or "unknown"))
    out.append("- Per-deal detail (prices, expiry, source URL) is in this week's daily briefings")
    out.append("")
    return out


def what_to_watch(snap, latest):
    if not latest:
        return ["## What to Watch", "", "No catalog snapshot yet.", ""]
    cutoff = (date.fromisoformat(latest) - timedelta(days=7)).isoformat()
    cutoff_ts = int(datetime.fromisoformat(cutoff).replace(tzinfo=timezone.utc).timestamp())
    fresh = []
    for mid, m in snap.items():
        created = m.get("created") or 0
        if created and created >= cutoff_ts:
            fresh.append((created, mid, m))
    fresh.sort(reverse=True)
    out = ["## What to Watch", ""]
    if not fresh:
        out.append("- No models added to the catalog in the last 7 days")
    else:
        out.append("- %d models entered the catalog in the last 7 days:" % len(fresh))
        for _, mid, m in fresh[:8]:
            tag = "free" if _price(m) == (0.0, 0.0) else "%s/%s" % (money(_price(m)[0]), money(_price(m)[1]))
            out.append("- **%s** - %s - %sK ctx" % (mid, tag, round((m.get("ctx") or 0) / 1000)))
    out.append("")
    return out


# Appended reference sections name every model in the catalog, so counting them would
# score every model N/N. Only the narrative part of a briefing counts as a mention.
NON_NARRATIVE = ("## Model Pricing Dashboard", "## Sources")


def narrative(text):
    cut = len(text)
    for marker in NON_NARRATIVE:
        i = text.find(marker)
        if i != -1:
            cut = min(cut, i)
    return text[:cut]


def short_name(name):
    # Catalog names are "Vendor: Model"; briefings write just the model part.
    return name.split(": ", 1)[-1].strip()


def most_mentioned(snap, files, limit=10):
    texts = [narrative(read_capped(os.path.join(REPORTS_DIR, f), 200000)).lower() for f in files]
    counts = {}
    for m in snap.values():
        name = short_name((m.get("name") or "").strip())
        # A name with no digit ("Extract", "Inkling") is a plain English word that
        # matches prose, not a model identifier.
        if len(name) < 4 or "(batch)" in name.lower() or not any(c.isdigit() for c in name):
            continue
        n = sum(1 for t in texts if name.lower() in t)
        if n >= 2:
            counts[name] = max(counts.get(name, 0), n)
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    # "GPT-6.2 Astra" is a substring of "GPT-6.2 Astra Pro", so both score the same
    # mention. Keep the longer name when the count is identical.
    ranked = [
        (n, c) for n, c in ranked
        if not any(o != n and c == oc and n.lower() in o.lower() for o, oc in ranked)
    ]
    out = ["## Most-Mentioned This Week", ""]
    if not ranked:
        out.append("- No model was named in more than one briefing this week")
        out.append("")
        return out
    out.append("Mention counts across the %d briefings in the window. This is frequency, not a quality ranking." % len(files))
    out.append("")
    for name, n in ranked[:limit]:
        out.append("- **%s** - %d of %d briefings" % (name, n, len(files)))
    out.append("")
    return out


def emit_weekly():
    days = snapshot_days()
    latest, baseline = pick_pair(days)
    snap = load_snapshot(latest) if latest else {}
    old = load_snapshot(baseline) if baseline else None
    files = report_files()
    added, removed, changed = diff(old, snap) if old is not None else ([], [], [])

    sections = []
    sections += glance(days, latest, baseline, snap, old, added, removed, changed, files)
    sections += delta(latest, baseline, added, removed, changed, snap)
    sections += free_watch(snap)
    sections += deal_ledger()
    sections += what_to_watch(snap, latest)
    sections += most_mentioned(snap, files)

    out = [SECTIONS_SEP, "\n".join(sections).rstrip(), BODIES_SEP]
    for f in files:
        out.append("### %s" % f[:-3])
        out.append(read_capped(os.path.join(REPORTS_DIR, f), 12000))
    return "\n".join(out)


def _self_check():
    def m(prompt=0.0, completion=0.0, ctx=1000000, created=0, name="X"):
        return {"name": name, "prompt": prompt, "completion": completion, "ctx": ctx, "created": created}

    old = {"a/x": m(0.000001, 0.000002), "b/y": m(0.0, 0.0), "c/z": m(0.000003, 0.000004)}
    new = {"a/x": m(0.0000005, 0.000002), "b/y": m(0.0, 0.0), "d/w": m(0.0, 0.0)}

    added, removed, changed = diff(old, new)
    assert added == ["d/w"], added
    assert removed == ["c/z"], removed
    assert len(changed) == 1 and changed[0][0] == "a/x", changed
    assert money(0.000001) == "$1.00", money(0.000001)

    # Baseline must be at least 7 days older than the newest snapshot.
    assert pick_pair([]) == (None, None)
    assert pick_pair(["2026-11-20"]) == ("2026-11-20", None)
    assert pick_pair(["2026-11-01", "2026-11-10", "2026-11-20"]) == ("2026-11-20", "2026-11-10")
    assert pick_pair(["2026-11-10", "2026-11-20"]) == ("2026-11-20", "2026-11-10")

    # Free/stealth classification: zero price and no ':free' suffix.
    snap = {"p/stealth": m(), "q/thing:free": m(), "r/paid": m(0.000001, 0.000002), "openrouter/free": m()}
    free = [mid for mid, v in snap.items() if _price(v) == (0.0, 0.0)]
    stealth = [mid for mid in free if not mid.endswith(":free") and mid != "openrouter/free"]
    assert stealth == ["p/stealth"], stealth

    # Reference sections are stripped so the pricing dashboard cannot fake a mention.
    assert narrative("a\n## Model Pricing Dashboard\nb") == "a\n"
    assert narrative("a\n## Sources\nb") == "a\n"
    assert narrative("no markers") == "no markers"

    # Catalog names carry a vendor prefix that briefings never write.
    assert short_name("OpenAI: GPT-6.2 Astra Pro") == "GPT-6.2 Astra Pro"
    assert short_name("NoColon") == "NoColon"

    print("OK - catalog diff self-check passed")


def main(argv):
    if "--self-check" in argv:
        return _self_check()
    print(emit_weekly())


if __name__ == "__main__":
    main(sys.argv[1:])
