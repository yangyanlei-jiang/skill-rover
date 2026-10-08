import json
import subprocess
import sys
from pathlib import Path
from common import Fixture

ROUTER = Path(__file__).resolve().parents[1]
CLI = ROUTER / "scripts" / "rover.py"

class CliTests(Fixture):
    def run_cli(self, *args, payload=None):
        return subprocess.run([sys.executable, str(CLI), "--state-dir", str(self.base / "state"), *args],
                              input=json.dumps(payload) if payload is not None else None,
                              text=True, capture_output=True)

    def test_fresh_due_cli_and_help(self):
        result = self.run_cli("due")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])
        self.assertEqual(self.run_cli("--help").returncode, 0)

    def test_install_requires_acknowledged_review_then_load_and_release(self):
        source = self.skill()
        denied = self.run_cli("install", str(source))
        self.assertNotEqual(denied.returncode, 0)
        result = self.run_cli("install", str(source), "--reviewed", "--review-hours", "0.00001")
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)["id"]
        result = self.run_cli("load", identity, "--session", "cli-session")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Path(json.loads(result.stdout)["path"]).is_file())
        result = self.run_cli("release", "--session", "cli-session")
        self.assertEqual(result.returncode, 0)
        state = json.loads(self.run_cli("status").stdout)
        self.assertEqual(state["uses"], {})

    def test_invalid_command_is_nonzero_and_does_not_modify_source(self):
        source = self.skill()
        result = self.run_cli("load", "../../outside", "--session", "s")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((source / "SKILL.md").is_file())

class IntegrationTests(Fixture):
    def setUp(self):
        super().setUp()
        self.integration = self.module("integration")
        self.life = self.module("lifecycle")
        self.store = self.module("store").Store(self.base / "state")

    def test_both_host_integrations_preserve_settings_and_are_idempotent(self):
        project = self.base / "project with spaces"
        project.mkdir()
        for host, folder, filename in [("claude", ".claude", "settings.json"), ("codex", ".codex", "hooks.json")]:
            directory = project / folder
            directory.mkdir(exist_ok=True)
            existing = {"env": {"EXAMPLE": "keep"}, "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo existing"}]}]}}
            (directory / filename).write_text(json.dumps(existing))
            self.integration.integrate(project, host, self.store.root, ROUTER)
            self.integration.integrate(project, host, self.store.root, ROUTER)
            saved = json.loads((directory / filename).read_text())
            self.assertEqual(saved["env"], {"EXAMPLE": "keep"})
            self.assertEqual(len(saved["hooks"]["SessionStart"]), 2)
            self.assertIn("PostToolUse", saved["hooks"])
            skill_dir = project / (".agents" if host == "codex" else ".claude") / "skills" / "skill-rover"
            self.assertEqual(skill_dir.resolve(), ROUTER.resolve())

    def test_due_reminder_does_not_count_as_review_and_throttles(self):
        a = self.life.install(self.store, self.skill(), review_seconds=60, now=0)
        self.life.load(self.store, a["id"], "s", now=100)
        payload = {"session_id": "s", "hook_event_name": "PostToolUse"}
        first = self.integration.hook(payload, self.store, now=160)
        self.assertIn("additionalContext", first["hookSpecificOutput"])
        self.assertEqual(self.integration.hook(payload, self.store, now=161), {})
        self.assertIn("hookSpecificOutput", self.integration.hook(payload, self.store, now=460))
        self.assertIsNone(self.store.read()["entries"][a["id"]]["reviewed_at"])

    def test_session_end_releases_usage(self):
        a = self.life.install(self.store, self.skill(), now=0)
        self.life.load(self.store, a["id"], "s", now=100)
        result = self.integration.hook({"session_id": "s", "hook_event_name": "SessionEnd"}, self.store, now=200)
        self.assertEqual(result, {})
        self.assertEqual(self.store.read()["uses"], {})

    def test_no_due_event_stays_quiet_and_unknown_event_ignored(self):
        self.assertEqual(self.integration.hook({"session_id": "s", "hook_event_name": "PostToolUse"}, self.store, now=100), {})
        self.assertEqual(self.integration.hook({"session_id": "s", "hook_event_name": "Unknown"}, self.store, now=100), {})

    def test_existing_unrelated_router_install_is_not_overwritten(self):
        project = self.base / "project"
        target = project / ".agents" / "skills" / "skill-rover"
        target.mkdir(parents=True)
        (target / "keep").write_text("user")
        with self.assertRaises(ValueError):
            self.integration.integrate(project, "codex", self.store.root, ROUTER)
        self.assertEqual((target / "keep").read_text(), "user")

