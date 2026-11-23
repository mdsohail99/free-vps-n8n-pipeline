# 🛡️ DevOps Operations, Log Tuning & Error Glossary

This document details critical operational considerations, log rotation adjustments, and API failure remediation procedures for maintaining your Always Free tier n8n host.

---

## 💾 1. VPS Disk & Log Rotation Management

Oracle Cloud's Always Free tier instances typically have 47GB of root storage space. Over time, Docker container execution logs can grow and exhaust disk space. 

To configure automatic log pruning for the `n8n` and `caddy` containers:

### Option A: Configure Global Docker Daemon Limits (Recommended)
Edit `/etc/docker/daemon.json` on your host:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```
Then restart the Docker engine:
```bash
sudo systemctl restart docker
```

### Option B: Retrieve Container Disk Usage
```bash
# Check overall disk capacity
df -h

# Check Docker space metrics
docker system df
```

---

## 🔄 2. Automated Weekly Maintenance & Safe Upgrades

To prevent instances from falling behind upstream releases or accumulating disk bloat, this repository includes an autonomous full-stack maintenance engine: [`infrastructure/vps_weekly_maintenance.py`](../infrastructure/vps_weekly_maintenance.py).

### How It Works:
1. **Host OS & Docker Engine**: Non-interactive `apt-get update && apt-get -y upgrade` to apply Linux kernel & package security patches.
2. **Atomic SQLite Backup**: Uses Python's native `sqlite3.backup` API against the active n8n database file without stopping the container.
3. **Automated Rollback**: Re-creates containers on `:latest` and queries `http://127.0.0.1:5678/healthz`. If unhealthy, it automatically restores the SQLite backup and restarts the previous container.
4. **PostgreSQL Dump (if running Aifo or external DB)**: Generates a timestamped `pg_dump` into `/home/ubuntu/aifo_backups/`.
5. **Strict 2-Backup Retention**: Automatically purges older backup files, strictly retaining the **latest 2 copies** (~64 MB total) to protect the Always Free 47GB storage quota.
6. **Docker Image Pruning**: Executes `docker image prune -f` after each run to delete dangling layers.

### Enabling the Weekly Cron:
Run this on your VPS host to schedule autonomous runs every Sunday at 3:00 AM AWST (Saturday 19:00 UTC):
```bash
(crontab -l 2>/dev/null; echo "0 19 * * 6 /usr/bin/python3 /home/ubuntu/maintenance/vps_weekly_maintenance.py >> /var/log/vps_weekly_maintenance.log 2>&1") | crontab -
```

---

## 🌐 3. API Failure & Error Code Glossary

### Notion API Errors

| Error Code | API Response Message | Cause | Resolution |
|---|---|---|---|
| **400** | `validation_error` / `body.children should be defined` | Double JSON serialization of block array (Common in n8n code blocks). | Update node code to pass a direct JavaScript object instead of calling `JSON.stringify()`. |
| **401** | `API token is invalid` | Missing or incorrect token in the `Authorization` header. | Verify `$env.NOTION_INTEGRATION_TOKEN` contains `Bearer ntn_...` prefix. |
| **404** | `object_not_found` | Notion Database ID is incorrect or the Integration does not have permissions to access the database page. | 1. Double-check your Notion database ID.<br>2. On the Notion Database UI page, click `...` → `Connections` → Add your Integration. |

### Slack API Errors

| Error Code | Cause | Resolution |
|---|---|---|
| **400** (Bad Request) | Invalid Block Kit layout JSON format payload. | Validate block JSON formatting in Slack's official [Block Kit Builder](https://app.slack.com/block-kit-builder). |
| **403** (Forbidden) | The Slack Webhook URL is invalid or has been revoked. | Generate a new Incoming Webhook URL in your Slack App admin dashboard. |

---

## 🧪 4. Local Sandbox Test Verification Guide

Before deploying a modified workflow file (`ai_daily_briefing_workflow.json`) to your live production host, you can run the offline Node.js test suite to check syntax errors, reference hooks, and schema formatting.

```bash
# 1. Install Node.js dependencies
npm install

# 2. Run local test execution harness
node sandbox_test.mjs
```
The test runner validates Node parameters, schedule triggers, SSH commands, Notion payload structure, and Sunday Weekly rollup logic.
