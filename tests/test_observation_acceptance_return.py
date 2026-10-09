"""Возврат с приёмки задачи 01M4C954HBJWEGD3AZS7Q3EHA4: позиция дозора
следует журналу, цикл `--observation` выдаёт STATE= и ход шага, вызов
`osascript` ограничен по времени, свой PID сверяется вместе с хостом,
`doctor` предупреждает о дозоре без процесса."""

import io
import json
import os
import socket
import subprocess
import sys
import types
import time
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import agent_log, artel, config, doctor, store, watch
from tests.sandbox import TaskSeededTmpRootTest, capture

OTHER = "T002"


def watch_time_stand_in(side_effect):
    """Заместитель модуля `time` только внутри `watch` (сторож
    tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py запрещает
    глобальную подмену `time.sleep`)."""
    return types.SimpleNamespace(sleep=mock.Mock(side_effect=side_effect),
                                 monotonic=time.monotonic)


class ObservationReturnTest(TaskSeededTmpRootTest):
    def setUp(self):
        super().setUp()
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)

    def command(self, *args):
        with mock.patch.object(sys, "argv", ["artel.py", *args]):
            return capture(artel.main)

    def register(self):
        return json.loads(self.command("observe", "register", "--client", "codex",
                                       "--chat", "chat-a", "--tasks", self.TASK))["id"]

    def run_watch(self, observation_id, on_sleep=SystemExit(0), *args):
        output = io.StringIO()
        with mock.patch.object(watch, "time", watch_time_stand_in(on_sleep)), \
             redirect_stdout(output):
            try:
                watch.cmd_watch(["--observation", observation_id,
                                 "--interval", "0.01", *args])
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    raise
        return output.getvalue()

    def journal_at(self, task_id, actor, action, detail, ago):
        conn = store.db()
        store.journal(conn, task_id, actor, action, detail)
        row_id = store.task_steps(conn, task_id)[-1]["id"]
        stamp = (datetime.now(timezone.utc) - timedelta(seconds=ago)
                 ).strftime("%Y-%m-%d %H:%M:%SZ")
        conn.execute("UPDATE steps SET ts=? WHERE id=?", (stamp, row_id))
        conn.commit()

    def test_added_task_history_is_not_replayed_after_quiet_polls(self):
        """Позиция «оповещено» идёт до максимума журнала, пока задачи набора
        молчат: после `observe add` история новой задачи не выводится.

        Ловит мутацию: позиция двигается только по событиям задач набора
        (`next_step = steps[-1]` либо прежняя) — тогда второй дозор после
        `observe add` печатает старые записи добавленной задачи.
        """
        observation_id = self.register()
        store.insert_task(store.db(), OTHER, "Чужая", "in_dev",
                          "task/t002-chuzhaya", config.DEFAULT_TARGET, 25.0)
        history = [f"история-B-{n}" for n in range(3)]
        for detail in history:
            store.journal(store.db(), OTHER, "test", "state -> review", detail)
        self.run_watch(observation_id)
        self.command("observe", "add", observation_id, "--tasks", OTHER)
        output = self.run_watch(observation_id)
        for detail in history:
            self.assertNotIn(detail, output)
        fresh = "свежее-B"
        store.journal(store.db(), OTHER, "test", "state -> review", fresh)
        self.assertIn(fresh, self.run_watch(observation_id))

    def test_events_position_reaches_journal_maximum_for_quiet_set(self):
        """`observe events` при молчащем наборе печатает POSITION= с текущими
        максимумами журнала, а не прежнюю позицию.

        Ловит мутацию: POSITION= остаётся на позиции «разобрано», пока
        события чужих задач растят журнал.
        """
        observation_id = self.register()
        store.insert_task(store.db(), OTHER, "Чужая", "in_dev",
                          "task/t002-chuzhaya", config.DEFAULT_TARGET, 25.0)
        store.journal(store.db(), OTHER, "test", "state -> review", "чужое")
        top = store.journal_maxima(store.db())
        output = self.command("observe", "events", observation_id)
        self.assertEqual(output.strip(), f"POSITION={top[0]},{top[1]}")

    def test_state_line_on_task_state_change(self):
        """Смена состояния задачи набора даёт строку STATE= в режиме
        `--observation`, как в прежнем цикле `watch`.

        Ловит мутацию: цикл `--observation` не сверяет состояние задач
        набора и молчит о смене состояния.
        """
        observation_id = self.register()
        ticks = []

        def on_sleep(_):
            ticks.append(1)
            if len(ticks) == 1:
                store.set_state(store.db(), self.TASK, "review", "test",
                                expected_state="in_dev")
            else:
                raise SystemExit(0)

        output = self.run_watch(observation_id, on_sleep)
        self.assertIn("STATE=review", output.splitlines())
        self.assertNotIn("STATE=in_dev", output)

    def test_live_step_progress_line_for_observed_task(self):
        """Живой шаг задачи набора даёт строку хода шага в `--observation`.

        Ловит мутацию: цикл `--observation` не выводит ход живого шага
        задач набора либо считает живым уже завершённый шаг.
        """
        observation_id = self.register()
        log = config.LOGS / "shag-observation.log"
        config.LOGS.mkdir(parents=True, exist_ok=True)
        log.write_text("", encoding="utf-8")
        detail = f"попытка 1/{config.AGENT_ATTEMPTS}, лог: {log}"
        self.journal_at(self.TASK, "developer", "agent run started", detail,
                        config.WATCH_PROGRESS_PERIOD_MIN * 60 + 30)
        output = self.run_watch(observation_id)
        self.assertIn(watch._PROGRESS_ACTION, output)
        store.journal(store.db(), self.TASK, "developer", "agent run finished", "")
        output = self.run_watch(observation_id)
        self.assertNotIn(watch._PROGRESS_ACTION, output)

    def test_pytest_lines_respect_line_budget(self):
        """Строки класса `pytest` в `--observation` ограничены `_LineBudget`.

        Ловит мутацию: чтение событий наблюдения печатает строки хода шага
        без границы строк задачи.
        """
        observation_id = self.register()
        details = [f"прогон-{n}" for n in range(3)]
        for detail in details:
            store.journal(store.db(), self.TASK, "developer",
                          agent_log.PYTEST_RUN_ACTION, detail)
        start = store.journal_maxima(store.db())
        with store.db() as conn:
            conn.execute("UPDATE observations SET notified_step_id=? WHERE id=?",
                         (start[0] - len(details), observation_id))
        with mock.patch.object(config, "WATCH_PROGRESS_LINES_PER_HOUR", 1):
            output = self.run_watch(observation_id)
        self.assertEqual(sum(detail in output for detail in details), 1)

    def test_own_pid_on_other_host_is_refused(self):
        """Совпавший PID на другом хосте — чужой дозор, не свой.

        Ловит мутацию: `claim_observation` признаёт свой PID без сверки
        хоста и молча перехватывает запись чужой машины.
        """
        observation_id = self.register()
        with store.db() as conn:
            conn.execute("UPDATE observations SET pid=?, hostname=?, started_at=? "
                         "WHERE id=?", (os.getpid(), "remote.example.invalid",
                                        datetime.now(timezone.utc).isoformat(),
                                        observation_id))
        with self.assertRaises(SystemExit) as refusal:
            self.run_watch(observation_id)
        self.assertIn("--takeover", str(refusal.exception))
        row = store.observation(store.db(), observation_id)
        self.assertEqual(row["hostname"], "remote.example.invalid")

    def test_doctor_warns_for_dead_pid_and_stale_link(self):
        """`doctor` даёт warn для мёртвого PID и протухшей связи, ok — для
        живого процесса и свежей связи.

        Ловит мутацию: проверка наблюдений всегда возвращает статус ok.
        """
        observation_id = self.register()
        now = datetime.now(timezone.utc)
        stale = (now - timedelta(seconds=config.OBSERVATION_STALE_SECONDS + 60)
                 ).isoformat()
        cases = (("alive", os.getpid(), now.isoformat(), "ok"),
                 ("fresh", None, now.isoformat(), "ok"),
                 ("dead", 1_000_000_000 + os.getpid(), now.isoformat(), "warn"),
                 ("stale", None, stale, "warn"))
        for label, pid, seen, status in cases:
            with self.subTest(label=label):
                with store.db() as conn:
                    conn.execute("UPDATE observations SET pid=?, hostname=?, "
                                 "last_seen_at=? WHERE id=?",
                                 (pid, socket.gethostname(), seen, observation_id))
                check = doctor.check_observations(store.db())
                self.assertEqual(check.status, status, check.detail)
                self.assertIn(label, check.detail)


def test_notification_timeout_is_reported_and_not_fatal(capsys):
    """Зависший `osascript` прерывается таймаутом, дозор продолжает.

    Ловит мутацию: `subprocess.run` вызывается без `timeout` либо
    `TimeoutExpired` не перехватывается и завершает дозор.
    """
    def hang(argv, *args, **kwargs):
        assert kwargs.get("timeout") == 10
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    with mock.patch.object(sys, "platform", "darwin"), \
         mock.patch.object(subprocess, "run", side_effect=hang):
        watch._notify("state -> spec_gate")
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("уведомление недоступно")
