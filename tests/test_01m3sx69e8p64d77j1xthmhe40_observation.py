"""Публичный CLI наблюдения и управляемого фонового запуска.

Группа: долгоживущий
Красен до реализации: обязательные client/chat и отказ при несовпадении контекста запуска по R1-F1 ещё не реализованы.

Контракт ответа Оператора: register печатает JSON с id; show --json содержит
id, project, client, chat, tasks, state, last_seen_at, fresh и runs.
Поля runs: task, pid, log. stop прекращает наблюдение; новое register
является явным способом возобновить его. Свежесть устанавливает только
watch --observation. Имена настроек heartbeat код выбирает сам; тест
ищет публичные именованные значения по их смыслу.
"""
import json
import os
import random
import sys
import threading
import time
import unittest
from unittest import mock

from orchestrator import artel, auto, config, store, watch, runner, fsm, budget, catalog, answer, lease
from tests.sandbox import TaskSeededTmpRootTest, capture, patch_sleep


class ObservationCliTest(TaskSeededTmpRootTest):
    def setUp(self):
        super().setUp()
        operator_env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        operator_env.start()
        self.addCleanup(operator_env.stop)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.chat = f"chat-{random.Random(self.seed).randrange(1 << 30)}"

    def test_ac2_show_persists_identity_tasks_state_and_last_contact(self):
        """Регистрация переживает отдельный вызов диагностики и показывает привязки.

        Ловит мутацию: show теряет project, chat или явный список задач,
        либо регистрация ошибочно отмечает связь свежей.
        """
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", self.TASK]):
            observation_id = json.loads(capture(artel.main))["id"]
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
            shown = json.loads(capture(artel.main))
        self.assertEqual(shown["id"], observation_id, self.seed)
        self.assertEqual(shown["project"], config.DEFAULT_TARGET, self.seed)
        self.assertEqual(shown["client"], "codex", self.seed)
        self.assertEqual(shown["chat"], self.chat, self.seed)
        self.assertEqual(shown["tasks"], [self.TASK], self.seed)
        self.assertEqual(shown["state"], "active", self.seed)
        self.assertIsNone(shown["last_seen_at"], self.seed)
        self.assertFalse(shown["fresh"], self.seed)

    def test_ac3_detached_launch_records_pid_log_and_observation(self):
        """Свежий наблюдатель разрешает run, а диагностика показывает связь запуска.

        Ловит мутацию: процесс запускается, но его PID, лог или ID
        наблюдения не сохраняются в диагностируемом состоянии.
        """
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", self.TASK]):
            observation_id = json.loads(capture(artel.main))["id"]
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]), patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                capture(artel.main)
        for command, pid in (("run", 43210), ("auto", 43211)):
            with self.subTest(command=command, seed=self.seed):
                proc = mock.Mock(pid=pid)
                with mock.patch.object(sys, "argv", ["artel.py", command, self.TASK, "--client", "codex", "--chat", self.chat]), mock.patch.object(artel.subprocess, "Popen", return_value=proc):
                    capture(artel.main)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
            shown = json.loads(capture(artel.main))
        for pid in (43210, 43211):
            self.assertTrue(any(r["task"] == self.TASK and r["pid"] == pid and r["log"].endswith(".log") for r in shown["runs"]), self.seed)

    def test_ac4_cli_changes_task_set_and_rejects_role_registration(self):
        """Оператор меняет явный набор через CLI, роль не подделывает регистрацию.

        Ловит мутацию: add/remove не сохраняет новый список либо роль
        получает возможность зарегистрировать наблюдение.
        """
        second = "T002"
        store.insert_task(store.db(), second, "Вторая", "in_dev", "task/t002", config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "claude", "--chat", self.chat, "--tasks", self.TASK]):
            observation_id = json.loads(capture(artel.main))["id"]
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "add", observation_id, "--tasks", second]):
            capture(artel.main)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
            self.assertCountEqual(json.loads(capture(artel.main))["tasks"], [self.TASK, second], self.seed)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "remove", observation_id, "--tasks", self.TASK]):
            capture(artel.main)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
            self.assertEqual(json.loads(capture(artel.main))["tasks"], [second], self.seed)
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}), mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", second]):
            with self.assertRaises(SystemExit):
                capture(artel.main)
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}), mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]):
            with self.assertRaises(SystemExit):
                capture(artel.main)

    def test_ac5_watch_heartbeat_makes_contact_fresh_with_three_period_limit(self):
        """Регистрация несвежа, а одна итерация штатного watch обновляет связь.

        Ловит мутацию: heartbeat вынесен из watch или порог отличается
        от трёх настроенных периодов — fresh остаётся ложным либо
        соотношение настроек расходится.
        """
        settings = [(name, value) for name, value in vars(config).items()
                    if name.isupper() and isinstance(value, (int, float))
                    and value > 0 and ("OBSERV" in name or "HEARTBEAT" in name)]
        periods = [(name, value) for name, value in settings
                   if any(word in name for word in ("HEARTBEAT", "PERIOD", "INTERVAL"))]
        thresholds = [(name, value) for name, value in settings
                      if any(word in name for word in ("STALE", "FRESH", "TTL", "TIMEOUT", "MAX_AGE"))]
        self.assertTrue(any(limit == 3 * period for _, period in periods
                            for _, limit in thresholds), self.seed)
        for client in ("codex", "claude"):
            with self.subTest(client=client, seed=self.seed):
                with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", client, "--chat", self.chat, "--tasks", self.TASK]):
                    observation_id = json.loads(capture(artel.main))["id"]
                with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
                    self.assertFalse(json.loads(capture(artel.main))["fresh"], self.seed)
                with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]), patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))), mock.patch.object(threading, "Timer", side_effect=AssertionError("hidden heartbeat timer")), mock.patch.object(artel.subprocess, "Popen", side_effect=AssertionError("external heartbeat service")):
                    with self.assertRaisesRegex(RuntimeError, "watch ended"):
                        capture(artel.main)
                with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
                    shown = json.loads(capture(artel.main))
                self.assertTrue(shown["fresh"], self.seed)
                self.assertIsNotNone(shown["last_seen_at"], self.seed)

    def test_ac6_run_and_auto_refuse_before_spawn_without_live_observer(self):
        """Ни run, ни auto не создаёт фоновый процесс без наблюдателя.

        Ловит мутацию: проверка свежести стоит после Popen — отказ
        появляется, но процесс уже создан.
        """
        for command in ("run", "auto"):
            with self.subTest(command=command, seed=self.seed):
                with mock.patch.object(sys, "argv", ["artel.py", command, self.TASK, "--client", "codex", "--chat", self.chat]), mock.patch.object(artel.subprocess, "Popen") as popen:
                    with self.assertRaises(SystemExit) as ctx:
                        capture(artel.main)
                    popen.assert_not_called()
                self.assertIn("наблюд", str(ctx.exception).lower(), self.seed)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", self.TASK]):
            observation_id = json.loads(capture(artel.main))["id"]
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]), patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                capture(artel.main)
        settings = [(name, value) for name, value in vars(config).items()
                    if name.isupper() and isinstance(value, (int, float))
                    and value > 0 and ("OBSERV" in name or "HEARTBEAT" in name)]
        periods = [(name, value) for name, value in settings
                   if any(word in name for word in ("HEARTBEAT", "PERIOD", "INTERVAL"))]
        thresholds = [(name, value) for name, value in settings
                      if any(word in name for word in ("STALE", "FRESH", "TTL", "TIMEOUT", "MAX_AGE"))]
        stale_name = next(name for name, limit in thresholds
                          if any(limit == 3 * period for _, period in periods))
        with mock.patch.object(config, stale_name, 0):
            time.sleep(0.01)
            for command in ("run", "auto"):
                with self.subTest(command=command, state="stale", seed=self.seed):
                    with mock.patch.object(sys, "argv", ["artel.py", command, self.TASK, "--client", "codex", "--chat", self.chat]), mock.patch.object(artel.subprocess, "Popen") as popen:
                        with self.assertRaises(SystemExit) as ctx:
                            capture(artel.main)
                        popen.assert_not_called()
                    self.assertTrue(any(word in str(ctx.exception).lower() for word in ("протух", "устар", "связ")), self.seed)

    def test_ac7_explicit_attach_runs_without_observation(self):
        """Передний план вызывает существующие run и auto без наблюдателя.

        Ловит мутацию: проверка наблюдения перенесена перед разбором
        --attach — передний план также получает отказ.
        """
        with mock.patch.object(runner, "cmd_run") as run, mock.patch.object(sys, "argv", ["artel.py", "run", self.TASK, "--attach"]):
            capture(artel.main)
            run.assert_called_once_with(self.TASK)
        with mock.patch.object(auto, "cmd_auto") as cycle, mock.patch.object(sys, "argv", ["artel.py", "auto", self.TASK, "--attach"]):
            capture(artel.main)
            cycle.assert_called_once_with(self.TASK, wait_zone=False)

    def test_ac8_unknown_foreign_unassigned_and_role_launch_refused(self):
        """Свежая связь одной задачи не разрешает чужие адреса и роль.

        Ловит мутацию: выбор наблюдения проверяет только fresh и
        игнорирует task, project либо роль вызывающего процесса.
        """
        store.insert_task(store.db(), "T002", "Не назначена", "in_dev", "task/t002", config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        store.insert_task(store.db(), "T003", "Чужой проект", "in_dev", "task/t003", "foreign", config.DEFAULT_BUDGET_USD)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", self.TASK]):
            observation_id = json.loads(capture(artel.main))["id"]
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]), patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                capture(artel.main)
        for task in ("T002", "T003", "T999"):
            with self.subTest(task=task, seed=self.seed):
                with mock.patch.object(sys, "argv", ["artel.py", "run", task, "--client", "codex", "--chat", self.chat]), mock.patch.object(artel.subprocess, "Popen") as popen:
                    with self.assertRaises(SystemExit):
                        capture(artel.main)
                    popen.assert_not_called()
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}), mock.patch.object(sys, "argv", ["artel.py", "run", self.TASK, "--client", "codex", "--chat", self.chat]), mock.patch.object(artel.subprocess, "Popen") as popen:
            with self.assertRaises(SystemExit):
                capture(artel.main)
            popen.assert_not_called()

    def test_ac8_launch_requires_matching_client_and_chat(self):
        """Контекст запуска обязателен и совпадает с наблюдением.

        Ловит мутацию: запуск использует только session_id или игнорирует
        отсутствие и несовпадение client/chat перед Popen.
        """
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", self.TASK]):
            observation_id = json.loads(capture(artel.main))["id"]
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]), patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                capture(artel.main)
        contexts = (
            [],
            ["--client", "codex"],
            ["--chat", self.chat],
            ["--client", "codex", "--chat", ""],
            ["--client", "unknown", "--chat", self.chat],
            ["--client", "claude", "--chat", self.chat],
            ["--client", "codex", "--chat", self.chat + "-other"],
        )
        for command in ("run", "auto"):
            for context in contexts:
                with self.subTest(command=command, context=context, seed=self.seed):
                    with mock.patch.object(sys, "argv", ["artel.py", command, self.TASK, *context]), mock.patch.object(artel.subprocess, "Popen") as popen:
                        with self.assertRaises(SystemExit):
                            capture(artel.main)
                        popen.assert_not_called()

    def test_ac9_other_task_decision_does_not_drop_shared_observation(self):
        """Решение по одной задаче оставляет вторую в свежем наблюдении.

        Ловит мутацию: stop, пауза или смена состояния одной задачи
        выключает общее наблюдение или удаляет остальные задачи.
        """
        store.insert_task(store.db(), "T002", "Вторая", "in_dev", "task/t002", config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", f"{self.TASK},T002"]):
            observation_id = json.loads(capture(artel.main))["id"]
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]), patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                capture(artel.main)
        refusal, _ = lease.acquire(store.db(), self.TASK, "active-role")
        self.assertIsNone(refusal, self.seed)
        with mock.patch.object(os, "kill", return_value=None), mock.patch.object(sys, "argv", ["artel.py", "stop", self.TASK]):
            capture(artel.main)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
            stopped_task = json.loads(capture(artel.main))
        self.assertIn("T002", stopped_task["tasks"], self.seed)
        self.assertTrue(stopped_task["fresh"], self.seed)
        with mock.patch.object(sys, "argv", ["artel.py", "pause", self.TASK]):
            capture(artel.main)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
            paused = json.loads(capture(artel.main))
        self.assertIn("T002", paused["tasks"], self.seed)
        self.assertTrue(paused["fresh"], self.seed)
        store.update_task(store.db(), self.TASK, state="escalated")
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "show", observation_id, "--json"]):
            shown = json.loads(capture(artel.main))
        self.assertIn("T002", shown["tasks"], self.seed)
        self.assertTrue(shown["fresh"], self.seed)

    def test_ac10_stop_requires_explicit_new_registration_to_resume(self):
        """Остановленное наблюдение не даёт auto разрешения до нового register.

        Ловит мутацию: stop оставляет прежнюю свежую запись пригодной
        для auto либо watch молча возобновляет её.
        """
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", self.TASK]):
            observation_id = json.loads(capture(artel.main))["id"]
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]), patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))):
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                capture(artel.main)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "stop", observation_id]):
            capture(artel.main)
        with mock.patch.object(sys, "argv", ["artel.py", "auto", self.TASK, "--client", "codex", "--chat", self.chat]), mock.patch.object(artel.subprocess, "Popen") as popen:
            with self.assertRaises(SystemExit):
                capture(artel.main)
            popen.assert_not_called()
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]):
            with self.assertRaises(SystemExit):
                capture(artel.main)
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", self.TASK]):
            replacement = json.loads(capture(artel.main))["id"]
        self.assertNotEqual(replacement, observation_id, self.seed)

    def test_ac11_observer_keeps_task_authority_and_lease_unchanged(self):
        """Чтение событий не меняет состояние, бюджет и право на lease.

        Ловит мутацию: адаптер watch вызывает операторскую команду
        или освобождает чужой lease во время heartbeat.
        """
        with mock.patch.object(sys, "argv", ["artel.py", "observe", "register", "--client", "codex", "--chat", self.chat, "--tasks", self.TASK]):
            observation_id = json.loads(capture(artel.main))["id"]
        before = dict(store.get_task(store.db(), self.TASK))
        with mock.patch.object(sys, "argv", ["artel.py", "watch", "--observation", observation_id]), patch_sleep(watch, mock.Mock(side_effect=RuntimeError("watch ended"))), mock.patch.object(fsm, "cmd_approve") as approve, mock.patch.object(budget, "cmd_budget") as change_budget, mock.patch.object(catalog, "cmd_new") as new_task, mock.patch.object(answer, "cmd_zones_extend") as expand_zones:
            with self.assertRaisesRegex(RuntimeError, "watch ended"):
                capture(artel.main)
            for forbidden in (approve, change_budget, new_task, expand_zones):
                forbidden.assert_not_called()
        after = dict(store.get_task(store.db(), self.TASK))
        for field in ("state", "budget_usd", "branch"):
            self.assertEqual(after[field], before[field], self.seed)
        self.assertIsNone(store.lease_row(store.db(), self.TASK), self.seed)
