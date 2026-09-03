"""Общая песочница приёмочных тестов задачи 01M1KCSTBYF1CRJBSY4P6VYQEA
(auto: детекция буксования цикла и алерты Оператору).

Тот же приём, что у tasks/T038/acceptance_tests/
test_auto_stop_on_repeated_advance_refusal.py и tasks/T034/acceptance_tests/
test_auto_guard_refusal.py: самодостаточная песочница (БД и артефакты во
временном каталоге, `cmd_run`/`gitcmd.git` подменены), не собрана поверх
классов tests/test_auto_cycle.py напрямую — тот модуль не задуман как
переиспользуемая библиотека вовне (его классы не экспортированы, только
исполняются unittest discover'ом).

ВАЖНО ДЛЯ РАЗРАБОТЧИКА: SPEC.md, требование 2 / AC-3, вводит новую именованную
константу `config.py` (порог холостых шагов), но НЕ фиксирует её имя — только
значение по умолчанию (5) и смысл. Тесты этой задачи (файл
`test_ac3_ac6_idle_step_threshold.py`) требуют ИМЕННО имя
`config.AUTO_STALL_STEPS_LIMIT` (выбор автора приёмочных тестов, по аналогии
с существующими `AUTO_MAX_STEPS`/`AUTO_STOP_*`, с оглядкой на название самой
задачи — «детекция буксования»/«буксует» в тексте ANSWER-1). Тесты — планка
(скил test-authoring, «Лок»): реализация обязана назвать константу так же
байт-в-байт, иначе тесты не соберутся (AttributeError на `config.
AUTO_STALL_STEPS_LIMIT`), а не просто не пройдут содержательно.
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

from orchestrator import (auto, catalog, config, fsm, gitcmd,  # noqa: E402
                          runner, store)

# Настоящая `cmd_run`, снятая до подмены (тем же приёмом, что и
# tests/test_auto_cycle.py::REAL_CMD_RUN) — тестам отказа `run` по бюджету/
# паузе нужна она, а не фейк: предмет проверки в том, как `auto` реагирует
# на реальный отказ, а не на его имитацию.
REAL_CMD_RUN = runner.cmd_run

READY_PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: песочница детекции буксования

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

DRAFT_PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: draft
schema_version: 1
---

# PLAN: песочница детекции буксования — черновик

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

# PLAN.md, guard-невалидный: `status: ready`, но без секции «Влияние на
# систему» — тот же класс дефекта, что у tasks/T034/acceptance_tests/
# test_auto_guard_refusal.py::BROKEN_PLAN_MD.
BROKEN_PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: песочница детекции буксования — сломанный guard

## Подход

## Шаги

## Покрытие требований
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: песочница детекции буксования

## Соответствие SPEC

## Замечания

## Вердикт

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""


def fake_git(*args: str) -> subprocess.CompletedProcess:
    """Подмена `gitcmd.git`: пустой ответ вместо обращения к репозиторию."""
    return subprocess.CompletedProcess(list(args), 0, "", "")


class FakeRun:
    """Подмена `cmd_run`: заготовленные исходы шагов вместо агента.

    Свой потолок вызовов (`arm`) пришпиливает `AUTO_MAX_STEPS`: холостой шаг
    состояние не двигает, без потолка тест висел бы, не останови цикл сам
    себя (тот же приём, что в tests/test_auto_cycle.py::FakeRun).
    """

    def __init__(self):
        self.script: list = []
        self.calls: list[str] = []
        self.limit: int | None = None

    def arm(self, steps: int) -> None:
        self.limit = len(self.calls) + steps

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        if self.limit is not None and len(self.calls) >= self.limit:
            raise AssertionError(
                f"цикл не остановился: шагов больше {self.limit}")
        self.calls.append(task_id)
        if self.script:
            self.script.pop(0)()


class FakeAdvance:
    """Подмена `fsm.cmd_advance`: сценарий журналирует заданный `action`
    (текст или пара `(action, detail)`) на своём шаге — или ничего — и
    всегда возвращает `False`: тот же по характеру исход, что и у
    настоящего отказа `advance`, отличного от отказа guard'ом (guard
    возвращает `True`, сюда, по устройству цикла auto, не долетает — SPEC
    T038, требование 3). Тот же приём, что tests/test_auto_cycle.py::
    FakeAdvance и tasks/T038/acceptance_tests/.../FakeAdvance, расширенный
    парой `(action, detail)` — этой задаче нужен разный `detail` при
    одинаковом `action` (требование 1, AC-1).
    """

    def __init__(self):
        self.script: list = []
        self.calls = 0

    def __call__(self, task_id: str, session_id: str | None = None) -> bool:
        self.calls += 1
        item = self.script.pop(0) if self.script else None
        if item is not None:
            if isinstance(item, tuple):
                action, detail = item
            else:
                action, detail = item, "деталь тестового отказа"
            store.journal(store.db(), task_id, "fsm", action, detail)
        return False


class StallDetectionSandbox(unittest.TestCase):
    """БД и артефакты во временном каталоге, `cmd_run`/`gitcmd.git`
    подменены (тем же минимальным набором патчей `config`, что и у
    tasks/T038/T034 acceptance_tests — без ROOT/PROJECTS/TARGETS/WORKTREES,
    которые тем песочницам тоже не понадобились)."""

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
        self.capture(catalog.cmd_new, "Детекция буксования")
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

    def set_state(self, state: str, **fields) -> None:
        """Ставит состояние (и, если нужно, счётчики) в обход переходов —
        тем же приёмом, что tests/test_auto_cycle.py::AutoCycleTest."""
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        for column, value in fields.items():
            conn.execute(f"UPDATE tasks SET {column}=? WHERE id=?",
                         (value, self.TASK))
        conn.commit()

    def write_plan(self, template: str = READY_PLAN_MD) -> None:
        (self.tdir / "PLAN.md").write_text(
            template.format(task=self.TASK), encoding="utf-8")

    def write_review(self, status: str, iteration: int) -> None:
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_MD.format(task=self.TASK, status=status, iteration=iteration),
            encoding="utf-8")

    def journal_rows(self) -> list[tuple[str, str, str]]:
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def journal_detail(self, action: str) -> str:
        """Detail единственной записи журнала с таким action."""
        details = [d for _, a, d in self.journal_rows() if a == action]
        self.assertEqual(len(details), 1, f"записей «{action}»: {len(details)}")
        return details[0]

    def open_attention_alerts(self) -> list:
        """Открытые алерты kind=attention, чей `message` ссылается на TASK.

        SPEC (AC-7..AC-13) формулирует критерий как «алерт... с id задачи и
        причиной остановки В ТЕКСТЕ» — проверяем по содержимому `message`,
        а не по конкретной раскладке колонок target/source, которую SPEC не
        фиксирует (то же намеренное решение, что и по имени константы
        порога — см. докстринг модуля).
        """
        return [a for a in store.open_alerts(store.db(), "attention")
                if self.TASK in (a["message"] or "")]


if __name__ == "__main__":
    unittest.main()
