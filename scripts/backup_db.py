"""
Automated Database Backup script.
Dumps database schema and data, and uploads to a private GitHub Gist or local storage.
"""

from __future__ import annotations

import os
import subprocess
import datetime
import urllib.request
import json
from core.logger import get_logger

log = get_logger("backup")


def run_db_backup() -> dict[str, str | bool]:
    """
    Dumps database and uploads to private GitHub Gist if GITHUB_TOKEN is provided.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"vhm_backup_{ts}.sql"
    tmp_path = f"/tmp/{backup_filename}"

    db_url = os.getenv("DATABASE_URL", "")
    token = os.getenv("GITHUB_TOKEN")

    # Local SQLite or PostgreSQL backup
    if db_url.startswith("postgres"):
        try:
            subprocess.run(["pg_dump", db_url, "-f", tmp_path], check=True)
            log.info("PostgreSQL dump generated at %s", tmp_path)
        except Exception as exc:
            log.error("pg_dump failed: %s", exc)
            return {"status": "error", "message": f"pg_dump error: {exc}"}
    else:
        # SQLite dump fallback
        try:
            db_path = "vehicle_health.db"
            if os.path.exists(db_path):
                with open(db_path, "rb") as src, open(tmp_path, "wb") as dst:
                    dst.write(src.read())
            log.info("SQLite database file backed up to %s", tmp_path)
        except Exception as exc:
            return {"status": "error", "message": f"SQLite backup error: {exc}"}

    # Upload to private GitHub Gist if GITHUB_TOKEN is present
    if token and os.path.exists(tmp_path):
        try:
            with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(1_000_000)  # Max 1MB for Gist upload

            gist_payload = {
                "description": f"Vehicle Health Monitor DB Backup - {ts}",
                "public": False,
                "files": {backup_filename: {"content": content}},
            }

            req = urllib.request.Request(
                "https://api.github.com/gists",
                data=json.dumps(gist_payload).encode("utf-8"),
                headers={
                    "Authorization": f"token {token}",
                    "User-Agent": "VehicleHealthBackup",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    res_data = json.loads(resp.read().decode("utf-8"))
                    gist_url = res_data.get("html_url")
                    log.info("Database backup uploaded to GitHub Gist: %s", gist_url)
                    return {"status": "success", "gist_url": gist_url, "file": tmp_path}
        except Exception as exc:
            log.error("Failed to upload backup to GitHub Gist: %s", exc)

    return {"status": "success", "file": tmp_path, "message": "Saved to local disk."}


if __name__ == "__main__":
    res = run_db_backup()
    print("DB Backup Result:", res)
