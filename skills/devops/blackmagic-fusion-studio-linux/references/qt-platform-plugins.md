# Qt Platform Plugins for Fusion Studio

## Problem

Fusion Studio bundles its own Qt5 libraries but does NOT include platform plugins. Without them, Qt aborts during `QGuiApplicationPrivate::createPlatformIntegration()` with a fatal error.

### Stack Trace Signature
```
Thread 1 "Fusion" received signal SIGABRT, Aborted.
#0  abort() in libc
#1  ?? in libQt5Core.so.5
#2  QMessageLogger::fatal()
#3  QGuiApplicationPrivate::createPlatformIntegration()
#4  QCoreApplicationPrivate::init()
```

### Error Messages
- `QWidget::setLayout: Cannot set layout to 0`
- `QApplication: invalid style override 'kvantum-dark' passed, ignoring it`
- Available styles: Windows, Fusion (NOT the themed ones)

## Solution

### Option 1: Use System Qt Plugins
```bash
export QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/qt/plugins/platforms
export QT_QPA_PLATFORM=xcb
export DISPLAY=:0
```

### Option 2: Copy Plugins to Fusion Directory
The expected plugin path is relative to Fusion's lib directory:
```bash
mkdir -p /opt/BlackmagicDesign/Fusion21/Frameworks/lib/../plugins/platforms
cp /usr/lib/qt/plugins/platforms/*.so /opt/BlackmagicDesign/Fusion21/Frameworks/lib/../plugins/platforms/
```

### Option 3: Use Frida to Defer Crash
Hook the `QWidget::setLayout` function to ignore null layout calls:
```javascript
var setLayout = Module.findExportByName('libQt5Widgets.so.5', '_ZN11QWidget6setLayoutEP7QLayout');
Interceptor.attach(setLayout, {
    onEnter: function(args) {
        if (args[1].isNull()) {
            // Skip the call, preventing fatal error
        }
    }
});
```

## Required Plugins (2025 Arch/Garuda)
```
libqeglfs.so      # EGL fullscreen
libqlinuxfb.so    # Linux framebuffer  
libqminimalegl.so # Minimal EGL
libqminimal.so    # Minimal (headless)
libqvnc.so        # VNC
libqxcb.so        # X11 (most common)
libqwayland-*.so  # Wayland
```

## Verification
```bash
# Check Fusion sees the plugins
ldd /opt/BlackmagicDesign/Fusion21/Fusion | grep Qt
ls -la /opt/BlackmagicDesign/Fusion21/Frameworks/lib/../plugins/platforms/ 2>/dev/null || echo "Missing plugins directory"
```

## Session Notes (2025-06-07)
- Fusion 21.0 GA on Arch/Garuda lacks bundled Qt plugins
- The DoLicensing pattern in resolve.py does NOT match GA release
- SIGABRT comes from Qt fatal() during QPA initialization, NOT license checks
- fuscript CLI works because it skips GUI initialization
- The bytes at 0x784960 were incorrectly NOP'd - it was a C++ destructor, not license code