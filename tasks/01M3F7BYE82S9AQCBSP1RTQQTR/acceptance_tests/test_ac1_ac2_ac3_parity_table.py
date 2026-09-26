"""AC-1, AC-2, AC-3 — 01M3F7BYE82S9AQCBSP1RTQQTR: таблица паритета
безопасности роли в `docs/stack.md`.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `docs/stack.md` несёт таблицу паритета безопасности роли со строкой
на каждый из восьми запретов перечня требования 1.
AC-2. Каждая строка таблицы называет, чем запрет закрыт у роли на Codex,
и несёт либо имя подтверждающей проверки doctor, либо пометку «не закрыт».
AC-3. Каждая строка с пометкой «не закрыт» называет компенсирующий гейт
пульта после шага либо явно помечена принятым риском.

Формулировки ячеек планка не диктует: запрет опознаётся широким набором
альтернатив (`_util.PROHIBITIONS`), средство закрытия — четвёркой из
самого AC-2 (`_util.CLOSURE_MEANS`), а имя проверки doctor сверяется с
ЖИВЫМ набором имён, собранным из `orchestrator/doctor/`
(`_util.doctor_check_names`), а не со списком, переписанным сюда руками.

Красен до реализации: markdown-таблиц в docs/stack.md сегодня нет ни
одной (весь документ — проза) — `parity_table()` отдаёт пустой список, и
первый же assert падает на всех восьми ненайденных запретах.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class ParityTableTest(unittest.TestCase):

    def setUp(self):
        self.text = _util.stack_md_text()
        self.rows = _util.parity_table(self.text)

    def test_ac1_table_carries_a_row_for_each_of_the_eight_prohibitions(self):
        """В `docs/stack.md` есть markdown-таблица, в строках которой
        опознаются все восемь запретов перечня требования 1: файлы вне
        рабочего каталога, сеть, Связка ключей и секреты, инструменты и
        MCP, хуки, чтение user-слоя Оператора, пул канарейки, посторонние
        файлы и защищённые пути.

        Ловит мутацию: таблица написана «по памяти» и теряет запрет,
        которого у Claude не видно с первого взгляда (хуки или посторонние
        файлы и защищённые пути), — `missing_prohibitions()` вернёт его
        имя, и `assertEqual([], …)` покраснеет с этим именем в тексте.
        """
        self.assertTrue(
            self.rows,
            "в docs/stack.md нет ни одной markdown-таблицы — таблица "
            "паритета безопасности роли обязательна (AC-1)")
        self.assertEqual(
            [], _util.missing_prohibitions(self.rows),
            "в таблице паритета нет строки на запрет(ы): "
            f"{_util.missing_prohibitions(self.rows)}; найдено строк: "
            f"{len(self.rows)}")

    def test_ac2_each_row_names_the_codex_closure_and_a_doctor_check_or_is_open(self):
        """Каждая строка таблицы паритета называет средство, которым
        запрет закрыт у роли на Codex (песочница, конфигурация дома роли,
        флаги команды шага, гейт пульта), и несёт либо имя живой проверки
        doctor, либо пометку «не закрыт».

        Ловит мутацию: строка о запрете, который у Codex ничем не закрыт,
        заполняется прочерком или обещанием «закрыто песочницей» без
        подтверждающей проверки — ни имени проверки, ни честной пометки
        «не закрыт» в строке нет, и `assertEqual([], …)` назовёт эту
        строку.
        """
        self.assertTrue(self.rows, "таблицы паритета в docs/stack.md нет")
        known = _util.doctor_check_names()

        no_closure, no_evidence = [], []
        for row in self.rows:
            lowered = row.lower()
            if not any(mean in lowered for mean in _util.CLOSURE_MEANS):
                no_closure.append(row.strip())
            if not _util.checks_named_in(row, known) and not _util.row_is_open(row):
                no_evidence.append(row.strip())

        self.assertEqual(
            [], no_closure,
            "строка(и) таблицы не называют, чем запрет закрыт у роли на "
            "Codex (песочница/дом роли/флаги команды шага/гейт пульта): "
            + " || ".join(no_closure))
        self.assertEqual(
            [], no_evidence,
            "строка(и) таблицы не несут ни имени живой проверки doctor, ни "
            "пометки «не закрыт»: " + " || ".join(no_evidence))

    def test_ac3_open_rows_name_a_compensating_gate_or_an_accepted_risk(self):
        """Каждая строка с пометкой «не закрыт» называет компенсирующий
        гейт пульта после шага либо явно помечена принятым риском.

        Ловит мутацию: честная пометка «не закрыт» ставится и на этом
        разговор заканчивается — Оператор читает таблицу, видит дыру и не
        видит, чем она держится; строка без слова «гейт» и без слова
        «риск» попадёт в список, и `assertEqual([], …)` покраснеет.
        """
        self.assertTrue(self.rows, "таблицы паритета в docs/stack.md нет")

        open_rows = [row for row in self.rows if _util.row_is_open(row)]
        uncompensated = [
            row.strip() for row in open_rows
            if not any(word in row.lower() for word in _util.COMPENSATION)]

        self.assertEqual(
            [], uncompensated,
            "строка(и) с пометкой «не закрыт» не называют ни компенсирующий "
            "гейт пульта, ни принятый риск: " + " || ".join(uncompensated))


if __name__ == "__main__":
    unittest.main()
