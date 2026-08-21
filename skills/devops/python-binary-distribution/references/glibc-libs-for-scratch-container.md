# glibc libs for FROM scratch containers

## Verified baseline (Arch/Garuda, Python 3.14, Nuitka 4.1.2)

A typical Python web service binary needs these libs in `/usr/lib` for the
FROM scratch container to find them at runtime. Verified 2026-06-20 on
iris-messenger migration.

| Lib | Path | Why needed | Can omit if... |
|---|---|---|---|
| `ld-linux-x86-64.so.2` | `/lib64/` | Dynamic linker itself — ELF interpreter | Never omit |
| `libc.so.6` | `/usr/lib/` | Base libc — always needed | Never omit |
| `libm.so.6` | `/usr/lib/` | Math (transitive via libc) | Never omit |
| `libdl.so.2` | `/usr/lib/` | dlopen for dynamic loading | Never omit |
| `libpthread.so.0` | `/usr/lib/` | Threading (asyncio, concurrent.futures) | App is single-threaded |
| `librt.so.1` | `/usr/lib/` | Real-time clocks, POSIX timers | Never omit |
| `libutil.so.1` | `/usr/lib/` | Misc (login, tty, etc.) | Never omit |
| `libresolv.so.2` | `/usr/lib/` | DNS resolution (urllib) | App does no DNS |
| `libz.so.1` | `/usr/lib/` | gzip/bz2 (Python stdlib) | App uses no compression |
| `libssl.so.3` | `/usr/lib/` | TLS (urllib3, requests) | App does no HTTPS |
| `libcrypto.so.3` | `/usr/lib/` | OpenSSL crypto (urllib3, pycryptodome) | App does no crypto |
| `libffi.so.8` | `/usr/lib/` | cffi (cryptography, pycparser) | App uses no cffi |
| `libexpat.so.1` | `/usr/lib/` | XML parsing (xml.etree, xmlrpc) | App parses no XML |
| `libsqlite3.so.0` | `/usr/lib/` | sqlite3 stdlib | App uses no sqlite |
| `libgcc_s.so.1` | `/usr/lib/` | GCC runtime (transitive via libc) | Never omit |

Total: ~13 MB. Add to this list if your binary pulls in extras.

## Discovery workflow

When you see "error while loading shared libraries: <lib>.so.6":

1. Find the lib on the host:
   ```bash
   find /usr/lib /usr/lib64 -name "<lib>*.so*" -not -path '*/lib32/*' 2>/dev/null
   ```
2. Copy to `lib/<lib>.so.6` (resolve symlinks with `readlink -f`)
3. Add `COPY lib/<lib>.so.6 /usr/lib/<lib>.so.6` to Containerfile
4. Rebuild with `--no-cache` (avoid layer caching the old broken image)
5. Retest

Each iteration is ~30 sec on a warm cache.

## Why `/usr/lib` not `/lib`?

glibc's default search path varies by distro. On Debian/Ubuntu, `/lib` is
typically a symlink to `/usr/lib`, so `COPY ... /lib/...` works. On
Arch/Garuda, `/lib` and `/lib64` are NOT in the default search path.

Verify with `LD_DEBUG=libs` inside a failing container:
```bash
podman run --rm -e LD_DEBUG=libs localhost/app:latest --help 2>&1 | grep "search path="
```

Expected output on Arch:
```
search path=/usr/lib/glibc-hwcaps/x86-64-v3:/usr/lib/glibc-hwcaps/x86-64-v2:/usr/lib
```

If you see `/lib` or `/lib64` in there instead, you're on Debian/Ubuntu —
the convention reverses.

## Libs NOT in the baseline (add per-app)

Common additions for specific stacks:

| Stack | Adds |
|---|---|
| `requests` + `urllib3` | `libssl.so.3`, `libcrypto.so.3` (already in baseline) |
| `cryptography` / `pyca` | `libffi.so.8` (already in baseline) |
| `gssapi` / Kerberos auth | `libgssapi_krb5.so.2`, `libkrb5.so.3`, `libk5crypto.so.3`, `libcom_err.so.2`, `libkrb5support.so.0` |
| `ldap3` / LDAP | `libsasl2.so.2`, `libldap.so.2` |
| `psycopg2` / PostgreSQL | `libpq.so.5`, `libssl.so.3`, `libcrypto.so.3` |
| `mysqlclient` / MySQL | `libmariadb.so.3` (or `libmysqlclient.so.21`) |
| `Pillow` / image processing | `libjpeg.so.62`, `libpng16.so.16`, `libtiff.so.5`, `libwebp.so.7`, `libz.so.1` (already in baseline) |
| `numpy` / scientific | `libopenblas.so.0` or `libmkl_rt.so.1` (or `libblas.so.3`) |
| `lxml` / XML | `libxml2.so.2`, `libxslt.so.1` |

For each addition, find on host, copy to `lib/`, add COPY line.

## When the binary STILL doesn't start

After all libs copied and verified, if you still see errors:

1. **Wrong arch**: `file app.bin` → must be x86-64 if your container is x86-64
2. **Wrong glibc version**: app was compiled against glibc 2.35, host has 2.33.
   Fix: rebuild on the target system, or use a static glibc (musl/Alpine — but
   glibc binaries won't run on musl)
3. **Missing symlink target**: `libssl.so.3` might need to be `libssl.so.3.0.X`
   if the binary's ELF metadata references the versioned name. Use
   `readelf -d app.bin | grep NEEDED` to see exact requirements
4. **Filesystem issue**: COPY in FROM scratch might not preserve xattrs.
   Use `COPY --chmod=0755` if the binary needs specific permissions
