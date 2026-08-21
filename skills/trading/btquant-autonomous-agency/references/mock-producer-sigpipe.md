# Mock Data Producer SIGPIPE — Never Use `| head -N`

The BTQuant mock data producer (`mock_data_producer.py`) writes live
trade and orderbook data to `/dev/shm/btquant` for the C++ terminal to
consume. It runs as a long-lived background process that streams
~100 trades/sec and ~20 orderbooks/sec indefinitely.

## The wrong pattern

```bash
# DO NOT DO THIS
python3 mock_data_producer.py 2>&1 | head -10
```

`head -10` exits after reading 10 lines. The pipe closes. Python's
SIGPIPE handler (default: terminate) kills the process on the next
print. The producer dies.

But the SHM file is left in a broken state:

```bash
$ ls -la /proc/<producer_pid>/fd/4
lrwx------ ... 4 -> /dev/shm/btquant (deleted)
```

The SHM file was created by the producer (via mmap), then the
producer was killed (via SIGPIPE), but Linux kept the inode alive
because the producer's FD was still open in a now-defunct state.
The file appears as `(deleted)` in `/proc/<pid>/fd/`. The C++
terminal can't find it by name (`/dev/shm/btquant` no longer exists in
the filesystem namespace) even though the inode persists.

## The right pattern

```bash
# CORRECT
python3 mock_data_producer.py > /tmp/btq_producer.log 2>&1
```

Redirect stdout/stderr to a file, NOT a pipe to head/tail/less. The
process runs until explicitly killed. The SHM file is created
normally and stays in the filesystem namespace.

When starting via Hermes terminal tool:

```python
terminal(
    background=True,
    command="cd /home/alca/projects/PubBTQuant && python3 mock_data_producer.py > /tmp/btq_producer.log 2>&1",
    notify_on_complete=False,  # long-lived, never exits
)
```

`notify_on_complete=False` is correct here because the producer
should run forever. The hint will tell you to use it only for
"long-lived processes that never exit" — that's exactly this case.

## Verifying the producer is healthy

```bash
# Process alive?
ps -o pid,etime,cmd -p <pid>

# SHM file present and fresh?
ls -la /dev/shm/btquant
# Should show ~15M, recently modified

# Producer's FD is healthy (not "(deleted)")
ls -la /proc/<pid>/fd/ | grep btquant
# Should show: ... 4 -> /dev/shm/btquant
# NOT:        ... 4 -> /dev/shm/btquant (deleted)
```

If you see `(deleted)` in the FD listing, the producer is in the
zombie state — it's running but writing to a dead inode that no
consumer can reach. Kill it (`kill <pid>`) and restart with the
correct pattern.

## The diagnostic chain when the terminal shows no data

1. `ls -la /dev/shm/btquant` — does the SHM file exist?
2. If yes, check producer PID is alive: `ps aux | grep mock_data_producer`
3. If alive, check FD health: `ls -la /proc/<pid>/fd/ | grep btquant`
4. If FD shows `(deleted)`, kill producer, delete SHM, restart with
   `> /tmp/btq_producer.log 2>&1`
5. If FD is clean, the issue is elsewhere (C++ consumer, build, etc.)

## Related anti-patterns

- `python3 ... 2>&1 | tee logfile | head -10` — same SIGPIPE problem
- `python3 ... &` without redirection — the process is killed when the
  parent shell exits; use `nohup` or a background tool that tracks the
  process
- `python3 ... > /dev/null` — works (no pipe) but you lose the log;
  use a logfile instead
