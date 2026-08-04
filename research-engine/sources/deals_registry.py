"""deals_registry.py — data-driven registry of official deal-intelligence sources.

Every entry is ONE fetch target: a URL plus the parser type needed to read it.
Platforms (Cursor, OpenAI, ...) map to one or more entry ids via ``PLATFORM_MAP``.
The scanner fetches each unique entry id at most once, so a platform that shares
an entry with another platform (e.g. ``openai`` / ``openai/codex`` both point at
the OpenAI Codex GitHub releases) is never double-fetched.

Entry fields:
    id        — unique stable identifier (used in state/error reporting)
    platform  — primary platform key (one of the keys in PLATFORM_MAP)
    company   — display name used in the output bullets and dedupe keys
    category  — "coding-platform" | "model-provider"
    priority  — 1 (AI coding platforms) or 2 (model providers)
    type      — parser type:
                * "github_releases"   — GitHub releases API JSON array
                * "github_org_repos"  — GitHub org repos JSON array (sorted by pushed)
                * "rss"               — RSS 2.0 or Atom XML feed
                * "html"              — HTML page (title + first ~8000 chars of text)
    url       — official source URL
    max_bytes — optional cap on the raw bytes read (keeps big pages fast)

Degradation policy: sources known to 404/403/fail TLS (google blog feed, AWS
whats-new feed, qwenlm feed, qwen.ai, zai-org/z-evals, ...) are KEPT in this
registry on purpose — the scanner logs them as failed and never crashes.

GitHub token support: every ``github_releases`` / ``github_org_repos`` entry
(api.github.com) transparently supports the optional ``GITHUB_TOKEN`` env var
(read in deals.py, never logged or persisted). With a token the unauthenticated
60 req/hr GitHub API limit becomes 5000 req/hr, so release announcements on
these entries are not silently missed under heavy scanning.
"""

