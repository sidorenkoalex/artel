"""Зелёный с рождения: AC-9 не описывает новое поведение задачи, а требует
НЕОСЛАБЛЕНИЯ существующих тестов регрессии №12 (`tests/
test_artifact_materialization.py`, `tests/test_fsm_autogate.py`) — эта
задача чинит каталог материализации/`cwd` прогона планки, не источник
истины `tasks/<id>/acceptance_tests/` (артефактная ветка, SPEC «Не
входит»), и оба файла живут вне зоны правки (`orchestrator/acceptance.py`,
`orchestrator/fsm.py`, `orchestrator/fsm_advance.py`) — они обязаны
оставаться зелёными и ДО, и ПОСЛЕ правки этой задачи, без единого удалённого
или смягчённого `assert`.

Прогоняет оба файла целиком, программно (`unittest.TestLoader`), а не
полагается на то, что разработчик не тронет их руками, — числовой счёт
пройденных/упавших тестов делает регресс видимым здесь же, а не только на
CI следующего коммита.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests import test_artifact_materialization, test_fsm_autogate  # noqa: E402


class Ac9Regression12SuitesStillGreenTest(unittest.TestCase):

    def test_ac9_existing_regression12_tests_are_not_weakened(self):
        """Оба модуля регрессии №12 целиком зелёные — ни один тест не
        удалён и не ослаблен настолько, чтобы перестать что-то проверять
        (число прогнанных тестов положительно) и ни один не упал.

        Ловит мутацию: правка этой задачи (`orchestrator/acceptance.py`)
        меняет сигнатуру/поведение так, что существующие тесты регрессии
        №12 (например, `MaterializeTaskDirTest`, юнит-случаи
        `_autogate_conditions`) начинают падать или тихо перестают
        запускаться (`tests_run == 0` при сломанном сборе тестов).
        """
        loader = unittest.TestLoader()
        suite = unittest.TestSuite([
            loader.loadTestsFromModule(test_artifact_materialization),
            loader.loadTestsFromModule(test_fsm_autogate),
        ])

        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)

        self.assertGreater(
            result.testsRun, 0,
            "сбор тестов регрессии №12 не нашёл ни одного теста — "
            "вероятная поломка импорта/сборки, не пустой файл")
        self.assertTrue(
            result.wasSuccessful(),
            f"регрессия №12 не должна ослабляться этой задачей: "
            f"failures={result.failures}, errors={result.errors}")


if __name__ == "__main__":
    unittest.main()
