#!/bin/sh
# Native Linux launcher for ePlus AI Toolkit. Checkout requires TUI approval.
# POSIX sh only: no bashisms, so `sh run-linux.sh` works on Ubuntu/Debian.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

usage() {
  printf '%s\n' \
    "ePlus AI Toolkit — Linux (Textual, Steps 0–5)" \
    "Usage: sh run-linux.sh [--help | --doctor | --check | --list | --step N [--sequence] | --sequence]" \
    "  (no flags)    Textual dashboard at Step 1, including optional confirmed checkout" \
    "  --help        Display this usage text; needs no dependencies or device" \
    "  --doctor      Read-only host and ADB inspection; NO Android writes" \
    "  --check       Step 0: Android/Frida setup diagnostics; MAY modify Android" \
    "  --list        Step 1: query offer metadata only, no checkout; MAY modify Android" \
    "  --step N      Open the dashboard with Step 0..5 selected (never auto-runs)" \
    "  --sequence    Open the dashboard with guided sequence controls" \
    "Steps 2–5 can submit real charges after explicit TUI confirmations." \
    "This toolkit is unofficial and not affiliated with Google." \
    "" \
    "Exit codes:" \
    "  0  success / usage displayed" \
    "  2  missing prerequisite (Python, venv, virtualenv tooling)" \
    "  3  ADB missing, no device online, or a device is unauthorized/offline" \
    "  4  multiple distinct Android devices; selection is ambiguous"
}

if [ "$#" -eq 1 ] && { [ "$1" = "--help" ] || [ "$1" = "-h" ]; }; then
  usage
  exit 0
fi

MODE=""
STEP=""
EXTRA=""
case "$#" in
  0) MODE="tui" ; STEP="1" ;;
  1) case "$1" in
    --doctor) MODE="doctor" ;;
    --check) MODE="check" ;;
    --list) MODE="list" ;;
    --sequence) MODE="tui" ; STEP="1" ; EXTRA="--sequence" ;;
    *) usage >&2; exit 2 ;;
  esac ;;
  2|3)
    if [ "$1" != "--step" ]; then usage >&2; exit 2; fi
    case "$2" in
      0|1|2|3|4|5) STEP="$2" ;;
      *) usage >&2; exit 2 ;;
    esac
    MODE="tui"
    if [ "$#" -eq 3 ]; then
      if [ "$3" != "--sequence" ]; then usage >&2; exit 2; fi
      EXTRA="--sequence"
    fi ;;
  *) usage >&2; exit 2 ;;
esac

# Reject a platform mismatch early so a copied command never silently misleads.
case "$(uname -s)" in
  Linux) : ;;
  *) printf '%s\n' "This launcher is for Linux; use run-macos.sh on macOS or .\\run-all.ps1 on Windows." >&2
     exit 2 ;;
esac

if ! command -v python3 >/dev/null 2>&1 ||
   ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  printf '%s\n' "Install Python 3.10+ to run this toolkit (Ubuntu 24.04 ships 3.12)." >&2
  exit 2
fi

if [ "$MODE" = "doctor" ]; then
  # Doctor runs before any virtual environment exists and never writes to Android.
  exec python3 scripts/linux-doctor.py "$@"
fi

if ! command -v adb >/dev/null 2>&1 && [ -z "${ADB_PATH:-}" ]; then
  printf '%s\n' "Install Android SDK Platform-Tools and check 'adb devices'." \
    "  sudo apt install -y adb android-sdk-platform-tools-common" \
    "  or set ADB_PATH=/path/to/adb" >&2
  exit 3
fi

# Prefer the stdlib venv module; fall back to uv when python3-venv is absent.
if [ ! -x .venv/bin/python ]; then
  printf '%s\n' "Creating project-local .venv (system Python is not modified)..."
  if python3 -m venv .venv >/dev/null 2>&1 && [ -x .venv/bin/python ]; then
    :
  elif command -v uv >/dev/null 2>&1 &&
       uv venv --python python3 --seed .venv >/dev/null 2>&1 && [ -x .venv/bin/python ]; then
    printf '%s\n' "Created .venv with uv (python3-venv is not installed)."
  else
    rm -rf .venv
    printf '%s\n' "Could not create .venv." \
      "  sudo apt install -y python3-venv python3-pip" \
      "  or install uv, then re-run this launcher." >&2
    exit 2
  fi
fi
PYTHON=.venv/bin/python

if ! "$PYTHON" -c "import importlib.metadata as m; import textual, frida; assert m.version('frida') == '16.5.9'" >/dev/null 2>&1; then
  printf '%s\n' "Installing pinned Textual and Frida 16.5.9 into .venv..."
  "$PYTHON" -m pip install --disable-pip-version-check -q -r requirements-tui.txt "frida==16.5.9" || {
    printf '%s\n' "Dependency installation failed. Check network access and retry." >&2
    exit 2
  }
fi

export PYTHONIOENCODING=utf-8:backslashreplace
export PYTHONUTF8=1
case "$MODE" in
  check) exec "$PYTHON" macos_runner.py --step 0 ;;
  list)  exec "$PYTHON" macos_runner.py --step 1 ;;
  tui)
    # Selecting a step never executes it; the TUI still requires its own approval.
    exec "$PYTHON" tui.py --step "$STEP" ${EXTRA:+"$EXTRA"} ;;
esac
exit 2