ENTRIES = [
    # ── Priority 1: AI coding platforms ──────────────────────────────────────
    {
        "id": "cursor-changelog",
        "platform": "cursor",
        "company": "Cursor",
        "category": "coding-platform",
        "priority": 1,
        "type": "html",
        "url": "https://cursor.com/changelog",
        "max_bytes": 400000,
    },
    {
        "id": "qoder-home",
        "platform": "qoder",
        "company": "Qoder",
        "category": "coding-platform",
        "priority": 1,
        "type": "html",
        "url": "https://qoder.com",
        "max_bytes": 400000,
    },
    {
        "id": "opencode-releases",
        "platform": "opencode",
        "company": "OpenCode",
        "category": "coding-platform",
        "priority": 1,
        "type": "github_releases",
        "url": "https://api.github.com/repos/sst/opencode/releases?per_page=5",
    },
    {
        "id": "claude-code-releases",
        "platform": "claude-code",
        "company": "Claude Code",
        "category": "coding-platform",
        "priority": 1,
        "type": "github_releases",
        "url": "https://api.github.com/repos/anthropics/claude-code/releases?per_page=5",
    },
    {
        "id": "openai-codex-releases",
        "platform": "openai",
        "company": "OpenAI",
        "category": "coding-platform",
        "priority": 1,
        "type": "github_releases",
        "url": "https://api.github.com/repos/openai/codex/releases?per_page=5",
    },
    {
        "id": "openai-news-rss",
        "platform": "openai",
        "company": "OpenAI",
        "category": "model-provider",
        "priority": 1,
        "type": "rss",
        "url": "https://openai.com/news/rss.xml",
        "max_bytes": 800000,
    },
    {
        "id": "google-blog-ai-feed",
        "platform": "google-ai-studio",
        "company": "Google AI",
        "category": "model-provider",
        "priority": 1,
        "type": "rss",
        "url": "https://blog.google/technology/ai/feed/",
        "max_bytes": 800000,
    },
    {
        "id": "windsurf-changelog",
        "platform": "windsurf",
        "company": "Windsurf",
        "category": "coding-platform",
        "priority": 1,
        "type": "html",
        "url": "https://windsurf.com/changelog",
        "max_bytes": 400000,
    },
    {
        "id": "kiro-home",
        "platform": "kiro",
        "company": "Kiro",
        "category": "coding-platform",
        "priority": 1,
        "type": "html",
        "url": "https://kiro.dev",
        "max_bytes": 400000,
    },
    {
        "id": "github-blog-changelog-feed",
        "platform": "github-copilot",
        "company": "GitHub Copilot",
        "category": "coding-platform",
        "priority": 1,
        "type": "rss",
        "url": "https://github.blog/changelog/feed/",
        "max_bytes": 800000,
    },
    {
        "id": "aws-whats-new-feed",
        "platform": "amazon-q",
        "company": "Amazon Q",
        "category": "coding-platform",
        "priority": 1,
        "type": "rss",
        "url": "https://aws.amazon.com/about-aws/whats-new/feed/",
        "max_bytes": 800000,
    },

    # ── Priority 2: model providers ──────────────────────────────────────────
    {
        "id": "anthropic-news",
        "platform": "anthropic",
        "company": "Anthropic",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://www.anthropic.com/news",
        "max_bytes": 400000,
    },
    {
        "id": "qwen-releases",
        "platform": "qwen",
        "company": "Qwen",
        "category": "model-provider",
        "priority": 2,
        "type": "github_releases",
        "url": "https://api.github.com/repos/QwenLM/Qwen3/releases?per_page=5",
    },
    {
        "id": "qwen-blog-feed",
        "platform": "qwen",
        "company": "Qwen",
        "category": "model-provider",
        "priority": 2,
        "type": "rss",
        "url": "https://qwenlm.github.io/blog/feed.xml",
        "max_bytes": 800000,
    },
    {
        "id": "qwencloud-home",
        "platform": "qwencloud",
        "company": "QwenCloud",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://www.qwen.ai",
        "max_bytes": 400000,
    },
    {
        "id": "zai-home",
        "platform": "zai",
        "company": "Z.ai",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://z.ai",
        "max_bytes": 400000,
    },
    {
        "id": "zai-zevals-releases",
        "platform": "zai",
        "company": "Z.ai",
        "category": "model-provider",
        "priority": 2,
        "type": "github_releases",
        "url": "https://api.github.com/repos/zai-org/z-evals/releases?per_page=5",
    },
    {
        "id": "deepseek-news",
        "platform": "deepseek",
        "company": "DeepSeek",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://api-docs.deepseek.com/news/news0809",
        "max_bytes": 400000,
    },
    {
        "id": "deepseek-v3-releases",
        "platform": "deepseek",
        "company": "DeepSeek",
        "category": "model-provider",
        "priority": 2,
        "type": "github_releases",
        "url": "https://api.github.com/repos/deepseek-ai/DeepSeek-V3/releases?per_page=5",
    },
    {
        "id": "moonshot-github",
        "platform": "moonshot",
        "company": "Moonshot AI",
        "category": "model-provider",
        "priority": 2,
        "type": "github_org_repos",
        "url": "https://api.github.com/orgs/moonshotai/repos?per_page=10&sort=pushed",
    },
    {
        "id": "moonshot-kimi",
        "platform": "moonshot",
        "company": "Moonshot AI",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://kimi.ai",
        "max_bytes": 400000,
    },
    {
        "id": "minimax-home",
        "platform": "minimax",
        "company": "MiniMax",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://www.minimax.io",
        "max_bytes": 400000,
    },
    {
        "id": "xai-home",
        "platform": "xai",
        "company": "xAI",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://x.ai",
        "max_bytes": 400000,
    },
    {
        "id": "xai-grok1-releases",
        "platform": "xai",
        "company": "xAI",
        "category": "model-provider",
        "priority": 2,
        "type": "github_releases",
        "url": "https://api.github.com/repos/xai-org/grok-1/releases?per_page=5",
    },
    {
        "id": "mistral-home",
        "platform": "mistral",
        "company": "Mistral",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://mistral.ai",
        "max_bytes": 400000,
    },
    {
        "id": "mistral-inference-releases",
        "platform": "mistral",
        "company": "Mistral",
        "category": "model-provider",
        "priority": 2,
        "type": "github_releases",
        "url": "https://api.github.com/repos/mistralai/mistral-inference/releases?per_page=5",
    },
    {
        "id": "cohere-blog",
        "platform": "cohere",
        "company": "Cohere",
        "category": "model-provider",
        "priority": 2,
        "type": "html",
        "url": "https://cohere.com/blog/rss.xml",
        "max_bytes": 400000,
    },
    {
        "id": "cohere-toolkit-releases",
        "platform": "cohere",
        "company": "Cohere",
        "category": "model-provider",
        "priority": 2,
        "type": "github_releases",
        "url": "https://api.github.com/repos/cohere-ai/cohere-toolkit/releases?per_page=5",
    },
]

