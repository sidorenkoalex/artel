"""Общие помощники приёмочных тестов этой планки (SPEC
01M1TKP45EM16ZMJGQKNZA5T7J): обнаружение эталонного класса лёгкой
песочницы переходов в `tests/sandbox.py` (требование 1, AC-1..AC-5) и
прогон его как unittest-зонда.

Тонкая надстройка сценария (skills/test-authoring.md, правило этой же
задачи, AC-7): НЕ переопределяет `disk_backed_*`/`advance_from_in_dev`
— только обнаруживает и вызывает то, что уже несёт `tests/sandbox.py`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tests import sandbox as sandbox_module  # noqa: E402

# Три помощника требования 1 SPEC, названные буквально (в отличие от
# имени самого класса — «по месту разработчика», требование 1) —
# фиксированный контракт этой планки.
REQUIRED_HELPER_NAMES = ("write_plan_ready", "write_acceptance_plank",
                         "advance_from_in_dev")


def find_light_transition_sandbox_classes() -> list:
    """Публичные подклассы `TmpRootTest` в `tests.sandbox`, несущие все
    три помощника требования 1 — независимо от того, как разработчик
    назвал сам класс."""
    found = []
    for name, obj in vars(sandbox_module).items():
        if name.startswith("_"):
            continue
        if not isinstance(obj, type):
            continue
        if not issubclass(obj, sandbox_module.TmpRootTest):
            continue
        if obj in (sandbox_module.TmpRootTest, sandbox_module.RealGitSandbox):
            continue
        if all(hasattr(obj, attr) for attr in REQUIRED_HELPER_NAMES):
            found.append(obj)
    return found


def run_probe(cls, body) -> dict:
    """Прогоняет `cls` как unittest-кейс с одним тестовым методом,
    телом которого служит `body(self, captured)` — `captured` доступен
    вызывающему коду ПОСЛЕ прогона (значения записаны до отката патчей
    setUp тестовым `tearDown`/`addCleanup`, сам словарь переживает их).

    `captured["_result_success"]` — прогон (`setUp`/тело/`tearDown`) не
    упал исключением; `_result_errors`/`_result_failures` — как у
    `unittest.TestResult`, для диагностики упавшего зонда.
    """
    captured: dict = {}

    class _Probe(cls):
        def test_probe(self):
            body(self, captured)

    result = unittest.TestResult()
    unittest.TestLoader().loadTestsFromTestCase(_Probe).run(result)
    captured["_result_success"] = result.wasSuccessful()
    captured["_result_errors"] = result.errors
    captured["_result_failures"] = result.failures
    return captured
