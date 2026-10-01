"""Дополнительные границы наблюдения и обратимой миграции."""
import json
import os
import sys
from unittest import mock

from orchestrator import artel, config, session, store
from tests.sandbox import TaskSeededTmpRootTest, capture


class ObservationEdgesTest(TaskSeededTmpRootTest):
    def setUp(self):
        super().setUp()
        operator_env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        operator_env.start()
        self.addCleanup(operator_env.stop)

    def test_migration_adds_observation_tables_to_existing_database(self):
        """Ловит мутацию: догон схемы пропускает таблицы наблюдений на старой БД."""
        conn = store.db()
        conn.executescript("DROP TABLE observations; DROP TABLE observation_tasks; "
                           "DROP TABLE observed_runs;")
        store.migrate(conn)
        self.assertTrue({"observations", "observation_tasks", "observed_runs"}.issubset(
            {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}))

    def test_two_chats_cannot_be_chosen_implicitly_for_one_task(self):
        """Ловит мутацию: запуск берёт один из двух чатов, хотя передан третий."""
        conn = store.db()
        identity = session.resolve_session_id(None)
        for chat in ("chat-a", "chat-b"):
            observation_id = store.register_observation(
                conn, config.DEFAULT_TARGET, "codex", chat, identity, [self.TASK])
            store.touch_observation(conn, observation_id)
        with mock.patch.object(artel.subprocess, "Popen", return_value=mock.Mock(pid=4242)) as popen:
            with self.assertRaises(SystemExit):
                artel._launch_detached("run", self.TASK, "codex", "chat-c")
            popen.assert_not_called()

    def test_two_chats_allow_only_the_named_observation(self):
        """Ловит мутацию: два чата одной сессии блокируют точный выбор нужного чата."""
        conn = store.db()
        identity = session.resolve_session_id(None)
        first = store.register_observation(
            conn, config.DEFAULT_TARGET, "codex", "chat-a", identity, [self.TASK])
        second = store.register_observation(
            conn, config.DEFAULT_TARGET, "codex", "chat-b", identity, [self.TASK])
        for observation_id in (first, second):
            store.touch_observation(conn, observation_id)
        with mock.patch.object(artel.subprocess, "Popen", return_value=mock.Mock(pid=4242)):
            capture(artel._launch_detached, "run", self.TASK, "codex", "chat-b")
        self.assertEqual(store.observed_runs(conn, first), [])
        self.assertEqual(len(store.observed_runs(conn, second)), 1)

    def test_explicit_add_reenables_task_after_manual_stop(self):
        """Ловит мутацию: повторное add не возвращает задачу, отключённую ручным stop."""
        conn = store.db()
        observation_id = store.register_observation(
            conn, config.DEFAULT_TARGET, "codex", "chat-a",
            session.resolve_session_id(None), [self.TASK])
        store.disable_task_observation(conn, self.TASK)
        self.assertEqual(store.observation_tasks(conn, observation_id), [])

        store.add_observation_tasks(conn, observation_id, [self.TASK])
        self.assertEqual(store.observation_tasks(conn, observation_id), [self.TASK])

    def test_codex_nested_script_registration_is_migrated_precisely(self):
        """Ловит мутацию: вложенная регистрация Codex с внешним скриптом остаётся без миграции."""
        script = self.root / "guard-artel-bg.py"
        script.write_text("# artel.py auto|run run_in_background\n", encoding="utf-8")
        path = self.root / "hooks.json"
        backup = self.root / "hooks.bak"
        document = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": f"python3 '{script}'"},
            {"type": "command", "command": "neighbor"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "delivery-monitor"}]}]}}
        path.write_text(json.dumps(document), encoding="utf-8")
        with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "inspect",
                                             "--client", "codex", "--config", str(path), "--json"]):
            self.assertEqual(json.loads(capture(artel.main))["status"], "supported")
        with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply",
                                             "--client", "codex", "--config", str(path),
                                             "--backup", str(backup), "--verified"]):
            capture(artel.main)
        migrated = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn(str(script), json.dumps(migrated))
        self.assertIn("neighbor", json.dumps(migrated))
        self.assertIn("delivery-monitor", json.dumps(migrated))
        self.assertTrue(backup.exists())

    def test_managed_guard_is_diagnosed_without_backup_or_change(self):
        """Ловит мутацию: управляемое подключение считается поддерживаемым и удаляется."""
        path = self.root / "hooks.json"
        backup = self.root / "hooks.bak"
        original = json.dumps({"hooks": [{"event": "PreToolUse",
                                         "name": "guard-artel-bg", "managed": True,
                                         "command": "guard-artel-bg artel.py run/auto run_in_background"}]})
        path.write_text(original, encoding="utf-8")
        with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "inspect",
                                             "--client", "codex", "--config", str(path), "--json"]):
            self.assertEqual(json.loads(capture(artel.main))["status"], "unknown")
        with mock.patch.object(sys, "argv", ["artel.py", "hook-migrate", "apply",
                                             "--client", "codex", "--config", str(path),
                                             "--backup", str(backup), "--verified"]):
            with self.assertRaises(SystemExit):
                capture(artel.main)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertFalse(backup.exists())

    def test_role_cannot_change_observation_or_migrate_hooks(self):
        """Ловит мутацию: роль получает возможность менять назначение задач или настройки hook."""
        for argv in (["observe", "register"], ["observe", "add", "any"],
                     ["watch", "--observation", "any"], ["hook-migrate", "apply"]):
            with self.subTest(argv=argv), mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}):
                with mock.patch.object(sys, "argv", ["artel.py", *argv]):
                    with self.assertRaises(SystemExit) as refusal:
                        capture(artel.main)
                    self.assertIn("недоступна", str(refusal.exception))
