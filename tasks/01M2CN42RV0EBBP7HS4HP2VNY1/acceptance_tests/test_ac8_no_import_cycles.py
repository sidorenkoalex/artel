"""AC-8 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: прямой импорт каждого из
`orchestrator.canary`, `orchestrator.pool_seal`, `orchestrator.catalog`,
`orchestrator.doctor` завершается без `ImportError` о циклическом
импорте (требование 5).

Красен до реализации: `orchestrator/pool_seal.py` ещё не существует —
`import orchestrator.pool_seal` в свежем интерпретаторе падает
`ModuleNotFoundError` (тоже проваливает тест: заодно фиксирует сам факт
существования модуля, не только отсутствие цикла).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

MODULES = (
    "orchestrator.canary",
    "orchestrator.pool_seal",
    "orchestrator.catalog",
    "orchestrator.doctor",
)


class NoImportCyclesTest(unittest.TestCase):

    def test_ac8_each_module_imports_standalone_without_cycle(self):
        """Сценарий: каждый из четырёх модулей импортируется В
        ОТДЕЛЬНОМ свежем интерпретаторе (не последовательно в одном
        процессе — тогда `sys.modules` первого импорта скрыл бы цикл,
        который проявился бы только при другом порядке импорта).

        Ловит мутацию: `pool_seal.py` на уровне модуля импортирует
        `canary` там, где сегодня нет причины (например, по инерции
        нового докстринг-комментария разработчик заводит настоящий
        `from . import canary` в pool_seal.py) — это завело бы цикл
        `canary -> pool_seal -> canary`, и подпроцесс для одного из
        модулей завершится с `ImportError`/`ImportError: cannot import
        name` в stderr.
        """
        failures = []
        for module in MODULES:
            proc = subprocess.run(
                [sys.executable, "-c", f"import {module}"],
                cwd=REPO_ROOT, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                failures.append(f"{module}: {proc.stderr.strip()[-500:]}")
        self.assertFalse(failures, "\n\n".join(failures))


if __name__ == "__main__":
    unittest.main()
