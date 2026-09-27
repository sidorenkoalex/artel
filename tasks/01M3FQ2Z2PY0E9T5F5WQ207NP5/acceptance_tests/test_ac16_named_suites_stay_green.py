"""AC-16 — 01M3FQ2Z2PY0E9T5F5WQ207NP5: названные наборы `tests/` зелёные,
ни один тест не удалён и не ослаблен, живой CLI провайдера не запускается.

Источник — SPEC.md, «Критерии приёмки»:

AC-16. `tests/test_canary.py`, `tests/test_doctor_canary_pool.py`,
`tests/test_models_doctor.py`, `tests/test_store_schema_migration_parity.py`
зелёные, ни один существующий тест не удалён и не ослаблен; ни один тест
задачи не запускает живой CLI провайдера.

Полный набор `tests/` здесь НЕ прогоняется (правило skills/
test-authoring.md: его гоняют CI и автогейт приёмки) — только четыре файла,
названные критерием поимённо.

«Не удалён и не ослаблен» проверяется тем, что проверяемо механически: ни
один тестовый метод, существовавший в этих файлах на main, не исчез и не
переименован. Переписанное ВНУТРИ метода утверждение планка не запрещает —
это предмет ревью по диффу.

«Живой CLI провайдера не запускается» проверяется по исходникам: ни
названные наборы, ни новые файлы `tests/` этой задачи не спавнят процесс,
нулевой элемент argv которого — имя CLI провайдера, и не зовут живой смок.
Мок, заглушка, перечисление имён провайдеров и разбор ЛОГА
`codex exec --json` под это правило не подпадают — они и не запускают
ничего.

Зелёный с рождения: четыре набора проходят на сегодняшнем коде, ни один
метод ещё не удалён и ни один тест живой CLI не зовёт — тест сохранения
существующего поведения; он краснеет ровно тогда, когда правка задачи
ломает, выкидывает чужой тест или заводит тест, платящий живой попыткой
провайдера.
"""
import io
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

#: Наборы, названные критерием поимённо.
NAMED_SUITES = ("test_canary.py", "test_doctor_canary_pool.py",
                "test_models_doctor.py",
                "test_store_schema_migration_parity.py")

#: Запуск живого CLI провайдера: спавн процесса, нулевой элемент argv
#: которого — имя CLI провайдера, и вызов живого смока. Перечисление имён
#: провайдеров в списке (без спавна) сюда не подпадает — оно ничего не
#: запускает.
LIVE_CLI_PATTERNS = (
    re.compile(r"""(?:subprocess\.(?:run|Popen|call|check_output)"""
               r"""|spawn_agent)\(\s*\[\s*["'](?:claude|codex)["']"""),
    re.compile(r"""(?:doctor\.)?(?:live_smoke|_live_smoke_run)\("""),
)


def _new_test_files() -> list:
    """Файлы `tests/*.py`, которых на main не было — тесты, заведённые
    этой задачей."""
    before = {Path(path).name for path in _util.main_tree_files("tests")}
    return sorted(path for path in _util.TESTS_DIR.glob("test_*.py")
                  if path.name not in before)


class NamedSuitesStayGreenTest(unittest.TestCase):

    def test_ac16_named_suites_pass_on_the_branch(self):
        """Четыре названных критерием набора `tests/` прогоняются целиком и
        проходят без единого провала.

        Ловит мутацию: колонка имени набора добавлена в таблицы метрик
        `add_column`'ом без переноса ключа — `tests/test_canary.py`
        (`CanaryBaselineStoreRoundtripTest`) читает бейзлайн по прежнему
        ключу и краснеет; агрегированный результат перестанет быть
        успешным, и провалившийся метод будет назван в тексте.
        """
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        missing = []
        for name in NAMED_SUITES:
            if not (_util.TESTS_DIR / name).is_file():
                missing.append(name)
                continue
            suite.addTests(loader.loadTestsFromName(f"tests.{Path(name).stem}"))

        self.assertEqual([], missing,
                         "файл(ы) названных наборов исчезли из ветки: "
                         + ", ".join(missing))

        result = unittest.TextTestRunner(stream=io.StringIO(),
                                         verbosity=0).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            "названные наборы не зелёные: провалы="
            + repr([str(case) for case, _ in result.failures])
            + "; ошибки=" + repr([str(case) for case, _ in result.errors]))

    def test_ac16_no_test_method_of_those_suites_disappeared(self):
        """Каждый тестовый метод, существовавший в этих файлах на main,
        существует в ветке под тем же именем.

        Ловит мутацию: тест, мешающий новой схеме или новому ключу
        бейзлайна (например `test_second_write_overwrites_the_same_title`),
        удалён или переименован вместо приведения к новому поведению —
        `assertEqual` назовёт исчезнувшее имя.
        """
        gone = []
        for name in NAMED_SUITES:
            local = _util.TESTS_DIR / name
            if not local.is_file():
                gone.append(f"{name}: файла нет")
                continue
            before = _util.unittest_method_names(_util.main_source(f"tests/{name}"))
            after = _util.unittest_method_names(local.read_text(encoding="utf-8"))
            gone.extend(f"{name}::{method}" for method in sorted(before - after))

        self.assertEqual(
            [], gone,
            "тестовый метод(ы) main исчезли из ветки — удаление теста это "
            "ослабление проверки (AC-16): " + ", ".join(gone))

    def test_ac16_no_test_of_the_task_launches_a_live_provider_cli(self):
        """Ни названные наборы, ни новые файлы `tests/` этой задачи не
        собирают argv с именем CLI провайдера нулевым элементом и не зовут
        живой смок.

        Ловит мутацию: провайдер роли в клоне проверяется «по-настоящему» —
        тест зовёт `codex`/`claude` живьём, чтобы убедиться, что шаг
        стартует; каждый прогон набора тестов платил бы попытками
        подписки, а на машине без второго CLI набор был бы красным.
        """
        offenders = []
        files = [_util.TESTS_DIR / name for name in NAMED_SUITES]
        files.extend(_new_test_files())
        for path in files:
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8")
            for pattern in LIVE_CLI_PATTERNS:
                match = pattern.search(source)
                if match is not None:
                    line = source[:match.start()].count("\n") + 1
                    offenders.append(f"{path.name}:{line}: {match.group(0)}")

        self.assertEqual([], offenders,
                         "тест(ы) запускают живой CLI провайдера: "
                         + ", ".join(offenders))


if __name__ == "__main__":
    unittest.main()
