# 🤖 AI Daily Briefing Workflow

An autonomous, 18-node production n8n workflow that crawls multi-source AI news, parses benchmark releases, queries OpenRouter free LLMs, inserts structured 6-section entries into Notion, and dispatches daily executive briefings to Slack.

---

## 📸 Workflow Architecture & Node Tree

```
⏰ Cron Trigger (7 AM)
  │
  ├── 🔍 Run Research Engine (Python Scraper: HackerNews, Techmeme, Reddit, Web)
  │
  ├── 📡 Fetch OpenRouter Live Model Pricing
  │
  ├── 🤖 OpenRouter LLM Synthesis (Free Router / NVIDIA Nemotron 70B)
  │
  ├── 📝 Parse Markdown → Notion Block Chunks
  │
  ├── 📄 Insert Page into Notion Database Archive
  │
  ├── 🗄️ Run 30-Day Automated Page Retention Pruning
  │
  └── 💬 Deliver Formatted Executive Summary Card to Slack
```

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
