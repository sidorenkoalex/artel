"""AC-4 (SPEC.md): `_run_developer_step` разложен на
`_refuse_before_start`, `_build_prompt`, `_run_attempts`,
`_escalate_after_attempts`.

Поведенческие уточнения этих же четырёх имён (AC-5 — контракт
`_refuse_before_start`; AC-6 — контракт `_run_attempts`) размечены
`manual` в test_manual_markers.py этой же планки: SPEC не называет их
сигнатуры, вызвать их напрямую значило бы придумать интерфейс, а не
проверить критерий.

Красен до реализации: `_run_developer_step` на этой ветке остаётся
монолитом на 207 строк — ни одного из четырёх имён в модуле нет.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import runner  # noqa: E402

DEVELOPER_STEP_HELPER_NAMES = (
    "_refuse_before_start", "_build_prompt", "_run_attempts",
    "_escalate_after_attempts",
)


class DeveloperStepHelpersExistTest(unittest.TestCase):

    def test_ac4_developer_step_helpers_exist_as_module_privates(self):
        """`_run_developer_step` разложен на четыре именованных в AC-4
        приватных помощника — модульных глобала `orchestrator.runner`
        (`_cmd_run` продолжает звать `_run_developer_step` как единую
        точку входа — AC-4 не требует разбора самого вызова `_cmd_run`).

        Ловит мутацию: разработчик разбирает `_run_developer_step` на
        функции с ДРУГИМИ именами (например `_pre_checks`/
        `_attempt_loop` вместо `_refuse_before_start`/`_run_attempts`) —
        код может остаться рабочим, но патчи тестов и трассируемость
        SPEC по этим четырём буквальным именам не сработают;
        `hasattr(runner, "_run_attempts")` и соседи откажут.
        """
        for name in DEVELOPER_STEP_HELPER_NAMES:
            with self.subTest(name=name):
                self.assertTrue(hasattr(runner, name),
                                f"{name} отсутствует в orchestrator.runner")
                self.assertTrue(callable(getattr(runner, name)),
                                f"{name} не является вызываемым объектом")
