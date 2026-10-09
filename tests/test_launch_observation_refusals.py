"""Тексты отказов отвязанного `run`/`auto` из-за наблюдения (SPEC
01M4FZ6QYPPKYQZFEX14QH8XT6, требование 5) сверх долгоживущих файлов
задачи: состояния названного наблюдения, которые те не перебирают, и
отказ «подходящего наблюдения нет». Каждый отказ называет наблюдение и
следующий шаг и не предлагает пару `--client`/`--chat`.
"""
import os
import sys
from unittest import mock

from orchestrator import artel, config, session, store
from tests.sandbox import TaskSeededTmpRootTest, capture


class LaunchObservationRefusalTest(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "CODEX_SANDBOX": "",
                                           "CODEX_SANDBOX_NETWORK_DISABLED": ""})
        env.start()
        self.addCleanup(env.stop)
        self.conn = store.db()

    def observe(self, tasks=None, session_id=None) -> str:
        return store.register_observation(
            self.conn, config.DEFAULT_TARGET, "", "",
            session_id or session.resolve_session_id(None),
            [self.TASK] if tasks is None else tasks)

    def refused(self, *argv) -> str:
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                mock.patch.object(artel.subprocess, "Popen") as popen:
            with self.assertRaises(SystemExit) as ctx:
                capture(artel.main)
            popen.assert_not_called()
        text = str(ctx.exception.code)
        for flag in ("--client", "--chat"):
            self.assertNotIn(flag, text, text)
        return text

    def test_named_observation_states_are_named_with_next_step(self):
        """Названное наблюдение: не найдено, не активно, задачи нет в
        наборе, чужая сессия, связи ещё нет — каждый отказ называет ID и
        шаг (`observe register`, `observe add <ID>`, `watch --observation <ID>`).

        Ловит мутацию: проверка состояния названного наблюдения снята
        (запуск идёт в прекращённое, чужое или без задачи — Popen
        вызван), либо отказ теряет ID наблюдения или следующий шаг.
        """
        stopped = self.observe()
        store.touch_observation(self.conn, stopped)
        store.stop_observation(self.conn, stopped)
        without_task = self.observe(tasks=[])
        store.touch_observation(self.conn, without_task)
        foreign = self.observe(session_id="other-session")
        store.touch_observation(self.conn, foreign)
        unseen = self.observe()
        cases = (("absent-id", "не найдено", "observe register --tasks"),
                 (stopped, "не активно", "observe register --tasks"),
                 (without_task, "задачи нет в наборе",
                  f"observe add {without_task} --tasks {self.TASK}"),
                 (foreign, "другой сессии", "observe register --tasks"),
                 (unseen, "связи с watch ещё нет",
                  f"watch --observation {unseen}"))
        for command in ("run", "auto"):
            for observation_id, state, step in cases:
                with self.subTest(command=command, state=state):
                    text = self.refused(command, self.TASK,
                                        "--observation", observation_id)
                    self.assertIn(observation_id, text)
                    self.assertIn(state, text)
                    self.assertIn(step, text)

    def test_no_suitable_observation_leads_to_register_or_add(self):
        """Подходящего наблюдения нет — отказ ведёт к `observe register` и
        `observe add`, а не к паре.

        Ловит мутацию: отказ без наблюдения по-прежнему требует пару
        клиент/чат или не называет команд регистрации/добавления.
        """
        self.observe(tasks=[])
        for command in ("run", "auto"):
            with self.subTest(command=command):
                text = self.refused(command, self.TASK)
                self.assertIn(f"observe register --tasks {self.TASK}", text)
                self.assertIn(f"observe add <ID> --tasks {self.TASK}", text)

    def test_launch_audit_record_has_observation_and_no_pair_when_absent(self):
        """Запуск без пары пишет в журнал задачи запись с pid и ID
        наблюдения и без `client=`/`chat=`.

        Ловит мутацию: запись аудита запуска пишется только при паре
        (запуск без пары не оставляет следа в журнале задачи) или
        подставляет пустую пару `client=, chat=`.
        """
        observation_id = self.observe()
        store.touch_observation(self.conn, observation_id)
        with mock.patch.object(sys, "argv", ["artel.py", "run", self.TASK]), \
                mock.patch.object(artel.subprocess, "Popen",
                                  return_value=mock.Mock(pid=31337)):
            capture(artel.main)
        rows = store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=?",
            (self.TASK, artel._DETACHED_LAUNCH_ACTION)).fetchall()
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("31337", rows[0][0])
        self.assertIn(observation_id, rows[0][0])
        self.assertNotIn("client=", rows[0][0])
        self.assertNotIn("chat=", rows[0][0])
