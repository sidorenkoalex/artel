"""Приёмочные тесты T038: стоп-кран `auto` по повторному отказу `advance`.

Источник — tasks/T038/SPEC.md, «Критерии приёмки» (AC-1..AC-4). Песочница —
тот же приём, что у tests/test_auto_cycle.py и tasks/T034/acceptance_tests/
test_auto_guard_refusal.py: БД и артефакты во временном каталоге, `cmd_run`
подменён заготовленным исходом шага, `gitcmd.git` — заглушкой.

AC-1 и AC-2 собраны через РЕАЛЬНЫЙ `fsm.cmd_advance` на живых артефактах —
так же, как T034 ловит отказ guard'ом настоящим BROKEN_PLAN_MD, а не его
пересказом. Для AC-1 источник отказа — `tests_writing`/трассируемость AC
(`orchestrator/fsm.py::_tests_writing_ac_state`): в этой песочнице без
настоящего git `_dirty_refuses` не срабатывает никогда (`fixation.read()`
видит пустой sha и молча пропускает сверку — тот же вырожденный случай,
на котором стоит весь стенд `gitcmd.git`-заглушек), а трассируемость AC —
чистый разбор файлов на диске, ей git не нужен вовсе.

AC-3 требует на двух ПОДРЯД шагах — то есть при неизменном `t["state"]`
между обоими вызовами `cmd_advance`, поскольку по условию оба шага не
поменяли состояние — ДВА РАЗНЫХ текста `action`. Ветки `cmd_advance`
выбираются исключительно по `state`; для любого состояния, дающего в этой
git-заглушенной песочнице журналируемый отказ, текст `action` — константа
одной и той же ветки (детали разнятся, действие — нет), поэтому две
разные формулировки подряд в одном состоянии реальным кодом здесь не
собрать без настоящего git или настоящего прогона pytest/unittest поверх
REVIEW.md (сам предмет проверки — не они, а сравнение в `auto.cmd_auto`).
Поэтому для AC-3 `fsm.cmd_advance` подменена управляемым дублем — тем же
приёмом, что и `SpyCommand`/`FakeRun` в tests/test_auto_cycle.py: тест
целится в логику цикла, а не в конкретную причину отказа fsm.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import auto, catalog, config, fsm, gitcmd, runner, store  # noqa: E402

# SPEC.md с AC-разметкой (schema_version 2) и без acceptance_tests/ на
# диске: `guard.acceptance_traceability_errors` вернёт одни и те же две
# ошибки («AC-1: нет теста...», «AC-2: нет теста...») на каждом вызове,
# пока файл не меняется, — детерминированный, воспроизводимый отказ.
SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
budget_usd: 15
---

# SPEC: песочница T038

## Контекст

## Требования

## Критерии приёмки

AC-1. Первый критерий песочницы.

AC-2. Второй критерий песочницы.

## Не входит
"""

DRAFT_PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: draft
schema_version: 1
---

# PLAN: песочница T038

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


