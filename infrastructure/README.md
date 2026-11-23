# 🐳 Infrastructure Setup & Scripts

This directory contains the core infrastructure deployment scripts, container definitions, and database generators for hosting n8n on Oracle Cloud Free Tier.

---

## 📁 Files Included

- **`vps_setup.sh`**: Automated 1-command bash installer script. Configures Ubuntu system packages, installs Docker Engine, sets up UFW/iptables rules, and configures container firewall.
- **`vps_weekly_maintenance.py`**: Full-stack automated weekly maintenance engine. Takes atomic SQLite backups of n8n and PostgreSQL dumps of Aifo, pulls latest images, verifies health endpoints with auto-rollback, enforces strict 2-backup storage retention, and prunes dangling Docker images.
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

# 3. (Optional) Run Safe Maintenance & Upgrades Manually
python3 infrastructure/vps_weekly_maintenance.py

# 4. (Optional) Set up Autonomous Weekly Maintenance Cron (Runs every Sunday at 3 AM AWST / Sat 19:00 UTC)
(crontab -l 2>/dev/null; echo "0 19 * * 6 /usr/bin/python3 $(pwd)/infrastructure/vps_weekly_maintenance.py >> /var/log/vps_weekly_maintenance.log 2>&1") | crontab -
```
