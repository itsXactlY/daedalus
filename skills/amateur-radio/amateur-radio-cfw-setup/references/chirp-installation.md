# CHIRP Installation on Arch Linux (no-sudo path)

The operator's environment is Arch with Zen kernel. Installing CHIRP via the AUR helper (`paru -S chirp-next` or `yay -S chirp`) is the obvious path, but it requires sudo password via an askpass helper, which is not available in non-tty sessions (cron jobs, agent sessions, remote shells). The path below installs CHIRP cleanly in a venv as the running user with no sudo.

## Step 1: Clone the daily CHIRP source

```
git clone --depth 1 https://github.com/kk7ds/chirp.git ~/chirp-git
```

kk7ds/chirp is the upstream Dan Smith / kk7ds development branch and contains the most current driver set. The `master` branch is what gets packaged; for daily drivers, the kk7ds branch is the better source.

## Step 2: Create a venv and install

```
python -m venv ~/chirp-venv
~/chirp-venv/bin/pip install --upgrade pip wheel
~/chirp-venv/bin/pip install -e ~/chirp-git[wx]
```

The `[wx]` extra pulls in wxPython 4.2.x, which is required for the GUI. The wheel is ~150 MB; on first install it takes a few minutes. On Python 3.14 (current Arch default) the prebuilt wheel installs cleanly with no source build.

## Step 3: Verify

```
~/chirp-venv/bin/chirp --version   # may not have a --version flag; that's fine
~/chirp-venv/bin/python -c "import chirp; print(chirp.__file__)"
```

## Step 4: Launch the GUI

```
~/chirp-venv/bin/chirp
```

This opens the wxPython GUI. From here: `Radio → Import` to load a CSV, `Radio → Connect to radio` to talk to a device.

## Common Pitfalls

1. **Sudo-required AUR helpers fail in non-tty sessions.** `paru -S` and `yay -S` will ask for sudo password. In cron jobs, agent sessions, or any non-interactive context, the prompt cannot be answered and the install fails silently. Use the pip-in-venv path above.
2. **PyPI's `chirp` package is stale and has a broken Fortran build (`vitterbi.pyf`).** Do not `pip install chirp` directly. Always install from the GitHub source.
3. **wxPython build from source takes 30+ minutes and needs GTK headers.** Use the prebuilt wheel — works on Python 3.10+ for common Linux distros including Arch.
4. **CHIRP does not have a driver for every radio.** Check the supported-radios page or grep the drivers directory before promising the operator a GUI workflow.

## Determining whether CHIRP supports a given radio

```
ls ~/chirp-git/chirp/drivers/ | grep -i "modelname"
```

If empty, CHIRP does not natively support that radio. The user can still use the Generic CSV radio for editing channel lists in a spreadsheet-like view, but they cannot flash to the radio from CHIRP.
