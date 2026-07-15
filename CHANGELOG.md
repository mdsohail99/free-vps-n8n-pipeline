# 📜 Changelog

All notable changes to the `free-vps-n8n-pipeline` project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
