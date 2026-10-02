"""Юнит-тесты `orchestrator/cycle_hint.py` (SPEC 01M3XTFJCC5TG63FHW907GQM4D)
сверх долгоживущего файла задачи: приоритет случая «а» над более свежим
«б», задача, удалённая из наблюдения, и склейка с префиксом места вызова.
"""
import os
from unittest import mock

from orchestrator import config, cycle_hint, store
from tests.sandbox import TaskSeededTmpRootTest

SESSION = "session-cycle-hint"


class CycleHintTest(TaskSeededTmpRootTest):
    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "ARTEL_SESSION_ID": SESSION})
        env.start()
        self.addCleanup(env.stop)
        self.conn = store.db()
        self.target = store.task_target(self.conn, self.TASK)

    def observe(self, client: str, chat: str, task_ids: list) -> str:
        observation_id = store.register_observation(
            self.conn, self.target, client, chat, SESSION, task_ids)
        store.touch_observation(self.conn, observation_id)
        return observation_id

    def test_enabled_observation_wins_over_fresher_one_without_task(self):
        """Случай «а» приоритетнее «б» даже при более старой связи.

        Ловит мутацию: выборка упорядочена только по `last_seen_at` —
        подсказка берёт свежее наблюдение без задачи и предлагает лишний
        `observe add`, хотя готовое наблюдение уже есть.
        """
        enabled = self.observe("codex", "chat-enabled", [self.TASK])
        fresher = self.observe("claude", "chat-fresher", [])
        store.touch_observation(self.conn, fresher)
        hint = cycle_hint.launch_hint(self.conn, self.TASK, "run")
        self.assertIn("--client codex --chat chat-enabled", hint[0], hint)
        self.assertIn(f"watch --observation {enabled}", "\n".join(hint), hint)
        self.assertNotIn("observe add", "\n".join(hint), hint)

    def test_task_removed_from_observation_suggests_observe_add(self):
        """Задача удалена из наблюдения (`observe remove`) — тоже случай «б».

        Ловит мутацию: строка `observation_tasks` ищется внутренним
        соединением — наблюдение без строки задачи выпадает из выборки и
        подсказка уходит в `observe register` рядом с живым наблюдением.
        """
        observation_id = self.observe("claude", "chat-removed", [self.TASK])
        store.remove_observation_tasks(self.conn, observation_id, [self.TASK])
        hint = cycle_hint.launch_hint(self.conn, self.TASK, "auto")
        text = "\n".join(hint)
        self.assertIn(f"observe add {observation_id} --tasks {self.TASK}", text)
        self.assertNotIn("observe register", text)
        self.assertIn("--client claude --chat chat-removed", hint[0])

    def test_launch_text_continues_caller_prefix_on_one_line(self):
        """Строка запуска идёт сразу за префиксом места вызова, шаги — ниже.

        Ловит мутацию: `launch_text` начинает текст переводом строки или
        шагом «сначала:» — префикс «дальше:» повисает без команды, а
        строка «дальше: artel.py auto <id>» разрывается.
        """
        text = "  дальше: " + cycle_hint.launch_text(
            self.conn, self.TASK, "auto", "— продолжит отсюда")
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith(
            f"  дальше: artel.py auto {self.TASK} --client "), text)
        self.assertTrue(lines[0].endswith("— продолжит отсюда"), text)
        self.assertEqual(lines[1].strip(), "сначала:", text)
        self.assertTrue(all(line.startswith("    ") for line in lines[1:]), text)
