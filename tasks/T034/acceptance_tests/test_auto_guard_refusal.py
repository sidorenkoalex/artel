"""Приёмочные тесты T034: AC-3, AC-4 — отказ guard'ом внутри цикла `auto`.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 2
(ревью T017): отказ `advance` guard'ом (структура артефакта-условия
сломана) должен останавливать цикл `auto`, а не запускать `cmd_run`
повторно для того же состояния (AC-3); состояние, где артефакт просто
ещё не в статусе `ready` (не отказ guard'ом), по-прежнему крутит цикл
до лимита шагов, как и до этой задачи (AC-4).

Песочница — тот же приём, что у `tests/test_auto_cycle.py`: `cmd_run`
подменён заготовленным исходом шага (агент «дописывает» PLAN.md),
`gitcmd.git` заглушкой — реальный git циклу здесь не нужен ни для
одного из двух сценариев (`_dirty_refuses` пропускает сверку на
пустом `current`, тем же приёмом, что и у пустых песочниц advance).
"""
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import auto, catalog, config, gitcmd, runner, store  # noqa: E402

# PLAN.md, guard-валидный: все четыре обязательные секции на месте.
READY_PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: T034 приёмка — фиктивная задача песочницы

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

# PLAN.md, guard-невалидный: `status: ready`, но секции «Влияние на
# систему» нет — тот же класс дефекта, что и у настоящей роли,
# забывшей секцию (guard.RULES["plan"]["sections"]).
BROKEN_PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: T034 приёмка — сломанный артефакт для отказа guard'а

## Подход

## Шаги

## Покрытие требований
"""

# PLAN.md, ещё не готов: guard тут вообще не при чём — advance из
# in_dev проверяет status ready/approved раньше вызова guard'а.
DRAFT_PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: draft
schema_version: 1
---

# PLAN: T034 приёмка — черновик, ещё не ready

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


def fake_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git`: пустой ответ вместо обращения к репозиторию."""
    return subprocess.CompletedProcess(list(args), 0, "", "")


class FakeRun:
    """Подмена `cmd_run`: вместо агента — заготовленные исходы шагов.

    Свой потолок вызовов (`arm`) пришпиливает `AUTO_MAX_STEPS`: холостой
    шаг состояние не двигает, и без потолка тест висел бы, а не падал,
    не останови цикл сам себя (тот же приём, что в tests/test_auto_cycle.py).
    """

    def __init__(self):
        self.script: list = []
        self.calls: list[str] = []
        self.limit: int | None = None

    def arm(self, steps: int) -> None:
        self.limit = len(self.calls) + steps

    def __call__(self, task_id: str) -> None:
        if self.limit is not None and len(self.calls) >= self.limit:
            raise AssertionError(
                f"цикл не остановился: шагов больше {config.AUTO_MAX_STEPS}")
        self.calls.append(task_id)
        if self.script:
            self.script.pop(0)()


class AutoGuardRefusalSandbox(unittest.TestCase):
    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude")):
            self.patch_object(config, attr, value)

        self.patch_object(gitcmd, "git", fake_git)
        self.agent = FakeRun()
        self.patch_object(runner, "cmd_run", self.agent)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Отказ guard'а в auto")
        self.tdir = config.TASKS / self.TASK

    def patch_object(self, target, attr: str, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def auto(self) -> str:
        self.agent.arm(config.AUTO_MAX_STEPS)
        return self.capture(auto.cmd_auto, self.TASK)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write_plan(self, template: str) -> None:
        (self.tdir / "PLAN.md").write_text(
            template.format(task=self.TASK), encoding="utf-8")

    def journal_rows(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]


class Ac3GuardRefusalStopsTheCycleTest(AutoGuardRefusalSandbox):
    """AC-3: отказ guard'ом внутри auto останавливает цикл, не ретраит шаг."""

    def test_ac3_guard_refusal_stops_the_cycle_cmd_run_not_called_again(self):
        self.set_state("in_dev")
        self.agent.script = [lambda: self.write_plan(BROKEN_PLAN_MD)]

        out = self.auto()

        self.assertEqual(
            len(self.agent.calls), 1,
            "цикл auto вызвал cmd_run повторно для того же состояния "
            "после отказа advance guard'ом")
        self.assertEqual(self.state(), "in_dev",
                         "состояние не должно было продвинуться дальше "
                         "отказавшего guard'а")

    def test_ac3_stop_is_journalled_and_printed_with_the_gate_hint(self):
        self.set_state("in_dev")
        self.agent.script = [lambda: self.write_plan(BROKEN_PLAN_MD)]

        out = self.auto()

        self.assertIn("auto остановлен", out)
        rows = self.journal_rows()
        stop_rows = [(actor, detail) for actor, action, detail in rows
                    if action == "auto остановлен"]
        self.assertEqual(len(stop_rows), 1,
                         f"записей остановки auto: {len(stop_rows)}")
        actor, detail = stop_rows[0]
        self.assertEqual(actor, "operator")
        self.assertIn("почини артефакт и повтори", detail,
                      "подсказка остановки не совпадает по смыслу с "
                      "подсказкой отказа guard'а вне цикла")


class Ac4NonGuardStateKeepsRunningTest(AutoGuardRefusalSandbox):
    """AC-4: состояние без отказа guard'ом (артефакт ещё не ready) не
    меняет поведения — цикл продолжает запускать cmd_run, как и раньше."""

    def test_ac4_plan_not_ready_yet_keeps_calling_cmd_run_until_the_limit(self):
        self.write_plan(DRAFT_PLAN_MD)
        self.set_state("in_dev")

        out = self.auto()

        self.assertEqual(
            len(self.agent.calls), config.AUTO_MAX_STEPS,
            "цикл остановился раньше лимита — PLAN.md просто не ready, "
            "это не отказ guard'ом")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertEqual(self.state(), "in_dev")

    def test_ac4_valid_ready_plan_still_advances_the_task(self):
        """Смежная гарантия: guard-валидный ready PLAN.md по-прежнему
        продвигает задачу дальше in_dev — исправление 2 не задело этот путь.

        Ревьювер за отсутствием сценария в FakeRun ничего не пишет и
        крутит цикл до лимита шагов в `review` — это отдельный, неотказный
        путь (REVIEW.md просто не готов), поэтому смотрим на состояние
        сразу после первого шага, а не на итоговое число вызовов агента.
        """
        self.set_state("in_dev")
        self.agent.script = [lambda: self.write_plan(READY_PLAN_MD)]

        self.auto()

        self.assertGreaterEqual(len(self.agent.calls), 1)
        self.assertEqual(self.state(), "review",
                         "guard-валидный PLAN.md должен был продвинуть "
                         "задачу дальше in_dev")


if __name__ == "__main__":
    unittest.main()