# Platform key -> ordered entry ids. Keys cover BOTH the Priority-1 platform names
# and the Priority-2 provider names from the spec; the sanity tests assert that.
PLATFORM_MAP = {
    # Priority 1 — AI coding platforms
    "cursor": ["cursor-changelog"],
    "qoder": ["qoder-home"],
    "opencode": ["opencode-releases"],
    "claude-code": ["claude-code-releases"],
    "openai/codex": ["openai-codex-releases", "openai-news-rss"],
    "google-ai-studio": ["google-blog-ai-feed"],
    "windsurf": ["windsurf-changelog"],
    "kiro": ["kiro-home"],
    "github-copilot": ["github-blog-changelog-feed"],
    "amazon-q": ["aws-whats-new-feed"],
    # Priority 2 — model providers
    "openai": ["openai-codex-releases", "openai-news-rss"],
    "anthropic": ["claude-code-releases", "anthropic-news"],
    "google": ["google-blog-ai-feed"],
    "qwen": ["qwen-releases", "qwen-blog-feed"],
    "qwencloud": ["qwencloud-home"],
    "zai": ["zai-home", "zai-zevals-releases"],
    "deepseek": ["deepseek-news", "deepseek-v3-releases"],
    "moonshot": ["moonshot-github", "moonshot-kimi"],
    "minimax": ["minimax-home"],
    "xai": ["xai-home", "xai-grok1-releases"],
    "mistral": ["mistral-home", "mistral-inference-releases"],
    "cohere": ["cohere-blog", "cohere-toolkit-releases"],
}

# Canonical platform/provider names the spec requires to be present.
P1_PLATFORMS = [
    "cursor", "qoder", "opencode", "claude-code", "openai/codex",
    "google-ai-studio", "windsurf", "kiro", "github-copilot", "amazon-q",
]
P2_PLATFORMS = [
    "openai", "anthropic", "google", "qwen", "qwencloud", "zai",
    "deepseek", "moonshot", "minimax", "xai", "mistral", "cohere",
]

_ENTRIES_BY_ID = {e["id"]: e for e in ENTRIES}


def all_entries():
    """Return the full registry as a list of entry dicts."""
    return list(ENTRIES)


def entry_by_id(entry_id):
    """Return the entry with the given id, or None."""
    return _ENTRIES_BY_ID.get(entry_id)


def entries_for_platform(platform):
    """Return the ordered list of entries mapped to a platform key."""
    return [_ENTRIES_BY_ID[i] for i in PLATFORM_MAP.get(platform, []) if i in _ENTRIES_BY_ID]


def platform_names():
    """Return all platform keys (both priority tiers)."""
    return set(PLATFORM_MAP.keys())


def unique_entries():
    """Return every distinct entry exactly once (platform sharing never double-fetches)."""
    seen = set()
    out = []
    for e in ENTRIES:
        if e["id"] not in seen:
            seen.add(e["id"])
            out.append(e)
    return out
