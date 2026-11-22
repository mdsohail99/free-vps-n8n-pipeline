#!/usr/bin/env python3
"""Daily free-model scan: which free/stealth models are usable right now.

Usage:
  python3 free_models.py            # one line per model in the fallback chain
  python3 free_models.py --json     # machine-readable
  python3 free_models.py --snapshot # write catalog/YYYY-MM-DD.json for the weekly diff
  python3 free_models.py --self-check

Mirrors the scan in Node 5 of the n8n workflow. The workflow is the runtime
version (it reuses the catalog it already fetches); this is the eyeball version
for "is a stealth model live today?" and the snapshot writer for the weekly diff.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

CATALOG = "https://openrouter.ai/api/v1/models"
KNOWN_GOOD = ["nvidia/nemotron-3.5-super-vl:free", "nvidia/nemotron-3.5-lightning:free"]
CHAIN_LIMIT = 4
CATALOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog")


def _is_text(m):
    a = m.get("architecture") or {}
    return "text" in (a.get("input_modalities") or []) and (a.get("output_modalities") or []) == ["text"]


def _is_zero(m):
    p = m.get("pricing") or {}
    return float(p.get("prompt") or 0) == 0 and float(p.get("completion") or 0) == 0


def select(models):
    """Return (chain, stealth_ids). Stealth first, then known-good, then :free by context."""
    text = [m for m in models if m.get("id") and _is_text(m)]
    stealth = [m["id"] for m in text if _is_zero(m) and not m["id"].endswith(":free") and m["id"] != "openrouter/free"]
    tagged = sorted((m for m in text if m["id"].endswith(":free")), key=lambda m: -(m.get("context_length") or 0))
    chain = stealth[:1] + KNOWN_GOOD + [m["id"] for m in tagged] + ["openrouter/free"]
    seen, out = set(), []
    for mid in chain:
        if mid not in seen:
            seen.add(mid)
            out.append(mid)
    return out[:CHAIN_LIMIT], stealth


def fetch():
    with urllib.request.urlopen(CATALOG, timeout=60) as r:
        return json.loads(r.read()).get("data") or []


def compact(models):
    """Only the fields the weekly diff needs, so a snapshot stays small."""
    out = {}
    for m in models:
        mid = m.get("id")
        if not mid:
            continue
        p = m.get("pricing") or {}
        out[mid] = {
            "name": m.get("name") or mid,
            "prompt": float(p.get("prompt") or 0),
            "completion": float(p.get("completion") or 0),
            "ctx": m.get("context_length") or 0,
            "created": m.get("created") or 0,
        }
    return out


def write_snapshot(models, day=None):
    """Write catalog/<day>.json. Returns the path."""
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(CATALOG_DIR, exist_ok=True)
    path = os.path.join(CATALOG_DIR, day + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"day": day, "models": compact(models)}, f)
    return path


def _self_check():
    def m(mid, prompt="0", completion="0", ctx=1000000, out=("text",)):
        return {"id": mid, "context_length": ctx, "pricing": {"prompt": prompt, "completion": completion},
                "architecture": {"input_modalities": ["text"], "output_modalities": list(out)}}

    chain, stealth = select([
        m("google/lyria-3-pro-preview", out=("text", "audio")),  # music -> excluded
        m("acme/stealth-preview"),                              # stealth -> first
        m("nvidia/nemotron-3.5-super-vl:free"),
        m("big/ctx:free", ctx=2000000),
        m("openrouter/free"),
        m("paid/model", "0.000001", "0.000002"),
    ])
    assert chain[0] == "acme/stealth-preview", chain
    assert "google/lyria-3-pro-preview" not in chain, chain
    assert "paid/model" not in chain, chain
    assert len(chain) <= CHAIN_LIMIT, chain
    assert stealth == ["acme/stealth-preview"], stealth

    chain, stealth = select([m("nvidia/nemotron-3.5-super-vl:free"), m("openrouter/free")])
    assert chain[:2] == KNOWN_GOOD, chain
    assert stealth == [], stealth

    chain, _ = select([])
    assert chain == KNOWN_GOOD + ["openrouter/free"], chain

    # Snapshot keeps only the fields the weekly diff reads.
    snap = compact([{"id": "a/b", "name": "B", "context_length": 1000, "created": 5,
                     "pricing": {"prompt": "0.000001", "completion": "0"}}, {"no_id": True}])
    assert list(snap) == ["a/b"], snap
    assert snap["a/b"] == {"name": "B", "prompt": 0.000001, "completion": 0.0, "ctx": 1000, "created": 5}, snap

    print("OK — free-model scan self-check passed")


def main(argv):
    if "--self-check" in argv:
        return _self_check()
    models = fetch()
    if "--snapshot" in argv:
        print("snapshot: " + write_snapshot(models))
    chain, stealth = select(models)
    if "--json" in argv:
        print(json.dumps({"chain": chain, "stealth": stealth}, indent=2))
        return
    print("stealth live: " + (", ".join(stealth) if stealth else "none"))
    for i, mid in enumerate(chain, 1):
        print(f"{i}. {mid}")


if __name__ == "__main__":
    main(sys.argv[1:])
