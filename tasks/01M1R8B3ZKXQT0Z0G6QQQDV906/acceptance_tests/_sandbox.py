"""Общая песочница приёмочных тестов 01M1R8B3ZKXQT0Z0G6QQQDV906 («auto
пробует переход по готовым артефактам до шага роли; PLAN status escalate
уводит в escalated»).

Предмет SPEC — момент, когда `orchestrator/auto.py::_cmd_auto` вызывает
`fsm.cmd_advance` относительно `runner.cmd_run` внутри ОДНОЙ итерации
цикла (требования 1-4, AC-1..AC-4). Готового различающего интерфейса
здесь нет (сам SPEC называет только два файла и две уже существующие
функции: `orchestrator/auto.py`, `orchestrator/fsm_advance.py::in_dev`) —
тесты AC-1..AC-4 бьют по НАБЛЮДАЕМОМУ порядку двух вызовов, подменяя
ОБА: `runner.cmd_run` и `fsm.cmd_advance`, тем же приёмом, что уже
применяет `tests/test_auto_cycle.py::FakeAdvance` к одному `fsm.
cmd_advance` (тот фейк только журналирует текст отказа и всегда
возвращает `False` — здесь то же самое расширено переходом состояния и
guard-отказом, оба нужны для AC-2 и AC-4/guard).

Код этой задачи (`orchestrator/auto.py`, `orchestrator/fsm_advance.py`)
ждёт мержа зависимости («Механика зон, часть 2»,
01M1P9QAG65GVF69YJEV0V18D9, SPEC «Контекст») — на момент написания этой
планки код ещё не тронут, весь этот каталог обязан быть красным
буквально по тексту нынешней реализации (см. докстринг каждого файла).

`AutoAdvanceOrderSandbox` расширяет `tests.test_auto_cycle.AutoCycleTest`
(БД/артефакты во временном каталоге, `git` не исполняется, `cmd_run`
уже подменён в базовом классе `FakeRun`) — здесь `runner.cmd_run`
подменяется ПОВТОРНО (после `super().setUp()`) `RecordingRun`, а `fsm.
cmd_advance` — `ScriptedAdvance`, оба пишут в общий `self.events`
(список кортежей `(kind, role)`), где `role` — `runner.step_role`
задачи НА МОМЕНТ вызова (до любой мутации состояния этим самым
вызовом) — так тест видит и порядок, и то, какую роль каждый вызов
застал.

`RoleRecordingRun` (AC-5, AC-7) и `LockConflictSandbox` (AC-7) — `tests.
test_acceptance_tests_flow.LockTest` несёт СОБСТВЕННЫЕ `test_*`-методы
(в отличие от `AutoCycleTest`/`FsmTest` — те только база); `unittest.
TestLoader.loadTestsFromModule` собирает КАЖДЫЙ `TestCase`-подкласс,
привязанный именем в пространстве модуля, включая привязанный голым
`from ... import ИмяКласса` — не только объявленный в самом модуле
инструкцией `class`. `test_ac7_...py` поэтому обязан делать `import
_sandbox` и обращаться `_sandbox.LockConflictSandbox` (атрибут модуля,
не привязка имени в СВОЁМ пространстве) — иначе `unittest discover`
дважды прогнал бы унаследованные тесты `LockTest` внутри одного файла
(однажды под именем подкласса этой задачи, второй раз под голым именем
`LockConflictSandbox`) — проверено прогоном самого этого каталога.
"""
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, fsm, runner, store  # noqa: E402
from tests.test_acceptance_tests_flow import LockTest  # noqa: E402
from tests.test_auto_cycle import AutoCycleTest  # noqa: E402


class RecordingRun:
    """Подмена `runner.cmd_run`: не спавнит агента — только запоминает
    роль состояния, которое застал вызов, в `events` (общий с `Scripted
    Advance` список, см. докстринг модуля)."""

    def __init__(self, events: list) -> None:
        self.events = events
        self.calls: list[str] = []

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        t = store.get_task(store.db(), task_id)
        self.events.append(("run", runner.step_role(t)))
        self.calls.append(task_id)


