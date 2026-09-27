"""Юнит-тесты ОДНОГО разбора строки зон (SPEC
01M3H3JW9XE1THF0HK8RESZ0CV, требования 1-4): `guard._zone_line_text`,
`guard.zone_line_items`, `guard.zone_items` и его потребитель
`budget.count_zone_paths`.

Планка задачи держит три сквозных критерия (элементы, число зон,
неизменность `catalog.py`). Здесь — свойства самого разбора, которых
критерии не называют: отсутствие отступа после переноса (так свёрстана
половина живых ТЗ пульта — `tasks/01M3FQ2Z2PY0E9T5F5WQ207NP5/TZ.md`),
порядок и состав перечня `zone_line_items` в отличие от множества
`zone_items`, идемпотентность приведения строки, синхронность двух копий
правила склейки (`guard._WRAPPED_PATH_BREAK` и остающаяся до следующей
задачи `catalog._TZ_WRAPPED_PATH_BREAK`) и само делегирование счёта зон
общему разбору — свойство, наблюдаемое только подменой
`guard.zone_line_items`, потому что на любом входе собственный разбор
`budget.count_zone_paths` по запятым давал то же число.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import budget, catalog  # noqa: E402
from scripts import guard  # noqa: E402

# Три точки разрыва правила: (голова до переноса, хвост следующей строки).
WRAPPED = (("orchestrator/", "budget.py"),
           ("orchestrator/zone_", "lock.py"),
           ("docs/reference/role-", "home.md"))

# Строка зон без переноса и её разбор — эталон «поведение не изменилось».
FLAT_LINE = "scripts/guard.py, orchestrator/budget.py, tests/."
FLAT_ITEMS = {"scripts/guard.py", "orchestrator/budget.py", "tests/"}


class ZoneLineTextTest(unittest.TestCase):

    def test_join_is_idempotent_and_survives_missing_indent(self):
        """Приведение строки зон снимает разрыв пути и при отступе
        следующей строки, и без него, а повторное приведение уже
        приведённой строки её не меняет.

        Отступ в правиле необязателен (`[ \\t]*`): живые ТЗ пульта рвут
        путь ровно на границе колонки, продолжая его с первой позиции
        следующей строки. Идемпотентность — то свойство, из-за которого
        предварительная склейка в `catalog._tz_zone_items` остаётся
        безвредной, пока её не убрали (требование 3).

        Ловит мутацию: отступ после переноса сделали обязательным
        (`\\n[ \\t]+`) — путь, продолженный без отступа, остаётся
        разорванным; либо приведение стало добавлять что-то к уже
        приведённой строке, и двойная склейка каталога начала расходиться
        с общим разбором.
        """
        for head, tail in WRAPPED:
            with self.subTest(разрыв=head[-1]):
                for indent in ("", " ", "    ", "\t"):
                    raw = f"scripts/guard.py, {head}\n{indent}{tail}, tests/."
                    once = guard._zone_line_text(raw)

                    self.assertEqual(once, f"scripts/guard.py, {head}{tail}, "
                                           f"tests/.")
                    self.assertEqual(guard._zone_line_text(once), once)

    def test_the_two_copies_of_the_wrap_rule_are_one_regex(self):
        """Правило склейки в `guard` и его копия в `catalog` — буквально
        одно выражение.

        Копия в `catalog._TZ_WRAPPED_PATH_BREAK` живёт до задачи, которая
        её снимет (файл занят зоной другой задачи в полёте). Пока копий
        две, разойтись они не имеют права: разное правило дало бы разное
        число зон у одного и того же ТЗ — в `new` одно, в калибровке
        бюджета другое.

        Ловит мутацию: одну из копий правят (сужают до `/`, добавляют
        символ разрыва), не тронув вторую — паттерны расходятся.
        """
        self.assertEqual(guard._WRAPPED_PATH_BREAK.pattern,
                         catalog._TZ_WRAPPED_PATH_BREAK.pattern)


class ZoneLineItemsTest(unittest.TestCase):

    def test_list_is_the_enumeration_only_in_the_order_written(self):
        """`zone_line_items` отдаёт только элементы перечня, в порядке
        записи, без кандидатов упоминаний путей из той же строки.

        Пояснение в скобках рядом с зоной — часть элемента, а не второй
        элемент: множество `zone_items` добавит упомянутый в нём путь
        (чтобы он считался классифицированным), перечень — нет, иначе
        калибровка бюджета считала бы зоны по прозе.

        Ловит мутацию: `zone_line_items` реализован через `zone_items`
        (или сам подмешивает `_path_mention_candidates`) — в перечне
        появляется `docs/stack.md`, которого в нём нет, и порядок
        элементов становится порядком обхода множества.
        """
        line = "scripts/guard.py (см. docs/stack.md), orchestrator/budget.py"

        self.assertEqual(guard.zone_line_items(line),
                         ["scripts/guard.py (см. docs/stack.md)",
                          "orchestrator/budget.py"])
        self.assertIn("docs/stack.md", guard.zone_items(line))

    def test_degenerate_inputs_give_the_previous_enumeration(self):
        """Вырожденные входы перечня: `None` и пустая строка — пустой
        список, завершающая точка предложения ТЗ снята, пустой элемент
        между запятыми отброшен, список frontmatter склеен запятой.

        Ловит мутацию: при выносе разбора в общую функцию потерян отсев
        пустых элементов или `rstrip(".")` — «a, , b» даёт три элемента, а
        `tests/.` остаётся отдельным от `tests/`.
        """
        self.assertEqual(guard.zone_line_items(None), [])
        self.assertEqual(guard.zone_line_items(""), [])
        self.assertEqual(guard.zone_line_items("a, , b"), ["a", "b"])
        self.assertEqual(guard.zone_line_items("tests/."), ["tests/"])
        self.assertEqual(guard.zone_line_items(["a/b.py", "tests/"]),
                         ["a/b.py", "tests/"])


class ZoneItemsWrapTest(unittest.TestCase):

    def test_wrapped_path_is_whole_and_the_fragment_is_not_a_zone(self):
        """Разорванный вёрсткой путь попадает в элементы целым, а
        обрывок-каталог до переноса самостоятельным элементом не
        становится.

        Обрывок опасен вдвойне: `orchestrator/` как зона накрывает почти
        любую задачу пульта (ложное пересечение замка зон), а настоящий
        путь при этом теряется целиком.

        Ловит мутацию: склейка применена к перечню, но не к тексту, из
        которого берутся кандидаты `PATH_MENTION` (или наоборот) — целый
        путь в множестве есть, а обрывок остаётся рядом с ним.
        """
        for head, tail in WRAPPED:
            with self.subTest(разрыв=head[-1]):
                items = guard.zone_items(f"{head}\n{tail}, tests/.")

                self.assertEqual(items, {head + tail, "tests/"})

    def test_prose_wrap_keeps_the_path_that_follows_it(self):
        """Перенос после слова прозы не склеивается: путь, стоящий в
        начале следующей строки, остаётся элементом и не слипается с
        текстом слева.

        `guard.PATH_MENTION` запрещает букву/цифру слева от кандидата —
        приклеенный к прозе путь перестал бы узнаваться вовсе.

        Ловит мутацию: у правила склейки потеряно условие «после /, _ или
        -» (снимается любой перенос с отступом) — `docs/stack.md`
        исчезает из элементов.
        """
        items = guard.zone_items("orchestrator/pull.py, задачи 01M3FQ2V77\n"
                                 "    docs/stack.md, tests/.")

        self.assertEqual(items, {"orchestrator/pull.py", "docs/stack.md",
                                 "tests/",
                                 "задачи 01M3FQ2V77\n    docs/stack.md"})

    def test_line_without_a_wrap_keeps_the_previous_items(self):
        """Строка зон без переноса разбирается ровно как до задачи.

        Ловит мутацию: при выносе разбора в общие `_zone_line_text`/
        `zone_line_items` потеряна обрезка элемента — без `strip()`
        элементы после запятой приходят с ведущим пробелом
        (` orchestrator/budget.py`), без `rstrip(".")` последний элемент
        остаётся с точкой предложения ТЗ (`tests/.`); в обоих случаях
        множество расходится с дозадачным.
        """
        self.assertEqual(guard.zone_items(FLAT_LINE), FLAT_ITEMS)


class CountZonePathsTest(unittest.TestCase):

    def test_wrapped_line_counts_as_the_same_line_without_the_wrap(self):
        """Число зон строки с разрывом пути равно числу зон той же строки
        без разрыва — и не зависит от того, есть ли отступ после переноса.

        Ловит мутацию: перенос внутри пути обработан не склейкой ДО
        разбора, а делением перечня ещё и по переносам строк
        (`re.split(r"[,\\n]", …)` вместо `split(",")` над приведённой
        строкой) — разорванный путь даёт две зоны вместо одной, и
        калибровка бюджета считает зоны по вёрстке ТЗ (проверено
        подменой: счёт становится 4 против 3 на всех трёх точках разрыва).

        Заявку «`count_zone_paths` вернули на собственный разбор по
        запятым» этот тест НЕ несёт: число элементов после деления по
        запятым к склейке безразлично (правило снимает только пробельный
        хвост после `/`, `_`, `-` и никогда не запятую), различающего
        входа не существует. Делегирование общему разбору — требование 2 —
        держит соседний
        `test_count_zone_paths_delegates_to_the_shared_enumeration`.
        """
        for head, tail in WRAPPED:
            with self.subTest(разрыв=head[-1]):
                flat = f"scripts/guard.py, {head}{tail}, tests/."
                for indent in ("", "    ", "\t"):
                    wrapped = (f"scripts/guard.py, {head}\n{indent}{tail}, "
                               f"tests/.")

                    self.assertEqual(budget.count_zone_paths(wrapped), 3)
                    self.assertEqual(budget.count_zone_paths(wrapped),
                                     budget.count_zone_paths(flat))

    def test_count_zone_paths_delegates_to_the_shared_enumeration(self):
        """Счёт зон идёт ЧЕРЕЗ общий разбор строки зон: результат —
        длина `guard.zone_line_items` от того же текста, своего разбора у
        `budget.count_zone_paths` нет (требование 2).

        Наблюдаемо это только подменой: на любом входе собственный разбор
        по запятым даёт то же число, что общий (различающего входа не
        существует — см. соседний тест), и без подмены требование «тот же
        разбор» остаётся без тестового прикрытия вовсе.

        Ловит мутацию: `count_zone_paths` вернулся на собственное деление
        по запятым (подменённый перечень не виден — счёт 2 вместо 3) либо
        пошёл через `guard.zone_items` (к перечню добавляются кандидаты
        упоминаний путей из той же строки — счёт 5 вместо 3).
        """
        line = "scripts/guard.py, tests/"

        with mock.patch.object(guard, "zone_line_items",
                               return_value=["один", "два", "три"]) as items:
            self.assertEqual(budget.count_zone_paths(line), 3)

        items.assert_called_once_with(line)

    def test_path_mentioned_in_a_note_does_not_add_a_zone(self):
        """Путь, упомянутый в пояснении рядом с зоной, число зон не
        увеличивает — ни в плоской строке, ни когда пояснение разорвано
        переносом.

        Ловит мутацию: счёт переписан на `len(guard.zone_items(text))` —
        кандидаты упоминаний путей попадают в счёт, две зоны становятся
        четырьмя, и ориентир калибровки завышается на каждой строке зон с
        пояснением.
        """
        self.assertEqual(
            budget.count_zone_paths("scripts/guard.py (см. docs/stack.md), "
                                    "tests/"), 2)
        self.assertEqual(
            budget.count_zone_paths("scripts/guard.py (см. docs/\n"
                                    "    stack.md), tests/"), 2)

    def test_degenerate_inputs_keep_their_previous_counts(self):
        """Вырожденные входы считаются ровно как до задачи: `None` и
        пустая строка — ноль, завершающая точка предложения ТЗ зону не
        добавляет, пустой элемент между запятыми не считается.

        Ловит мутацию: `count_zone_paths` перестал принимать `None`
        (падает трейсбеком вместо нуля) — гейт SPEC ронял бы approve на
        SPEC без поля `zones:`.
        """
        for text, expected in ((None, 0), ("", 0), ("tests/", 1),
                               ("scripts/guard.py.", 1), ("a, , b", 2),
                               (FLAT_LINE, 3)):
            with self.subTest(строка=text):
                self.assertEqual(budget.count_zone_paths(text), expected)


if __name__ == "__main__":
    unittest.main()
