"""Приёмочный тест AC-4 задачи 01M3H3JW9XE1THF0HK8RESZ0CV.

AC-4: тесты покрывают перенос внутри пути, перенос после слова прозы
без склейки и строку без переноса; `tests/test_guard_zones.py`,
`tests/test_guard_path_mentions.py`, `tests/test_catalog_tz_path_check.py`,
`tests/test_catalog_zone_overlap.py`, `tests/test_spec_budget.py` и
`tests/test_budget_calibration_table.py` проходят без ослабления.

Перенос внутри пути покрыт планкой AC-1; здесь — два остальных
сценария критерия (проза и строка без переноса) как наблюдаемое
поведение разбора, наличие новых тестов в зоне `tests/` и состояние
шести названных наборов: они зелены и ни один их тест не исчез.

Красен до реализации: ветка задачи ещё не тронула ни одного файла в tests/ — сценарии переноса покрыть пока нечем.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402
from orchestrator import acceptance  # noqa: E402
from scripts import guard  # noqa: E402

NAMED_SUITES = (
    "tests/test_guard_zones.py",
    "tests/test_guard_path_mentions.py",
    "tests/test_catalog_tz_path_check.py",
    "tests/test_catalog_zone_overlap.py",
    "tests/test_spec_budget.py",
    "tests/test_budget_calibration_table.py",
)

# Строка зон без переноса и её разбор до задачи: поведение обязано
# остаться прежним.
FLAT_LINE = "scripts/guard.py, orchestrator/budget.py, tests/."
FLAT_ITEMS = {"scripts/guard.py", "orchestrator/budget.py", "tests/"}

# Перенос после слова прозы: путь стоит в начале следующей строки.
PROSE_LINE = "scripts/guard.py, задачи 01M3FQ2V77\n    docs/stack.md, tests/"


def declared_test_names(source: str) -> set[str]:
    """Имена тестовых функций в тексте python-файла."""
    return {line.split("def ", 1)[1].split("(", 1)[0]
            for line in source.splitlines()
            if line.strip().startswith("def test_")}


class TestsCoverWrapCasesTest(unittest.TestCase):

    def test_ac4_named_suites_are_green(self):
        """Шесть названных в критерии наборов проходят на дереве задачи.

        Прогон — тем же раннером и флагами, которыми пульт принимает
        тесты (`acceptance._pytest_command`), а не собственной сборкой
        команды.

        Ловит мутацию: склейка добавлена в `zone_items` без условия
        отступа/символа разрыва и ломает разбор «Зоны:» в
        `test_catalog_tz_path_check.py` — набор краснеет.
        """
        res = subprocess.run(acceptance._pytest_command(*NAMED_SUITES),
                             cwd=_util.REPO_ROOT, capture_output=True,
                             text=True, timeout=100)

        self.assertEqual(res.returncode, 0,
                         f"названные в AC-4 наборы красные:\n"
                         f"{(res.stdout + res.stderr)[-2000:]}")

    def test_ac4_named_suites_keep_their_tests(self):
        """Ни один тест названных наборов не исчез относительно общего
        предка ветки с main.

        Зелёный прогон достигается и удалением неудобного теста —
        критерий требует прохождения БЕЗ ослабления, поэтому имена
        тестов, существовавшие до задачи, обязаны остаться на месте
        (добавлять новые можно).

        Ловит мутацию: тест существующего набора, упавший на новой
        склейке, удалён или переименован вместо починки кода — имя
        пропадает из файла.
        """
        if _util.current_branch() == _util.config.MAIN_BRANCH:
            self.skipTest("рабочее дерево на main — сравнивать не с чем")

        for path in NAMED_SUITES:
            with self.subTest(набор=path):
                before = declared_test_names(_util.text_at_merge_base(path))
                now = declared_test_names(
                    (_util.REPO_ROOT / path).read_text(encoding="utf-8"))

                self.assertEqual(before - now, set())

    def test_ac4_branch_adds_tests_for_the_wrap(self):
        """Ветка задачи меняет зону `tests/`.

        Критерий требует покрытия трёх сценариев переноса тестами
        репозитория, а не одной только планкой приёмки: без правок в
        `tests/` покрывать их нечем.

        Ловит мутацию: разработчик правит `scripts/guard.py` и
        `orchestrator/budget.py` и на этом останавливается — тесты
        сценариев переноса в репозитории не появляются.
        """
        if _util.current_branch() == _util.config.MAIN_BRANCH:
            self.skipTest("рабочее дерево на main — диффить не с чем")

        changed = [p for p in _util.changed_paths() if p.startswith("tests/")]

        self.assertTrue(changed, "ветка не добавила тестов в tests/")

    def test_ac4_prose_wrap_is_not_joined(self):
        """Перенос после слова прозы путь не склеивает и не теряет.

        В строке зон перенос стоит после слова прозы, а путь начинается
        со следующей строки: склейка здесь запрещена — она приклеила бы
        букву слева от пути, и `PATH_MENTION` перестал бы его узнавать.

        Ловит мутацию: склейка снимает ЛЮБОЙ перенос с отступом
        (потеряно условие «после /, _ или -») — путь начала следующей
        строки слипается с прозой и исчезает из набора элементов.
        """
        items = guard.zone_items(PROSE_LINE)

        self.assertIn("docs/stack.md", items)
        for item in items:
            self.assertNotIn("01M3FQ2V77docs", item)

    def test_ac4_line_without_wrap_keeps_previous_items(self):
        """Строка зон без переноса разбирается ровно как до задачи.

        Три элемента через запятую с завершающей точкой предложения ТЗ
        дают тот же набор, что пульт получал по этой строке раньше.

        Ловит мутацию: склейка реализована срезкой пробельных символов
        по краям элементов заодно с переносом — завершающая точка ТЗ
        перестаёт сниматься и `tests/.` остаётся отдельным элементом.
        """
        self.assertEqual(guard.zone_items(FLAT_LINE), FLAT_ITEMS)


if __name__ == "__main__":
    unittest.main()
