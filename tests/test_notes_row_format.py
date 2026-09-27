"""Юнит-тесты единого формата строки бэклога (`orchestrator/notes.py`,
tasks/01M3HST4SGX0SPKAGNHVY7DWHM, требования 1-8): обе формы строки,
нормализация приоритета и даты по шапке раздела, дописка состояния с
разделителем, `--state` как второе имя `--append`.

Чистыми функциями (`_apply_insert`/`_apply_append`/`_apply_set_priority`)
без git: предмет здесь — преобразование текста документа, и настоящий
origin к нему ничего не добавляет. Сквозной путь команды против настоящего
git — `tasks/01M3HST4SGX0SPKAGNHVY7DWHM/acceptance_tests/` (материализуются
только на время задачи); постоянный регресс — здесь.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import notes  # noqa: E402
from tests.sandbox import SchemaTmpRootTest  # noqa: E402

# Пятиколоночная «Копилка» с колонками «П» и «Дата» — как на вершине
# origin/main (SPEC, «Материалы»).
BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где | Состояние |
|---|---|---|---|---|
| 1 | 01.01 | СОСТОЯНИЕЕСТЬ | orchestrator/x.py | прежнее состояние |
| 2 | 01.01 | СОСТОЯНИЕПУСТО | orchestrator/y.py |  |
| 3 | 01.01 | СОСТОЯНИЕПРОЧЕРК | orchestrator/z.py | — |
"""

# Раздел БЕЗ колонки «П», но С колонкой «Дата»: нормализация приоритета
# такому разделу не полагается (требование 5), нормализация даты — да.
NO_PRIORITY_TEXT = """## Бэклог

| Кандидат | Дата |
|---|---|
| Кандидат A | 01.01 |
"""

# Раздел С колонкой «П», но БЕЗ колонки «Дата»: дата в ячейке другой
# колонки не трогается (требование 6 привязан к заголовку, не к виду
# содержимого).
NO_DATE_TEXT = """## Очередь Оператора

| П | Действие | Условие |
|---|---|---|
| 1 | Действие A | сразу |
"""

ROW_CELLS = ("2", "27.09", "текст", "где", "состояние")
FRAMED = "| " + " | ".join(ROW_CELLS) + " |"
BARE = " | ".join(ROW_CELLS)


def inserted_row(text: str, source: str = BACKLOG_TEXT,
                 section: str = "копилка", marker: str = "текст") -> str:
    """Строка, которую `_apply_insert` вставила в документ."""
    new_text, _section_key = notes._apply_insert(source, section, text)
    rows = [line for line in new_text.split("\n")
            if marker in line and line.strip().startswith("|")]
    assert len(rows) == 1, rows
    return rows[0]


