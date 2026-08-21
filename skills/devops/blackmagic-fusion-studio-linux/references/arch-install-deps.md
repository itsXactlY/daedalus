# Arch Linux (Garuda) — Fusion Studio 21 Install Notes

## Dependencies

Fusion 21 is a Qt5/OpenGL application. On Arch, install these packages:

```
sudo pacman -S qt5-base qt5-x11extras qt5-svg glu libxcb xcb-util xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-cursor dbus libgl fontconfig freetype2 alsa-lib
```

For CUDA support (used for some decoding):
```
sudo pacman -S cuda
```

## Install Path

```
/opt/BlackmagicDesign/Fusion21/
```

Typical structure:
- `Fusion` — main ELF binary
- `libfusionsystem.so` — core library (license checks live here)
- `libFusionCore.so` — core library (no license checks)
- `libddm.so`, `libfusion*.so` — supporting libraries
- `Frameworks/lib/` — bundled Qt5, OpenCV, CUDA, OpenImageIO libs
- `.license/` — license file directory (created by resolve.py)
- `Plugins/` — plugin binaries
- `Fuses/` — user-modifiable tools

## Install Procedure

1. Extract the tarball:
   ```
   sudo tar xzf Blackmagic_Fusion_Studio_21.0_Linux.tar.gz -C /opt/
   ```

2. Run resolve.py patch:
   ```
   cd /path/to/Blackmagic_Fusion_Studio_21.0_Linux/
   sudo python3 resolve.py --targets fusion
   ```

3. Verify:
   ```
   RLM_LICENSE=/opt/BlackmagicDesign/Fusion21/.license/blackmagic.lic /opt/BlackmagicDesign/Fusion21/Fusion
   ```

## Known Issues on Arch

| Issue | Fix |
|-------|-----|
| SIGSEGV on launch | Binary not patched, or patch at wrong offset |
| "Needs activation" dialog | Try NOP fix instead of EB 11 (see SKILL.md) |
| No GUI visible | Check DISPLAY env var; launch from terminal to see errors |
| Missing python2 | Fusion installer script checks for python2; symlink or set SKIP_PACKAGE_CHECK=1 |
| Qt platform plugin error | Set `QT_QPA_PLATFORM_PLUGIN_PATH=/opt/BlackmagicDesign/Fusion21/Frameworks/plugins` or `Frameworks/platforms/` |

## License File

Path: `/opt/BlackmagicDesign/Fusion21/.license/blackmagic.lic`
Format (RLM):
```
LICENSE blackmagic fusionstudio 999999 permanent uncounted
 hostid=ANY issuer=CGP customer=CGP issued=28-dec-2023
 akey=0000-0000-0000-0000 _ck=00 sig="00"
```

The env var `RLM_LICENSE` must point to this file at launch.
