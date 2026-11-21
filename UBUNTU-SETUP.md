# Ubuntu 24.04+ — Linux port

**Languages:** **English** · [Bahasa Indonesia](UBUNTU-SETUP.id.md)

Native Linux support for **ePlus AI Toolkit**. This page covers Ubuntu 24.04+ with
Python 3 and Android SDK Platform-Tools. It reuses the existing Python/Frida engine
(`ultra0.py`) and the shared Textual dashboard through the same native adapter that
macOS uses (`macos_runner.py`). **PowerShell is not required or used on Linux.**

> [!CAUTION]
> **Unofficial project. Potential billing charges.** Steps **2–5** can open a real
> Google Play checkout and may automatically tap **Subscribe**. An offer appearing in
> a list, a shown first-phase price of zero, or a logged "Subscribe attempted" message
> does **not** establish eligibility, an active subscription, a free subscription, or a
> changed renewal date. Verify the exact account, today's charge, future pricing and
> renewal date directly in Google Play before any checkout.

> [!WARNING]
> **Setup and Step 0/1 are not side-effect-free.** A run may install Frida on the
> Android side, push the bundled billing module (`assets/modules/module_521.b64`) to
> the device, **clear the Android HTTP proxy** (`settings put global http_proxy :0`),
> and **force-stop VPN apps** that intercept Play traffic. Those changes persist after
> the tool exits. Use only a dedicated authorized device.

## Requirements

| Component | Requirement |
| --- | --- |
| OS | Ubuntu 24.04+ (tested on 24.04.5), x86_64 or arm64 |
| Python | 3.10+ (Ubuntu 24.04 ships 3.12.3) |
| ADB | Android SDK Platform-Tools on `PATH`, or `ADB_PATH=/path/to/adb` |
| Android | **Rooted** device/emulator with **Google Play Store** + **Google One**, signed in to the account you are authorized to check |
| Frida | **16.5.9** host, installed into the project `.venv` by the launcher; the Android-side `frida-server` must be the matching version |
| Disk | ~500 MB for `.venv` and Platform-Tools |

