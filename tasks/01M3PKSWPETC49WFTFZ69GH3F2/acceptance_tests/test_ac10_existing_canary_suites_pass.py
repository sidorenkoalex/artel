"""AC-10 — 01M3PKSWPETC49WFTFZ69GH3F2: существующие наборы частей пульта,
которые задача не меняет, проходят.

Группа: разовый

Источник — SPEC.md, «Критерии приёмки»:

AC-10. Выбор шаблонов и наборов, локальный слой моделей клона, вход
Codex клона, сравнение с базовой линией, вердикт штатного прогона и
формат сводки для штатного прогона не меняются: существующие тесты этих
частей проходят без ослабления.

Наборы этих частей: выбор шаблонов — `tests/test_canary_template_flag.py`;
наборы ролей и локальный слой моделей клона — `tests/test_canary_sets.py`;
вход Codex клона — `tests/test_canary_codex_clone_auth.py`; сравнение с
базовой линией, вердикт и сводка — `tests/test_canary.py`. Прогоняются
целиком загрузчиком unittest в процессе планки (полный набор `tests/` —
дело CI). «Без ослабления» по удалённым методам сверяет AC-11; правку
утверждений внутри метода — ревью по диффу.

Зелёный с рождения: все четыре набора проходят на коде до задачи — тест
сохранения существующего поведения; краснеет, когда переход на процесс
клона ломает одну из этих частей или файл набора исчезает.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _clone_drive  # noqa: E402

SUITES = ("test_canary_template_flag", "test_canary_sets",
          "test_canary_codex_clone_auth", "test_canary")


class ExistingCanarySuitesTest(unittest.TestCase):

    def test_ac10_existing_suites_of_unchanged_parts_pass(self):
        """Четыре набора `tests/` частей, которые задача не меняет, есть в
        ветке и проходят целиком без единого провала и ошибки.

        Ловит мутацию: `_ephemeral_clone` при переходе на процесс клона
        перестаёт класть локальный слой клона после `catalog.cmd_init` или
        переопределять `CODEX_HOME` (`tests/test_canary_codex_clone_auth.py::
        EphemeralCloneCodexHomeTest` краснеет), либо `_run_verdict`/
        `_baseline_deviation_note` переписаны под результат клона с иной
        формулой (`tests/test_canary.py` краснеет) — провалившийся метод
        назван в тексте.
        """
        tests_dir = _clone_drive.CODE_ROOT / "tests"
        missing = [s for s in SUITES if not (tests_dir / f"{s}.py").is_file()]
        self.assertEqual(missing, [], f"наборы исчезли из ветки: {missing}")
        loader = unittest.TestLoader()
        suite = unittest.TestSuite(
            loader.loadTestsFromName(f"tests.{name}") for name in SUITES)
        self.assertEqual(list(loader.errors), [],
                         "наборы не загружаются: " + "; ".join(
                             str(e)[:400] for e in loader.errors))
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertTrue(
            result.wasSuccessful(),
            "наборы не зелёные: провалы="
            + repr([str(case) for case, _ in result.failures])
            + "; ошибки=" + repr([str(case) for case, _ in result.errors]))
        self.assertGreater(result.testsRun, 0)


if __name__ == "__main__":
    unittest.main()