def fake_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git`: пустой ответ вместо обращения к репозиторию."""
    return subprocess.CompletedProcess(list(args), 0, "", "")


class FakeRun:
    """Подмена `cmd_run`: агент ничего не делает и не пишет артефакты —
    ход цикла в этих тестах задаёт исключительно поведение `advance`.

    Свой потолок вызовов (`arm`) пришпиливает `AUTO_MAX_STEPS`: холостой
    шаг состояние не двигает, и без потолка тест висел бы, а не падал, не
    останови цикл сам себя (тот же приём, что в tests/test_auto_cycle.py).
    """

    def __init__(self):
        self.calls: list[str] = []
        self.limit: int | None = None

    def arm(self, steps: int) -> None:
        self.limit = len(self.calls) + steps

    def __call__(self, task_id: str) -> None:
        if self.limit is not None and len(self.calls) >= self.limit:
            raise AssertionError(
                f"цикл не остановился: шагов больше {config.AUTO_MAX_STEPS}")
        self.calls.append(task_id)


class FakeAdvance:
    """Подмена `fsm.cmd_advance` (только AC-3, см. докстринг модуля):
    сценарий журналирует заданный текст `action` (или ничего) и всегда
    возвращает `False` — тот же по характеру исход, что и у настоящего
    отказа `advance`, отличного от отказа guard'ом (требование 3 SPEC)."""

    def __init__(self):
        self.script: list = []
        self.calls = 0

    def __call__(self, task_id: str) -> bool:
        self.calls += 1
        action = self.script.pop(0) if self.script else None
        if action is not None:
            store.journal(store.db(), task_id, "fsm", action,
                          "деталь тестового отказа")
        return False


class AutoStopSandbox(unittest.TestCase):
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
        self.capture(catalog.cmd_new, "Стоп-кран auto")
        self.tdir = config.TASKS / self.TASK

    def patch_object(self, target, attr: str, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def capture(self, fn, *args) -> str:
        import io
        from contextlib import redirect_stdout
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

    def write_spec_without_tests(self) -> None:
        (self.tdir / "SPEC.md").write_text(
            SPEC_MD.format(task=self.TASK), encoding="utf-8")

    def write_draft_plan(self) -> None:
        (self.tdir / "PLAN.md").write_text(
            DRAFT_PLAN_MD.format(task=self.TASK), encoding="utf-8")

    def journal_rows(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def journal_detail(self, action: str) -> str:
        details = [d for _, a, d in self.journal_rows() if a == action]
        self.assertEqual(len(details), 1, f"записей «{action}»: {len(details)}")
        return details[0]


class Ac1RepeatedIdenticalRefusalStopsTheCycleTest(AutoStopSandbox):
    """AC-1: два подряд отказа `advance` с одинаковым текстом `action`
    останавливают цикл на втором из них."""

    def setUp(self):
        super().setUp()
        self.write_spec_without_tests()
        self.set_state("tests_writing")

    def test_ac1_cmd_run_is_not_called_a_third_time(self):
        state_before = self.state()

        self.auto()

        self.assertEqual(
            len(self.agent.calls), 2,
            "цикл вызвал cmd_run больше двух раз — не остановился на "
            "втором подряд отказе advance с тем же текстом")
        self.assertEqual(self.state(), state_before,
                         "задача не осталась в состоянии, в котором была "
                         "перед первым из двух отказавших шагов")

    def test_ac1_both_refusals_are_journalled_with_the_same_action_text(self):
        self.auto()

        refusals = [(actor, action, detail) for actor, action, detail in
                    self.journal_rows()
                    if action.startswith("переход отклонён")]
        self.assertEqual(len(refusals), 2,
                         f"записей отказа advance: {len(refusals)}")
        self.assertEqual(refusals[0][1], refusals[1][1],
                         "текст action разошёлся между двумя подряд отказами")

    def test_ac1_stop_names_the_reason_and_the_advance_hint(self):
        out = self.auto()

        refusal_actions = [action for _, action, _ in self.journal_rows()
                           if action.startswith("переход отклонён")]
        reason_text = refusal_actions[-1]

        self.assertIn("auto остановлен", out)
        self.assertIn(reason_text, out)
        self.assertIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out)

    def test_ac1_stop_is_journalled_once_with_the_same_reason(self):
        self.auto()

        detail = self.journal_detail("auto остановлен")
        refusal_actions = [action for _, action, _ in self.journal_rows()
                           if action.startswith("переход отклонён")]
        self.assertIn(refusal_actions[-1], detail)
        self.assertIn(
            f"почини причину и повтори artel.py advance {self.TASK}", detail)


class Ac2UnjournalledRefusalDoesNotStopTest(AutoStopSandbox):
    """AC-2: шаги без смены состояния, где `advance` не записал в журнал
    отказ «переход отклонён: ...» (артефакт-условие ещё не ready), не
    останавливаются этим правилом — цикл крутится до своего лимита шагов,
    как и до этой задачи."""

    def setUp(self):
        super().setUp()
        self.write_draft_plan()
        self.set_state("in_dev")

    def test_ac2_no_refusal_reaches_the_journal(self):
        self.auto()

        refusals = [action for _, action, _ in self.journal_rows()
                   if action.startswith("переход отклонён")]
        self.assertEqual(refusals, [],
                         "advance не должен был журналировать отказ — "
                         "PLAN.md просто ещё не в статусе ready")

    def test_ac2_cycle_keeps_calling_cmd_run_until_the_step_limit(self):
        out = self.auto()

        self.assertEqual(
            len(self.agent.calls), config.AUTO_MAX_STEPS,
            "цикл остановился раньше штатного лимита шагов — но здесь "
            "нет журналируемого отказа advance, который мог бы это "
            "объяснить по правилу T038")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)
        self.assertEqual(self.state(), "in_dev")


class Ac3DifferentRefusalTextDoesNotStopTest(AutoStopSandbox):
    """AC-3: два подряд отказа `advance` с РАЗНЫМ текстом `action` не
    останавливают цикл по правилу T038 (см. докстринг модуля — почему
    здесь `fsm.cmd_advance` управляемый дубль, а не реальный код)."""

    def setUp(self):
        super().setUp()
        self.set_state("in_dev")
        self.advance = FakeAdvance()
        self.advance.script = [
            "переход отклонён: рабочая копия артефактов грязная",
            "переход отклонён: трассируемость AC",
        ]
        self.patch_object(fsm, "cmd_advance", self.advance)

    def test_ac3_the_cycle_is_not_stopped_by_the_mismatched_pair(self):
        out = self.auto()

        self.assertEqual(
            self.advance.calls, config.AUTO_MAX_STEPS,
            "цикл остановился раньше штатного лимита шагов — два подряд "
            "отказа с РАЗНЫМ текстом action не должны были его остановить")
        self.assertIn(f"лимит {config.AUTO_MAX_STEPS} шагов", out)

    def test_ac3_stop_reason_is_the_step_limit_not_a_reused_refusal(self):
        out = self.auto()

        self.assertNotIn(
            f"почини причину и повтори artel.py advance {self.TASK}", out,
            "остановка сослалась на подсказку правила T038 — но пара "
            "отказов с разным текстом не должна была его включить")


if __name__ == "__main__":
    unittest.main()

# AC-4: skip — регрессия существующих тестов (tests/test_auto_cycle.py и
# остального пакета) уже проверяется CI-прогоном всей сюиты на каждый
# коммит (guard-джоб пульта); обёрточный unittest здесь был бы повторным
# запуском той же сюиты изнутри unittest discover текущего каталога, а не
# новой проверкой. T038 не трогает сценарии и ассерты tests/test_auto_cycle.py
# (только читает orchestrator/auto.py и orchestrator/fsm.py) — принцип
# целостности (CLAUDE.md) соблюдён самим фактом, что этот файл не менялся.
