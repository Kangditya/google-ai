"""Linux port tests. All ADB/Frida/checkout interactions are mocked or stubbed.

No test here contacts Google Play, opens a checkout, or writes to a real Android
device. ADB is simulated by a stub shell script whose arguments are logged so we
can assert the doctor never issues a state-changing command.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

import macos_runner
from tui_core import command_for_step, is_native_platform

ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "scripts/linux-doctor.py"
LAUNCHER = ROOT / "run-linux.sh"

# Any of these would modify a real device. The read-only doctor must never emit them.
DEVICE_WRITE_TOKENS = (
    "push", "pull", "install", "uninstall", "root", "unroot", "reboot",
    "remount", "disable-verity", "enable-verity", "forward", "reverse",
    "settings put", "am force-stop", "am start", "pm clear", "kill",
)


def write_stub_adb(directory: Path, devices_output: str = "", version_output="Android Debug Bridge version 1.0.41",
                   shell_responses: dict[str, str] | None = None) -> tuple[Path, Path]:
    """Create a stub `adb` that logs its argv and answers like a quiet device.

    Device and shell output travel through files rather than shell quoting so
    tabs and real newlines survive intact.
    """
    log = directory / "adb-argv.log"
    devices_file = directory / "devices.txt"
    devices_file.write_text(devices_output, encoding="utf-8")
    responses = directory / "shell-responses.json"
    responses.write_text(json.dumps(shell_responses or {}), encoding="utf-8")
    stub = directory / "adb"
    stub.write_text(
        f"""#!/bin/sh
printf '%s\\n' "$*" >> {str(log)!r}
case "$1" in
  version) printf '%s\\n' {version_output!r} ; exit 0 ;;
  devices) printf '%s\\n' "List of devices attached" ; cat {str(devices_file)!r} ; exit 0 ;;
esac
# Per-device shell queries: match the joined arguments against the response map.
{_SHELL_DISPATCH.format(responses=str(responses))}
exit 0
""",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub, log


_SHELL_DISPATCH = """python3 - {responses} "$*" <<'PY'
import json, sys
table = json.load(open(sys.argv[1]))
key = " ".join(sys.argv[2:])
for pattern, value in table.items():
    if pattern in key:
        print(value)
        break
