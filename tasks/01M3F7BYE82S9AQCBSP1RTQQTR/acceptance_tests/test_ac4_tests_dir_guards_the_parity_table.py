"""AC-4 — 01M3F7BYE82S9AQCBSP1RTQQTR: тест в `tests/` стережёт таблицу
паритета в `docs/stack.md`.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Тест в tests/ читает docs/stack.md и падает, если в таблице нет
строки хотя бы на один запрет перечня требования 1 или если хотя бы у
одной строки нет ни имени проверки doctor, ни пометки «не закрыт».

Критерий говорит не «такой тест написан», а «такой тест ПАДАЕТ» на двух
названных поломках документа — поэтому планка сверяет именно это: берёт
все тестовые методы `tests/`, чей сценарий (метод, его `setUp` и
помощники, на которые он ссылается) упоминает `stack.md`, оставляет
прошедшие на сегодняшнем документе и прогоняет их повторно на документе,
которому подменено содержимое (строка запрета удалена; у строки отобрано
и имя проверки doctor, и пометка «не закрыт»). Хотя бы один из них обязан
покраснеть на каждой подмене — иначе тест в `tests/` не различает тот
дефект, ради которого заведён.

Подмена — на уровне ЧТЕНИЯ файла (`Path.read_text`/`open` по имени
`stack.md`), а не правкой документа на диске: как именно тест в `tests/`
вычисляет путь (`config.ROOT`, `Path(__file__)`), планка не диктует, а
документ репозитория прогоном планки не трогается.

Красен до реализации: таблицы паритета в docs/stack.md ещё нет, мутацию
строки строить не из чего — `setUp` оставляет `self.rows` пустым, и
первый assert падает раньше отбора кандидатов.
"""
import builtins
import io
import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

STACK_MD_NAME = "stack.md"


@contextmanager
def stack_md_reads(text: str):
    """Под этим контекстом любое чтение файла с именем `stack.md` —
    хоть `Path.read_text`, хоть `open` — отдаёт `text`; чтение всех
    остальных файлов идёт настоящим кодом."""
    real_read_text = Path.read_text
    real_open = builtins.open

    def read_text(self, *args, **kwargs):
        if self.name == STACK_MD_NAME:
            return text
        return real_read_text(self, *args, **kwargs)

    def fake_open(file, mode="r", *args, **kwargs):
        try:
            name = os.path.basename(os.fspath(file))
        except TypeError:
            name = ""
        if name == STACK_MD_NAME and "w" not in mode and "a" not in mode:
            return io.StringIO(text)
        return real_open(file, mode, *args, **kwargs)

    with mock.patch.object(Path, "read_text", read_text), \
            mock.patch.object(builtins, "open", fake_open):
        yield


class ParityTableGuardedByTestsDirTest(unittest.TestCase):

    def setUp(self):
        self.text = _util.stack_md_text()
        self.rows = _util.parity_table(self.text)

    def document_without_a_prohibition_row(self) -> str:
        """Документ, из которого удалена строка таблицы, без которой
        хотя бы один запрет перечня требования 1 остаётся непокрытым."""
        for row in self.rows:
            rest = [other for other in self.rows if other is not row]
            if _util.missing_prohibitions(rest):
                return "\n".join(line for line in self.text.splitlines()
                                 if line != row) + "\n"
        return ""

    def document_with_a_row_without_evidence(self) -> str:
        """Документ, в котором у одной строки отобрано и имя проверки
        doctor, и пометка «не закрыт»."""
        known = _util.doctor_check_names()
        for row in self.rows:
            crippled = row
            for name in _util.checks_named_in(row, known):
                crippled = crippled.replace(name, "—")
            for mark in _util.NOT_CLOSED:
                crippled = crippled.replace(mark, "—").replace(
                    mark.capitalize(), "—")
            if crippled != row:
                return self.text.replace(row, crippled)
        return ""

    def candidates_passing_today(self) -> list:
        """Кандидаты, проходящие на сегодняшнем документе, — только их
        краснота под подменой что-то значит."""
        ids = _util.test_methods_mentioning(STACK_MD_NAME)
        self.assertTrue(
            ids,
            "в tests/ нет ни одного тестового метода, чей сценарий "
            "упоминает stack.md — тест, стерегущий таблицу паритета, "
            "обязателен (AC-4)")
        outcomes = _util.run_test_methods(ids)
        good = _util.passing(outcomes)
        self.assertTrue(
            good,
            "ни один тест tests/, упоминающий stack.md, не проходит на "
            "сегодняшнем документе: " + repr(outcomes))
        return good

    def test_ac4_tests_dir_test_reddens_when_a_prohibition_row_disappears(self):
        """Тест из `tests/`, зелёный на сегодняшнем `docs/stack.md`,
        краснеет, когда из таблицы паритета удалена строка одного из
        восьми запретов перечня требования 1.

        Ловит мутацию: тест в `tests/` сверяет документ на «таблица
        вообще есть» (ищет заголовок раздела или считает строки), а не
        покрытие перечня — удалённая строка запрета проходит мимо него, и
        таблица тихо теряет предмет, ради которого заведена.
        """
        self.assertTrue(self.rows, "таблицы паритета в docs/stack.md нет "
                                   "— мутацию строки строить не из чего")
        mutated = self.document_without_a_prohibition_row()
        self.assertTrue(
            mutated,
            "ни одна строка таблицы не является единственной для своего "
            "запрета — мутация «нет строки на запрет» не построена")

        good = self.candidates_passing_today()
        with stack_md_reads(mutated):
            outcomes = _util.run_test_methods(good)

        self.assertTrue(
            _util.failing(outcomes),
            "ни один тест tests/ не покраснел на документе без строки "
            "запрета — проверены: " + _util.describe(good))

    def test_ac4_tests_dir_test_reddens_when_a_row_loses_its_evidence(self):
        """Тот же тест из `tests/` краснеет, когда у строки таблицы нет
        ни имени проверки doctor, ни пометки «не закрыт».

        Ловит мутацию: тест сверяет только перечень запретов (левую
        колонку) и не смотрит, чем строка подтверждена, — таблица
        зарастает прочерками во второй половине, а `doctor` о её
        обещаниях ничего не знает.
        """
        self.assertTrue(self.rows, "таблицы паритета в docs/stack.md нет "
                                   "— мутацию строки строить не из чего")
        mutated = self.document_with_a_row_without_evidence()
        self.assertTrue(
            mutated,
            "ни у одной строки таблицы нечего отобрать (ни имени проверки "
            "doctor, ни пометки «не закрыт») — это уже нарушение AC-2")

        good = self.candidates_passing_today()
        with stack_md_reads(mutated):
            outcomes = _util.run_test_methods(good)

        self.assertTrue(
            _util.failing(outcomes),
            "ни один тест tests/ не покраснел на строке без имени проверки "
            "doctor и без пометки «не закрыт» — проверены: "
            + _util.describe(good))


if __name__ == "__main__":
    unittest.main()