def cells(line: str) -> list:
    """Ячейки строки — собственным разбором, не `notes._row_cells`:
    проверять нормализацию инструментом самой реализации значило бы не
    проверять её вовсе."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


class RowFormsTest(unittest.TestCase):

    def test_framed_and_bare_text_give_the_same_row(self):
        """Текст с обрамляющими чертами и тот же текст без них дают
        байт-в-байт одну и ту же строку таблицы — и это форма
        `| ячейка | … |`, которую документ несёт сегодня (требование 1).

        Ловит мутацию: обрамление снимается безусловным `text.strip("|")`
        либо не снимается вовсе — обрамлённая форма тогда либо отказывает
        по числу колонок, либо даёт строку с пустыми крайними ячейками, и
        равенство двух строк ломается.
        """
        self.assertEqual(inserted_row(FRAMED), inserted_row(BARE))
        self.assertEqual(inserted_row(FRAMED), FRAMED)

    def test_single_leading_pipe_is_not_treated_as_framing(self):
        """Черта только в начале (обрамления нет) — ячейки считаются как
        есть: `| 2 | 27.09 | текст | где | состояние` даёт ШЕСТЬ ячеек
        против пятиколоночной шапки, то есть отказ (требование 1: черты
        снимаются, только когда текст И начинается, И заканчивается ими).

        Ловит мутацию: снятие обрамления сделано через `strip("|")` или
        `lstrip("|")` — односторонняя черта тогда молча съедается, и
        строка с лишней пустой ячейкой уезжает в документ.
        """
        with self.assertRaises(SystemExit) as cm:
            notes._apply_insert(BACKLOG_TEXT, "копилка", f"| {BARE}")
        self.assertIn("5", str(cm.exception))

    def test_cell_count_is_checked_after_unframing(self):
        """Обрамлённая строка из трёх ячеек против пятиколоночной шапки —
        отказ, называющий ожидаемое число колонок (требование 2).

        Ловит мутацию: число ячеек сверяется с шапкой ДО снятия
        обрамления — три ячейки плюс два пустых обрамляющих поля дают
        ровно пять, и строка молча вставляется вместо отказа.
        """
        with self.assertRaises(SystemExit) as cm:
            notes._apply_insert(BACKLOG_TEXT, "копилка", "| 1 | 2 | 3 |")
        self.assertIn("5", str(cm.exception))


class InsertedPriorityTest(unittest.TestCase):

    def test_letter_and_digit_forms_both_give_the_digit(self):
        """Ячейка приоритета «П2», «п2», « П 2 » и «2» дают в документе
        «2» (требования 3, 5).

        Ловит мутацию: нормализация применена только к пути
        `--set-priority` и забыта у вставки строки — буква приезжает в
        документ как есть.
        """
        for value in ("П2", "п2", " П 2 ", "2"):
            with self.subTest(value=value):
                row = inserted_row(
                    f"{value} | 27.09 | текст | где | состояние")
                self.assertEqual(cells(row)[0], "2", row)

    def test_unrecognized_priority_refuses_naming_a_valid_form(self):
        """«высокий», «5», «0», «П7» и пустая ячейка — отказ, текст
        которого несёт пример допустимой формы (требование 4); диапазон
        1..4 не расширяется вместе с приёмом формы «П<цифра>».

        Ловит мутацию: разбор стал `int(text.lstrip("Пп"))` без сверки
        границ — «5» и «П7» проходят вместо отказа; либо пример формы из
        текста отказа убран (`assertRegex(…, r"[1-4]")` проходил и на
        прежнем тексте «вне диапазона 1..4», замечание R1-F5 ревью итерации
        1) — тест красен на отсутствии `PRIORITY_FORM_EXAMPLE`.
        """
        for value in ("высокий", "5", "0", "П7", ""):
            with self.subTest(value=value):
                with self.assertRaises(SystemExit) as cm:
                    notes._apply_insert(
                        BACKLOG_TEXT, "копилка",
                        f"{value} | 27.09 | текст | где | состояние")
                self.assertIn(notes.PRIORITY_FORM_EXAMPLE, str(cm.exception))

    def test_section_without_priority_column_is_not_normalized(self):
        """Раздел без колонки «П» нормализации приоритета не получает:
        «высокий» в первой колонке «Бэклога» — не отказ, а обычный текст
        (требование 5, «раздел без такой колонки нормализации не
        получает»); дата в колонке «Дата» того же раздела при этом
        нормализуется.

        Ловит мутацию: колонка приоритета определяется НОМЕРОМ (нулевой
        ячейкой), а не заголовком шапки — тест красен на `SystemExit`
        вместо вставленной строки.
        """
        row = inserted_row("высокий | 22.09.2026", NO_PRIORITY_TEXT, "бэклог",
                           "высокий")
        self.assertEqual(cells(row), ["высокий", "22.09"], row)


class InsertedDateTest(unittest.TestCase):

    def test_year_is_dropped_short_form_and_non_dates_survive(self):
        """Ячейка даты «22.09.2026» теряет год, «27.09» не меняется,
        «сразу» (датой не является ни в одной форме) остаётся как есть и
        отказом не считается (требование 6).

        Ловит мутацию: ячейка разбирается строго как «ДД.ММ.ГГГГ»
        (`cell.split(".")` с обращением к третьему элементу) — уже
        краткая форма теряет содержимое либо роняет команду; отказ на
        не-дату красит третий случай.
        """
        for given, expected in (("22.09.2026", "22.09"), ("27.09", "27.09"),
                                ("22.9.26", "22.9"), ("сразу", "сразу")):
            with self.subTest(given=given):
                row = inserted_row(
                    f"2 | {given} | текст | где | состояние")
                self.assertEqual(cells(row)[1], expected, row)

    def test_date_shaped_cell_of_another_column_is_untouched(self):
        """Дата с годом в колонке, чей заголовок не «Дата», не трогается:
        раздел «Очередь Оператора» колонки «Дата» не несёт вовсе
        (требование 6).

        Ловит мутацию: нормализация даты применяется к ЛЮБОЙ ячейке,
        похожей на дату, вместо ячейки названной колонки — «22.09.2026» в
        колонке «Действие» теряет год.
        """
        row = inserted_row("П3 | 22.09.2026 | сразу", NO_DATE_TEXT, "очередь",
                           "22.09.2026")
        self.assertEqual(cells(row), ["3", "22.09.2026", "сразу"], row)


class SetPriorityTest(unittest.TestCase):

    def test_both_forms_write_the_digit(self):
        """`--set-priority` с «П2» и с «2» — в документе «2» (требование
        5, второй путь нормализации).

        Ловит мутацию: ведущая «П» снимается при ПРОВЕРКЕ, а в файл
        пишется исходный текст ячейки (`cells[col] = text` вместо
        нормализованного значения).
        """
        for value in ("П2", "2"):
            with self.subTest(value=value):
                new_text, _key = notes._apply_set_priority(
                    BACKLOG_TEXT, "СОСТОЯНИЕЕСТЬ", value)
                row = [line for line in new_text.split("\n")
                       if "СОСТОЯНИЕЕСТЬ" in line][0]
                self.assertEqual(cells(row)[0], "2", row)

    def test_range_is_not_widened_by_the_letter_form(self):
        """«5», «П7», «0» и «высокий» по-прежнему отказ с примером формы.

        Ловит мутацию: сверка границ снята вместе с заменой `int(text)` на
        разбор формы «П<цифра>» — значения вне 1..4 проходят; либо пример
        формы из текста отказа убран на этом втором пути нормализации
        (замечание R1-F5 ревью итерации 1).
        """
        for value in ("5", "П7", "0", "высокий"):
            with self.subTest(value=value):
                with self.assertRaises(SystemExit) as cm:
                    notes._apply_set_priority(BACKLOG_TEXT, "СОСТОЯНИЕЕСТЬ",
                                              value)
                self.assertIn(notes.PRIORITY_FORM_EXAMPLE, str(cm.exception))

    def test_section_without_priority_column_refuses_instead_of_cell_zero(self):
        """Раздел без колонки «П» — именованный отказ «менять негде», а не
        молчаливая правка нулевой ячейки (требование 5).

        Ловит мутацию: колонка приоритета по-прежнему `cells[0]` — вместо
        отказа затирается колонка «Кандидат».
        """
        with self.assertRaises(SystemExit) as cm:
            notes._apply_set_priority(NO_PRIORITY_TEXT, "Кандидат A", "2")
        self.assertIn(notes.PRIORITY_HEADER, str(cm.exception))


class StateAppendTest(unittest.TestCase):

    FILLED = re.compile(r"(?P<old>.*) — (?P<stamp>\d\d\.\d\d): (?P<new>.*)")
    EMPTY = re.compile(r"(?P<stamp>\d\d\.\d\d): (?P<new>.*)")

    def appended_cell(self, key: str, text: str) -> str:
        new_text, _key = notes._apply_append(BACKLOG_TEXT, key, text)
        row = [line for line in new_text.split("\n") if key in line][0]
        return cells(row)[-1]

    def test_filled_cell_keeps_old_text_and_gets_dated_separator(self):
        """Дописка к непустой ячейке даёт `<прежний текст> — <ДД.ММ>:
        <новый текст>`: прежний текст цел, новый отделён разделителем с
        текущей датой пульта (требование 7).

        Ловит мутацию: прежний текст затёрт (дописка реализована через
        путь `--set-state`, заменяющий ячейку целиком) либо разделителя
        нет вовсе (прежнее склеивание одним пробелом) — `fullmatch` не
        проходит или группа «old» не совпадает.
        """
        cell = self.appended_cell("СОСТОЯНИЕЕСТЬ", "ДОПИСКА")

        match = self.FILLED.fullmatch(cell)
        self.assertIsNotNone(match, cell)
        self.assertEqual(match.group("old"), "прежнее состояние", cell)
        self.assertEqual(match.group("new"), "ДОПИСКА", cell)
        self.assertEqual(match.group("stamp"), notes._today_stamp(), cell)

    def test_empty_and_dash_cells_get_no_leading_separator(self):
        """Дописка к пробельной ячейке и к ячейке с прочерком «—» даёт
        `<ДД.ММ>: <новый текст>` без ведущего разделителя (требование 7).

        Ловит мутацию: пустой признан только пробельный случай, прочерк
        «—» трактуется как обычный текст — ячейка получает `— — <ДД.ММ>:
        …`, и `fullmatch` без ведущего разделителя её не принимает.
        """
        for key in ("СОСТОЯНИЕПУСТО", "СОСТОЯНИЕПРОЧЕРК"):
            with self.subTest(key=key):
                cell = self.appended_cell(key, "ДОПИСКА")

                match = self.EMPTY.fullmatch(cell)
                self.assertIsNotNone(match, cell)
                self.assertEqual(match.group("new"), "ДОПИСКА", cell)

    def test_second_append_keeps_the_first_one_whole(self):
        """Вторая дописка не съедает первую: обе даты и оба текста в
        ячейке (требование 7 — «прежний текст ячейки сохраняется
        целиком», в том числе уже дописанный).

        Ловит мутацию: разделитель ставится, но прежний текст обрезается
        по первому разделителю (попытка «нормализовать» ячейку) — первая
        дописка теряется.
        """
        once, _key = notes._apply_append(BACKLOG_TEXT, "СОСТОЯНИЕПУСТО",
                                         "ПЕРВАЯ")
        twice, _key = notes._apply_append(once, "СОСТОЯНИЕПУСТО", "ВТОРАЯ")

        cell = cells([line for line in twice.split("\n")
                      if "СОСТОЯНИЕПУСТО" in line][0])[-1]
        self.assertIn("ПЕРВАЯ", cell)
        self.assertIn("ВТОРАЯ", cell)


class StateFlagAliasTest(SchemaTmpRootTest):
    """`--state` — второе имя `--append` (требование 8). Схема БД заведена:
    `cmd_note` читает `merge_locks`/`tasks` на каждый вызов (окно тишины),
    а сам `_run` здесь подменён — до git дело не доходит."""

    def test_state_and_append_build_the_same_request(self):
        """`note --state <ключ> --text …` и `note --append <ключ> --text …`
        строят одну и ту же запись вида `append`.

        Ловит мутацию: `--state` принят отдельным флагом и ведёт в свой
        путь (например в `set-state`, заменяющий ячейку целиком) — записи
        перестают совпадать.
        """
        seen = []
        with mock.patch.object(notes, "_run", side_effect=seen.append):
            notes.cmd_note(["--state", "КЛЮЧ", "--text", "текст"])
            notes.cmd_note(["--append", "КЛЮЧ", "--text", "текст"])

        self.assertEqual(seen[0], seen[1], seen)
        self.assertEqual(seen[0]["kind"], "append", seen)

    def test_state_without_text_refuses_naming_the_flag_that_was_used(self):
        """`--state` без `--text` — отказ, называющий `--state`, а не
        соседний `--append`.

        Ловит мутацию: текст отказа захардкожен на `--append` — Оператор
        читает про флаг, которым не пользовался.
        """
        with self.assertRaises(SystemExit) as cm:
            notes.cmd_note(["--state", "КЛЮЧ"])
        self.assertIn("--state", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
