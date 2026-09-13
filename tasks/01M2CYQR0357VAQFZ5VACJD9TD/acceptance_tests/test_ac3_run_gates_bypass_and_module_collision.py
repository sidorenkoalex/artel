"""Приёмочный тест AC-3 (tasks/01M2CYQR0357VAQFZ5VACJD9TD/SPEC.md,
частично — точечные свойства, воспроизводимые в песочнице; остальное —
`# AC-3: skip` в test_manual_and_escalation_markers.py):
«обход `_run_gates` у `_acceptance_run_refuses` сохранён» и коллизия
имени `orchestrator/gates.py` (флэт-модуль политики `gates.yaml`,
ADR-0007/T066) с новым пакетом гейтов НЕ материализуется — пакет назван
`orchestrator/advance_gates/` (ANSWER-1.md, вопрос 1, вариант б), не
`orchestrator/gates/`.

Первый пункт AC-3 воспроизводим по исходнику функции — `_run_gates`
не встречается среди `co_names` `_acceptance_run_refuses` ни до, ни
после переноса. Второй пункт — прямое следствие переименования пакета
из ANSWER-1.md/ANSWER-2.md: без него `import orchestrator.gates`
переставал бы резолвиться в старый флэт-модуль (CPython отдаёт
приоритет одноимённому пакету-директории с `__init__.py` над
модулем-файлом того же имени) и ронял бы `tests/test_gates.py` (9
тестов) — что и было причиной прежней эскалации AC-3, снятой ANSWER-2.

Полный набор `tests/` зелёный, идентичность текстов отказов/журнала/
кодов выхода/схемы БД — свойства КОММИТА в целом, не изолированного
объекта в песочнице; их проверяет CI/автогейт (см. `# AC-3: skip` в
test_manual_and_escalation_markers.py).

Красен до реализации: `orchestrator/advance_gates/` не существует —
`test_ac3_gates_policy_module_not_shadowed_by_new_package` падает на
`importlib.import_module("orchestrator.advance_gates")`
(ModuleNotFoundError), поскольку пакета ещё нет.

Зелёный с рождения: `test_ac3_acceptance_run_refuses_bypasses_run_gates_framework`
проходит уже сегодня — обращается к `fsm_advance._acceptance_run_refuses`
БЕЗ алиасного пути через пакет (это имя доступно в `fsm_advance` и до, и
после переноса, требование 2 SPEC), а сама функция в её нынешнем виде в
`orchestrator/fsm_advance.py` уже не проходит через `_run_gates` — тест
сохранения существующего поведения, которое перенос обязан не сломать.
"""
import importlib
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


class RunGatesBypassAndModuleCollisionTest(unittest.TestCase):

    def test_ac3_acceptance_run_refuses_bypasses_run_gates_framework(self):
        """`_acceptance_run_refuses` не проходит через каркас `_run_gates`
        ни до, ни после переноса в `orchestrator/advance_gates/
        acceptance.py` — докстринг функции прямо фиксирует это решение
        (см. `PLAN «Подход»`), и SPEC требование 3/AC-3 требует сохранить
        его дословно при переносе.

        Ловит мутацию: разработчик «выравнивает» перенесённую функцию
        под остальные гейты (`_capacity_gate_refuses`,
        `_zones_gate_refuses`), заворачивая её тело в
        `_run_gates(conn, task_id, [lambda: ...])` — правдоподобная
        правка «за компанию» при переезде в один файл с гейтами,
        использующими каркас; имя `_run_gates` появится среди
        `co_names` функции.
        """
        from orchestrator import fsm_advance

        func = fsm_advance._acceptance_run_refuses
        self.assertNotIn(
            "_run_gates", func.__code__.co_names,
            "_acceptance_run_refuses теперь ссылается на _run_gates — "
            "обход каркаса потерян при переносе")

    def test_ac3_gates_policy_module_not_shadowed_by_new_package(self):
        """Старый флэт-модуль `orchestrator/gates.py` (политика
        `gates.yaml`: `policy`, `AUTO`, `MANUAL`) продолжает резолвиться
        как модуль-файл после появления нового пакета гейтов перехода —
        новый пакет назван `orchestrator/advance_gates/`, а не
        `orchestrator/gates/`, поэтому коллизии имён нет.

        Ловит мутацию: пакет по ошибке (буквальное прочтение исходного
        текста SPEC до правки ANSWER-1.md) назван `orchestrator/gates/`
        — тогда `import orchestrator.gates` резолвится в НОВЫЙ пакет
        (CPython предпочитает пакет-директорию одноимённому файлу),
        `orchestrator.gates.__file__` укажет на
        `.../gates/__init__.py`, а `hasattr(orchestrator.gates, "policy")`
        станет `False`.
        """
        # Пакет из требования 1 (с поправкой ANSWER-1.md) обязан
        # существовать и не быть тем же модулем, что "orchestrator.gates".
        advance_gates = importlib.import_module("orchestrator.advance_gates")
        gates = importlib.import_module("orchestrator.gates")

        self.assertTrue(
            gates.__file__.endswith("gates.py"),
            f"orchestrator.gates резолвится не в флэт-модуль: "
            f"{gates.__file__}")
        for name in ("policy", "AUTO", "MANUAL"):
            self.assertTrue(
                hasattr(gates, name),
                f"orchestrator.gates.{name} недоступен — модуль "
                f"политики затенён новым пакетом гейтов")
        self.assertNotEqual(
            Path(gates.__file__).resolve(),
            Path(advance_gates.__file__).resolve(),
            "orchestrator.gates и orchestrator.advance_gates — один и "
            "тот же файл")


if __name__ == "__main__":
    unittest.main()
