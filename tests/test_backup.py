"""Run with python3 -m unittest discover -s tests -v (bash, jq and tar required).

Exercise the backup script with real archives and a fake router/network in /tmp.
"""

import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
FAKE_COMMAND = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
name = pathlib.Path(sys.argv[0]).name
root = pathlib.Path(os.environ["TEST_ROOT"])
with (root / "calls.jsonl").open("a") as stream:
    stream.write(json.dumps([name, args]) + "\n")
if name == "curl":
    url = next((a for a in args if a.startswith(("http://", "https://"))), "")
    if url.startswith("http://127.0.0.1:79/rci"):
        token = os.environ.get("REQUIRED_TOKEN", "")
        if token and "X-Ndma-Tkn: " + token not in args:
            sys.exit(22)
        endpoint = url.split("/rci", 1)[1].strip("/")
        if endpoint == "whoami":
            sys.exit(22 if os.environ.get("REVOKED_TOKEN") else 0)
        if endpoint == "show/version":
            print(json.dumps(dict(device="Test router", release="5.0", title="KeeneticOS 5", hw_id="KN-TEST")))
        elif endpoint == "system":
            print(json.dumps(dict(hostname="router", description="Test router")))
        elif endpoint == "ls":
            entries = {} if os.environ.get("MISSING_DRIVE") else {
                root.name + ":": dict(mounted=os.environ.get("MOUNTED", "yes")),
                "storage:": dict(mounted="yes"),
            }
            print(json.dumps(dict(entry=entries)))
        elif endpoint == "":
            command = json.loads(args[args.index("-d") + 1])[0]["parse"]
            if os.environ.get("COPY_HTTP_ERROR"):
                sys.exit(22)
            if os.environ.get("COPY_RESPONSE"):
                print(os.environ["COPY_RESPONSE"])
            else:
                destination = command.split(" ", 2)[2]
                device, relative = destination.split(":", 1)
                drive = root / "opt/backups" if device == "storage" else root
                if not os.environ.get("COPY_NO_FILE"):
                    (drive / relative).write_text("" if os.environ.get("COPY_EMPTY") else "router backup\n")
                print('[{"status": "success"}]')
        else:
            sys.exit("Unexpected RCI endpoint: " + endpoint)
    elif url.startswith("https://api.github.com/"):
        if url != "https://api.github.com/repos/KirillShchetinnikov/KeenSnap/releases/latest":
            sys.exit("Unexpected update source: " + url)
        print('{"tag_name": "1.4.3"}')
    elif url.startswith("https://api.telegram.org/"):
        print('{"ok":true}\n200')
    else:
        sys.exit("Unexpected network request: " + url)
elif name == "opkg":
    if args == ["list-installed"]:
        print("tar - 1.0\n7-zip - 1.0")
    elif args == ["print-architecture"]:
        print("arch aarch64-3.10 10")
    else:
        sys.exit("Unexpected package operation")
elif name == "7zz":
    print("7-Zip test banner\nScanning the drive:\nCreating archive...")
    pathlib.Path(args[-2]).write_bytes(b"encrypted archive placeholder")
    if os.environ.get("SEVENZIP_FAIL"):
        print("ERROR: archive creation failed", file=sys.stderr)
        sys.exit(2)
    print("Everything is Ok")
elif name == "tar":
    if os.environ.get("TAR_FAIL"):
        print("archive creation failed", file=sys.stderr)
        sys.exit(2)
    os.execv(os.environ["REAL_TAR"], ["tar"] + args)
elif name == "keensnap":
    sys.exit(0)
elif name == "wg":
    print("wg0\ttest-private-key")
elif name not in ("logger", "s3cmd", "chown", "crond", "killall"):
    sys.exit("Unexpected command: " + name)
