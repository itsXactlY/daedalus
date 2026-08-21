# Harness Audit Checklist (verified 2026-08-07)

Order matters: understand install → repo → network → services → logs → disk.
Always work secret-safe (never print auth.json/.env values).

## 0. Context
- Load skills: `daedalus-harness-internals`, `daedalus-core-capabilities`,
  `daedalus-provider-model-resolution` (read-only if user-owned).
- `mazemaker_recall(query="daedalus agent harness audit ...")` for prior audits.
- `daedalus --version` + `daedalus doctor` for the fast health pass.

## 1. Install location & repo state
```bash
which daedalus; readlink -f "$(which daedalus)"; daedalus --version
cd /path/to/hermes-agent
git branch -vv                      # checked-out branch vs tracking remote
git rev-list --count HEAD..origin/main   # >0 = runtime behind = update black hole
git remote -v                       # fork vs upstream; upstream present?
git log --oneline -5                # local rework commits?
```
Update black hole: runtime on a feature branch → `daedalus update` syncs
origin/main only; the running code never receives upstream fixes while the
log says "Already up to date!".

## 2. Network exposure (the critical section)
```bash
ss -tlnp                            # all listeners, owners
readlink /proc/<pid>/cwd            # what does an http.server actually serve?
tr '\0' ' ' < /proc/<pid>/cmdline
cat /etc/exports                    # NFS exports — check all_squash/anonuid
systemctl is-active nfs-server ufw firewalld nftables
command -v ufw nft iptables
ip -4 addr show                     # LAN subnet
```
Red flags seen 2026-08-07: `/home/alca` exported rw to whole LAN with
`all_squash,anonuid=1000` (= remote writes AS the user), `no_root_squash`
mounts, `python3 -m http.server` on 0.0.0.0, ollama `*:11434`, podman passt
forwarding `*:8765`, zero firewall.

## 3. Services (systemd user)
```bash
systemctl --user list-units --all | grep -iE 'daedalus|gateway|cron|mcp'
systemctl --user is-active daedalus-cron-tick.timer daedalus-gateway.service
systemctl --user cat <unit>         # ExecStart reveals the real command
```
`failed` timer + inactive service = cron stack dead even if jobs are enabled.
Check `~/.daedalus/cron/jobs.json` (python parse: name/schedule/enabled/skills).

## 4. Logs
```bash
ls -la ~/.daedalus/logs/ | sort -k5 -n   # growth is a smell
tail -15 <biggest logs>                # mcp-stderr.log, gateway.log, update.log
```
Crash-loop signature: same error line every ~5s, no backoff, single shared
append-file with no rotation.

## 5. Disk hygiene — check BEFORE deleting anything
```bash
du -sh venv.stale.runtime-* .daedalus-runtime
cat venv/pyvenv.cfg                    # home= may point INTO .daedalus-runtime → NOT junk
ls ~/.daedalus | grep -E '\.bak|\.corrupt'
du -sh ~/.daedalus/skills; find ~/.daedalus/skills -name SKILL.md | wc -l
```
Cautious cleanup ("vorsichtig"): `mv` to `~/.local/share/Trash/files/<name>-<date>/`
or `~/.daedalus/.archive-<date>/` — never rm. Curator: `daedalus curator status` →
`daedalus curator run` (prune-only here; consolidation off).

## 6. Secret-safe inspection pattern
```python
# keys + lengths only, never values:
def walk(o, p=''):
    if isinstance(o, dict):
        for k, v in o.items():
            np = f'{p}.{k}' if p else k
            if isinstance(v, (dict, list)): walk(v, np)
            else: print(f'{np}: len={len(str(v))} plaintext_like={...}')
```
`grep -oE '^KEY=.{0,6}' f | sed 's/=.\{0,6\}/=***/'` for env files;
`grep -h KEY ~/.bash_history | sed -E 's/(KEY=).{0,4}.*/\1***/'`.

## 7. Config parsing without secrets
```python
import yaml, json; c = yaml.safe_load(open('~/.daedalus/config.yaml'))
# print model/providers/memory/gateway/toolsets/security/approvals sections
```
Compare `auth.json active_provider` vs `config.yaml model.provider` (mismatch
was live on this host: auth=nous, config=deepseek).

## 8. Fix verification loop
Every fix gets a live proof: MCP → call the tool; firewall → `ufw status verbose`
(after operator runs the script); log rotation → run script, check `.gz`;
git sync → `git rev-list --count` before/after. Then save
`ops:<phase>-<date>` memory with memory IDs.
