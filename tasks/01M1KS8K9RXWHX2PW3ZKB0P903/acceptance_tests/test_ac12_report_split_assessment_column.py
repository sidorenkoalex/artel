"""Приёмочные тесты 01M1KS8K9RXWHX2PW3ZKB0P903 — AC-12, оставшаяся часть
(`artel report` показывает наличие и содержание секции «Оценка объёма и
деление» рядом с диффом/шагами/стоимостью закрытой задачи).

Эта часть была эскалирована в `test_ac_manual_and_escalate_markers.py`
(маркер `# AC-12`, снят этим коммитом) — критерий не называл источник
данных для ЗАКРЫТОЙ задачи произвольного момента, а контракт `cmd_report`
«ни одного вызова git» (tasks/T092/SPEC.md, требование 9) исключал прямое
чтение `tasks/<id>/SPEC.md`. ANSWER-2 отвечает буквально: новая колонка
`split_assessment` таблицы `tasks` — текст секции «Оценка объёма и
деление» либо литеральная строка «сигналов нет» (секция пуста/отсутствует),
заполняется на входе задачи в merge_gate тем же переходом, что и
`diff_bytes` (ANSWER-1, `test_ac12_report_diff_bytes_column.py`); `artel
report` читает колонку без git; для задач, закрытых до появления колонки —
прочерк (тот же приём, что уже применён к `diff_bytes`).

Часть про фактический размер диффа/число шагов/стоимость покрыта отдельно
`test_ac12_report_diff_bytes_column.py` — этот файл проверяет только
добавку ANSWER-2 (`split_assessment`), не дублируя те тесты.

Черный ящик через `orchestrator.store`/`orchestrator.report` — та же
изолированная временная БД/каталог, что и остальные тесты AC-12
(`tests.sandbox.TmpRootTest`), без импорта недописанной реализации.

Красен до реализации: `orchestrator/store.py::SCHEMA` сегодня не несёт
колонку `split_assessment` в таблице `tasks` (проверено `grep -n
split_assessment -r orchestrator` — пусто) — `store.update_task(conn,
task_id, split_assessment=...)` падает `ValueError: tasks: нет колонок
split_assessment` (валидация имён полей в `update_task`,
`orchestrator/store.py`) и на уровне схемы, и на уровне отчёта, пока
разработчик не добавит колонку (ANSWER-2, AC-12) и её показ в
`report.py`.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import report, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class SplitAssessmentColumnExistsTest(TmpRootTest):
    """Таблица `tasks` свежесозданной схемы несёт колонку
    `split_assessment` (ANSWER-2, AC-12).

    Ловит мутацию: колонка не добавлена в `SCHEMA`/`migrate()` —
    множество имён колонок не содержит `split_assessment`, assertion
    падает.
    """

    def test_ac12_tasks_table_has_split_assessment_column(self):
        conn = store.db()
        store.create_schema(conn)

        columns = store.table_columns(conn, "tasks")

        self.assertIn(
            "split_assessment", columns,
            f"таблица tasks не несёт колонку split_assessment (ANSWER-2, "
            f"AC-12): колонки {sorted(columns)}")


class ReportShowsSplitAssessmentContentTest(TmpRootTest):
    """Для закрытой задачи с заполненным `split_assessment` (нарезка на
    части) отчёт показывает текст секции «Оценка объёма и деление»
    рядом с диффом/шагами/стоимостью этой же задачи.

    Ловит мутацию: report добавляет показ diff_bytes/шагов/стоимости
    (ANSWER-1), но не читает новую колонку split_assessment вовсе —
    текст секции нигде не появляется в html.
    """

    SPLIT_TEXT = ("деление на 2 части: ядро (сигналы, guard) первой, "
                  "интеграция (report) второй")

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T910", "Закрытая задача-фикстура split",
                          "done", branch="task/t910-x",
                          target=store.config.DEFAULT_TARGET,
                          budget_usd=25.0)
        store.update_task(conn, "T910", split_assessment=self.SPLIT_TEXT)

    def test_ac12_report_shows_split_assessment_text(self):
        html = report._esc(self.SPLIT_TEXT)
        self.capture(report.cmd_report)
        rendered = (store.config.ROOT / ".artel" / "report.html").read_text(
            encoding="utf-8")

        self.assertIn(
            html, rendered,
            f"отчёт не показывает текст секции «Оценка объёма и деление» "
            f"({self.SPLIT_TEXT!r}) закрытой задачи T910 (ANSWER-2, "
            f"AC-12)")


class ReportShowsSignalsNoneLiterallyTest(TmpRootTest):
    """Для закрытой задачи, у которой сигналы не сработали (секция пуста
    или отсутствует), `split_assessment` несёт литеральную строку
    «сигналов нет» (ANSWER-2) — отчёт показывает её буквально, а не
    заменяет собственной заглушкой (например, голым прочерком, который
    ANSWER-2 резервирует за случаем «задача закрыта до появления
    колонки»).

    Ловит мутацию: report для пустого/непустого содержания
    split_assessment показывает одну и ту же заглушку («—» или
    аналог) — путает «сигналов не было» (значение колонки заполнено
    буквальной строкой) с «колонки ещё не существовало у этой строки»
    (значение NULL, другой тест-кейс).
    """

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T911", "Закрытая задача без сигналов",
                          "done", branch="task/t911-x",
                          target=store.config.DEFAULT_TARGET,
                          budget_usd=25.0)
        store.update_task(conn, "T911", split_assessment="сигналов нет")

    def test_ac12_report_shows_signals_none_literally(self):
        self.capture(report.cmd_report)
        html = (store.config.ROOT / ".artel" / "report.html").read_text(
            encoding="utf-8")

        self.assertIn(
            "сигналов нет", html,
            "отчёт не показывает буквальную строку «сигналов нет» для "
            "закрытой задачи T911 с пустой секцией «Оценка объёма и "
            "деление» (ANSWER-2, AC-12)")


class ReportShowsDashForTaskClosedBeforeSplitColumnTest(TmpRootTest):
    """Закрытая задача без заполненного `split_assessment` (NULL —
    строка старше появления колонки) показывает прочерк, как явно
    оговорено ANSWER-2 — сравнением ДВУХ отчётов ОДНОЙ и той же задачи
    (сперва без split_assessment, затем с ним), тем же приёмом, что уже
    применён к diff_bytes в `test_ac12_report_diff_bytes_column.py`
    (`ReportShowsDashForTaskClosedBeforeColumnTest`) — поиск голого «—»
    по всему html ловит статичные фразы разметки, не зависящие от этой
    колонки.

    Ловит мутацию: report показывает `None`/пустую строку вместо
    прочерка для строки с NULL `split_assessment`, путая «секция
    неизвестна» с «секция пуста» (у которой уже есть отдельное
    буквальное значение «сигналов нет», см. предыдущий тест).
    """

    SET_TEXT = "монолит принят Оператором 2026-09-04: одна зона правки"

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T912", "Закрытая задача до колонки split",
                          "done", branch="task/t912-x",
                          target=store.config.DEFAULT_TARGET,
                          budget_usd=25.0)

    def _report_html(self) -> str:
        self.capture(report.cmd_report)
        return (store.config.ROOT / ".artel" / "report.html").read_text(
            encoding="utf-8")

    def test_ac12_report_shows_dash_for_missing_split_assessment(self):
        html_before = self._report_html()

        conn = store.db()
        store.update_task(conn, "T912", split_assessment=self.SET_TEXT)
        html_after = self._report_html()

        self.assertNotIn(
            self.SET_TEXT, html_before,
            "отчёт для задачи без split_assessment уже содержит текст, "
            "предназначенный для случая ПОСЛЕ заполнения — фикстуры "
            "теста перепутаны")
        self.assertIn(
            self.SET_TEXT, html_after,
            f"отчёт не показывает текст секции {self.SET_TEXT!r} после "
            f"заполнения split_assessment (ANSWER-2, AC-12)")

        dashes_before = html_before.count("—")
        dashes_after = html_after.count("—")
        self.assertEqual(
            dashes_before, dashes_after + 1,
            f"заполнение split_assessment должно убрать РОВНО один "
            f"прочерк-заглушку из отчёта — прочерков без split_assessment: "
            f"{dashes_before}, с split_assessment: {dashes_after}")


if __name__ == "__main__":
    import unittest
    unittest.main()
