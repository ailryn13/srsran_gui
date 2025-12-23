#!/usr/bin/env python3
"""
Quick Start Guide for srsRAN GUI
This script helps users get started quickly
"""

import sys
import os
import subprocess
from pathlib import Path

def print_header():
    print("=" * 70)
    print(" " * 20 + "srsRAN GUI - Quick Start")
    print("=" * 70)
    print()

def check_python():
    """Check Python version"""
    print("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 6:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro} is installed")
        return True
    else:
        print(f"✗ Python 3.6+ required, found {version.major}.{version.minor}.{version.micro}")
        return False

def check_tkinter():
    """Check if Tkinter is available"""
    print("Checking Tkinter availability...")
    try:
        import tkinter
        print(f"✓ Tkinter version {tkinter.TkVersion} is available")
        return True
    except ImportError:
        print("✗ Tkinter is not installed")
        print()
        print("To install Tkinter:")
        print("  Ubuntu/Debian: sudo apt-get install python3-tk")
        print("  Fedora/RHEL:   sudo dnf install python3-tkinter")
        print("  macOS:         Tkinter should be included with Python")
        return False

def check_dependencies():
    """Check if dependencies are installed"""
    print("Checking dependencies...")
    # Currently no external dependencies required (Tkinter comes with Python)
    print("✓ No external dependencies required")
    return True

def check_srsran():
    """Check if srsRAN binaries are available"""
    print("Checking srsRAN installation...")
    binaries = ['srsepc', 'srsenb', 'srsue']
    found = []
    
    for binary in binaries:
        result = subprocess.run(['which', binary], capture_output=True, text=True)
        if result.returncode == 0:
            path = result.stdout.strip()
            print(f"✓ {binary} found at {path}")
            found.append(binary)
        else:
            print(f"✗ {binary} not found in PATH")
    
    if len(found) == 0:
        print()
        print("Note: srsRAN binaries not found. You'll need to:")
        print("  1. Install srsRAN from https://www.srsran.com/")
        print("  2. Configure binary paths in the GUI Configuration tab")
        return False
    elif len(found) < 3:
        print()
        print("Note: Some srsRAN components are missing.")
        print("You can still use the GUI and configure paths manually.")
        return True
    else:
        return True

def print_next_steps(has_srsran):
    """Print next steps for the user"""
    print()
    print("=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print()
    
    if not has_srsran:
        print("1. Install srsRAN:")
        print("   Visit https://www.srsran.com/ for installation instructions")
        print()
    
    print("2. Start the GUI:")
    print("   python3 srsran_gui.py")
    print("   or")
    print("   ./launch.sh")
    print()
    
    print("3. Configure srsRAN:")
    print("   - Go to the Configuration tab")
    print("   - Set binary paths for EPC, eNB, and UE")
    print("   - Optionally set configuration files")
    print("   - Click 'Save Configuration'")
    print()
    
    print("4. Start components:")
    print("   - Go to the Control Panel tab")
    print("   - Click 'Start All' or start components individually")
    print("   - Monitor status and logs")
    print()
    
    print("5. For more information:")
    print("   - Read README.md for detailed documentation")
    print("   - Check MOCKUP.md for GUI layout")
    print("   - Run demo.py to see feature overview")
    print()

def main():
    """Main quick start function"""
    print_header()
    
    checks = []
    checks.append(("Python 3.6+", check_python()))
    checks.append(("Tkinter", check_tkinter()))
    checks.append(("Dependencies", check_dependencies()))
    checks.append(("srsRAN", check_srsran()))
    
    print()
    print("=" * 70)
    print("Status Summary:")
    print("=" * 70)
    
    all_ok = True
    has_srsran = False
    
    for name, status in checks:
        symbol = "✓" if status else "✗"
        status_text = "OK" if status else "MISSING"
        print(f"{symbol} {name:.<50} {status_text}")
        if not status and name != "srsRAN":
            all_ok = False
        if name == "srsRAN" and status:
            has_srsran = True
    
    print_next_steps(has_srsran)
    
    if all_ok:
        print("You're ready to run srsRAN GUI!")
        print()
        print("Run: python3 srsran_gui.py")
        print()
    else:
        print("Please install missing components before running the GUI.")
        print()

if __name__ == '__main__':
    main()
