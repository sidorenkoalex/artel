"""AC-4: ни один изменённый файл `tests/` не потерял тестовых методов
относительно главной ветки и не несёт выключенных тестов.

«Изменённый файл» и «тестовый метод» считаются тем же кодом, каким их
считает сам пульт: точка расхождения с главной веткой —
`gitcmd.diff_base` (origin/<main>, если ref заведён, иначе локальная
главная ветка), разбор методов и маркеров пропуска —
`scripts/guard.py::qualified_test_methods`/`test_skip_markers` (там же
живёт перечень `skip`/`skipIf`/`skipUnless`/`expectedFailure`, названный
критерием). Своего разбора планка не заводит: расхождение двух счётчиков
иначе обнаруживалось бы разными числами в разных местах.

Зелёный с рождения: до правки разработчика ни один файл `tests/` от
главной ветки не отличается, перечень изменённых пуст, и проверять
нечего. Тест сторожит саму правку — он становится содержательным ровно
в тот момент, когда разработчик трогает `tests/`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from scripts import guard  # noqa: E402


class TestMethodsNotWeakenedTest(unittest.TestCase):
    """Сверка изменённых файлов `tests/` с главной веткой."""

    def test_ac4_changed_tests_files_keep_methods_and_carry_no_skips(self):
        """Для каждого файла `tests/`, чей текст отличается от текста в
        точке расхождения с главной веткой: число тестовых методов не
        меньше прежнего, и ни один тест файла не выключен декоратором
        пропуска/ожидаемого провала или вызовом пропуска в теле.

        Ловит мутацию: сценарий, мешающий покрытию ярусов (тот самый
        `test_missing_unused_tool_gives_no_line_at_all`, покрасневший
        27.09), выключается `@unittest.skip` или удаляется целиком —
        планка задачи зеленеет, а свойство «строка инструмента печатается
        по востребованности, а не по реестру провайдеров» больше никем не
        проверяется.
        """
        base = _util.main_base_ref()
        self.assertTrue(
            base, "git не ответил на запрос точки расхождения ветки задачи с "
                  "главной веткой — сверить число тестов не с чем")

        for rel in _util.changed_tests_files(base):
            with self.subTest(file=rel):
                before = guard.qualified_test_methods(_util.text_at(base, rel))
                head_source = _util.text_on_disk(rel)
                after = guard.qualified_test_methods(head_source)

                self.assertGreaterEqual(
                    len(after), len(before),
                    f"{rel}: было {len(before)} тестовых методов, стало "
                    f"{len(after)}; исчезли: "
                    f"{sorted(set(before) - set(after))}")
                self.assertEqual(
                    guard.test_skip_markers(head_source), {},
                    f"{rel}: тесты выключены пропуском")


if __name__ == "__main__":
    unittest.main()