"""Общая песочница приёмочных тестов T070 (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из `test_ac*.py`).

Обёртка над `tests.test_invariants.FsmTest` (T001, git/агент заглушены,
`FakeProc`) — тот же приём, что и `tasks/T060/acceptance_tests/
test_max_parallel_tasks.py::LimiterSandbox`: `pause`/`resume` не берут
lease задачи и не спавнят агента сами, а `run`/`auto`, `kill`,
`approve`/`reject`, `advance` — уже проверенные тем же стендом команды
(SPEC T070, требования 2, 3, 6-8).

## Допущения интерфейса, которые вводит этот файл

SPEC называет только внешнюю форму команд (`pause <id>`, `resume <id>`,
требования 1, 3) и не фиксирует модуль/имя функций, которые их
реализуют — тем же приёмом, что и остальные однопредметные CLI-команды
пульта (`orchestrator/release.py::cmd_release`, `orchestrator/
cleanup.py::cmd_kill`, `orchestrator/budget.py::cmd_budget`):

- Новый модуль `orchestrator/pause.py` с функциями
  `cmd_pause(task_id: str) -> None` и `cmd_resume(task_id: str) -> None`.
- Пометка паузы — что-то в строке `tasks` БД (требование 4 SPEC называет
  только факт «запись в БД задачи», не схему, не имя колонки): тесты
  проверяют пометку через наблюдаемое поведение (`run`/`auto`
  отказывают/не отказывают начинать шаг) и через дифф словаря строки
  `tasks` целиком (что-то в ней изменилось / не изменилось ничего
  лишнего), а не через `SELECT` конкретной колонки по имени.
- Прогон ДО реализации падает `ModuleNotFoundError: No module named
  'orchestrator.pause'` — ожидаемо (skills/test-authoring: «падать на
  отсутствующей пока реализации — нормально»), не брак теста.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import cleanup, config, fsm, pause, runner, store  # noqa: E402
from tests.test_invariants import FakeProc, FsmTest  # noqa: E402

__all__ = ["invoke", "PauseSandbox", "pause", "cleanup", "config", "fsm",
          "runner", "store", "mock"]


def invoke(call) -> tuple:
    """(стдаут, код выхода). Отказ команды пульта уходит либо `sys.exit`
    (код в исключении), либо печатью + обычным `return` (код `None`) —
    тот же приём сверки, что и `tasks/T062/acceptance_tests/
    test_ac1_ac2_ac3_ac5_release_command.py::_invoke`."""
    buf = io.StringIO()
    code = None
    try:
        with redirect_stdout(buf):
            call()
    except SystemExit as exc:
        code = exc.code
    return buf.getvalue(), code


class PauseSandbox(FsmTest):
    """`FsmTest` (T001, git/агент заглушены) + утилиты, специфичные для
    приёмочных тестов `pause`/`resume`."""

    def journal_len(self) -> int:
        return len(store.task_steps(store.db(), self.TASK))

    def journal_tail(self, since: int) -> list:
        return store.task_steps(store.db(), self.TASK)[since:]

    def journal_tail_text(self, since: int) -> str:
        rows = self.journal_tail(since)
        return "\n".join(f"{r['actor']} {r['action']} {r['detail']}"
                         for r in rows)

    def run_with_fake_agent(self, call) -> tuple:
        """Прогон команды с подменённым `spawn_agent` — успешный
        одностроковый вывод агента, тот же приём, что и
        `tests.test_invariants.FsmTest.run_command`."""
        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out, _ = invoke(call)
        return out, popen

    def run_with_mid_step_side_effect(self, call, side_effect) -> tuple:
        """`spawn_agent`, который сначала исполняет `side_effect` (событие,
        происходящее «во время» уже стартовавшего агентного шага — здесь
        `pause`), а затем как обычно отдаёт `FakeProc` успешного шага."""
        def fake_popen(*args, **kwargs):
            side_effect()
            return FakeProc(["готово\n"])
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=fake_popen) as popen:
            out, _ = invoke(call)
        return out, popen

    def task_dict(self, task_id=None) -> dict:
        return dict(store.get_task(store.db(), task_id or self.TASK))