PY"""


class LinuxRuntimeRoutingTests(unittest.TestCase):
    """Platform routing must reach the native adapter on Linux, never PowerShell."""

    def test_linux_is_a_native_platform(self):
        self.assertTrue(is_native_platform("linux"))
        self.assertTrue(is_native_platform("darwin"))
        self.assertFalse(is_native_platform("win32"))
        self.assertFalse(is_native_platform("cygwin"))

    def test_linux_routes_to_native_adapter_with_approval_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "macos_runner.py").write_text("# mock", encoding="utf-8")
            with patch("tui_core.sys.platform", "linux"):
                for step in range(6):
                    with self.subTest(step=step):
                        command = command_for_step(step, root)
                        self.assertEqual(command[0], sys.executable)
                        self.assertEqual(command[1], str(root / "macos_runner.py"))
                        self.assertEqual(command[command.index("--step") + 1], str(step))
                        # Paid stages keep the adapter's fail-closed second gate.
                        self.assertEqual("--confirmed" in command, step >= 2)
                        self.assertEqual("--active-confirmed" in command, step >= 3)
                        # The Linux route must never fall back to Windows tooling.
                        self.assertNotIn("-File", command)
                        self.assertFalse(any("run-all.ps1" in part for part in command))
                        self.assertFalse(any("powershell" in part.lower() for part in command))
                        self.assertNotIn("--force", command)

    def test_linux_fails_closed_when_adapter_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("tui_core.sys.platform", "linux"):
                with self.assertRaises(FileNotFoundError):
                    command_for_step(1, Path(temp))

    def test_windows_still_uses_powershell_route(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "run-all.ps1").write_text("# test", encoding="utf-8")
            with patch("tui_core.sys.platform", "win32"):
                command = command_for_step(3, root, shell="powershell.exe")
            self.assertEqual(command[-4:], ["-File", str(root / "run-all.ps1"), "-Step", "3"])

    def test_tui_reports_native_mode_on_linux(self):
        from tui import is_macos_platform
        with patch("tui.sys.platform", "linux"):
            with patch("tui_core.sys.platform", "linux"):
                self.assertTrue(is_macos_platform())
        with patch("tui.sys.platform", "win32"):
            with patch("tui_core.sys.platform", "win32"):
                self.assertFalse(is_macos_platform())

    def test_linux_tui_exposes_six_steps_and_never_auto_runs(self):
        """The dashboard opens at the requested step without launching a child."""
        from textual.widgets import Select
        from tui import GoogleAITUI
        with tempfile.TemporaryDirectory() as temp:
            with patch("tui_core.sys.platform", "linux"):
                app = GoogleAITUI(repo=Path(temp), selected_step=2)
            with patch("tui.subprocess.Popen") as child:
                async def drive():
                    async with app.run_test(size=(100, 30)) as pilot:
                        self.assertEqual(app.query_one("#step", Select).value, 2)
                        self.assertEqual(len(app.query("#workflow .workflow-step")), 6)
                        self.assertFalse(app.busy)
                        await pilot.pause()
                import asyncio
                asyncio.run(drive())
                child.assert_not_called()

    def test_linux_paid_stage_still_requires_approval_modal(self):
        from tui import Approval, GoogleAITUI
        with tempfile.TemporaryDirectory() as temp:
            with patch("tui_core.sys.platform", "linux"):
                app = GoogleAITUI(repo=Path(temp), selected_step=3)
            with patch("tui.subprocess.Popen") as child:
                async def drive():
                    async with app.run_test(size=(100, 30)) as pilot:
                        app._confirm_stage(2, False)
                        await pilot.pause()
                        self.assertIsInstance(app.screen, Approval)
                        self.assertFalse(app.busy)
                import asyncio
                asyncio.run(drive())
                child.assert_not_called()


    def test_elapsed_timer_survives_widget_teardown(self):
        """The 1 s timer must return quietly when the app is not mounted.

        It previously queried #elapsed unconditionally, so a tick racing app
        teardown raised NoMatches and turned a clean exit into a traceback.
        """
        from tui import GoogleAITUI
        with tempfile.TemporaryDirectory() as temp:
            app = GoogleAITUI(repo=Path(temp), selected_step=1)
            app.busy = True
            app._started_at = 0.0
            app._last_activity_at = 0.0
            for _ in range(3):
                app._refresh_elapsed()  # returns quietly; cancellation is expected


class LinuxLauncherTests(unittest.TestCase):
    """Argument handling for run-linux.sh; no devices or dependencies needed."""

    def invoke(self, *args):
        return subprocess.run(["sh", str(LAUNCHER), *args], cwd=ROOT,
                              capture_output=True, text=True, timeout=60)

    def test_launcher_is_valid_posix_shell(self):
        result = subprocess.run(["sh", "-n", str(LAUNCHER)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_needs_no_dependencies_and_mentions_real_charges(self):
        result = self.invoke("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Steps 2", result.stdout)
        self.assertIn("real charges", result.stdout)
        self.assertIn("--doctor", result.stdout)
        self.assertIn("sh run-linux.sh", result.stdout)
        self.assertNotIn("ultra0.py --force", result.stdout)

    def test_launcher_never_passes_force_to_the_engine(self):
        source = LAUNCHER.read_text(encoding="utf-8")
        self.assertNotIn("--force", source)

    def test_invalid_arguments_fail_with_usage_error(self):
        for args in (["--bogus"], ["--step"], ["--step", "9"], ["--step", "two"],
                     ["--step", "2", "--junk"], ["--list", "--check"]):
            with self.subTest(args=args):
                result = self.invoke(*args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_doctor_path_runs_before_dependency_setup(self):
        """--doctor must not require, create, or install into a virtual environment."""
        source = LAUNCHER.read_text(encoding="utf-8")
        doctor_at = source.index('MODE" = "doctor"')
        venv_at = source.index("python3 -m venv")
        self.assertLess(doctor_at, venv_at, "doctor must be handled before .venv creation")


class LinuxDoctorTests(unittest.TestCase):
    """The doctor is read-only and fails closed on missing or ambiguous devices."""

    def run_doctor(self, adb_path=None, devices="", shell_responses=None):
        with tempfile.TemporaryDirectory() as temp:
            tempdir = Path(temp)
            env = dict(os.environ)
            env.pop("ADB_PATH", None)
            if adb_path is not None:
                env["ADB_PATH"] = str(adb_path)
            if adb_path is None:
                # Guarantee `adb` is not resolvable for the missing-ADB case.
                env["PATH"] = str(tempdir)
            result = subprocess.run([sys.executable, str(DOCTOR)],
                                    capture_output=True, text=True, timeout=120, env=env)
            return result

    def test_missing_adb_exits_2_without_installing_anything(self):
        result = self.run_doctor(adb_path=None)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Install Platform-Tools", result.stdout)
        self.assertIn("No Android settings, packages, or processes were changed", result.stdout)

    def test_no_devices_exits_3(self):
        with tempfile.TemporaryDirectory() as temp:
            stub, _log = write_stub_adb(Path(temp), devices_output="")
            result = self.run_doctor(adb_path=stub)
        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertIn("No Android device connected", result.stdout)

    def test_unauthorized_device_exits_3_and_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            stub, _log = write_stub_adb(Path(temp), devices_output="ABC123\tunauthorized")
            result = self.run_doctor(adb_path=stub)
        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertIn("ABC123", result.stdout)
        self.assertIn("unauthorized", result.stdout)
        self.assertIn("Allow USB debugging", result.stdout)

    def test_offline_device_exits_3(self):
        with tempfile.TemporaryDirectory() as temp:
            stub, _log = write_stub_adb(Path(temp), devices_output="XYZ789\toffline")
            result = self.run_doctor(adb_path=stub)
        self.assertEqual(result.returncode, 3, result.stdout)
        self.assertIn("offline", result.stdout)

    def test_multiple_devices_fail_closed_as_ambiguous(self):
        with tempfile.TemporaryDirectory() as temp:
            stub, _log = write_stub_adb(
                Path(temp), devices_output="emulator-5554\tdevice\nR58M12345\tdevice")
            result = self.run_doctor(adb_path=stub)
        self.assertEqual(result.returncode, 4, result.stdout)
        self.assertIn("candidate devices are online", result.stdout)
        self.assertIn("refuses to guess", result.stdout)

    def test_single_device_reports_facts_and_exit_0(self):
        responses = {
            "ro.product.cpu.abi": "arm64-v8a",
            "ro.build.version.release": "14",
            "ro.build.version.sdk": "34",
            "shell id": "uid=0(root) gid=0(root)",
            "pm list packages": "package:com.android.vending\n"
                                "package:com.google.android.apps.subscriptions.red",
            "pidof frida-server": "4321",
        }
        with tempfile.TemporaryDirectory() as temp:
            stub, log = write_stub_adb(Path(temp), devices_output="emulator-5554\tdevice",
                                       shell_responses=responses)
            result = self.run_doctor(adb_path=stub)
            logged = log.read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("arm64-v8a", result.stdout)
        self.assertIn("Google Play Store installed", result.stdout)
        self.assertIn("Google One        installed", result.stdout)
        self.assertIn("frida-server      running", result.stdout)
        # The doctor is read-only: no device-mutating adb subcommand was issued.
        for token in DEVICE_WRITE_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token, logged)

    def test_unrooted_device_and_missing_apps_are_reported(self):
        responses = {
            "shell id": "uid=10123(u0_a123)",
            "pm list packages": "package:com.android.vending",
        }
        with tempfile.TemporaryDirectory() as temp:
            stub, _log = write_stub_adb(Path(temp), devices_output="emulator-5554\tdevice",
                                        shell_responses=responses)
            result = self.run_doctor(adb_path=stub)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("no - the engine requires root", result.stdout)
        self.assertIn("Google One        MISSING", result.stdout)

    def test_doctor_never_prints_a_google_account_identifier(self):
        """Account IDs must never reach doctor output, even if a device reports one."""
        responses = {
            "shell id": "uid=0(root)",
            "pm list packages": "package:com.android.vending\n"
                                "package:com.google.android.apps.subscriptions.red",
        }
        with tempfile.TemporaryDirectory() as temp:
            stub, _log = write_stub_adb(Path(temp), devices_output="emulator-5554\tdevice",
                                        shell_responses=responses)
            result = self.run_doctor(adb_path=stub)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIsNone(re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", result.stdout),
                          "doctor output must not contain an email address")


class LinuxAdapterGateTests(unittest.TestCase):
    """The adapter's account/offer/confirmation gates stay intact on Linux."""

    def test_paid_stages_require_both_confirmations(self):
        with self.assertRaisesRegex(RuntimeError, "confirmations"):
            macos_runner.run_stage(2, "device-1", {})
        with self.assertRaisesRegex(RuntimeError, "confirmations"):
            macos_runner.run_stage(3, "device-1", {}, confirmed=True)

    def test_stage_scoped_offers_never_use_force_or_switch_accounts(self):
        offers = {2: ("pro12", "12months-eft"), 3: ("pro6", "6months-eft"),
                  4: ("pro6b", "6months-eft-2"), 5: ("pro6c", "6months-eft-ss-2026")}
        for step, (plan, offer) in offers.items():
            with self.subTest(step=step):
                command = macos_runner.stage_command(step, "emulator-5554", "alice@example.com")
                self.assertEqual(command[command.index("--plan") + 1], plan)
                self.assertEqual(macos_runner.STAGES[step][1], offer)
                for required in ("--no-add", "--no-switch"):
                    self.assertIn(required, command)
                self.assertNotIn("--force", command)

    def test_listing_route_is_read_only(self):
        command = macos_runner.stage_command(1, "emulator-5554")
        self.assertIn("--list", command)
        for forbidden in ("--force", "--stack", "--confirmed"):
            self.assertNotIn(forbidden, command)

    def test_checkout_needs_a_verified_email_not_a_placeholder(self):
        for placeholder in ("", "current@device", "not-an-email"):
            with self.subTest(account=placeholder):
                with self.assertRaises(ValueError):
                    macos_runner.stage_command(2, "emulator-5554", placeholder)

    def test_device_serial_must_be_explicit(self):
        for serial in ("", "-s"):
            with self.subTest(serial=serial):
                with self.assertRaises(ValueError):
                    macos_runner.stage_command(0, serial)

    def test_preflight_rejects_ambiguous_devices(self):
        with patch("macos_runner.shutil.which", return_value="/usr/bin/adb"), \
             patch("macos_runner.metadata.version", return_value="16.5.9"), \
             patch("macos_runner.online_serials", return_value=["a", "b"]), \
             patch("macos_runner.auto_select_device", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Multiple different Android devices"):
                macos_runner.preflight()

    def test_preflight_rejects_wrong_frida_version(self):
        with patch("macos_runner.shutil.which", return_value="/usr/bin/adb"), \
             patch("macos_runner.metadata.version", return_value="17.0.0"):
            with self.assertRaisesRegex(RuntimeError, "Frida 16.5.9 required"):
                macos_runner.preflight()

    def test_preflight_reports_missing_adb(self):
        with patch.dict(os.environ, {"ADB_PATH": ""}, clear=False), \
             patch("macos_runner.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "ADB is missing"):
                macos_runner.preflight()


def flat_markdown(path: Path) -> str:
    """Join wrapped lines and drop emphasis markers so assertions test content."""
    text = path.read_text(encoding="utf-8").replace("*", "")
    return re.sub(r"\s+", " ", text)


class LinuxDocumentationTests(unittest.TestCase):
    def test_ubuntu_guide_covers_prerequisites_and_commands(self):
        guide = ROOT / "UBUNTU-SETUP.md"
        self.assertTrue(guide.is_file(), "UBUNTU-SETUP.md must document the Linux port")
        text = guide.read_text(encoding="utf-8")
        for required in (
            "run-linux.sh", "--doctor", "--check", "--list", "--step",
            "adb devices", "python3", "Frida", "US$1", "2–5",
            "python3-venv", "ADB_PATH",
        ):
            with self.subTest(section=required):
                self.assertIn(required, text)

    def test_ubuntu_guide_has_rollback_vps_and_license_sections(self):
        text = (ROOT / "UBUNTU-SETUP.md").read_text(encoding="utf-8")
        lowered = text.lower()
        for heading in ("## rollback", "## vps feasibility",
                        "## security and license caveats"):
            with self.subTest(heading=heading):
                self.assertIn(heading, lowered)

    def test_ubuntu_guide_warns_about_charges_and_device_changes(self):
        text = flat_markdown(ROOT / "UBUNTU-SETUP.md")
        self.assertIn("[!CAUTION]", text)
        self.assertIn("http_proxy", text)
        # The unaudited embedded payload must be called out explicitly.
        self.assertIn("module_521.b64", text)
        self.assertIn("has not been independently audited", text)

    def test_ubuntu_guide_forbids_exposing_debug_ports(self):
        text = flat_markdown(ROOT / "UBUNTU-SETUP.md")
        for port in ("5037", "5555", "27042"):
            with self.subTest(port=port):
                self.assertIn(port, text)
        self.assertIn("Never expose", text)
        # Any mention of these shortcuts must be a prohibition, not a recipe.
        for forbidden in ("--network host", "--privileged"):
            with self.subTest(shortcut=forbidden):
                self.assertIn(f"Do not use `{forbidden}`", text)


if __name__ == "__main__":
    unittest.main()
