---
name: hermes-zip-backup
description: Backup ~/.hermes/ to NAS as ZIP with compression, automount handling, and retention cleanup.
category: devops
---

# Hermes ZIP Backup

Backs up `/home/alca/.hermes/` to `/mnt/nas/unsortiert/hermes_backup/zips/` as a max-compression ZIP archive.

## Key Pitfalls

### NAS uses autofs — must trigger mount before checking
`/mnt/nas/unsortiert` is an autofs NFS mount. `mountpoint -q /mnt/nas` does NOT work — you must:
1. Access the specific subpath (`ls "$DEST"`) to trigger the automount
2. Then check `mountpoint -q /mnt/nas/unsortiert`

### ZIP -9 on 2.6GB+ over NFS is too slow for foreground
Always run in **background mode** — the compression + NFS write for a 2.6GB source takes 10+ minutes. Use:
```bash
bash /home/alca/.hermes/scripts/hermes-zip-backup.sh
```
as a background terminal process (not foreground).

### `.hermes/` is growing rapidly
Recent archives: 29MB → 894MB → 1.7GB. Monitor for session DBs or audio cache bloat. Script excludes `venv/` (root + nested `*/venv/` and `*/.venv/`), `node_modules/`, `logs/`, `audio_cache/`, `honcho/honcho.log`, and WAL/SHM files. Key: script `cd`s into `.hermes/` directly so glob patterns match without path prefix.

## Script Location
`/home/alca/.hermes/scripts/hermes-zip-backup.sh`

## Script Behavior
- Trigger autofs mount, verify it's live
- `zip -9 -r` with exclusions (logs, audio_cache, WAL/SHM)
- Verify archive created, log size
- Clean archives older than 30 days
- All logging to `~/.hermes/logs/hermes-backup.log`

## Existing Archives
Located at `/mnt/nas/unsortiert/hermes_backup/zips/`. Pattern: `hermes_backup_YYYYMMDD_HHMMSS.zip`
