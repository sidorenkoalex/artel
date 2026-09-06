"""AC-7 (tasks/01M1TKNXX5YN5KT4WHG4T44JWV/SPEC.md): существующие тесты
проходят без правки их утверждений.

Три файла ниже — прямые юнит-тесты гейтов, которые эта задача
рефакторит (`tests/test_capacity_gate.py`/`tests/test_zones_gate.py`/
`tests/test_fsm_review_rework_gate.py`): они зовут `_capacity_gate_
refuses`/`_zones_gate_refuses`/`_review_rework_gate_refuses`/
`_reviewer_verdict_baseline`/`_split_zone_paths`/`_touches_zone`/
`_plan_zones_extension_paths` НАПРЯМУЮ и проверяют побочный эффект
(журнал) сразу после вызова — если рефакторинг переведёт эти функции на
чисто-предикатный стиль без сохранения СТАРОГО поведения при прямом
вызове по этому же имени, их утверждения (`assertTrue`/`assertIn` на
содержимом журнала) перестанут выполняться. Полный набор `tests/`
намеренно не запускается здесь (гоняет CI, `tasks/<id>/acceptance_tests`
не место для этого, см. скил test-authoring) — только три файла, прямо
затронутые зоной этой задачи.

Зелёный с рождения: эти три файла уже проходят на сегодняшнем
(нерефакторенном) коде — тест фиксирует их прохождение как планку,
которую рефакторинг обязан не сломать.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

_AFFECTED_TEST_MODULES = (
    "tests.test_capacity_gate",
    "tests.test_zones_gate",
    "tests.test_fsm_review_rework_gate",
)


class Ac7ExistingGateTestsStillPassTest(unittest.TestCase):

    def test_ac7_capacity_zones_and_rework_unit_tests_pass_unmodified(self):
        """Прогон `python3 -m unittest tests.test_capacity_gate
        tests.test_zones_gate tests.test_fsm_review_rework_gate`
        завершается кодом 0 — существующие утверждения этих файлов
        (проверка журнала/побочных эффектов вызовов гейтов по старым
        именам) не тронуты рефакторингом каркаса.

        Ловит мутацию: гейт-функции переведены на чисто-предикатный стиль
        БЕЗ сохранения побочного эффекта при прямом вызове по старому
        имени (например `_capacity_gate_refuses` перестал сам звать
        `store.journal`) — эти существующие тесты начнут падать, и код
        возврата subprocess станет ненулевым.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *_AFFECTED_TEST_MODULES],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)

        self.assertEqual(
            result.returncode, 0,
            f"существующие тесты гейтов обязаны остаться зелёными:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
