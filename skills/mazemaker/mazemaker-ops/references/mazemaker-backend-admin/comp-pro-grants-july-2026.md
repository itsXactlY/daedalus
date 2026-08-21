# Comp-Pro Grants — July 2026

Two consecutive comp-Pro grants performed on 2026-07-06, establishing the
repeatable procedure codified in the parent skill.

## Grant 1: usr_3c17ea3f6a63429e9a14f1f3d7b00d02

| Detail | Value |
|---|---|
| Date | 2026-07-06 ~08:40 UTC |
| Email | (unknown — no email_plain column in schema) |
| Reason | "sorry for the backend-down inconvenience" |
| Expiry | 2026-08-05 08:42 UTC |
| Backup | `mazemaker.db.bak.comp-20260706-0840` |

**First attempt failure**: tried `systemctl --user` units first — failed because
SSHing as root has no D-Bus session. Cleaned up stray `--user` unit files.
Re-learned: always use system-level units.

**SQLite quoting trap**: the first SQL UPDATE used double-quoted literals in
the WHERE clause (`WHERE id="usr_..."`) — sqlite3 treats double-quoted values
as column identifiers, so the WHERE matched nothing. Fix: pipe SQL via stdin
with single-quoted literals.

## Grant 2: usr_50d8ccf025db475c896058805d8068bb

| Detail | Value |
|---|---|
| Date | 2026-07-06 09:31 UTC |
| Email | martin@auskadi.com |
| Reason | 30-day comp Pro (no specific stated reason) |
| Expiry | 2026-08-05 09:30:59 UTC |
| Backup | `mazemaker.db.bak.comp-usr50d8cc-20260706-0931` |

**Quoting hell incident**: tried inline `ssh mazemaker-prod "bash -c '...'"` with
nested heredocs and `$(date -u)` inside the remote script. The heredoc delimiter
`'SCRIPT'` plus SQL single quotes created a 3-level escaping nightmare that
crashed with `Syntaxfehler beim unerwarteten Symbol »(«`.

**Fix that became the procedure**: write local `.sh` files → `scp` to VPS →
execute on remote. Avoids all quoting issues.

## Common Elements

Both grants use the same revert architecture:
- Conditional revert: only `free` if `tier=pro AND stripe_customer_id IS NULL`
- Self-disabling timer (fires once, then deactivates itself)
- Logging to `comp-revert.log`

## Cron cleanup note

The `seats.py` "downgrade-cron" mentioned in mazemaker docs **does not exist**
on this VPS. The timer-based approach is the only expiry mechanism.
