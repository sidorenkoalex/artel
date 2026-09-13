"""AC-1 (SPEC.md): `run_agent_once` разложен на приватные функции
`_prepare_step`, `_spawn_and_wait`, `_account_step` и на функции
исходов `_finish_timeout`, `_finish_failed`, `_finish_missing_artifact`,
`_finish_ok`; сигнатура, тип и значение возврата `run_agent_once` не
меняются.

Красен до реализации: до рефакторинга `orchestrator/runner.py` несёт
только `run_agent_once` одним телом на 262 строки — семи приватных
имён из AC-1 в модуле нет вовсе, `hasattr` первого теста падает на
самой первой из них (`_prepare_step`).
"""
import inspect
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import runner  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RunAgentOnceSandbox  # noqa: E402

DECOMPOSED_HELPER_NAMES = (
    "_prepare_step", "_spawn_and_wait", "_account_step",
    "_finish_timeout", "_finish_failed", "_finish_missing_artifact",
    "_finish_ok",
)


class RunAgentOnceHelpersExistTest(RunAgentOnceSandbox):

    def test_ac1_prepare_and_finish_helpers_exist_as_module_privates(self):
        """`run_agent_once` разложен на семь именованных в AC-1 приватных
        помощников, живущих модульными глобалами `orchestrator.runner`
        (не методами класса, не вложенными функциями, не в новом модуле).

        Ловит мутацию: разработчик переносит подготовку/запуск/учёт/
        исходы во вложенные функции внутри тела `run_agent_once`
        (замыкания) вместо модульных `_prepare_step`/`_spawn_and_wait`/
        `_account_step`/`_finish_*` — код может остаться рабочим и все
        существующие tests/ зелёными, но `hasattr(runner, "_prepare_step")`
        и его соседи откажут: имена не появились на уровне модуля.
        """
        for name in DECOMPOSED_HELPER_NAMES:
            with self.subTest(name=name):
                self.assertTrue(hasattr(runner, name),
                                f"{name} отсутствует в orchestrator.runner")
                self.assertTrue(callable(getattr(runner, name)),
                                f"{name} не является вызываемым объектом")

    def test_ac1_run_agent_once_return_contract_is_unchanged(self):
        """Сигнатура `run_agent_once` (`conn, task_id, role, prompt,
        attempt`) и форма её возврата — тройка `(исход: str, пояснение:
        str, класс_отказа: str | None)` — остаются теми же, что и до
        разбора на фазы: сверяется параметрами сигнатуры и одним живым
        вызовом (окружение роли недоступно — `role_env` бросает
        `OSError`, ветка исхода "skipped").

        Ловит мутацию: разбор на `_prepare_step`/`_spawn_and_wait`/
        `_account_step` меняет публичный контракт — например,
        `run_agent_once` начинает возвращать словарь вместо тройки,
        либо теряет позиционный параметр `attempt` (передавая его через
        `**kwargs` новой внутренней функции и забывая проксировать
        наружу) — `assertEqual(list(sig.parameters), ...)` или
        `assertIsInstance(outcome, tuple)`/`assertEqual(len(outcome), 3)`
        откажут.
        """
        sig = inspect.signature(runner.run_agent_once)
        self.assertEqual(list(sig.parameters),
                         ["conn", "task_id", "role", "prompt", "attempt"])

        with mock.patch.object(runner, "role_env",
                               side_effect=OSError("нет места")):
            outcome = self.run_once()

        self.assertIsInstance(outcome, tuple)
        self.assertEqual(len(outcome), 3)
        status, reason, failure_class = outcome
        self.assertIsInstance(status, str)
        self.assertIsInstance(reason, str)
        self.assertIsNone(failure_class)
        self.assertEqual(outcome,
                         ("skipped", "окружение роли не подготовлено: нет места",
                          None))
