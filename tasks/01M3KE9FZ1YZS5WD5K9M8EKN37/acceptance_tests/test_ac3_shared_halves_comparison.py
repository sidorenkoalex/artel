"""AC-3: новую пару сверяет ТА ЖЕ сверка половин, что и остальные.

Красен до реализации: пары `model_reasoning_effort=high` нет в
`CONFIG_OVERRIDES`, поэтому членство не выполняется; снятие строки из
образца существующую сверку не красит (сверять нечего), а ни один модуль
`tests/test_*.py` про новую настройку ещё не знает.
"""
import importlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _util

# Сверка половин «образец ⇄ перечень команды шага» — два существующих
# метода, названные AC-3. Имена берутся из формулировки критерия, а не
# из сегодняшнего содержимого файла.
COMPARISON_METHODS = (
    ("StepCommandTest", "test_overrides_repeat_the_curated_config_pair_for_pair"),
    ("CuratedHomeTest",
     "test_curated_config_repeats_the_command_overrides_pair_for_pair"),
)
COMPARISON_MODULE = "tests.test_providers_codex"
TESTS_DIR = "tests"


def _failed(result) -> bool:
    return bool(result.failures or result.errors)


class Ac3SharedComparisonTest(unittest.TestCase):
    """Сверка половин покрывает новую пару членством в
    `CONFIG_OVERRIDES`, а не отдельной копией на её имя."""

    def setUp(self):
        self.pair = (_util.REASONING_KEY, _util.REASONING_VALUE)
        self.module = importlib.import_module(COMPARISON_MODULE)
        self.cases = []
        for class_name, method in COMPARISON_METHODS:
            cls = getattr(self.module, class_name, None)
            self.assertIsNotNone(
                cls, f"{COMPARISON_MODULE}.{class_name} не найден")
            self.assertTrue(
                hasattr(cls, method),
                f"{COMPARISON_MODULE}.{class_name}.{method} не найден")
            self.cases.append((cls, method))

    def _tmpdir(self) -> Path:
        tmp = tempfile.TemporaryDirectory(prefix="artel-plank-codex-")
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def _modules_naming_the_key(self) -> list:
        """Модули `tests/test_*.py`, текст которых называет ключ глубины
        рассуждения, — там и живут проверки половин по требованию 8."""
        found = []
        for path in sorted((_util.REPO_ROOT / TESTS_DIR).glob("test_*.py")):
            if _util.REASONING_KEY in path.read_text(encoding="utf-8"):
                found.append(f"{TESTS_DIR}.{path.stem}")
        return found

    def test_ac3_dropping_the_setting_from_either_half_reddens_the_comparison(self):
        """Пара входит в `CONFIG_OVERRIDES` — и этим попадает под обе
        стороны существующей сверки; снятие настройки из образца красит
        обе стороны сверки, снятие из перечня команды шага красит
        проверки половин в `tests/`.

        Ловит мутацию: пару вписали литералом прямо в `command()` мимо
        `CONFIG_OVERRIDES` («флаг же один») — argv команды шага
        совпадает, но сверка половин перестаёт видеть новую пару:
        наблюдаемо, что после снятия строки из образца оба метода сверки
        остаются зелёными, то есть расхождение половин проходит молча.
        """
        self.assertIn(self.pair, _util.codex_provider.CONFIG_OVERRIDES)

        for cls, method in self.cases:
            with self.subTest(baseline=method):
                self.assertFalse(
                    _failed(_util.run_test_case(cls, method)),
                    f"{method} красен ещё до мутации")

        # --- половина «образец настроек дома роли»
        root = _util.reference_copy_without_reasoning(self._tmpdir())
        with mock.patch.object(_util.config, "ROOT", root):
            for cls, method in self.cases:
                with self.subTest(curated_without=method):
                    self.assertTrue(
                        _failed(_util.run_test_case(cls, method)),
                        f"{method} зелен на образце без "
                        f"{_util.REASONING_KEY}")

        # --- половина «перечень команды шага»
        modules = self._modules_naming_the_key()
        self.assertTrue(
            modules,
            f"ни один модуль {TESTS_DIR}/test_*.py не называет "
            f"{_util.REASONING_KEY}")
        without = tuple(item for item in
                        _util.codex_provider.CONFIG_OVERRIDES
                        if item != self.pair)
        loader = unittest.defaultTestLoader
        with mock.patch.object(_util.codex_provider, "CONFIG_OVERRIDES",
                               without):
            red = [name for name in modules
                   if _failed(_util.run_suite(loader.loadTestsFromModule(
                       importlib.import_module(name))))]

        self.assertTrue(
            red,
            f"снятие пары из CONFIG_OVERRIDES не покраснило ни один из "
            f"модулей {modules}")


if __name__ == "__main__":
    unittest.main()
