"""Позиции просмотра и подтверждения наблюдения через публичные команды.

Группа: долгоживущий
Красен до реализации: у `observe` ещё нет `events` и `acknowledge`, а
`show` не выдаёт позиции; вызовы отказывают или не возвращают поля.
"""

import io
import json
import os
import random
import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from unittest import mock

from orchestrator import artel, config, store, watch
from tests.sandbox import TaskSeededTmpRootTest, capture


def watch_time_stand_in(side_effect):
    """Заместитель модуля `time` только внутри `watch`: подменена лишь пауза
    (сторож tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py запрещает
    глобальную подмену `time.sleep`)."""
    return types.SimpleNamespace(sleep=mock.Mock(side_effect=side_effect),
                                 monotonic=time.monotonic)


class ObservationContractTest(TaskSeededTmpRootTest):
    def setUp(self):
        super().setUp()
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        self.seed = time.time_ns()
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def command(self, *args):
        with mock.patch.object(sys, "argv", ["artel.py", *args]):
            return capture(artel.main)

    def run_watch(self, *args):
        output = io.StringIO()
        with redirect_stdout(output):
            try:
                watch.cmd_watch(list(args))
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise
        return output.getvalue()

    def register(self, tasks=None):
        return json.loads(self.command("observe", "register", "--client", "codex",
                                       "--chat", "chat-a", "--tasks",
                                       ",".join(tasks or [self.TASK])))["id"]

    def show(self, observation_id):
        return json.loads(self.command("observe", "show", observation_id))

    def event(self, task=None, action="agent run finished", detail=None):
        token = detail or f"event-{self.rng.randrange(10**9)}"
        store.journal(store.db(), task or self.TASK, "test", action, token)
        return token

    def alert(self):
        token = f"alert-{self.rng.randrange(10**9)}"
        conn = store.db()
        with conn:
            conn.execute("INSERT INTO alerts(target, kind, source, message, ts) "
                         "VALUES (?, 'test', 'test', ?, '2026-01-01')",
                         (config.DEFAULT_TARGET, token))
        return token

    def maxima(self):
        conn = store.db()
        return (conn.execute("SELECT COALESCE(MAX(id), 0) FROM steps").fetchone()[0],
                conn.execute("SELECT COALESCE(MAX(id), 0) FROM alerts").fetchone()[0])

    def test_ac1_registration_and_restarted_watch_use_saved_position(self):
        """Регистрация пропускает историю; два запуска забирают новые записи по разу.

        Ловит мутацию: повторный дозор перечитывает ранее напечатанный маркер
        либо пропускает маркер, созданный между остановкой процесса и запуском.
        """
        old_step, old_alert = self.event(), self.alert()
        observation_id = self.register()
        shown = self.show(observation_id)
        self.assertEqual((shown["notified"]["step_id"],
                          shown["notified"]["alert_id"]), self.maxima(), self.seed)
        self.assertEqual((shown["acknowledged"]["step_id"],
                          shown["acknowledged"]["alert_id"]), self.maxima(), self.seed)
        first_step, first_alert = self.event(), self.alert()

        def stop_process(_):
            raise SystemExit(0)

        with mock.patch.object(watch, "time", watch_time_stand_in(stop_process)):
            first_output = self.run_watch("--observation", observation_id,
                                          "--interval", "0.01")
        self.assertNotIn(old_step, first_output, self.seed)
        self.assertNotIn(old_alert, first_output, self.seed)
        self.assertIn(first_step, first_output, self.seed)
        self.assertIn(first_alert, first_output, self.seed)
        second_step, second_alert = self.event(), self.alert()
        with mock.patch.object(watch, "time", watch_time_stand_in(stop_process)):
            second_output = self.run_watch("--observation", observation_id,
                                           "--interval", "0.01")
        for token in (first_step, first_alert):
            self.assertNotIn(token, second_output, self.seed)
        for token in (second_step, second_alert):
            self.assertEqual(second_output.count(token), 1, self.seed)

    def test_ac1_migration_initializes_missing_positions_to_current_maxima(self):
        """Старая строка наблюдения получает снимок максимумов при миграции.

        Ловит мутацию: миграция оставляет NULL либо начинает старое
        наблюдение с нуля и повторно показывает исторические события.
        """
        observation_id = self.register()
        self.event()
        self.alert()
        top = self.maxima()
        conn = store.db()
        conn.execute("ALTER TABLE observations RENAME TO old_observations")
        conn.execute("CREATE TABLE observations (id TEXT PRIMARY KEY, target TEXT, "
                     "client TEXT, chat TEXT, session_id TEXT, state TEXT, "
                     "last_seen_at TEXT, created_at TEXT)")
        conn.execute("INSERT INTO observations SELECT id, target, client, chat, "
                     "session_id, state, last_seen_at, created_at FROM old_observations")
        conn.execute("DROP TABLE old_observations")
        conn.commit()
        store.migrate(conn)
        shown = self.show(observation_id)
        for name in ("notified", "acknowledged"):
            self.assertEqual((shown[name]["step_id"], shown[name]["alert_id"]),
                             top, self.seed)

    def test_ac2_steps_across_tasks_are_ordered_and_read_together(self):
        """Более ранняя запись второй задачи остаётся в общем потоке.

        Ловит мутацию: чтение по задачам или ранний выход после поздней
        записи первой задачи скрывает более раннюю запись второй.
        """
        other = "T002"
        store.insert_task(store.db(), other, "Вторая", "in_dev", "task/t002",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        observation_id = self.register([self.TASK, other])
        earlier = self.event(other)
        later = self.event(self.TASK)
        sql = []
        real_db = store.db

        def traced_db():
            conn = real_db()
            conn.set_trace_callback(sql.append)
            return conn

        with mock.patch.object(store, "db", side_effect=traced_db), \
             mock.patch.object(watch, "time", watch_time_stand_in(SystemExit(0))):
            output = self.run_watch("--observation", observation_id,
                                    "--interval", "0.01")
        self.assertLess(output.index(earlier), output.index(later), self.seed)
        reads = [statement for statement in sql
                 if "select" in statement.lower() and "from steps" in statement.lower()
                 and "max(" not in statement.lower()]
        self.assertEqual(len(reads), 1, f"зерно {self.seed}: {reads}")

    def test_ac3_events_and_acknowledge_are_monotone_and_bounded(self):
        """Подтверждение скрывает события, не откатывается и отвергает будущее.

        Ловит мутацию: запоздалое подтверждение понижает позицию или
        подтверждение сверх текущего максимума принимается.
        """
        observation_id = self.register()
        step = self.event()
        alert = self.alert()
        top = self.maxima()
        self.assertIn(step, self.command("observe", "events", observation_id), self.seed)
        self.assertIn(alert, self.command("observe", "events", observation_id), self.seed)
        self.command("observe", "acknowledge", observation_id, "--through",
                     f"{top[0]},{top[1]}")
        after = self.command("observe", "events", observation_id)
        self.assertNotIn(step, after, self.seed)
        self.assertNotIn(alert, after, self.seed)
        self.command("observe", "acknowledge", observation_id, "--through", "0,0")
        acknowledged = self.show(observation_id)["acknowledged"]
        self.assertEqual((acknowledged["step_id"], acknowledged["alert_id"]),
                         top, self.seed)
        with self.assertRaises(SystemExit) as refusal:
            self.command("observe", "acknowledge", observation_id, "--through",
                         f"{top[0] + 1},{top[1]}")
        self.assertIn("максим", str(refusal.exception).lower(), self.seed)
        with self.assertRaises(SystemExit) as malformed:
            self.command("observe", "acknowledge", observation_id,
                         "--through", "not-a-pair")
        self.assertTrue(str(malformed.exception), self.seed)
        self.assertEqual((self.show(observation_id)["acknowledged"]["step_id"],
                          self.show(observation_id)["acknowledged"]["alert_id"]),
                         top, self.seed)
        # Одновременные одинаковые подтверждения не должны конфликтовать
        # или откатывать уже достигнутую пару.
        barrier = threading.Barrier(2)

        def confirm():
            barrier.wait()
            return artel.main()

        with mock.patch.object(sys, "argv", ["artel.py", "observe", "acknowledge",
                                                observation_id, "--through",
                                                f"{top[0]},{top[1]}"]):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = [pool.submit(confirm) for _ in range(2)]
                for result in results:
                    result.result(timeout=10)
        acknowledged = self.show(observation_id)["acknowledged"]
        self.assertEqual((acknowledged["step_id"], acknowledged["alert_id"]),
                         top, self.seed)

    def test_ac4_role_events_only_session_guard_and_no_task_or_lease_change(self):
        """Роль читает события, но не подтверждает; чужая сессия отвергается.

        Ловит мутацию: `events` берёт lease, меняет состояние задачи либо
        разрешает роли подтверждение или чужой сессии просмотр.
        """
        observation_id = self.register()
        self.event()
        before = store.get_task(store.db(), self.TASK)["state"]
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}):
            self.command("observe", "events", observation_id)
            with self.assertRaises(SystemExit):
                self.command("observe", "acknowledge", observation_id,
                             "--through", "0,0")
        top = self.maxima()
        self.command("observe", "acknowledge", observation_id,
                     "--through", f"{top[0]},{top[1]}")
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], before)
        self.assertIsNone(store.db().execute(
            "SELECT task_id FROM leases WHERE task_id=?", (self.TASK,)).fetchone())
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "other-session"}):
            for args in (("events", observation_id),
                         ("acknowledge", observation_id, "--through", "0,0")):
                with self.subTest(args=args):
                    with self.assertRaises(SystemExit) as refusal:
                        self.command("observe", *args)
                    self.assertIn("сесси", str(refusal.exception), self.seed)

    def test_ac13_filtered_watch_still_advances_notified_position(self):
        """Отсеянный шаг больше не появляется после смены фильтра.

        Ловит мутацию: позиция уведомления остаётся перед шагом,
        отсеянным `--events`, и следующий дозор печатает его.
        """
        observation_id = self.register()
        hidden = self.event()
        with mock.patch.object(watch, "time", watch_time_stand_in(SystemExit(0))):
            self.run_watch("--observation", observation_id,
                           "--events", "alerts", "--interval", "0.01")
        with mock.patch.object(watch, "time", watch_time_stand_in(SystemExit(0))):
            output = self.run_watch("--observation", observation_id,
                                    "--events", "steps", "--interval", "0.01")
        self.assertNotIn(hidden, output, self.seed)
        self.assertGreaterEqual(self.show(observation_id)["notified"]["step_id"],
                                self.maxima()[0], self.seed)

    def test_ac14_events_from_and_filtered_maxima(self):
        """Явная пара повторяет хвост, а POSITION учитывает фильтрованные id.

        Ловит мутацию: `--from` читает включительно либо POSITION остаётся
        перед отсеянным событием.
        """
        observation_id = self.register()
        start = self.maxima()
        step = self.event()
        self.alert()
        top = self.maxima()
        output = self.command("observe", "events", observation_id,
                              "--from", f"{start[0]},{start[1]}",
                              "--events", "steps")
        self.assertIn(step, output, self.seed)
        self.assertEqual(output.splitlines()[-1], f"POSITION={top[0]},{top[1]}",
                         self.seed)
        empty = self.command("observe", "events", observation_id,
                             "--from", f"{top[0]},{top[1]}")
        self.assertEqual(empty.strip(), f"POSITION={top[0]},{top[1]}", self.seed)
        with self.assertRaises(SystemExit) as malformed:
            self.command("observe", "events", observation_id,
                         "--from", "not-a-pair")
        self.assertTrue(str(malformed.exception), self.seed)
        with self.assertRaises(SystemExit) as refusal:
            watch.cmd_watch(["--observation", observation_id,
                             "--events", "unknown-class"])
        available = str(refusal.exception).split("доступны:", 1)[1]
        available = available.strip(" )").split(", ")
        for event_class in available:
            with self.subTest(event_class=event_class):
                self.command("observe", "events", observation_id,
                             "--events", event_class)

    def test_ac15_repeat_and_late_ack_report_last_advance_metadata(self):
        """Поздний вызов сообщает метаданные последнего продвижения.

        Ловит мутацию: повтор перезаписывает время или client/chat,
        либо поздний вызов сообщает свои метаданные вместо прежних.
        """
        observation_id = self.register()
        self.event()
        self.alert()
        top = self.maxima()
        self.command("observe", "acknowledge", observation_id, "--through",
                     f"{top[0]},{top[1]}", "--client", "codex", "--chat", "first")
        initial = self.show(observation_id)["acknowledged"]
        repeat = self.command("observe", "acknowledge", observation_id,
                              "--through", f"{top[0]},{top[1]}",
                              "--client", "claude", "--chat", "repeat")
        self.assertIn(initial["at"], repeat, self.seed)
        self.assertEqual(self.show(observation_id)["acknowledged"], initial,
                         self.seed)
        output = self.command("observe", "acknowledge", observation_id,
                              "--through", "0,0", "--client", "claude",
                              "--chat", "late")
        self.assertEqual(self.show(observation_id)["acknowledged"], initial,
                         self.seed)
        for value in ("уже разобрано", initial["at"], "codex", "first"):
            self.assertIn(value, output, self.seed)
        self.assertNotIn("late", output, self.seed)
        self.event()
        next_top = self.maxima()
        self.command("observe", "acknowledge", observation_id, "--through",
                     f"{next_top[0]},0", "--client", "claude", "--chat", "new")
        advanced = self.show(observation_id)["acknowledged"]
        self.assertEqual((advanced["step_id"], advanced["alert_id"]),
                         (next_top[0], top[1]), self.seed)
        self.assertEqual((advanced["client"], advanced["chat"]),
                         ("claude", "new"), self.seed)
