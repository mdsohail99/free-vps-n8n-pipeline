#!/usr/bin/env python3
"""
vps_weekly_maintenance.py - Full-stack weekly updater for entire VPS.

Upgrades:
1. Host OS security patches & Docker engine (`apt-get upgrade`).
2. n8n workflow engine (atomic SQLite backup, pull latest, verify healthz, rollback if failed).
3. Aifo stack (pg_dump PostgreSQL backup, pull compose images, verify /health).
4. Strict storage retention: keeps max 2 backups for n8n and max 2 backups for Aifo.
5. System cleanup: prunes dangling Docker images to prevent disk bloat.
"""

import os
import sys
import time
import glob
import sqlite3
import argparse
import subprocess
import urllib.request

# Paths
N8N_DIR = "/home/ubuntu/n8n"
N8N_BACKUP_DIR = "/home/ubuntu/n8n_backups"
N8N_DB_SOURCE = "/var/lib/docker/volumes/n8n_n8n_data/_data/database.sqlite"
N8N_HEALTH_URL = "http://127.0.0.1:5678/healthz"

AIFO_DIR = "/opt/aifo"
AIFO_BACKUP_DIR = "/home/ubuntu/aifo_backups"
AIFO_HEALTH_URL = "http://127.0.0.1:9101/health"

MAX_BACKUPS = 2


def run_cmd(cmd, cwd=None, check=True):
    res = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed [{cmd}]: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout.strip()


def prune_dir(directory, pattern, max_keep=MAX_BACKUPS):
    files = sorted(glob.glob(os.path.join(directory, pattern)), key=os.path.getmtime)
    while len(files) > max_keep:
        oldest = files.pop(0)
        try:
            os.remove(oldest)
            print(f"  [Storage] Purged old backup: {os.path.basename(oldest)}")
        except OSError as e:
            print(f"  [Warning] Failed to delete {oldest}: {e}")
    remaining = [os.path.basename(f) for f in sorted(glob.glob(os.path.join(directory, pattern)), key=os.path.getmtime)]
    print(f"  [Storage] Preserved backups ({len(remaining)}/{max_keep}): {', '.join(remaining)}")


def check_url(url, timeout_sec=60):
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MaintenanceCheck/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(3)
    return False


def upgrade_system():
    print("\n[1/4] Upgrading Host OS & Docker Engine Packages...")
    try:
        run_cmd("apt-get update")
        res = run_cmd("DEBIAN_FRONTEND=noninteractive apt-get -y upgrade")
        print("  Host OS packages up to date.")
    except Exception as e:
        print(f"  Warning during apt upgrade: {e}")


def upgrade_n8n():
    print("\n[2/4] Checking & Upgrading n8n Pipeline...")
    os.makedirs(N8N_BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(N8N_BACKUP_DIR, f"n8n_backup_{stamp}.sqlite")

    print(f"  Creating atomic SQLite backup...")
    src = sqlite3.connect(N8N_DB_SOURCE)
    dst = sqlite3.connect(backup_file)
    src.backup(dst)
    dst.close()
    src.close()
    print(f"  Backup created: {os.path.basename(backup_file)} ({os.path.getsize(backup_file) / (1024*1024):.1f} MB)")
    prune_dir(N8N_BACKUP_DIR, "n8n_backup_*.sqlite")

    print("  Pulling latest n8n image and updating container...")
    run_cmd("docker pull docker.n8n.io/n8nio/n8n:latest")
    run_cmd("docker compose up -d", cwd=N8N_DIR)

    print("  Verifying n8n health...")
    if not check_url(N8N_HEALTH_URL, 60):
        print("  CRITICAL: n8n health check failed! Restoring backup...")
        run_cmd("docker compose down", cwd=N8N_DIR, check=False)
        src = sqlite3.connect(backup_file)
        dst = sqlite3.connect(N8N_DB_SOURCE)
        src.backup(dst)
        dst.close()
        src.close()
        run_cmd("docker compose up -d", cwd=N8N_DIR)
        raise RuntimeError("n8n health check failed; rolled back to previous backup.")
    
    version = run_cmd("docker run --rm docker.n8n.io/n8nio/n8n:latest n8n --version", check=False)
    print(f"  n8n is HEALTHY on version {version.strip()}")


def upgrade_aifo():
    print("\n[3/4] Checking & Upgrading Aifo Stack...")
    os.makedirs(AIFO_BACKUP_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(AIFO_BACKUP_DIR, f"aifo_backup_{stamp}.sql")

    print(f"  Dumping Aifo PostgreSQL database...")
    dump_out = run_cmd("docker exec aifo-postgres-1 pg_dump -U aifo -d aifo --no-owner --no-privileges")
    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(dump_out)
    print(f"  Backup created: {os.path.basename(backup_file)} ({os.path.getsize(backup_file) / 1024:.1f} KB)")
    prune_dir(AIFO_BACKUP_DIR, "aifo_backup_*.sql")

    print("  Updating Aifo base images & restarting stack...")
    run_cmd("docker compose pull", cwd=AIFO_DIR, check=False)
    run_cmd("docker compose up -d", cwd=AIFO_DIR)

    print("  Verifying Aifo API health...")
    if not check_url(AIFO_HEALTH_URL, 45):
        raise RuntimeError("Aifo API health check failed after update!")
    print("  Aifo API is HEALTHY.")


def cleanup_storage():
    print("\n[4/4] Storage Hygiene & Pruning...")
    out = run_cmd("docker image prune -f", check=False)
    print("  Dangling docker images cleaned.")
    df_out = run_cmd("df -h / | awk 'NR==2 {print $4 \" available (\" $5 \" used)\"}'")
    print(f"  Disk space: {df_out}")


def main():
    print("==================================================")
    print(f" VPS Safe Maintenance Run: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("==================================================")

    upgrade_system()
    upgrade_n8n()
    upgrade_aifo()
    cleanup_storage()

    print("\n==================================================")
    print(" SUCCESS: All services, Docker, and Host OS updated safely!")
    print("==================================================")


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as err:
        print(f"\n[ERROR] Maintenance failed: {err}", file=sys.stderr)
        sys.exit(1)
