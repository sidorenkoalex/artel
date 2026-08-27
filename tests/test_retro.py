"""Юнит-тесты генерации содержимого RETRO (orchestrator/retro.py, SPEC T043).

Сквозной путь (запись файла, git add/commit, некритичность провала) уже
покрыт приёмочными тестами `tasks/T043/acceptance_tests/` и
`tests/test_fsm_retro.py` — здесь только чистые функции генератора,
без git и без FSM-песочницы.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, retro, store  # noqa: E402

SPEC_TEXT = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: задача для теста

## Контекст

Первая строка контекста.
Вторая строка контекста — не должна попасть в дайджест.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

ACCEPTANCE_FIXTURE = ('''"""Фикстура."""
# @AC-2: manual — причина.
import unittest


class T(unittest.TestCase):
    def test_@ac1_one(self):
        pass
''').replace("@ac", "ac").replace("@AC", "AC")


class RetroGenerationTest(unittest.TestCase):
    """Песочница: ROOT/DB/TASKS во tmpdir — тот же приём, что
    `tests/test_fsm_map_regen.py::RegenerateAndCommitMapTest`."""

    TASK = "T900"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks")):
            self._patch(attr, value)
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача для теста",
                          "merge_gate", "task/t900-x", config.DEFAULT_TARGET,
                          50.0)

    def _patch(self, attr, value):
        from unittest import mock
        patcher = mock.patch.object(config, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_spec(self, text=SPEC_TEXT) -> None:
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(text, encoding="utf-8")

    def write_acceptance_tests(self) -> None:
        adir = config.TASKS / self.TASK / "acceptance_tests"
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "test_fixture.py").write_text(ACCEPTANCE_FIXTURE,
                                              encoding="utf-8")

    def add_step(self, actor, action, detail="") -> None:
        store.journal(self.conn, self.TASK, actor, action, detail)

    def test_build_done_has_merge_sha_address_and_first_context_line_only(self):
        self.write_spec()
        store.update_task(self.conn, self.TASK, spent_usd=1.5,
                          review_iters=1, accept_rejects=0)
        self.add_step("developer", "agent run finished",
                      "rc=0, попытка 1/1, стоимость $1.5000, токенов 42")

        text = retro.build_done(self.conn, self.TASK, "deadbeef" * 5)

        self.assertIn("deadbeef" * 5 + f":tasks/{self.TASK}/", text)
        self.assertIn("Первая строка контекста.", text)
        self.assertNotIn("Вторая строка контекста", text)
        self.assertIn("developer", text)
        self.assertLessEqual(len(text.splitlines()), 30)

    def test_build_done_is_deterministic(self):
        self.write_spec()
        self.write_acceptance_tests()
        store.update_task(self.conn, self.TASK, spent_usd=2.0)
        self.add_step("developer", "agent run finished",
                      "rc=0, попытка 1/1, стоимость $2.0000, токенов 10")
        self.add_step("fsm", "state -> escalated", "причина A")

        first = retro.build_done(self.conn, self.TASK, "cafe" * 10)
        second = retro.build_done(self.conn, self.TASK, "cafe" * 10)

        self.assertEqual(first, second)

    def test_build_done_aggregates_cost_per_actor_across_events(self):
        self.add_step("developer", "agent run finished",
                      "rc=1, попытка 1/2, стоимость $1.0000, токенов 10")
        self.add_step("developer", "agent run finished",
                      "rc=0, попытка 2/2, стоимость $0.5000, токенов 5")

        text = retro.build_done(self.conn, self.TASK, "aaaa" * 10)

        self.assertIn("developer: $1.50, 15 токенов", text)

    def test_build_done_escalations_show_count_and_last_verbatim(self):
        self.add_step("fsm", "state -> escalated", "первая причина")
        self.add_step("operator", "state -> in_dev", "продолжаем")
        self.add_step("fsm", "state -> escalated", "последняя причина")

        text = retro.build_done(self.conn, self.TASK, "bbbb" * 10)

        self.assertIn("последняя причина", text)
        self.assertNotIn("первая причина", text)
        self.assertIn("2", text)

    def test_build_done_without_escalations_says_none(self):
        text = retro.build_done(self.conn, self.TASK, "cccc" * 10)

        self.assertIn("Эскалации: нет", text)

    def test_build_killed_has_no_artifacts_and_no_address_form(self):
        self.add_step("operator", "state -> killed", "kill switch")

        text = retro.build_killed(self.conn, self.TASK)

        self.assertIn(retro.NO_ARTIFACTS_NOTE, text)
        self.assertIn("kill switch", text)
        self.assertNotRegex(text, r"[0-9a-f]{40}:tasks/")

    def test_build_killed_survives_missing_task_dir(self):
        """`tasks/<id>/` уже убран `cleanup` — генератор не падает
        (SPEC, требование 6: БД остаётся источником истины)."""
        self.add_step("operator", "state -> killed", "kill switch")
        self.assertFalse((config.TASKS / self.TASK).exists())

        text = retro.build_killed(self.conn, self.TASK)

        self.assertIn(self.TASK, text)
        self.assertIn("0 тест(ов)", text)

    def test_build_killed_without_kill_step_has_fallback_reason(self):
        text = retro.build_killed(self.conn, self.TASK)

        self.assertIn("причина не найдена в журнале", text)


if __name__ == "__main__":
    unittest.main()