A **headless VPS is not a supported runtime** — see [VPS feasibility](#vps-feasibility).

## Install

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip adb android-sdk-platform-tools-common unzip

git clone <your-fork-url> google-ai
cd google-ai
sh run-linux.sh --help      # no dependencies or device access required
sh run-linux.sh --doctor    # read-only host + ADB inspection
```

`--help` and `--doctor` do **not** need a connected Android device, and `--doctor`
performs no Android writes. The launcher creates a project-local `.venv` on the
first run that needs it; if `python3-venv` is unavailable it falls back to
[`uv`](https://docs.astral.sh/uv/), and if neither works it stops with exit code 2
and the exact `apt` command.

### Commands

```bash
sh run-linux.sh --help       # usage; no dependencies or device access required
sh run-linux.sh --doctor     # host and ADB inspection; NO Android writes
sh run-linux.sh --check      # Step 0 diagnostics;        MAY modify Android
sh run-linux.sh --list       # Step 1 offer metadata;     MAY modify Android
sh run-linux.sh               # interactive TUI at Step 1
sh run-linux.sh --step 2     # TUI with Step 2 preselected; never auto-executes
sh run-linux.sh --sequence   # TUI with guided sequence controls
```

Selecting a step in the TUI **never** starts it. Steps 2–5 additionally push an
approval modal, and the adapter adds `--confirmed` (Steps 2–5) and
`--active-confirmed` (Steps 3–5) as a second fail-closed gate. Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Success / usage displayed |
| 2 | Missing prerequisite (Python < 3.10, no venv tooling, wrong platform) |
| 3 | ADB missing, no device online, or the device is `unauthorized`/`offline` |
| 4 | Multiple distinct devices online; selection is ambiguous |

## Expected output

`sh run-linux.sh --doctor` on a host with no device attached:

```
ePlus AI Toolkit - Linux doctor (read-only)
  Host OS      Linux 6.x (x86_64)
  Python       3.12.3 at /usr/bin/python3
  Git          git version 2.43.0
  Project venv present
  Host Frida   16.5.9 (pinned 16.5.9)
  ADB          /usr/bin/adb
    Android Debug Bridge version 1.0.41
  Devices      1 reported, 1 online
    emulator-5554  [device]
  Device facts (read-only):
    ABI               arm64-v8a
    Android release   14 (SDK 34)
    Root (adb shell)  yes
    Google Play Store installed
    Google One        installed
    frida-server      running
    Frida device match uses USB transports only; ADB port forwarding alone
    does not establish a usable Frida target.

  No Android settings, packages, or processes were changed by this command.
  Next: sh run-linux.sh --check  (Step 0; MAY modify the Android device)
```

With no device: `Devices 0 reported, 0 online` and exit code 3. With two online
devices: exit code 4 and a refusal to guess.

## USB device permissions

Inspect before changing anything:

```bash
ls /etc/udev/rules.d/                 # existing rules
groups                                # is your user in plugdev?
adb devices -l
```

Ubuntu's `android-sdk-platform-tools-common` package usually installs adequate
`udev` rules. Add a **narrowly scoped** rule only for a vendor ID that genuinely
lacks one, then `sudo udevadm control --reload-rules && sudo udevadm trigger`.
Never enable unrestricted debugging, and never globally disable the firewall.
For emulators, `adb connect 127.0.0.1:<port>` over loopback is preferred over
exposing a TCP transport.

## Android configuration this project changes

Run `sh run-linux.sh --check` only on a **dedicated authorized device**. Expect:

- **Frida install**: downloads the official `frida-server` 16.5.9 build matching the
  device ABI and starts it as root (`/data/local/tmp/frida-server`).
- **Billing module**: pushes the repo's base64-encoded APK/DEX payload
  (`assets/modules/module_521.b64`) to the device. **This component has not been
  independently audited** — review it before use.
- **HTTP proxy reset**: `settings put global http_proxy :0` if a proxy is set.
- **VPN handling**: force-stops known Clash packages that intercept Play traffic.
  They must be restarted by you afterwards.
- **ADB root**: may run `adb root` or `su -c` to obtain a root shell.

The engine never adds or switches Google accounts in the guarded routes used here
(`--no-add --no-switch`) and never passes `--force`.

## Billing safety

Steps 2–5 can create real Google Play charges. In the currently reported 24-month
sequence, Steps 2, 3 and 4 each involve a **separate ~US$1 card-verification event**:
**3 × US$1 = US$3** across three transactions, not one US$3 charge. An event may be a
temporary authorization hold rather than a settled charge, typically clearing in
1–14 business days depending on the bank. A zero-priced introductory phase is **not**
proof of eligibility or of free renewal. Step 5 is optional and outside that example.

The toolkit never uses `--force` to bypass Play-account verification and cannot change
eligibility. Review any real checkout on the Android screen in a separate, deliberate
session. `Stop`/`Exit` does not undo a checkout that was already submitted.

## Testing

Host-only checks, no device and no checkout:

```bash
sh -n run-linux.sh
python3 -m py_compile tui.py tui_core.py macos_runner.py ultra0.py device_selector.py
python3 -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

Linux-specific suites (all ADB/Frida/checkout interactions mocked):

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_linux.py' -v
```

Note that `tests/test_english_only.py` walks the whole tree and will scan `.venv`
if it exists; that is a pre-existing upstream limitation, not a Linux regression.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Could not create .venv` (exit 2) | `sudo apt install -y python3-venv python3-pip`, or install `uv` |
| `ADB is missing` (exit 3) | `sudo apt install -y adb android-sdk-platform-tools-common`, or set `ADB_PATH` |
| Device shows `unauthorized` | Accept **Allow USB debugging** on the device; `adb kill-server && adb start-server` |
| Device shows `offline` | Reconnect the cable or restart the emulator |
| `Multiple different Android devices` (exit 4) | Disconnect extras; the tool refuses to guess |
| `Root is unavailable` | Enable root for the emulator instance; on a physical device root must already be provisioned |
| `Frida 16.5.9 required` | Delete `.venv` and re-run the launcher, or `uv pip install --python .venv/bin/python frida==16.5.9` |
| `Unsupported device ABI` | The device ABI has no matching official `frida-server` build |
| Google Play says account verification required | Stop. Review Google Account Security; do not retry or use `--force` |

## Rollback

```bash
# Remove the local runtime only; source files are untouched.
rm -rf .venv ultra0-report

# Stop Android-side helpers on the device (requires root).
adb -s <serial> shell "su -c 'pkill frida-server'"
adb -s <serial> shell "rm -f /data/local/tmp/frida-server /data/local/tmp/module_521.apk"

# Restore a proxy value you deliberately replaced (check the original first).
adb -s <serial> shell settings get global http_proxy
```

Restart any VPN app the toolkit force-stopped. To undo the code change completely,
switch back to `main` on your fork.

## VPS feasibility

**Blocked / not verified.** A headless Ubuntu VPS does not provide the required
Android runtime, and upstream Frida selection enumerates **USB-type** Frida devices —
so ADB port forwarding alone does **not** create a usable Frida target.

- **Preferred**: run the toolkit and the Android instance on the same local machine,
  and reach that machine only from trusted local or SSH sessions.
- **Optional**: acceptable only if the VPS hosts a compatible dedicated Android
  environment (KVM nested virtualization, sufficient RAM, Play-certified image) or
  has a verified secure tunnel to the authorized device, with **both** ADB and Frida
  mapped to the **same** Android instance. This configuration has **not** been tested
  here; do not claim support without an actual run.

Never expose ADB server `5037`, Android ADB `5555`, or Frida `27042` on a public
interface. Do not publish a web dashboard or a Caddy route for this tool. Do not use
`--network host` in Docker. Do not use `--privileged` in Docker. Do not use host USB
passthrough as a shortcut. Bind any required transport to host loopback and reach it
over SSH after review.

## Security and license caveats

- The bundled `assets/modules/module_521.b64` payload has **not** been independently
  audited. Treat it as untrusted code that can run inside Google Play on the device.
- Local reports land in `ultra0-report/` and are **sensitive**: they can contain the
  Google Play account address and offer/purchase metadata. `ultra0-report/`, `logs/`,
  and `*.json` account artifacts are git-ignored. Never paste them into an issue.
- The upstream repository declares **no repository-wide LICENSE**. `THIRD_PARTY_NOTICES.md`
  preserves an original MIT notice **only for the upstream-derived portions**. Do not
  assume all contributions — including this Linux port — are MIT licensed. Confirm
  with the copyright holder before redistribution.
- This project is unofficial and not affiliated with, endorsed by, or supported by
  Google, Google Play, Google One, NetEase, or MuMuPlayer.

## Files added by the Linux port

| File | Purpose |
| --- | --- |
| `run-linux.sh` | POSIX launcher: `--help`, `--doctor`, `--check`, `--list`, `--step`, `--sequence` |
| `scripts/linux-doctor.py` | Read-only host + ADB inspection backend for `--doctor` |
| `tests/test_linux.py` | Mocked Linux regression tests (routing, launcher, doctor, approval gates) |
| `UBUNTU-SETUP.md` | This guide |

Changed files: `tui_core.py` (`NATIVE_PLATFORMS`, `is_native_platform()`,
`command_for_step()` routing) and `tui.py` (platform predicate). The upstream
engine, billing JavaScript, and adapter contract are unchanged.
