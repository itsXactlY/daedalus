# build-recipe.md — verified podroid native-python rootfs (2026-07-11)

## Canonical builder
`vm-image/build_rootfs_native.sh` (podroid-hermes repo). Runs on x86_64 host:

```
podman run --rm --platform=linux/arm64 \
  -v /tmp/hermes-agent-src.tgz:/src.tgz:ro \
  -v vm-image/start_hermes_venv.sh:/start.sh:ro \
  -v android/.../assets/hermes-pod:/outdir \
  arm64v8/alpine:3.23 sh -c '
    apk add --no-cache python3 py3-pip libgcc libstdc++ openssl ca-certificates \
          sqlite-libs libffi zlib bash tini build-base
    mkdir -p /build && tar xzf /src.tgz -C /build
    python3 -m venv /opt/hermes/venv
    /opt/hermes/venv/bin/pip install --no-cache-dir --upgrade pip wheel setuptools
    /opt/hermes/venv/bin/pip install --no-cache-dir /build[termux]
    /opt/hermes/venv/bin/hermes --version
    cp /start.sh /opt/hermes/start.sh && chmod +x /opt/hermes/start.sh
    cat > /wrapper.c <<CEOF
    #include <unistd.h>
    int main(void){ execl("/opt/hermes/start.sh","hermes-agent",(char*)0); _exit(127); }
    CEOF
    gcc -static -Os -o /opt/hermes/hermes-agent.bin /wrapper.c
    chmod +x /opt/hermes/hermes-agent.bin
    apk del build-base >/dev/null 2>&1 || true
    rm -rf /root/.cache /wrapper.c
    apk cache clean >/dev/null 2>&1 || true
    cd / && tar --exclude=./proc --exclude=./sys --exclude=./dev \
        --exclude=./build --exclude=./src.tgz --exclude=./outdir \
        -cf /outdir/rootfs.tar .
  '
```

## start.sh MUST end in `hermes gateway run`
Wrong: `exec /opt/hermes/venv/bin/hermes gateway`   <- prints banner, never binds api_server.
Right: `exec /opt/hermes/venv/bin/hermes gateway run`

## Verify (emulated arm64 alpine, rootfs.tar mounted ro)
```
podman run --rm --platform=linux/arm64 -v $PWD/rootfs.tar:/rootfs.tar:ro arm64v8/alpine:3.23 sh -c '
  mkdir -p /r && tar -xf /rootfs.tar -C /r
  chroot /r /opt/hermes/venv/bin/hermes --version
  chroot /r /opt/hermes/venv/bin/python3 -c "import psutil,cryptography,openai,hermes_cli,gateway;print(\"IMPORTS OK\")"
  chroot /r /opt/hermes/hermes-agent.bin --gateway --host=0.0.0.0 --port=8088 > /r/tmp/gw.log 2>&1 &
  for i in $(seq 1 50); do wget -qO- http://127.0.0.1:8088/health >/dev/null 2>&1 && break; sleep 1; done
  wget -qO- http://127.0.0.1:8088/health; wget -qO- http://127.0.0.1:8088/v1/models
  cat /r/tmp/gw.log
'
```
Expect: `hermes --version` prints v0.15.1 py3.12.13 (rootfs python); IMPORTS OK;
/health 200; /v1/models returns JSON with context_length. If all ports
connection-refused -> start.sh used `hermes gateway` (no run).

## Sizes
- With build-base left in: ~525 MB. After `apk del build-base`: ~253 MB.
- Base alpine has no `file` binary -> skip `chroot ... file ...` in verify.
