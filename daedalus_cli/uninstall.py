"""
Daedalus Agent Uninstaller.

Provides options for:
- Full uninstall: Remove everything including configs and data
- Keep data: Remove code but keep ~/.daedalus/ (configs, sessions, logs)
"""

import shutil
import subprocess
from pathlib import Path

from daedalus_constants import get_daedalus_home

from daedalus_cli.colors import Colors, color

def log_info(msg: str):
    print(f"{color('→', Colors.CYAN)} {msg}")

def log_success(msg: str):
    print(f"{color('✓', Colors.GREEN)} {msg}")

def log_warn(msg: str):
    print(f"{color('⚠', Colors.YELLOW)} {msg}")

def get_project_root() -> Path:
    """Get the project installation directory."""
    return Path(__file__).parent.parent.resolve()


def find_shell_configs() -> list:
    """Find shell configuration files that might have PATH entries."""
    home = Path.home()
    configs = []
    
    candidates = [
        home / ".bashrc",
        home / ".bash_profile",
        home / ".profile",
        home / ".zshrc",
        home / ".zprofile",
    ]
    
    for config in candidates:
        if config.exists():
            configs.append(config)
    
    return configs


def remove_path_from_shell_configs():
    """Remove Daedalus PATH entries from shell configuration files."""
    configs = find_shell_configs()
    removed_from = []
    
    for config_path in configs:
        try:
            content = config_path.read_text()
            original_content = content
            
            new_lines = []
            skip_next = False
            
            for line in content.split('\n'):
                if '# Daedalus Agent' in line or '# daedalus' in line:
                    skip_next = True
                    continue
                if skip_next and ('daedalus' in line.lower() and 'PATH' in line):
                    skip_next = False
                    continue
                skip_next = False
                
                if 'daedalus' in line.lower() and ('PATH=' in line or 'path=' in line.lower()):
                    continue
                    
                new_lines.append(line)
            
            new_content = '\n'.join(new_lines)
            
            while '\n\n\n' in new_content:
                new_content = new_content.replace('\n\n\n', '\n\n')
            
            if new_content != original_content:
                config_path.write_text(new_content)
                removed_from.append(config_path)
                
        except Exception as e:
            log_warn(f"Could not update {config_path}: {e}")
    
    return removed_from


def remove_wrapper_script():
    """Remove the daedalus wrapper script if it exists."""
    wrapper_paths = [
        Path.home() / ".local" / "bin" / "daedalus",
        Path("/usr/local/bin/daedalus"),
    ]
    
    removed = []
    for wrapper in wrapper_paths:
        if wrapper.exists():
            try:
                content = wrapper.read_text()
                if 'daedalus_cli' in content or 'daedalus' in content:
                    wrapper.unlink()
                    removed.append(wrapper)
            except Exception as e:
                log_warn(f"Could not remove {wrapper}: {e}")
    
    return removed


def uninstall_gateway_service():
    """Stop and uninstall the gateway service if running."""
    import platform
    
    if platform.system() != "Linux":
        return False
    
    try:
        from daedalus_cli.gateway import get_service_name
        svc_name = get_service_name()
    except Exception:
        svc_name = "daedalus-gateway"

    service_file = Path.home() / ".config" / "systemd" / "user" / f"{svc_name}.service"
    
    if not service_file.exists():
        return False
    
    try:
        subprocess.run(
            ["systemctl", "--user", "stop", svc_name],
            capture_output=True,
            check=False
        )
        
        subprocess.run(
            ["systemctl", "--user", "disable", svc_name],
            capture_output=True,
            check=False
        )
        
        service_file.unlink()
        
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            check=False
        )
        
        return True
        
    except Exception as e:
        log_warn(f"Could not fully remove gateway service: {e}")
        return False


