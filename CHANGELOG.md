# 📜 Changelog

All notable changes to the `free-vps-n8n-pipeline` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [1.1.0] - 2026-11-24

### Added
- 🛡️ **Full-Stack Safe Weekly Maintenance Engine** (`infrastructure/vps_weekly_maintenance.py`): Automated zero-downtime maintenance script providing non-interactive Host OS package upgrades, live atomic SQLite backups via `sqlite3.backup`, PostgreSQL database dumps, container image updates, automated rollback on failed `/healthz` checks, strict 2-backup storage retention, and dangling Docker image pruning.
- 🔄 **Docker Compose Update**: Defaulted n8n container image to `docker.n8n.io/n8nio/n8n:latest` across `docker-compose.yml` and `infrastructure/docker-compose.yml` to prevent self-hosted instances from falling behind upstream releases.
- 🔥 **AI Deals, Pricing & Launch Intelligence** (`research-engine/deals.py` + `deals_core.py` + `sources/deals_registry.py`): Daily scanner of 28 official sources across 10 AI coding platforms (Cursor, Qoder, OpenCode, Claude Code, OpenAI/Codex, Google AI Studio, Windsurf, Kiro, GitHub Copilot, Amazon Q Developer) and 12 model providers (OpenAI, Anthropic, Google DeepMind, Qwen, QwenCloud, Z.ai, DeepSeek, Moonshot AI, MiniMax, xAI, Mistral, Cohere). Flags 29 promotion keywords plus launch signals (new models, benchmarks, context windows, agent products, IDE integrations) with day-over-day state-file dedupe. Optional `GITHUB_TOKEN` env var raises GitHub API rate limit from 60 → 5000 req/hr.
- 🧠 **New briefing section in the AI Daily Briefing workflow** (`ai_daily_briefing_workflow.json`, Nodes 3/6/7/12): The 7AM run now also executes the deals scanner over SSH; the LLM prompt generates structured 17-field promotion cards with 🚨 EXPIRING SOON (≤7 days) / 🔥 LAST CHANCE (≤48 hrs) markers, launch & product intelligence bullets, a "Top Money Saving Opportunity" final summary, and a no-filler fallback line; the Slack morning card surfaces the top deal when one exists. No new Notion properties were added.
- 🧪 **Deals scanner unit tests** (`research-engine/tests/test_deals.py`): 34 tests covering keyword detection, launch signals, RSS/Atom/GitHub/HTML parsing, date normalization, state-file dedupe, registry coverage of all 22 platforms, and GitHub-token header scoping.
- 🔧 **`.gitignore` fix**: anchored `tests/` to `/tests/` so `research-engine/tests/` is tracked while root firewall tests stay ignored.

---

## [1.0.0] - 2026-07-15

### Added
- 🚀 **Turnkey Oracle Cloud Free Tier Bootstrap Script (`vps_setup.sh`)**: Automates Docker engine, Caddy auto-HTTPS reverse proxy, iptables firewall tuning, and n8n container deployment on ARM (aarch64).
- ⚙️ **Production AI Daily Briefing Workflow (`ai_daily_briefing_workflow.json`)**: 18-node automated pipeline featuring daily scraping, OpenRouter model routing, Notion page insertion, block appending, local archiving, and real-time Slack alerts.
- 📡 **Multi-Source News Crawler Engine (`research-engine/`)**: Standard Python 3.12 library parser fetching HackerNews, Techmeme, Reddit, and web news streams.
- 🗄️ **Automated Notion Database Builder (`setup_notion_db.py`)**: 1-command Python script to auto-generate the Notion report database schema with custom multi-select tags and views.
- 🧪 **Offline Sandbox Test Suite (`sandbox_test.mjs`)**: Node.js mock execution validator for offline workflow testing.
- 📸 **Comprehensive Visual Asset Portfolio (`images/`)**: High-res dark mode visual screenshots covering repository architecture, VPS host status, n8n visual graph, Slack morning alerts, and 6-page Notion catalog.
- 📁 **Modular Multi-Workflow Architecture**: Created standard taxonomy under `workflows/<category>/<workflow-name>/` for long-term project expansion.
