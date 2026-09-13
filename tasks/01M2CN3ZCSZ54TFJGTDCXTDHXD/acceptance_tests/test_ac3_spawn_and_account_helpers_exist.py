"""AC-3 (SPEC.md): `_spawn_and_wait` открывает файл промпта, вызывает
`spawn_agent`, запускает перекачку вывода (pump), обрабатывает таймаут
и снятие группы процессов и возвращает `proc`, `pump`, `rc`,
`timed_out`, `killed_group`; `_account_step` выполняет учёт шага
(friction, `spend.*`, `budget.check_program_spend`) без изменения
вызовов и их порядка.

Существование обоих помощников уже проверено `test_ac1_...
prepare_and_finish_helpers_exist_as_module_privates` (AC-1 называет их
в том же перечне) — здесь та же проверка под именем AC-3 не
повторяется настоящим ассертом. SPEC не называет ни сигнатуру
`_spawn_and_wait`/`_account_step` (какие аргументы, в каком порядке),
ни то, как ИМЕННО вызывающий код получает их результат — вызвать их
напрямую и свериться с возвращаемой пятёркой `proc/pump/rc/timed_out/
killed_group` означало бы придумать за разработчика интерфейс, которого
критерий не фиксирует (conventions-core: «тест на то, что не написано
в AC — такой же дефект»). Сам факт «friction/spend/budget вызываются в
прежнем порядке» и «таймаут корректно снимает группу процессов» —
наблюдаемое поведение `run_agent_once` в целом, уже покрытое полным
набором `tests/` (tests/test_agent_log.py::StepFrictionTest,
OutputPumpTest, RealSubprocessPumpTest — pump/таймаут/kill группы;
tests/test_step_cost.py, tests/test_agent_failure.py — friction/
spend/бюджет и их относительный порядок в журнале) и подтверждённое
зелёным полным прогоном (AC-9).

Красен до реализации: `hasattr(runner, "_spawn_and_wait")` — `False`,
приватного помощника с этим именем в модуле до разбора нет вовсе.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import runner  # noqa: E402


class SpawnAndAccountHelpersExistTest(unittest.TestCase):

    def test_ac3_spawn_and_wait_and_account_step_exist_as_module_privates(self):
        """`_spawn_and_wait` и `_account_step` — приватные глобалы модуля
        `orchestrator.runner`, оба вызываемые (не константы, не классы
        без `__call__`).

        Ловит мутацию: разработчик сливает запуск/ожидание и учёт
        обратно в тело `run_agent_once` (или в один общий помощник вместо
        двух раздельных, например единый `_run_and_account`) — заявленная
        AC-3 декомпозиция на ДВЕ отдельные функции с этими именами не
        состоится, `hasattr(runner, "_account_step")` откажет, даже если
        весь остальной набор `tests/` останется зелёным.
        """
        for name in ("_spawn_and_wait", "_account_step"):
            with self.subTest(name=name):
                self.assertTrue(hasattr(runner, name),
                                f"{name} отсутствует в orchestrator.runner")
                self.assertTrue(callable(getattr(runner, name)),
                                f"{name} не является вызываемым объектом")
