"""test_deals.py — unit tests for the deal-intelligence scanner.

Runs with BOTH:
    python -m unittest discover -s research-engine/tests -v
    python -m pytest research-engine/tests -q

stdlib-only (unittest); no network access required.
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

# Make research-engine/ importable regardless of how the test runner boots.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deals_core import (  # noqa: E402
    PROMO_KEYWORDS,
    classify,
    cap_items_per_source,
    compute_active_flag,
    dedupe_items,
    dedupe_items_within_run,
    detect_launch_keywords,
    github_headers,
    html_to_text,
    load_state,
    make_key,
    match_keywords,
    merge_state_keys,
    make_url_key,
    normalize_date,
    filter_fresh_items,
    parse_feed,
    parse_github_org_repos,
    parse_github_releases,
    save_state,
    strip_html,
    truncate,
)
from sources.deals_registry import (  # noqa: E402
    ENTRIES,
    P1_PLATFORMS,
    P2_PLATFORMS,
    PLATFORM_MAP,
    all_entries,
    entry_by_id,
    entries_for_platform,
    platform_names,
    unique_entries,
)


class KeywordDetectionTests(unittest.TestCase):
    def test_exact_keyword_list(self):
        """The registry MUST use the exact keyword list from the spec."""
        expected = [
            "90% off", "95% off", "98% off", "99% off", "launch promotion",
            "limited time", "free credits", "credits multiplier",
            "token multiplier", "bonus credits", "preview pricing",
            "beta pricing", "early access", "free trial", "extended trial",
            "student", "startup", "enterprise credits", "discount", "coupon",
            "promo", "resource pack", "price drop", "price reduction",
            "usage multiplier", "off peak", "night pricing", "happy hours",
            "weekend pricing",
        ]
        self.assertEqual(PROMO_KEYWORDS, expected)

    def test_positive_matches(self):
        cases = [
            ("Get Free Credits now", ["free credits"]),
            ("90% off all plans", ["90% off"]),
            ("Early Access available", ["early access"]),
            ("Student discount available", ["student", "discount"]),
            ("Startup program: limited time offer", ["limited time", "startup"]),
            ("99% off launch promotion", ["99% off", "launch promotion", "promo"]),
            ("Weekend pricing for off peak usage", ["off peak", "weekend pricing"]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(match_keywords(text), expected)

    def test_negative_matches(self):
        negatives = [
            "We value open source contributions",
            "Check out our new developer platform",
            "The weather in San Francisco today",
            "Our quarterly engineering report",
        ]
        for text in negatives:
            with self.subTest(text=text):
                self.assertEqual(match_keywords(text), [])

    def test_discount_code_flags_via_discount_substring(self):
        """'discount' is a keyword, so 'discount code' still flags on 'discount'."""
        self.assertIn("discount", match_keywords("discount code SAVE20"))

    def test_case_insensitive(self):
        self.assertEqual(match_keywords("FREE CREDITS WEEKEND PRICING"),
                         ["free credits", "weekend pricing"])

    def test_classify_combines_title_and_summary(self):
        promo, launch = classify("Summer update", "Get 90% off and free credits today")
        self.assertEqual(promo, ["90% off", "free credits"])
        self.assertEqual(launch, [])

    def test_launch_signals(self):
        cases = [
            ("Introducing GPT-5, our new frontier model", "new-model"),
            ("SWE-bench Pro: a new coding benchmark", "new-benchmark"),
            ("Now with a 1M token context window", "new-context-window"),
            ("Introducing Codex Agent", "new-agent-product"),
            ("New VS Code integration released", "new-ide-integration"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertIn(expected, detect_launch_keywords(text))

    def test_no_false_launch_on_plain_text(self):
        self.assertEqual(detect_launch_keywords("We fixed some bugs"), [])


class StateAndDedupeTests(unittest.TestCase):
    def _item(self, company, title):
        return {
            "company": company,
            "title": title,
            "key": make_key(company, title),
        }

    def test_dedupe_first_run_new_then_not_new(self):
        item = self._item("Cursor", "Get 90% off Pro")
        new1, merged = dedupe_items([item], [])
        self.assertEqual(len(new1), 1)
        self.assertIn(item["key"], merged)
        # second run with the merged keys => no longer new
        new2, merged2 = dedupe_items([item], merged)
        self.assertEqual(len(new2), 0)
        self.assertEqual(len(merged2), 1)

    def test_all_items_enter_state_even_when_known(self):
        known = [self._item("Cursor", "Old item")["key"]]
        old = self._item("Cursor", "Old item")
        fresh = self._item("OpenAI", "New item")
        new, merged = dedupe_items([old, fresh], known)
        self.assertEqual([i["key"] for i in new], [fresh["key"]])
        self.assertEqual(len(merged), 2)

    def test_state_file_create_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "deals_state.json")
            self.assertFalse(os.path.exists(path))
            state = load_state(path)  # fresh when missing
            self.assertEqual(state["keys"], [])
            item = self._item("Anthropic", "Extended trial available")
            new, merged = dedupe_items([item], state["keys"])
            state["keys"] = merged
            state["last_run"] = "2026-08-04 12:00 UTC"
            save_state(path, state)
            self.assertTrue(os.path.exists(path))
            reloaded = load_state(path)
            self.assertEqual(reloaded["last_run"], "2026-08-04 12:00 UTC")
            self.assertIn(item["key"], reloaded["keys"])
            # second run against the reloaded state reports nothing new
            new2, _ = dedupe_items([item], reloaded["keys"])
            self.assertEqual(len(new2), 0)

    def test_state_file_corrupt_degrades_to_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad_state.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{ this is not json !!")
            state = load_state(path)
            self.assertEqual(state["keys"], [])

    def test_make_key_stable_and_truncated(self):
        self.assertEqual(make_key("Cursor", "Free Credits!"),
                         make_key("cursor", "  FREE  credits! "))
        long_a = "A" * 300
        long_b = "A" * 120 + "DIFFERENT"
        self.assertEqual(make_key("X", long_a), make_key("X", long_b))
        self.assertNotEqual(make_key("Cursor", "Free Credits"),
                            make_key("OpenAI", "Free Credits"))

    def test_state_cap_drops_oldest(self):
        merged = merge_state_keys([], [f"k{i}" for i in range(2500)], cap=2000)
        self.assertEqual(len(merged), 2000)
        self.assertNotIn("k0", merged)
        self.assertIn("k2499", merged)

    def test_freshness_drops_old_dated_items_but_keeps_unknown(self):
        items = [
            {"title": "old", "date": "2026-07-01"},
            {"title": "boundary", "date": "2026-07-21"},
            {"title": "unknown", "date": "Unknown"},
        ]
        kept = filter_fresh_items(items, ref_date=date(2026, 8, 4))
        self.assertEqual([item["title"] for item in kept], ["boundary", "unknown"])

    def test_cap_prefers_active_dated_items_over_unknown(self):
        items = [
            {"source": "a", "title": "unknown", "date": "Unknown", "active": False, "key": "u"},
            {"source": "a", "title": "fresh", "date": "2026-08-03", "active": False, "key": "f"},
            {"source": "a", "title": "active", "date": "2026-08-01", "active": True, "key": "a"},
        ]
        self.assertEqual([i["key"] for i in cap_items_per_source(items, cap=2)], ["a", "f"])

    def test_dedupe_winner_is_priority_aware_not_input_order(self):
        older = {"key": "same", "url_key": "url", "date": "2026-07-20", "priority": 2, "is_active_deal": False}
        winner = {"key": "same", "url_key": "url", "date": "2026-08-03", "priority": 1, "is_active_deal": True, "title": "winner"}
        self.assertEqual(dedupe_items_within_run([older, winner])[0], winner)

    def test_expired_active_offer_is_not_active(self):
        self.assertFalse(compute_active_flag(["coupon"], "2026-08-01", ref_date=date(2026, 8, 4), expiry_date="2026-08-03"))
        self.assertTrue(compute_active_flag(["coupon"], "2026-08-01", ref_date=date(2026, 8, 2), expiry_date="2026-08-03"))

    def test_source_cap_and_url_dedupe(self):
        items = [
            {"source": "a", "date": "2026-08-04", "key": "a1", "url_key": "u1"},
            {"source": "a", "date": "2026-08-03", "key": "a2", "url_key": "u2"},
            {"source": "a", "date": "2026-08-02", "key": "a3", "url_key": "u3"},
        ]
        capped = cap_items_per_source(items, cap=2)
        self.assertEqual([item["key"] for item in capped], ["a1", "a2"])
        duplicate = {"key": "different", "url_key": "u1"}
        self.assertEqual(len(dedupe_items_within_run(capped + [duplicate])), 2)

    def test_active_deal_flag_is_additive(self):
        self.assertFalse(compute_active_flag(["discount"], "2026-08-04", ref_date=date(2026, 8, 4)))
        self.assertFalse(compute_active_flag(["coupon"], "2026-07-01", ref_date=date(2026, 8, 4)))
        self.assertTrue(compute_active_flag(["coupon"], "2026-08-01", ref_date=date(2026, 8, 4)))


class HtmlExtractionTests(unittest.TestCase):
    def test_undated_html_index_drops_historical_keyword_match(self):
        from unittest import mock
        import deals

        entry = {"id": "html", "type": "html", "company": "OpenAI", "platform": "openai",
                 "category": "model-provider", "priority": 2, "url": "https://example.test/news"}
        old_index = "<title>News</title><p>Our 2024 student discount promo is archived.</p>"
        with mock.patch.object(deals, "read_url", return_value=old_index):
            self.assertEqual(deals.scan_source(entry), [])

    def test_undated_html_current_signal_is_retained(self):
        from unittest import mock
        import deals

        entry = {"id": "html", "type": "html", "company": "OpenAI", "platform": "openai",
                 "category": "model-provider", "priority": 2, "url": "https://example.test/news"}
        current = "<title>Free Credits</title><p>Currently available to all new users.</p>"
        with mock.patch.object(deals, "read_url", return_value=current):
            self.assertEqual(len(deals.scan_source(entry)), 1)

    def test_strip_html(self):
        html = ("<html><body><h1>Free Credits</h1><p>Get <b>90% off</b> today "
                "&amp; more!</p></body></html>")
        text = strip_html(html)
        self.assertIn("Free Credits", text)
        self.assertIn("90% off", text)
        self.assertIn("&", text)  # entities decoded
        self.assertNotIn("<h1>", text)

    def test_html_to_text_extracts_title_and_removes_script_style(self):
        html = (
            "<html><head><title>Free Credits Bonanza</title>"
            "<style>.x{color:red}</style></head>"
            "<body><p>Get <b>90% off</b> now</p><script>alert('xss')</script>"
            "</body></html>"
        )
        title, text = html_to_text(html)
        self.assertEqual(title, "Free Credits Bonanza")
        self.assertIn("90% off", text)
        self.assertIn("Get", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("<p>", text)

    def test_truncate(self):
        self.assertEqual(truncate("abc", 5), "abc")
        self.assertEqual(truncate("abcdef", 3), "abc")


class GithubAuthHeaderTests(unittest.TestCase):
    def test_no_token_means_no_auth_header_anywhere(self):
        """No token -> no Authorization header, even for GitHub API URLs."""
        self.assertEqual(github_headers("https://api.github.com/repos/sst/opencode/releases?per_page=5", None), {})
        self.assertEqual(github_headers("https://api.github.com/repos/sst/opencode/releases?per_page=5", ""), {})
        self.assertEqual(github_headers("https://api.github.com/repos/sst/opencode/releases?per_page=5", "   "), {})

    def test_non_github_url_never_gets_token(self):
        """The Bearer token must never leak to non-GitHub hosts."""
        self.assertEqual(github_headers("https://cursor.com/changelog", "secret-token"), {})
        self.assertEqual(github_headers("https://github.blog/changelog/feed/", "secret-token"), {})
        self.assertEqual(github_headers("https://github.com/example/repo", "secret-token"), {})

    def test_github_api_url_with_token_gets_bearer(self):
        self.assertEqual(
            github_headers("https://api.github.com/repos/anthropics/claude-code/releases?per_page=5", "tok-123"),
            {"Authorization": "Bearer tok-123"},
        )
        self.assertEqual(
            github_headers("https://api.github.com/orgs/moonshotai/repos?per_page=10&sort=pushed", "tok-123"),
            {"Authorization": "Bearer tok-123"},
        )

    def test_no_url_is_safe(self):
        self.assertEqual(github_headers(None, "tok"), {})
        self.assertEqual(github_headers("", "tok"), {})

    def test_read_url_merges_token_only_for_github_api(self):
        """Integration: read_url applies extra headers and never leaks them."""
        from unittest import mock

        import deals

        captured = []

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, n=-1):
                return b""

        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return FakeResp()

        with mock.patch.object(deals, "urlopen", side_effect=fake_urlopen):
            # GitHub API entry -> token attached
            gh_entry = entry_by_id("opencode-releases")
            deals.read_url(gh_entry["url"], headers=github_headers(gh_entry["url"], "tok-abc"))
            # Non-GitHub host -> token NOT attached
            deals.read_url("https://cursor.com/changelog", headers=github_headers("https://cursor.com/changelog", "tok-abc"))

        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0].get_header("Authorization"), "Bearer tok-abc")
        self.assertIsNone(captured[1].get_header("Authorization"))


class FeedParsingTests(unittest.TestCase):
    RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Feed</title><link>http://example.com</link><description>d</description>
  <item>
    <title>Launch Promotion: 50% off</title>
    <link>http://example.com/promo</link>
    <pubDate>Tue, 04 Aug 2026 12:00:00 GMT</pubDate>
    <description><![CDATA[Get <b>Free Credits</b> today]]></description>
  </item>
  <item>
    <title>Plain update</title>
    <link>http://example.com/plain</link>
    <pubDate>Mon, 03 Aug 2026 09:00:00 GMT</pubDate>
    <description>Nothing here</description>
  </item>
</channel></rss>"""

    ATOM_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Early Access for enterprise credits</title>
    <link href="http://example.com/atom/1"/>
    <published>2026-08-04T08:00:00Z</published>
    <summary>Beta pricing preview</summary>
  </entry>
