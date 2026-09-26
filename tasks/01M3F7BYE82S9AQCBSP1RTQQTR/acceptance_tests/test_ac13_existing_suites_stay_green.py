"""AC-13 — 01M3F7BYE82S9AQCBSP1RTQQTR: тесты провайдеров, doctor, модели
шага роли и манифеста стека остаются зелёными и не ослаблены.

Источник — SPEC.md, «Критерии приёмки»:

AC-13. Полный прогон tests/ зелёный; тесты провайдеров, doctor, модели
шага роли и манифеста стека, существовавшие на main, проходят без правок,
ослабляющих их проверки.

Полный набор `tests/` здесь НЕ прогоняется (правило skills/
test-authoring.md: его гоняет CI и автогейт приёмки, а не отдельный тест
планки, которому пульт отводит 120 секунд). Прогоняется ровно то, что
критерий перечисляет поимённо, — файлы провайдеров, doctor, модели шага
роли и манифеста стека, отобранные глобом по ДЕРЕВУ main, а не по
сегодняшнему каталогу: набор, из которого файл убрали веткой, иначе
сузился бы сам собой.

Вторая половина критерия («без правок, ослабляющих их проверки»)
проверяется механически тем, что механически проверяемо: ни один тестовый
метод, существовавший на main в этих файлах, не исчез и не переименован.
Переписанное ВНУТРИ метода утверждение (`warn` -> `fail` требования 5 —
законное ужесточение) планка не запрещает: это предмет ревью по диффу.

Зелёный с рождения: перечисленные наборы проходят на сегодняшнем коде, и
ни один метод ещё не удалён — тест сохранения существующего поведения,
он краснеет ровно тогда, когда правка требований 4-5 ломает или
выкидывает чужой тест.
"""
import fnmatch
import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import gitcmd  # noqa: E402

#: Глобы файлов `tests/`, названных критерием: провайдеры, doctor,
#: модели шага роли, манифест стека.
PATTERNS = ("test_providers*.py", "test_doctor*.py", "test_runner*model*.py",
            "test_stack*.py", "test_models*.py")


def _main_test_files() -> list:
    """Пути `tests/…`, попадающие под глобы, В ДЕРЕВЕ main."""
    paths = gitcmd.ls_tree_files(_util.MAIN_SHA, "tests")
    if paths is None:
        raise AssertionError(f"дерево {_util.MAIN_SHA} не прочитано")
    return sorted(path for path in paths
                  if any(fnmatch.fnmatch(os.path.basename(path), pattern)
                         for pattern in PATTERNS))


class ExistingSuitesStayGreenTest(unittest.TestCase):

    def test_ac13_named_suites_pass_on_the_branch(self):
        """Файлы `tests/` провайдеров, doctor, модели шага роли и
        манифеста стека, существовавшие на main, прогоняются целиком и
        проходят без единого провала.

        Ловит мутацию: сужение окружения по провайдеру ломает соседний
        сценарий чужого набора — например, шаг роли на Claude перестаёт
        получать токен подписки (`tests/test_providers.py::
        StepEnvironmentTest`) или смок Codex теряет пункт про дом роли, —
        агрегированный результат перестанет быть успешным, и провалившийся
        метод будет назван в тексте.
        """
        files = _main_test_files()
        self.assertTrue(files, "глобы не нашли ни одного файла на main")

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        missing = []
        for path in files:
            if not (_util.TESTS_DIR / os.path.basename(path)).is_file():
                missing.append(path)
                continue
            suite.addTests(loader.loadTestsFromName(
                f"tests.{Path(path).stem}"))

        self.assertEqual(
            [], missing,
            "файл(ы) тестов, существовавшие на main, исчезли из ветки: "
            + ", ".join(missing))

        result = unittest.TextTestRunner(stream=io.StringIO(),
                                         verbosity=0).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            "наборы провайдеров/doctor/модели шага роли/манифеста стека "
            "не зелёные: провалы="
            + repr([str(case) for case, _ in result.failures])
            + "; ошибки=" + repr([str(case) for case, _ in result.errors]))

    def test_ac13_no_test_method_of_those_suites_disappeared(self):
        """Каждый тестовый метод, существовавший в этих файлах на main,
        существует в ветке под тем же именем.

        Ловит мутацию: тест, мешающий новой сборке окружения (скажем,
        `test_a_registered_secret_of_a_foreign_provider_is_still_a_yellow_
        line`), удалён или переименован вместо того, чтобы быть
        приведённым к новому — ужесточённому — поведению; `assertEqual`
        назовёт исчезнувшее имя.
        """
        gone = []
        for path in _main_test_files():
            local = _util.TESTS_DIR / os.path.basename(path)
            if not local.is_file():
                gone.append(f"{path}: файла нет")
                continue
            before = _util.test_method_names(_util.main_source(path))
            after = _util.test_method_names(local.read_text(encoding="utf-8"))
            gone.extend(f"{path}::{name}" for name in sorted(before - after))

        self.assertEqual(
            [], gone,
            "тестовый метод(ы) main исчезли из ветки — удаление теста это "
            "ослабление проверки (AC-13): " + ", ".join(gone))


if __name__ == "__main__":
    unittest.main()
