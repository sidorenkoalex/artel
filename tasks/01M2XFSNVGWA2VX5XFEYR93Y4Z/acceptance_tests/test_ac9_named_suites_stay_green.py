"""Приёмочный тест AC-9 задачи 01M2XFSNVGWA2VX5XFEYR93Y4Z: прогон
поимённо названных SPEC наборов `tests/test_zones_gate.py`,
`tests/test_zones_approve.py`, `tests/test_auto_cycle.py` — зелёный.

Зелёный с рождения: критерий требует НЕПОРЧИ уже существующих наборов —
на сегодняшнем коде они зелёные, и тест обязан быть зелёным сразу; он
краснеет ровно тогда, когда правка задачи ломает любой из трёх. Стаб
корректной реализации здесь не нужен и не применим: предмет проверки —
уже существующее поведение, а не отсутствующий код.

Прогон — отдельным процессом (`python3 -m unittest <модули>` из корня
репозитория), а не импортом внутрь текущего: наборы гоняют собственные
песочницы, патчащие `orchestrator.config`/`gitcmd` модульно, и их
запуск внутри уже работающего процесса планки перемешал бы патчи. Три
файла целиком укладываются в единицы секунд — отдельный процесс дешевле
любой попытки их переиспользовать.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Ровно те три набора, что перечислены в AC-9 и в требовании 7 SPEC.
NAMED_SUITES = ("tests.test_zones_gate", "tests.test_zones_approve",
                "tests.test_auto_cycle")

# Потолок прогона: сегодня три файла занимают около трёх секунд; запас
# на порядок покрывает медленный раннер CI и всё ещё далёк от потолка
# `-o timeout=120`, которым пульт принимает планку.
RUN_TIMEOUT_SEC = 60


class Ac9NamedSuitesStayGreenTest(unittest.TestCase):
    """AC-9."""

    def test_ac9_named_suites_stay_green(self):
        """`tests/test_zones_gate.py`, `tests/test_zones_approve.py`,
        `tests/test_auto_cycle.py` проходят на коде задачи.

        Ловит мутацию: различая причину отказа, трогают общий текст
        отказа гейта зон или классификацию отказов `auto` шире, чем
        требует SPEC — например, переименовывают действие «переход
        отклонён: гейт зон» или относят к классу «роль ещё не закончила»
        любой отказ `in_dev`; оба ломают перечисленные наборы
        (`ZonesGateGitFailureTest`, `AutoStopsOnRepeatedAdvanceRefusalTest`),
        и этот тест краснеет.
        """
        res = subprocess.run(
            [sys.executable, "-m", "unittest", *NAMED_SUITES],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            timeout=RUN_TIMEOUT_SEC)

        self.assertEqual(
            res.returncode, 0,
            "прогон названных SPEC наборов не зелёный:\n"
            f"--- stdout ---\n{res.stdout[-4000:]}\n"
            f"--- stderr ---\n{res.stderr[-6000:]}")


if __name__ == "__main__":
    unittest.main()