</feed>"""

    def test_rss_parse_fields(self):
        items = parse_feed(self.RSS_XML)
        self.assertEqual(len(items), 2)
        first = items[0]
        self.assertEqual(first["title"], "Launch Promotion: 50% off")
        self.assertEqual(first["link"], "http://example.com/promo")
        self.assertEqual(first["date_raw"], "Tue, 04 Aug 2026 12:00:00 GMT")
        self.assertEqual(first["description"], "Get Free Credits today")

    def test_atom_parse_fields(self):
        items = parse_feed(self.ATOM_XML)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "Early Access for enterprise credits")
        self.assertEqual(item["link"], "http://example.com/atom/1")
        self.assertEqual(item["date_raw"], "2026-08-04T08:00:00Z")
        self.assertEqual(item["description"], "Beta pricing preview")

    def test_github_releases_parse(self):
        payload = json.dumps([
            {
                "tag_name": "v1.0",
                "name": "Launch",
                "published_at": "2026-08-04T00:00:00Z",
                "html_url": "http://example.com/releases/v1.0",
                "body": "Get 90% off during launch promotion",
            },
            {
                "tag_name": "v0.9",
                "name": None,
                "published_at": "2026-07-01T00:00:00Z",
                "html_url": "http://example.com/releases/v0.9",
                "body": None,
            },
        ])
        items = parse_github_releases(payload)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "v1.0 - Launch")
        self.assertEqual(items[0]["date_raw"], "2026-08-04T00:00:00Z")
        self.assertIn("90% off", items[0]["description"])
        self.assertEqual(items[1]["title"], "v0.9")

    def test_github_releases_empty_and_invalid(self):
        self.assertEqual(parse_github_releases("[]"), [])
        with self.assertRaises(ValueError):
            parse_github_releases('{"not": "a list"}')

    def test_github_org_repos_parse(self):
        payload = json.dumps([
            {
                "full_name": "MoonshotAI/kimi-code",
                "html_url": "http://example.com/kimi-code",
                "pushed_at": "2026-08-04T11:13:16Z",
                "description": "Kimi Code CLI - free trial for students",
            }
        ])
        items = parse_github_org_repos(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "MoonshotAI/kimi-code")
        self.assertEqual(items[0]["date_raw"], "2026-08-04T11:13:16Z")

    def test_normalize_date(self):
        self.assertEqual(normalize_date("2026-08-04T12:00:00Z"), "2026-08-04")
        self.assertEqual(normalize_date("Tue, 04 Aug 2026 12:00:00 GMT"), "2026-08-04")
        self.assertEqual(normalize_date(""), "Unknown")
        self.assertEqual(normalize_date(None), "Unknown")
        self.assertEqual(normalize_date("garbage"), "Unknown")


class RegistrySanityTests(unittest.TestCase):
    def test_every_entry_valid(self):
        for entry in ENTRIES:
            with self.subTest(entry=entry["id"]):
                self.assertTrue(entry["url"].startswith(("http://", "https://")),
                                f"{entry['id']} url invalid: {entry['url']}")
                self.assertTrue(entry.get("company"), f"{entry['id']} missing company")
                self.assertIn(entry.get("category"), ("coding-platform", "model-provider"),
                              f"{entry['id']} bad category")
                self.assertTrue(entry.get("id"))
                self.assertIn(entry.get("type"),
                              ("github_releases", "github_org_repos", "rss", "html"))
                self.assertIn(entry["platform"], PLATFORM_MAP,
                              f"{entry['id']} platform {entry['platform']} not in map")
                self.assertIsNotNone(entry_by_id(entry["id"]))

    def test_priority_platforms_are_in_map(self):
        for name in P1_PLATFORMS:
            with self.subTest(platform=name):
                self.assertIn(name, PLATFORM_MAP)
                self.assertTrue(entries_for_platform(name), f"{name} maps to no entries")
        for name in P2_PLATFORMS:
            with self.subTest(provider=name):
                self.assertIn(name, PLATFORM_MAP)
                self.assertTrue(entries_for_platform(name), f"{name} maps to no entries")

    def test_all_expected_platform_names_present(self):
        expected = set(P1_PLATFORMS) | set(P2_PLATFORMS)
        self.assertTrue(expected.issubset(platform_names()))

    def test_unique_entries_no_duplicate_fetch_ids(self):
        ids = [e["id"] for e in unique_entries()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(unique_entries()), len(ENTRIES))

    def test_openai_fetched_once_across_both_tiers(self):
        """openai/codex (P1) and openai (P2) must share entries, not duplicate."""
        p1 = entries_for_platform("openai/codex")
        p2 = entries_for_platform("openai")
        self.assertEqual([e["id"] for e in p1], [e["id"] for e in p2])


class FlaggedItemPipelineTests(unittest.TestCase):
    def test_dalle_launch_wording_is_not_current_promotion_evidence(self):
        from deals import _to_item

        item = _to_item(entry_by_id("openai-news-rss"), {
            "title": "DALL·E now available in beta",
            "link": "https://openai.com/index/dall-e-now-available-in-beta",
            "date_raw": "2022-07-20",
            "description": "DALL·E now available in beta with free credits.",
        })

        self.assertIsNotNone(item)
        self.assertFalse(item["active"])
        self.assertFalse(item["is_active_deal"])

    def test_quick_scan_drops_stale_dalle_item_even_when_marked_active(self):
        from deals import format_compact, run_scan

        stale_dalle = {
            "company": "OpenAI",
            "title": "DALL·E now available in beta",
            "url": "https://openai.com/index/dall-e-now-available-in-beta",
            "date": "2022-07-20",
            "keywords": ["now-available"],
            "source": "openai-news-rss",
            "platform": "openai",
            "priority": 1,
            "summary": "DALL·E now available in beta",
            "expiry_date": "Unknown",
            "key": make_key("OpenAI", "DALL·E now available in beta"),
            "url_key": make_url_key("https://openai.com/index/dall-e-now-available-in-beta"),
            "active": True,
            "is_active_deal": False,
        }
        # run_scan stamps its own UTC "today", so the fresh item must be dated today.
        fresh = dict(stale_dalle, title="Fresh OpenAI promotion",
                     date=datetime.now(timezone.utc).date().isoformat(),
                     key=make_key("OpenAI", "Fresh OpenAI promotion"),
                     url_key=make_url_key("https://example.test/fresh"),
                     active=False, is_active_deal=False)
        entry = {"id": "openai-news-rss", "type": "rss"}

        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, "deals_state.json")
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump({"last_run": "2022-07-20 00:00 UTC",
                           "keys": [stale_dalle["key"]]}, fh)
            with patch("deals.scan_source", return_value=[stale_dalle, fresh]):
                result = run_scan(entries=[entry], quick=True, state_file=state_path,
                                  freshness_days=14, max_workers=1)

        self.assertEqual([item["title"] for item in result["items"]], [fresh["title"]])
        self.assertEqual([item["title"] for item in result["new_items"]], [fresh["title"]])
        compact = format_compact(result)
        self.assertNotIn("DALL·E now available in beta", compact)
        self.assertIn("Fresh OpenAI promotion", compact)

    def test_flag_flow_marks_promo_and_launch(self):
        """Integration: classify -> key -> dedupe -> new detection."""
        from deals import _to_item  # imported lazily to avoid CLI side effects

        entry = entry_by_id("cursor-changelog")
        raw = {
            "title": "Introducing our new agent with free credits",
            "link": "https://cursor.com/changelog#agent",
            "date_raw": "2026-08-04T10:00:00Z",
            "description": "Limited time offer",
        }
        item = _to_item(entry, raw)
        self.assertIsNotNone(item)
        self.assertEqual(item["company"], "Cursor")
        self.assertIn("free credits", item["keywords"])
        self.assertIn("new-agent-product", item["keywords"])
        self.assertEqual(item["date"], "2026-08-04")

        # Unrelated item -> not flagged at all.
        raw2 = {"title": "Bug fixes and perf", "link": "https://cursor.com", "date_raw": "", "description": ""}
        self.assertIsNone(_to_item(entry, raw2))

    def test_to_item_adds_internal_dedupe_and_active_metadata(self):
        from deals import _to_item

        entry = entry_by_id("openai-news-rss")
        item = _to_item(entry, {
            "title": "Coupon code SAVE20",
            "link": "https://example.test/deal?utm_source=rss",
            "date_raw": "2026-08-04T00:00:00Z",
            "description": "Use the code today.",
        })
        self.assertEqual(item["url_key"], make_url_key("https://example.test/deal?utm_source=rss"))
        self.assertTrue(item["is_active_deal"])


if __name__ == "__main__":
    unittest.main()
