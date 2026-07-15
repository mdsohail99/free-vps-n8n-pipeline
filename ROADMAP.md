# 🗺️ Project Roadmap

This document outlines the development direction, planned features, and community vision for `free-vps-n8n-pipeline`. Our goal is to maintain a reference library of production-ready, zero-cost automation workflows running on self-hosted infrastructure.

---

## 🎯 Current Status (Version 1.0.0)

- [x] **Automated VPS Bootstrap (`infrastructure/vps_setup.sh`)**: 1-command installer script for Oracle Cloud Free Tier ARM VPS.
- [x] **Dockerized Reverse Proxy Stack**: n8n + Caddy 2 with automatic Let's Encrypt TLS/SSL cert management.
- [x] **AI Daily Briefing Workflow (`workflows/ai-intelligence/ai-daily-briefing/`)**: Complete end-to-end 18-node news intelligence pipeline.
- [x] **Multi-Source Crawler Engine (`research-engine/`)**: HackerNews, Techmeme, Reddit, and web scraper with zero pip dependencies.
- [x] **Notion Schema Automation (`infrastructure/setup_notion_db.py`)**: Automatic Notion database structure generator.
- [x] **Dual Delivery System**: Automated 6-section Notion intelligence catalog archive + formatted Slack morning alerts.

---

## 🚀 Upcoming Releases & Future Vision

### Phase 2: Infrastructure Expansion & One-Click Deployments
- [ ] 🛠️ **Terraform / Ansible One-Click Blueprints**: Automated provisioning for AWS Lightsail, Hetzner, and DigitalOcean free/cheap tiers.
- [ ] 💾 **Automated Backup & Disaster Recovery**: Script to back up n8n workflows, credentials database, and `.env` configs to encrypted remote storage.
- [ ] 📊 **VPS Monitoring Dashboard**: Integrated Lightweight Prometheus & Grafana stack for CPU, memory, and container uptime tracking.

### Phase 3: Additional Production Automation Workflows
- [ ] 📧 **Workflow: Smart Email Triage & Summarizer**: Automatic inbox categorization, priority tagging, and AI executive draft generation.
- [ ] 🧾 **Workflow: Autonomous Invoice & Receipt Parser**: Extract line items, totals, and vendor info from email PDFs into Notion/Airtable.
- [ ] 🌐 **Workflow: Uptime & Domain SSL Monitor**: 24/7 endpoint health monitor with instant Slack/Telegram outage notifications.
- [ ] 🐙 **Workflow: GitHub Repository Activity Digest**: Automated weekly release, commit, and pull request summary rollup.

---

## 🤝 Community Feedback & Feature Requests

Have a workflow idea or infrastructure improvement?
- Open a feature request in [GitHub Issues](https://github.com/mdsohail99/free-vps-n8n-pipeline/issues).
- Check our [`CONTRIBUTING.md`](CONTRIBUTING.md) to submit a pull request.
