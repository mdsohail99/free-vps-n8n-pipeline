# 🤖 AI Daily Briefing Workflow

An autonomous, 18-node production n8n workflow that crawls multi-source AI news, parses benchmark releases, scans official sources for **AI deals, pricing & launch intelligence**, queries OpenRouter free LLMs, inserts structured sections into Notion, and dispatches daily executive briefings to Slack.

---

## 📸 Workflow Architecture & Node Tree

```
⏰ Cron Trigger (7 AM)
  │
  ├── 🔍 Run Research Engine (Python Scraper: HackerNews, Techmeme, Reddit, Web)
  │        └── 🔥 Run Deals Scanner (research-engine/deals.py — 28 official sources)
  │              (Cursor, Qoder, OpenCode, Claude Code, OpenAI/Codex, Google AI Studio,
  │               Windsurf, Kiro, GitHub Copilot, Amazon Q + 12 model providers)
  │
  ├── 📡 Fetch OpenRouter Live Model Pricing
  │
  ├── 🤖 OpenRouter LLM Synthesis (Free Router / NVIDIA Nemotron 70B)
  │        └── Includes "🔥 AI Deals, Pricing & Launch Intelligence" section:
  │              promo cards (17 fields), 🚨 EXPIRING SOON / 🔥 LAST CHANCE markers,
  │              launch & product intelligence, "Top Money Saving Opportunity" summary
  │
  ├── 📝 Parse Markdown → Notion Block Chunks
  │
  ├── 📄 Insert Page into Notion Database Archive
  │
  ├── 🗄️ Run 30-Day Automated Page Retention Pruning
  │
  └── 💬 Deliver Formatted Executive Summary Card to Slack (incl. 🔥 Top Deal when present)
```

---

## 🔥 AI Deals, Pricing & Launch Intelligence

The workflow now monitors official sources (changelogs, GitHub releases, RSS feeds, homepages) every day so you never miss:

- New model launches, preview/beta/early-access programs
- Launch discounts, introductory pricing, price drops, off-peak pricing
- Free credits, credits/token multipliers, bonus credits, resource packs
- Free/extended trials, student & startup offers, enterprise credits
- Subscription changes and new API credits

For every promotion the LLM outputs a structured card (**Company | Product | Model | Promotion | Original Price | Discounted Price | Percentage Saved | Eligible Plans | Countries | Start Date | End Date | Remaining Days | Automatic? | Coupon Required? | Can stack? | Official link | My action required | Priority**), marks expiring offers (**🚨 EXPIRING SOON** ≤ 7 days, **🔥 LAST CHANCE** ≤ 48 hrs), and closes with a **Top Money Saving Opportunity / Estimated Savings / Should I switch today?** summary. When nothing new exists it writes exactly: *"No significant discounts or launch promotions detected today."*

The scanner (`research-engine/deals.py`) is stdlib-only, dedupes day-over-day via a state file (`deals_state.json`) so the briefing only surfaces *new* signals, degrades gracefully if a source is down, and supports an optional `GITHUB_TOKEN` env var (GitHub API rate limit 60 → 5000 req/hr).

> **Deploy note:** copy `research-engine/` to `/home/ubuntu/research-engine/` on the VPS so the SSH node can find `deals.py`. Optionally export `GITHUB_TOKEN` in the ubuntu user's environment.

---

## 📦 Directory Contents

- **`workflow.json`**: Production n8n workflow definition file ready for 1-click import.
- **`sample.env`**: Environment variables reference required for workflow execution.
- **`screenshots/`**: Visual execution gallery showing workflow nodes, Notion database output, and Slack alerts.

---

## 🔑 Required Credentials

1. **`Notion API`** (`Header Auth`): Notion Integration Token (`ntn_...`).
2. **`OpenRouter API`** (`Header Auth`): OpenRouter API Key (`sk-or-v1-...`).
3. **`VPS SSH`** (`SSH Key`): SSH Private Key for VPS command execution.

---

## ⚡ Execution Setup

1. Import `workflow.json` into your n8n UI.
2. Ensure your `.env` file on your VPS host contains `NOTION_DATABASE_ID`, `NOTION_INTEGRATION_TOKEN`, and `SLACK_WEBHOOK_URL`.
3. Select your credentials in n8n UI for `Node 6`, `Node 8`, `Node 14`, and `Node 16`.
4. Toggle workflow to **Active**.
