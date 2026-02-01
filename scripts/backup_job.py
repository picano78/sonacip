#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def _run_backup() -> None:
    # Prefer installed CLI when present.
    candidates = [
        Path("/usr/local/bin/sonacip"),
        Path("/opt/sonacip/sonacip"),
    ]
    cmd = None
    for c in candidates:
        if c.exists():
            cmd = [str(c), "backup"]
            break
    if not cmd:
        raise RuntimeError("sonacip backup CLI not found (expected /usr/local/bin/sonacip).")

    subprocess.run(cmd, check=True)


def _prune_backups(root: Path, retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    if not root.exists():
        return 0

    now = datetime.now(timezone.utc).timestamp()
    cutoff = now - (retention_days * 86400)
    deleted = 0
    for p in root.glob("sonacip_backup_*.tar.gz"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                deleted += 1
        except FileNotFoundError:
            continue
    return deleted


def main() -> int:
    backup_root = Path(os.environ.get("BACKUP_DIR", "/opt/sonacip/backups/system"))
    retention_days = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))

    backup_root.mkdir(parents=True, exist_ok=True)

    _run_backup()
    deleted = _prune_backups(backup_root, retention_days)
    print(f"backup_pruned={deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