def run_uninstall(args):
    """
    Run the uninstall process.
    
    Options:
    - Full uninstall: removes code + ~/.daedalus/ (configs, data, logs)
    - Keep data: removes code but keeps ~/.daedalus/ for future reinstall
    """
    project_root = get_project_root()
    daedalus_home = get_daedalus_home()
    
    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.MAGENTA, Colors.BOLD))
    print(color("│            ⚕ Daedalus Agent Uninstaller                  │", Colors.MAGENTA, Colors.BOLD))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.MAGENTA, Colors.BOLD))
    print()
    
    print(color("Current Installation:", Colors.CYAN, Colors.BOLD))
    print(f"  Code:    {project_root}")
    print(f"  Config:  {daedalus_home / 'config.yaml'}")
    print(f"  Secrets: {daedalus_home / '.env'}")
    print(f"  Data:    {daedalus_home / 'cron/'}, {daedalus_home / 'sessions/'}, {daedalus_home / 'logs/'}")
    print()
    
    print(color("Uninstall Options:", Colors.YELLOW, Colors.BOLD))
    print()
    print("  1) " + color("Keep data", Colors.GREEN) + " - Remove code only, keep configs/sessions/logs")
    print("     (Recommended - you can reinstall later with your settings intact)")
    print()
    print("  2) " + color("Full uninstall", Colors.RED) + " - Remove everything including all data")
    print("     (Warning: This deletes all configs, sessions, and logs permanently)")
    print()
    print("  3) " + color("Cancel", Colors.CYAN) + " - Don't uninstall")
    print()
    
    try:
        choice = input(color("Select option [1/2/3]: ", Colors.BOLD)).strip()
    except (KeyboardInterrupt, EOFError):
        print()
        print("Cancelled.")
        return
    
    if choice == "3" or choice.lower() in ("c", "cancel", "q", "quit", "n", "no"):
        print()
        print("Uninstall cancelled.")
        return
    
    full_uninstall = (choice == "2")
    
    print()
    if full_uninstall:
        print(color("⚠️  WARNING: This will permanently delete ALL Daedalus data!", Colors.RED, Colors.BOLD))
        print(color("   Including: configs, API keys, sessions, scheduled jobs, logs", Colors.RED))
    else:
        print("This will remove the Daedalus code but keep your configuration and data.")
    
    print()
    try:
        confirm = input(f"Type '{color('yes', Colors.YELLOW)}' to confirm: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        print("Cancelled.")
        return
    
    if confirm != "yes":
        print()
        print("Uninstall cancelled.")
        return
    
    print()
    print(color("Uninstalling...", Colors.CYAN, Colors.BOLD))
    print()
    
    log_info("Checking for gateway service...")
    if uninstall_gateway_service():
        log_success("Gateway service stopped and removed")
    else:
        log_info("No gateway service found")
    
    log_info("Removing PATH entries from shell configs...")
    removed_configs = remove_path_from_shell_configs()
    if removed_configs:
        for config in removed_configs:
            log_success(f"Updated {config}")
    else:
        log_info("No PATH entries found to remove")
    
    log_info("Removing daedalus command...")
    removed_wrappers = remove_wrapper_script()
    if removed_wrappers:
        for wrapper in removed_wrappers:
            log_success(f"Removed {wrapper}")
    else:
        log_info("No wrapper script found")
    
    log_info("Removing installation directory...")
    
    try:
        if project_root.exists():
            if daedalus_home in project_root.parents or project_root.parent == daedalus_home:
                shutil.rmtree(project_root)
                log_success(f"Removed {project_root}")
            else:
                shutil.rmtree(project_root)
                log_success(f"Removed {project_root}")
    except Exception as e:
        log_warn(f"Could not fully remove {project_root}: {e}")
        log_info("You may need to manually remove it")
    
    if full_uninstall:
        log_info("Removing configuration and data...")
        try:
            if daedalus_home.exists():
                shutil.rmtree(daedalus_home)
                log_success(f"Removed {daedalus_home}")
        except Exception as e:
            log_warn(f"Could not fully remove {daedalus_home}: {e}")
            log_info("You may need to manually remove it")
    else:
        log_info(f"Keeping configuration and data in {daedalus_home}")
    
    print()
    print(color("┌─────────────────────────────────────────────────────────┐", Colors.GREEN, Colors.BOLD))
    print(color("│              ✓ Uninstall Complete!                      │", Colors.GREEN, Colors.BOLD))
    print(color("└─────────────────────────────────────────────────────────┘", Colors.GREEN, Colors.BOLD))
    print()
    
    if not full_uninstall:
        print(color("Your configuration and data have been preserved:", Colors.CYAN))
        print(f"  {daedalus_home}/")
        print()
        print("To reinstall later with your existing settings:")
        print(color("  curl -fsSL https://raw.githubusercontent.com/NousResearch/daedalus/main/scripts/install.sh | bash", Colors.DIM))
        print()
    
    print(color("Reload your shell to complete the process:", Colors.YELLOW))
    print("  source ~/.bashrc  # or ~/.zshrc")
    print()
    print("Thank you for using Daedalus Agent! ⚕")
    print()