class ScriptedAdvance:
    """Подмена `fsm.cmd_advance` с управляемым исходом каждого вызова —
    сценарий заполняется методами `arm_*` (по одному элементу на вызов;
    пусто — вызов ведёт себя как отказ «артефакт не готов», требование 3:
    ничего не журналирует, возвращает `False`).

    Четыре исхода, ортогональные друг другу, — ровно классы, которые
    различает SPEC (требования 3-4):
    - `arm_not_ready()` — «артефакт роли не готов» (нет записи в
      журнале) — требование 3, шаг роли обязан запуститься.
    - `arm_journaled_refusal(text)` — журналируемый отказ другого класса
      (лок/свежесть/ёмкость/«дерево не на ветке») — требование 4, шаг
      роли не запускается.
    - `arm_guard_refusal()` — guard отклонил артефакт-условие
      (`cmd_advance` возвращает `True`) — требование 4, шаг роли не
      запускается, цикл останавливается немедленно.
    - `arm_transition(new_state)` — переход состояния (требование 2):
      пишет `new_state` в БД напрямую (тот же приём, что `set_state` в
      `tests/test_auto_cycle.py::AutoCycleTest`, не через `store.
      set_state` — этому дублёру не нужен CAS настоящего перехода) и
      возвращает `False`.
    """

    def __init__(self, events: list) -> None:
        self.events = events
        self.script: list = []
        self.calls = 0

    def arm_not_ready(self, n: int = 1) -> None:
        self.script.extend([None] * n)

    def arm_journaled_refusal(self, text: str, n: int = 1) -> None:
        self.script.extend([("journal", text)] * n)

    def arm_guard_refusal(self, n: int = 1) -> None:
        self.script.extend([("guard",)] * n)

    def arm_transition(self, new_state: str) -> None:
        self.script.append(("transition", new_state))

    def __call__(self, task_id: str, session_id: str | None = None) -> bool:
        self.calls += 1
        conn = store.db()
        t = store.get_task(conn, task_id)
        self.events.append(("advance", runner.step_role(t)))
        action = self.script.pop(0) if self.script else None
        if action is None:
            return False
        kind = action[0]
        if kind == "journal":
            # `text` — САМ `action` записи (класс отказа, тот же приём,
            # что и настоящие обработчики `fsm_advance.py`: "переход
            # отклонён: лок приёмочных тестов" и т.п. — строка, которую
            # `_advance_refusal`/стоп-кран T038 сравнивают на равенство и
            # печатают в итоговом сообщении), не свободный `detail`.
            store.journal(conn, task_id, "fsm", action[1],
                          "деталь тестового отказа")
            return False
        if kind == "guard":
            return True
        if kind == "transition":
            conn.execute("UPDATE tasks SET state=? WHERE id=?",
                         (action[1], task_id))
            conn.commit()
            return False
        raise AssertionError(f"неизвестное действие сценария: {action}")


class AutoAdvanceOrderSandbox(AutoCycleTest):
    """`AutoCycleTest` + `RecordingRun`/`ScriptedAdvance`, делящие один
    `self.events`, — песочница AC-1..AC-4."""

    def setUp(self) -> None:
        super().setUp()
        self.events: list[tuple[str, str | None]] = []
        self.run_double = RecordingRun(self.events)
        self.advance = ScriptedAdvance(self.events)
        self.patch_object(runner, "cmd_run", self.run_double)
        self.patch_object(fsm, "cmd_advance", self.advance)


class RoleRecordingRun:
    """Подмена `runner.cmd_run`, безопасная и ДО реализации этой SPEC
    (когда `cmd_run` кое-где ещё вызывается вхолостую до того, как
    `advance` успевает отказать/перевести состояние, — AC-5, AC-7): не
    спавнит агента, только запоминает роль состояния, которое застал
    вызов."""

    def __init__(self) -> None:
        self.roles: list[str | None] = []

    def __call__(self, task_id: str, session_id: str | None = None) -> None:
        t = store.get_task(store.db(), task_id)
        self.roles.append(runner.step_role(t))


class LockConflictSandbox(LockTest):
    """`LockTest` (реальный git, лок `acceptance_tests/` — T023) — для
    AC-7: `runner.cmd_run` подменён `RoleRecordingRun` (без этого
    реализация ДО этой SPEC спавнила бы настоящего агента, прежде чем
    лок успеет отказать), порог холостых шагов поднят выше
    `AUTO_MAX_STEPS`, чтобы стоп-кран T038 (два одинаковых отказа
    подряд) успел сработать первым — тот же приём, что `tests/
    test_auto_cycle.py::AutoStopsOnRepeatedAdvanceRefusalTest`."""

    def setUp(self) -> None:
        super().setUp()
        self.recorder = RoleRecordingRun()
        run_patcher = mock.patch.object(runner, "cmd_run", self.recorder)
        run_patcher.start()
        self.addCleanup(run_patcher.stop)
        stall_patcher = mock.patch.object(config, "AUTO_STALL_STEPS_LIMIT",
                                          config.AUTO_MAX_STEPS + 1)
        stall_patcher.start()
        self.addCleanup(stall_patcher.stop)
