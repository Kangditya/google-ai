#!/usr/bin/env python3
"""Read-only Linux host and ADB inspection for ePlus AI Toolkit.

This is the `--doctor` backend. It performs NO Android writes: no adb root, no
package pushes, no `settings put`, no process kills, no installs, and no
virtual environment creation. Every adb call below is a read: `devices`,
`getprop`, `pm list packages`, `pm path`, and `pidof`.

Account identifiers are never printed. Exit codes match run-linux.sh:
  0  host looks usable
  2  a local prerequisite is missing (Python, ADB not executable)
  3  no device online, or the only candidates are unauthorized/offline
  4  multiple distinct devices; automatic selection is ambiguous
"""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRIDA_REQUIRED = "16.5.9"
MIN_PYTHON = (3, 10, 0)
GOOGLE_ONE = "com.google.android.apps.subscriptions.red"
PLAY_STORE = "com.android.vending"


def run(argv: list[str], timeout: int = 10) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def find_adb() -> str | None:
    configured = os.environ.get("ADB_PATH", "").strip()
    if configured and Path(configured).is_file():
        return configured
    for candidate in ("adb", "/usr/bin/adb",
                      str(Path.home() / "Android/Sdk/platform-tools/adb"),
                      "/usr/local/bin/adb", "/snap/bin/adb"):
        resolved = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if resolved:
            return resolved
    return None


def adb_query(adb: str, *args: str) -> str:
    result = run([adb, *args])
    if result is None or result.returncode != 0:
        return ""
    return result.stdout.strip()


def parse_devices(adb: str) -> list[tuple[str, str]]:
    """Return (serial, state) pairs from `adb devices`, in reported order."""
    output = adb_query(adb, "devices")
    found = []
    for line in output.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2:
            found.append((fields[0], fields[1]))
    return found


def describe_device(adb: str, serial: str) -> list[str]:
    """Read-only per-device facts. No command here changes Android state."""
    abi = adb_query(adb, "-s", serial, "shell", "getprop ro.product.cpu.abi")
    release = adb_query(adb, "-s", serial, "shell", "getprop ro.build.version.release")
    sdk = adb_query(adb, "-s", serial, "shell", "getprop ro.build.version.sdk")
    root = "uid=0" in adb_query(adb, "-s", serial, "shell", "id")
    packages = adb_query(adb, "-s", serial, "shell", "pm", "list", "packages")
    frida_pid = adb_query(adb, "-s", serial, "shell", "pidof", "frida-server")
    return [
        f"    ABI               {abi or 'unknown'}",
        f"    Android release   {release or 'unknown'} (SDK {sdk or 'unknown'})",
        f"    Root (adb shell)  {'yes' if root else 'no - the engine requires root'}",
        f"    Google Play Store {'installed' if 'package:' + PLAY_STORE in packages else 'MISSING'}",
        f"    Google One        {'installed' if 'package:' + GOOGLE_ONE in packages else 'MISSING'}",
        f"    frida-server      {'running' if frida_pid else 'not running (--check would install it)'}",
    ]


def frida_support_note() -> str:
    """Upstream selects USB-transport Frida devices; ADB forwarding alone is not enough."""
    return ("    Frida device match uses USB transports only; ADB port forwarding alone "
            "does not establish a usable Frida target.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only host and ADB inspection (no Android writes)")
    parser.add_argument("--doctor", action="store_true",
                        help="accepted for symmetry with run-linux.sh")
    parser.parse_args(argv)

    problems: list[tuple[int, str]] = []

    print("ePlus AI Toolkit - Linux doctor (read-only)")
    print(f"  Host OS      {platform.system()} {platform.release()} ({platform.machine()})")
    print(f"  Python       {platform.python_version()} at {sys.executable}")
    if sys.version_info < MIN_PYTHON:
        problems.append((2, "Python 3.10+ is required; Ubuntu 24.04 ships 3.12."))
    git_version = run(["git", "--version"])
    git_text = git_version.stdout.strip() if git_version else ""
    print(f"  Git          {git_text or 'not found (optional)'}")

    venv_ok = (ROOT / ".venv/bin/python").is_file()
    print(f"  Project venv {'present' if venv_ok else 'absent (the launcher creates it)'}")
    try:
        installed = importlib.metadata.version("frida")
    except importlib.metadata.PackageNotFoundError:
        installed = None
    print(f"  Host Frida   {installed or 'not installed in this interpreter'} (pinned {FRIDA_REQUIRED})")
    if installed and installed != FRIDA_REQUIRED:
        print(f"    Note: an unpacked Frida {installed} is unrelated to .venv; "
              f"the launcher pins {FRIDA_REQUIRED} inside .venv.")

    adb = find_adb()
    if not adb:
        print("  ADB          not found")
        problems.append((2, "Install Platform-Tools: sudo apt install -y adb "
                            "android-sdk-platform-tools-common, or set ADB_PATH."))
    else:
        version = adb_query(adb, "version")
        first = version.splitlines()[0] if version else "version unavailable"
        print(f"  ADB          {adb}")
        print(f"    {first}")

    devices: list[tuple[str, str]] = []
    if adb:
        devices = parse_devices(adb)
        usable = [(serial, state) for serial, state in devices if state == "device"]
        print(f"  Devices      {len(devices)} reported, {len(usable)} online")
        for serial, state in devices:
            print(f"    {serial}  [{state}]")
        for serial, state in devices:
            if state == "unauthorized":
                problems.append((3, f"Device {serial} is unauthorized: accept the "
                                    "'Allow USB debugging' prompt on the device."))
            elif state == "offline":
                problems.append((3, f"Device {serial} is offline: reconnect the cable "
                                    "or restart the ADB server."))
        if not devices:
            problems.append((3, "No Android device connected. Start a rooted device or "
                                "emulator with ADB debugging enabled."))
        elif not usable:
            problems.append((3, "No device reached the 'device' state."))
        elif len(usable) > 1:
            problems.append((4, f"{len(usable)} candidate devices are online. "
                                "Disconnect extras or pass a single authorized device; "
                                "the engine refuses to guess."))
        else:
            print("  Device facts (read-only):")
            for line in describe_device(adb, usable[0][0]):
                print(line)
            print(frida_support_note())

    print("\n  No Android settings, packages, or processes were changed by this command.")
    print("  Next: sh run-linux.sh --check  (Step 0; MAY modify the Android device)")
    print("        sh run-linux.sh          (Textual dashboard at Step 1)")

    if problems:
        exit_code = max(code for code, _ in problems)
        print("\nResult: attention needed")
        for code, message in problems:
            print(f"  [{code}] {message}")
        return exit_code
    print("\nResult: host and device look usable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
