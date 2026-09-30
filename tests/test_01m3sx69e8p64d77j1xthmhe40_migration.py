"""Публичная миграция пользовательских подключений guard-artel-bg.

Группа: долгоживущий
Красен до реализации: команда hook-migrate пока отсутствует.

Контракт ответа Оператора: все подкоманды принимают --client codex|claude
и --config <path>; inspect дополнительно --json и возвращает status
(supported/absent/unknown) с reason для unknown. apply принимает
--backup <path> и --verified: последний означает, что Оператор уже
проверил равноценную замену. restore принимает --backup <path>.
Поддерживаемые файлы: Codex hooks.json со списком hooks; Claude Code
settings.json с группами hooks. Неизвестные/managed записи не удаляются.
"""
import json
import os
import random
import sys
from unittest import mock

from orchestrator import artel, config, lease, store
from tests.sandbox import TaskSeededTmpRootTest, capture


class MigrationCliTest(TaskSeededTmpRootTest):
    def setUp(self):
        super().setUp()
        operator_env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        operator_env.start()
        self.addCleanup(operator_env.stop)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")

    def test_ac12_inspect_distinguishes_supported_absent_and_unknown(self):
        """Инвентаризация двух форматов сообщает три исхода без записи файла.

        Ловит мутацию: неизвестная или отсутствующая запись считается
        поддерживаемой и инспектор меняет конфигурацию при чтении.
        """
        for client in ("codex", "claude"):
            with self.subTest(client=client, seed=self.seed):
                path = self.root / f"{client}-inspect.json"
                if client == "codex":
                    supported = {"hooks": [{"event": "PreToolUse", "name": "guard-artel-bg", "command": "guard-artel-bg artel.py run/auto run_in_background"}]}
                    absent = {"hooks": [{"event": "Stop", "command": "delivery-monitor"}]}
                    unknown = {"hooks": [{"event": "Unrecognized", "name": "guard-artel-bg", "command": "guard-artel-bg artel.py run/auto run_in_background"}]}
                else:
                    supported = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "guard-artel-bg artel.py run/auto run_in_background"}]}]}}
                    absent = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "delivery-monitor"}]}]}}
                    unknown = {"hooks": {"UnknownEvent": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "guard-artel-bg artel.py run/auto run_in_background"}]}]}}
                for value, expected in ((supported, "supported"), (absent, "absent"), (unknown, "unknown")):
                    path.write_text(json.dumps(value), encoding="utf-8")
                    original = path.read_bytes()
                    with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "inspect", "--client", client, "--config", str(path), "--json"]):
                        result = json.loads(capture(artel.main))
                    self.assertEqual(result["status"], expected, self.seed)
                    if expected == "unknown":
                        self.assertTrue(result["reason"], self.seed)
                        backup = self.root / f"{client}-unknown.bak"
                        with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply", "--client", client, "--config", str(path), "--backup", str(backup), "--verified"]):
                            with self.assertRaises(SystemExit):
                                capture(artel.main)
                    self.assertEqual(path.read_bytes(), original, self.seed)

    def test_ac13_apply_requires_verification_then_removes_only_target_guard(self):
        """Без подтверждённой замены apply отказывает; после него снимает guard.

        Ловит мутацию: apply снимает контролирующий hook до проверки
        либо удаляет соседний PreToolUse hook вместе с целевым.
        """
        for client in ("codex", "claude"):
            with self.subTest(client=client, seed=self.seed):
                path = self.root / f"{client}-apply.json"
                backup = self.root / f"{client}-apply.bak"
                if client == "codex":
                    source = {"hooks": [{"event": "PreToolUse", "name": "guard-artel-bg", "command": "guard-artel-bg artel.py run/auto run_in_background"}, {"event": "PreToolUse", "name": "neighbor", "command": "other-guard"}, {"event": "PreToolUse", "name": "guard-artel-bg", "command": "guard-artel-bg other-tool"}]}
                else:
                    source = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "guard-artel-bg artel.py run/auto run_in_background"}, {"type": "command", "command": "other-guard"}, {"type": "command", "command": "guard-artel-bg other-tool"}]}]}}
                path.write_text(json.dumps(source), encoding="utf-8")
                original = path.read_bytes()
                with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "inspect", "--client", client, "--config", str(path), "--json"]):
                    self.assertEqual(json.loads(capture(artel.main))["status"], "supported", self.seed)
                with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply", "--client", client, "--config", str(path), "--backup", str(backup)]):
                    with self.assertRaises(SystemExit):
                        capture(artel.main)
                self.assertEqual(path.read_bytes(), original, self.seed)
                with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply", "--client", client, "--config", str(path), "--backup", str(backup), "--verified"]):
                    capture(artel.main)
                migrated = path.read_text(encoding="utf-8")
                self.assertNotIn("guard-artel-bg artel.py run/auto run_in_background", migrated, self.seed)
                self.assertIn("guard-artel-bg other-tool", migrated, self.seed)
                self.assertIn("other-guard", migrated, self.seed)

    def test_ac14_preserves_neighbors_delivery_monitor_and_idempotence(self):
        """Миграция оставляет монитор доставки и произвольные настройки.

        Ловит мутацию: apply переписывает весь hooks или меняет
        конфигурацию повторно, когда целевого подключения уже нет.
        """
        for client in ("codex", "claude"):
            with self.subTest(client=client, seed=self.seed):
                path = self.root / f"{client}-neighbors.json"
                backup = self.root / f"{client}-neighbors.bak"
                if client == "codex":
                    source = {"theme": "dark", "hooks": [{"event": "PreToolUse", "name": "guard-artel-bg", "command": "guard-artel-bg artel.py run/auto run_in_background"}, {"event": "Stop", "command": "delivery-monitor"}, {"event": "PreToolUse", "command": "neighbor"}]}
                else:
                    source = {"theme": "dark", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "guard-artel-bg artel.py run/auto run_in_background"}, {"type": "command", "command": "neighbor"}]}], "Stop": [{"hooks": [{"type": "command", "command": "delivery-monitor"}]}]}}
                path.write_text(json.dumps(source), encoding="utf-8")
                with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply", "--client", client, "--config", str(path), "--backup", str(backup), "--verified"]):
                    capture(artel.main)
                result = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(result["theme"], "dark", self.seed)
                self.assertIn("delivery-monitor", json.dumps(result), self.seed)
                self.assertIn("neighbor", json.dumps(result), self.seed)
                once = path.read_bytes()
                backup_once = backup.read_bytes()
                with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply", "--client", client, "--config", str(path), "--backup", str(backup), "--verified"]):
                    capture(artel.main)
                self.assertEqual(path.read_bytes(), once, self.seed)
                self.assertEqual(backup.read_bytes(), backup_once, self.seed)

    def test_ac15_backup_restores_original_configuration_for_both_clients(self):
        """После изменения restore возвращает исходные байты обоих файлов.

        Ловит мутацию: резервная копия сохраняется после изменения
        или restore собирает приближённый JSON вместо исходного файла.
        """
        for client in ("codex", "claude"):
            with self.subTest(client=client, seed=self.seed):
                path = self.root / f"{client}-restore.json"
                backup = self.root / f"{client}-restore.bak"
                if client == "codex":
                    source = {"hooks": [{"event": "PreToolUse", "name": "guard-artel-bg", "command": "guard-artel-bg artel.py run/auto run_in_background"}], "theme": "light"}
                else:
                    source = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "guard-artel-bg artel.py run/auto run_in_background"}]}]}, "theme": "light"}
                path.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
                original = path.read_bytes()
                with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply", "--client", client, "--config", str(path), "--backup", str(backup), "--verified"]):
                    capture(artel.main)
                self.assertEqual(backup.read_bytes(), original, self.seed)
                with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "restore", "--client", client, "--config", str(path), "--backup", str(backup)]):
                    capture(artel.main)
                self.assertEqual(path.read_bytes(), original, self.seed)

    def test_ac16_migration_does_not_interrupt_live_role_lease(self):
        """При живом lease миграция файла не посылает сигнал и не снимает lease.

        Ловит мутацию: apply завершает роль перед изменением hook —
        сигнал или исчезновение записи lease делает тест красным.
        """
        refusal, _ = lease.acquire(store.db(), self.TASK, "active-role")
        self.assertIsNone(refusal, self.seed)
        before = dict(store.lease_row(store.db(), self.TASK))
        path = self.root / "live-role-hooks.json"
        backup = self.root / "live-role-hooks.bak"
        path.write_text(json.dumps({"hooks": [{"event": "PreToolUse", "name": "guard-artel-bg", "command": "guard-artel-bg artel.py run/auto run_in_background"}]}), encoding="utf-8")
        with mock.patch.object(os, "kill", return_value=None) as signals:
            with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "inspect", "--client", "codex", "--config", str(path), "--json"]):
                capture(artel.main)
            self.assertEqual(dict(store.lease_row(store.db(), self.TASK)), before, self.seed)
            self.assertTrue(all(call.args[1] == 0 for call in signals.call_args_list), self.seed)
            with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply", "--client", "codex", "--config", str(path), "--backup", str(backup), "--verified"]):
                capture(artel.main)
            self.assertTrue(all(call.args[1] == 0 for call in signals.call_args_list), self.seed)
        self.assertEqual(dict(store.lease_row(store.db(), self.TASK)), before, self.seed)
