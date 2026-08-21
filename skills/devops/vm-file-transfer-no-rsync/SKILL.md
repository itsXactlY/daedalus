---
name: vm-file-transfer-no-rsync
category: devops
description: Transfer files/directories to a VM when rsync is not available, using tar + base64 + scp pipeline.
triggers:
  - rsync not found on VM
  - need to copy directory to QEMU VM
  - local file transfer to remote without rsync
---

# VM File Transfer Without Rsync

When rsync is not available on a VM (e.g., QEMU/jack-in-a-box), use this pipeline.

## The Problem
`rsync` not installed on target VM. Need to transfer directories/files reliably.

## The Solution: tar + scp stdin

### Directory (full workflow)
```bash
# 1. On HOST — package directory
tar czf /tmp/mydir.tar.gz mydir/

# 2. On HOST — upload via scp DIRECTLY (simpler than stdin pipeline)
scp -P 2222 -i ~/.ssh/jiab_test /tmp/mydir.tar.gz testuser@127.0.0.1:/tmp/

# 3. On VM — extract
ssh -p 2222 -i ~/.ssh/jiab_test testuser@127.0.0.1 "tar xzf /tmp/mydir.tar.gz -C /target/"

# 4. Cleanup on VM
ssh -p 2222 -i ~/.ssh/jiab_test testuser@127.0.0.1 "rm /tmp/mydir.tar.gz"
```

### Verification
```bash
ssh -p 2222 -i ~/.ssh/jiab_test testuser@127.0.0.1 "ls -la /target/mydir/"
```

### IMPORTANT: Use 127.0.0.1, NOT localhost
`ssh testuser@localhost` fails with QEMU port forwarding. Use `testuser@127.0.0.1` explicitly.

## Why not scp directly?
scp with large directories can be unreliable. `tar | scp_stdin` lets you atomically transfer the archive, then extract on the other side.

## When rsync IS available
Use the normal path — it's faster and supports resume:
```bash
rsync -avz -e "ssh -p 2222 -i ~/.ssh/jiab_test" mydir/ testuser@localhost:/target/
```

## Key Config (QEMU jack-freeze-test VM)
- SSH key: `~/.ssh/jiab_test`
- Port: `2222`
- User: `testuser`
- Host: `localhost` (local QEMU port forwarding)