'''


class BackupIntegrationTests(unittest.TestCase):
    def setUp(self):
        Path("/tmp/mnt").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="keensnap-tests-", dir="/tmp/mnt")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.opt = self.root / "opt"
        self.drive = self.opt / "backups"
        self.drive.mkdir(parents=True)
        self.config = self.root / "config"
        self.config.mkdir()
        shutil.copy(REPO / "common/config.conf", self.config / "config.conf")
        shutil.copy(REPO / "common/keensnap-config.sh", self.root / "keensnap-config.sh")
        self.overrides = self.config / "config.d"
        self.overrides.mkdir()
        self.log = self.root / "backup.log"
        self.log.touch()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for command in ("curl", "opkg", "logger", "7zz", "tar", "keensnap", "wg", "crond", "killall", "chown"):
            executable = self.bin / command
            executable.write_text(FAKE_COMMAND)
            executable.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        TEST_ROOT=str(self.root), REAL_TAR=shutil.which("tar"),
                        TMPDIR=str(self.root))
        self.script = self.root / "keensnap-init"
        source = (REPO / "common/keensnap-init").read_text()
        source = source.replace('CONFIG_DIR="/opt/etc/keensnap"', f'CONFIG_DIR="{self.config}"')
        source = source.replace('KEENSNAP_DIR="/opt/root/KeenSnap"', f'KEENSNAP_DIR="{self.root}"')
        source = source.replace('-C /opt ', f'-C "{self.opt}" ')
        self.script.write_text(source)
        self.cli = self.root / "cli.sh"
        cli = (REPO / "common/keensnap.sh").read_text()
        cli = cli.replace('CONFIG_DIR="/opt/etc/keensnap"', f'CONFIG_DIR="{self.config}"')
        cli = cli.replace('KEENSNAP_DIR="/opt/root/KeenSnap"', f'KEENSNAP_DIR="{self.root}"')
        cli = cli.replace('CRON_FILE="/opt/etc/crontab"', f'CRON_FILE="{self.root}/crontab"')
        self.cli.write_text(cli)

    def run_cli(self, command):
        return subprocess.run(["bash", str(self.cli), command], env=self.env,
                              text=True, capture_output=True, timeout=15)

    def run_backup(self, **overrides):
        settings = dict(LOG_FILE=str(self.log), SELECTED_DRIVE=str(self.drive),
                        BACKUP_STARTUP_CONFIG=True, AUTO_UPDATE=False,
                        TELEGRAM_SUCCESS_NOTIFY=True, BOT_TOKEN="test-token", CHAT_ID="123")
        settings.update(overrides)
        (self.overrides / "10-local.conf").write_text("".join(
            f"{key}={str(value).lower() if isinstance(value, bool) else json.dumps(value)}\n"
            for key, value in settings.items()))
        result = subprocess.run(["bash", str(self.script), "start", "manual"],
                                env=self.env, text=True, capture_output=True, timeout=15)
        self.assertFalse(list(self.root.glob("keensnap-status.*")))
        return result

    def calls(self, command="curl"):
        return [args for name, args in map(json.loads, (self.root / "calls.jsonl").read_text().splitlines())
                if name == command]

    def success_notifications(self):
        return [args for args in self.calls() if any("Бэкап KeenSnap успешно завершён" in arg for arg in args)]

    def test_success_with_token_and_without_token(self):
        for token in ("", "rci-secret"):
            with self.subTest(token=bool(token)):
                self.env["REQUIRED_TOKEN"] = token
                result = self.run_backup(RCI_TOKEN=token)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                requests = [args for args in self.calls() if any("/rci" in arg for arg in args)]
                current_requests = requests[-5:] if token else requests
                self.assertTrue(all("-A" in args for args in current_requests))
                if token:
                    self.assertTrue(all("X-Ndma-Tkn: " + token in args for args in current_requests))
                else:
                    self.assertFalse(any("X-Ndma-Tkn:" in arg for args in requests for arg in args))
                archive = next(self.drive.glob("*.tar.gz"))
                with tarfile.open(archive) as backup:
                    self.assertTrue(any(name.endswith("startup-config.txt") for name in backup.getnames()))
                self.assertTrue(self.success_notifications())

    def test_revoked_token_stops_before_copy(self):
        self.env["REVOKED_TOKEN"] = "1"
        result = self.run_backup(RCI_TOKEN="revoked")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Токен RCI недействителен", result.stdout)
        self.assertFalse(list(self.drive.iterdir()))
        self.assertFalse(self.success_notifications())

    def test_system_backup_overrides_separate_files_and_keeps_entware(self):
        result = self.run_backup(BACKUP_SYSTEM=True, BACKUP_STARTUP_CONFIG=True,
                                 BACKUP_FIRMWARE=True, BACKUP_ENTWARE=True,
                                 BACKUP_WG_PRIVATE_KEY=True, UPLOAD_METHOD="Telegram")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        commands = [json.loads(args[args.index("-d") + 1])[0]["parse"]
                    for args in self.calls() if "http://127.0.0.1:79/rci/" in args]
        self.assertEqual(len(commands), 1)
        self.assertTrue(commands[0].startswith("copy flash:/backup "))
        with tarfile.open(next(self.drive.glob("*.tar.gz"))) as archive:
            names = archive.getnames()
            self.assertTrue(any(name.endswith("_system.backup") for name in names))
            self.assertTrue(any(name.endswith("_Entware.tar.gz") for name in names))
            self.assertFalse(any(name.endswith("WireGuard-Private-Key.txt") for name in names))
            self.assertFalse(any(name.endswith(("startup-config.txt", "firmware.bin")) for name in names))
        report = next(arg for args in self.calls() for arg in args if arg.startswith("caption="))
        self.assertIn("System", report)
        self.assertNotIn("startup-config", report)
        self.assertNotIn("firmware", report)
        self.assertNotIn("WireGuard-Private-Key", report)
        self.assertEqual(self.calls("wg"), [])
        self.assertTrue(self.success_notifications())

    def test_disabled_system_backup_keeps_separate_config_firmware_and_wg(self):
        result = self.run_backup(BACKUP_SYSTEM=False, BACKUP_FIRMWARE=True, BACKUP_WG_PRIVATE_KEY=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with tarfile.open(next(self.drive.glob("*.tar.gz"))) as archive:
            names = archive.getnames()
            self.assertTrue(any(name.endswith("startup-config.txt") for name in names))
            self.assertTrue(any(name.endswith("firmware.bin") for name in names))
            self.assertTrue(any(name.endswith("WireGuard-Private-Key.txt") for name in names))
            self.assertFalse(any(name.endswith("_system.backup") for name in names))
        self.assertEqual(self.calls("wg"), [["show", "all", "private-key"]])

    def test_system_backup_rejects_missing_or_empty_image_without_fallback(self):
        for failure in ("COPY_NO_FILE", "COPY_EMPTY"):
            with self.subTest(failure=failure):
                self.env.pop("COPY_NO_FILE", None)
                self.env.pop("COPY_EMPTY", None)
                self.env[failure] = "1"
                result = self.run_backup(BACKUP_SYSTEM=True, BACKUP_FIRMWARE=True,
                                         BACKUP_WG_PRIVATE_KEY=True,
                                         UPLOAD_METHOD="Telegram")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("не создан или пуст", result.stdout)
                reports = [arg for args in self.calls() for arg in args if arg.startswith("caption=")]
                self.assertIn("System: ошибка", reports[-1])
                self.assertNotIn("Бэкап startup-config", result.stdout)
                self.assertNotIn("Бэкап firmware", result.stdout)
                self.assertEqual(self.calls("wg"), [])
                self.assertFalse(self.success_notifications())

    def test_unsupported_system_backup_is_error_without_fallback(self):
        self.env["COPY_RESPONSE"] = '[{"status":"error","message":"unsupported command"}]'
        result = self.run_backup(BACKUP_SYSTEM=True, BACKUP_FIRMWARE=True, BACKUP_WG_PRIVATE_KEY=True)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Ошибка при сохранении системы", result.stdout)
        self.assertIn("Проверьте поддержку flash:/backup", result.stdout)
        self.assertNotIn("Бэкап startup-config", result.stdout)
        self.assertNotIn("Бэкап firmware", result.stdout)
        self.assertEqual(self.calls("wg"), [])
        self.assertFalse(self.success_notifications())

    def test_copy_errors_fail_backup_and_are_visible_in_report(self):
        for response in ('[{"result":{"status":"error","message":"copy failed"}}]', 'not json', 'null'):
            with self.subTest(response=response):
                self.env["COPY_RESPONSE"] = response
                result = self.run_backup(UPLOAD_METHOD="Telegram", BACKUP_FIRMWARE=True)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("Ошибка при сохранении startup-config", result.stdout)
                self.assertIn("Ошибка при сохранении firmware", result.stdout)
                reports = [arg for args in self.calls() for arg in args if arg.startswith("caption=")]
                self.assertIn("startup-config: ошибка", reports[-1])
                self.assertIn("firmware: ошибка", reports[-1])
                self.assertFalse(self.success_notifications())

    def test_http_copy_error_fails_backup(self):
        self.env["COPY_HTTP_ERROR"] = "1"
        result = self.run_backup()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.success_notifications())

    def test_missing_and_unmounted_drive_stop_backup(self):
        for state in (dict(MISSING_DRIVE="1"), dict(MOUNTED="no")):
            with self.subTest(state=state):
                self.env.pop("MISSING_DRIVE", None)
                self.env.pop("MOUNTED", None)
                self.env.update(state)
                result = self.run_backup()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("не подключён", result.stdout)
                self.assertFalse(list(self.drive.iterdir()))

    def test_empty_and_nonexistent_path_stop_backup(self):
        for path in ("", str(self.drive / "absent")):
            with self.subTest(path=path):
                result = self.run_backup(SELECTED_DRIVE=path)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(list(self.drive.iterdir()))

    def test_mounted_drive_subdirectory(self):
        target = self.drive / "subfolder"
        target.mkdir()
        result = self.run_backup(SELECTED_DRIVE=str(target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(list(target.glob("*.tar.gz")))

    def test_internal_storage(self):
        self.script.write_text(self.script.read_text().replace('= "/storage"', f'= "{self.drive}"'))
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(list(self.drive.glob("*.tar.gz")))

    def test_successful_update_preserves_success_exit_code(self):
        self.script.write_text(self.script.read_text().replace('SCRIPT_VERSION=""', 'SCRIPT_VERSION="1.0"'))
        result = self.run_backup(AUTO_UPDATE=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.calls("keensnap"), [["script_update", "silent"]])

    def test_entware_excludes_absolute_paths_patterns_and_current_backup(self):
        for name in ("var/log/test.log", "cache/file", "tmp/temporary", "keep/data.txt"):
            path = self.opt / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("test data")
        result = self.run_backup(BACKUP_ENTWARE=True, ENTWARE_EXCLUDE="/opt/var/log cache tmp/*")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with tarfile.open(next(self.drive.glob("*.tar.gz"))) as backup:
            member = next(member for member in backup if member.name.endswith("_Entware.tar.gz"))
            with tarfile.open(fileobj=io.BytesIO(backup.extractfile(member).read())) as entware:
                names = entware.getnames()
                self.assertIn("./keep/data.txt", names)
                self.assertFalse(any("test.log" in name or "cache" in name or "temporary" in name for name in names))
                self.assertFalse(any("backup20" in name for name in names))

    def test_entware_tar_failure_without_error_keyword_is_failure(self):
        self.env["TAR_FAIL"] = "1"
        result = self.run_backup(BACKUP_ENTWARE=True, ARCHIVE_PASSWORD="password")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Ошибка при сохранении Entware", result.stdout)
        self.assertFalse(self.success_notifications())

    def test_encrypted_archive_uses_low_compression_and_one_thread(self):
        result = self.run_backup(ARCHIVE_PASSWORD="password")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("-mx=1", self.calls("7zz")[0])
        self.assertIn("-mmt=1", self.calls("7zz")[0])
        self.assertIn("Архив создан", result.stdout)
        self.assertNotIn("7-Zip test banner", result.stdout)
        self.assertNotIn("Scanning the drive:", self.log.read_text())
        self.assertNotIn("Everything is Ok", self.log.read_text())

    def test_encrypted_archive_failure_keeps_diagnostics(self):
        self.env["SEVENZIP_FAIL"] = "1"
        result = self.run_backup(ARCHIVE_PASSWORD="password")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Ошибка при создании архива", result.stdout)
        self.assertIn("ERROR: archive creation failed", result.stdout)
        self.assertIn("ERROR: archive creation failed", self.log.read_text())
        self.assertFalse(list(self.drive.glob("*.7z")))
        self.assertFalse(self.success_notifications())

    def test_archive_error_sends_current_log(self):
        self.env["TAR_FAIL"] = "1"
        result = self.run_backup()
        self.assertNotEqual(result.returncode, 0)
        documents = [arg for args in self.calls() for arg in args if arg.startswith("document=@")]
        self.assertEqual(documents, [f"document=@{self.log}"])
        self.assertIn("Ошибка при создании архива", self.log.read_text())
        self.assertFalse(self.success_notifications())

    def test_cli_status_uses_rci_token(self):
        (self.overrides / "10-local.conf").write_text('RCI_TOKEN="cli-secret"\n')
        self.env["REQUIRED_TOKEN"] = "cli-secret"
        result = self.run_cli("status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Test router", result.stdout)
        self.assertTrue(all("X-Ndma-Tkn: cli-secret" in args for args in self.calls()))

    def test_cli_status_shows_effective_system_backup_selection(self):
        (self.overrides / "10-local.conf").write_text(
            'BACKUP_SYSTEM=true\nBACKUP_STARTUP_CONFIG=true\nBACKUP_FIRMWARE=true\n'
            'BACKUP_ENTWARE=true\nBACKUP_WG_PRIVATE_KEY=true\n')
        result = self.run_cli("status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("System, Entware", result.stdout)
        self.assertNotIn("Startup-Config", result.stdout)
        self.assertNotIn("Firmware", result.stdout)
        self.assertNotIn("WireGuard-Private-Key", result.stdout)

    def prepare_installer(self):
        for command in ("s3cmd", "chown", "crond", "killall"):
            executable = self.bin / command
            executable.write_text(FAKE_COMMAND)
            executable.chmod(0o755)
        config_dir = self.opt / "etc/keensnap"
        config_dir.mkdir(parents=True)
        shutil.copy(REPO / "common/config.conf", config_dir / "config.conf")
        app_dir = self.opt / "root/KeenSnap"
        app_dir.mkdir(parents=True)
        shutil.copy(REPO / "common/keensnap-config.sh", app_dir / "keensnap-config.sh")
        installer = self.root / "postinst"
        installer.write_text((REPO / "common/ipk/postinst").read_text().replace("/opt", str(self.opt)))
        return installer, config_dir

    def test_install_keeps_overrides_and_does_not_migrate_legacy_configs(self):
        installer, config_dir = self.prepare_installer()
        overrides = config_dir / "config.d"
        overrides.mkdir()
        local_config = overrides / "10-local.conf"
        custom = 'RCI_TOKEN="custom-token"\nCRON_SCHEDULE=""\n'
        local_config.write_text(custom)
        legacy = self.opt / "root/KeenSnap/config.conf"
        legacy.write_text('RCI_TOKEN="legacy-token"\n')
        old_defaults = config_dir / "defaults.conf"
        old_defaults.write_text('CRON_SCHEDULE="5 4 * * *"\n')
        result = subprocess.run(["bash", str(installer)], env=self.env,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(local_config.read_text(), custom)
        self.assertEqual(local_config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(legacy.read_text(), 'RCI_TOKEN="legacy-token"\n')
        self.assertTrue(old_defaults.is_file())
        self.assertEqual((config_dir / "config.conf").read_text(), (REPO / "common/config.conf").read_text())
        self.assertFalse((self.opt / "etc/crontab").read_text())

    def test_fresh_install_uses_defaults_without_creating_user_config(self):
        installer, config_dir = self.prepare_installer()
        result = subprocess.run(["bash", str(installer)], env=self.env,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((config_dir / "config.d").is_dir())
        self.assertFalse(list((config_dir / "config.d").iterdir()))
        self.assertIn("0 3 * * * root PATH=", (self.opt / "etc/crontab").read_text())

    def test_defaults_work_with_empty_or_missing_overrides_directory(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                if missing:
                    self.overrides.rmdir()
                result = self.run_cli("config")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("BACKUP_SYSTEM='false'", result.stdout)
                self.assertIn("CRON_SCHEDULE='0 3 * * *'", result.stdout)

    def test_ordered_overrides_and_shell_values_apply_to_cli_and_backup(self):
        # Create the later file first to distinguish filename order from directory order.
        (self.overrides / "90-final.conf").write_text(
            'export BACKUP_SYSTEM="true"\nCRON_SCHEDULE=""\n'
            'CHAT_ID=""\nBACKUP_SYSTEM=false\nBACKUP_SYSTEM=true\n'
            'HASHTAG="a single \'quote\' and $CHAT_ID"\n')
        (self.overrides / "05-earlier.conf").write_text('BACKUP_SYSTEM=false\nCHAT_ID="early"\n')
        (self.overrides / "99-ignore.conf-opkg").write_text('BACKUP_SYSTEM=false\n')
        (self.overrides / "99-directory.conf").mkdir()
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with tarfile.open(next(self.drive.glob("*.tar.gz"))) as archive:
            self.assertTrue(any(name.endswith("_system.backup") for name in archive.getnames()))
        result = self.run_cli("config")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        effective = self.root / "effective.conf"
        effective.write_text(result.stdout)
        values = subprocess.run(
            ["sh", "-c", '. "$1"; printf "%s\\n" "$BACKUP_SYSTEM" "$CHAT_ID" "$HASHTAG"', "sh", str(effective)],
            text=True, capture_output=True, timeout=15)
        self.assertEqual(values.returncode, 0, values.stderr)
        self.assertEqual(values.stdout, "true\n\na single 'quote' and \n")
        self.assertEqual(result.stdout.count("BACKUP_SYSTEM="), 1)
        result = self.run_cli("apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.root / "crontab").read_text())


if __name__ == "__main__":
    unittest.main()
