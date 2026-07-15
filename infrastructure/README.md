# 🐳 Infrastructure Setup & Scripts

This directory contains the core infrastructure deployment scripts, container definitions, and database generators for hosting n8n on Oracle Cloud Free Tier.

---

## 📁 Files Included

- **`vps_setup.sh`**: Automated 1-command bash installer script. Configures Ubuntu system packages, installs Docker Engine, sets up UFW/iptables rules, configures swap space, and launches Docker Compose.
- **`docker-compose.yml`**: Docker service definitions for `n8n` and `caddy`.
- **`Caddyfile`**: Automatic Let's Encrypt SSL reverse proxy configuration.
- **`setup_notion_db.py`**: Automated Notion database schema generator script.
- **`.env.example`**: Environment variables template.

---

## 🚀 Usage

```bash
# 1. Execute VPS Bootstrap Script
bash infrastructure/vps_setup.sh

# 2. Generate Notion Database Schema
python3 infrastructure/setup_notion_db.py
```
