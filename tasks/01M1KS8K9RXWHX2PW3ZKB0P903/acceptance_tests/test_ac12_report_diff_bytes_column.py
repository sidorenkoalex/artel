"""Приёмочные тесты 01M1KS8K9RXWHX2PW3ZKB0P903 — AC-12 (`artel report`
показывает по каждой закрытой задаче фактический размер диффа, число
шагов и стоимость).

AC-12 сам по себе не называл, где хранится «размер диффа» — test_author
эскалировал именно это (см. историю `test_ac_manual_and_escalate_
markers.py` до правки этим коммитом: контракт T092 «report... ни одного
вызова git» не позволяет посчитать диф «на лету»). ANSWER-1 отвечает
буквально: новая колонка `diff_bytes` в таблице `tasks` (схема
`store.py`), заполняется при входе задачи на merge_gate тем же
значением, что уже считает гейт ёмкости; `artel report` читает колонку
без вызова git; для задач без колонки — прочерк.

Часть AC-12 про «наличие и содержание секции «Оценка объёма и деление»»
рядом с этими же значениями покрыта отдельным файлом —
`test_ac12_report_split_assessment_column.py`: ANSWER-1 не называл, как
report получает содержимое секции конкретной ЗАКРЫТОЙ задачи, не нарушая
контракт «без git» (инвариант 28 docs/invariants.md — чтение артефактов
задачи ветко-зависимо, именно через git); эта часть была эскалирована
отдельно и отвечена ANSWER-2 (новая колонка `split_assessment`, тот же
переход merge_gate, что и `diff_bytes`).

Черный ящик через `orchestrator.store`/`orchestrator.report` — та же
изолированная временная БД/каталог, что `tests/test_report.py::
CmdReportIntegrationTest` (`tests.sandbox.TmpRootTest`), без импорта
недописанной реализации.

Красен до реализации: `orchestrator/store.py::SCHEMA` сегодня не несёт
колонку `diff_bytes` в таблице `tasks` (проверено `grep -n diff_bytes -r
orchestrator` — пусто) — `store.update_task(conn, task_id,
diff_bytes=...)` падает `ValueError: tasks: нет колонок diff_bytes`
(валидация имён полей в `update_task`, `orchestrator/store.py`) и на
уровне схемы, и на уровне отчёта, пока разработчик не добавит колонку
(ANSWER-1, AC-12) и её показ в `report.py`.
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests"))

from orchestrator import report, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


def _word_boundary(number) -> re.Pattern:
    return re.compile(rf"\b{re.escape(str(number))}\b")


class DiffBytesColumnExistsTest(TmpRootTest):
    """Таблица `tasks` свежесозданной схемы несёт колонку `diff_bytes`
    (ANSWER-1, AC-12).

    Ловит мутацию: колонка не добавлена в `SCHEMA`/`migrate()` — множество
    имён колонок не содержит `diff_bytes`, assertion падает.
    """

    def test_ac12_tasks_table_has_diff_bytes_column(self):
        conn = store.db()
        store.create_schema(conn)

        columns = store.table_columns(conn, "tasks")

        self.assertIn(
            "diff_bytes", columns,
            f"таблица tasks не несёт колонку diff_bytes (ANSWER-1, "
            f"AC-12): колонки {sorted(columns)}")


class ReportShowsDiffBytesStepsAndCostTest(TmpRootTest):
    """Для закрытой (`done`) задачи с заполненным `diff_bytes` отчёт
    показывает фактический размер диффа, число шагов журнала и
    стоимость — три значения одной задачи в единственной изолированной
    БД теста, так что любое их появление в отчёте однозначно относится
    именно к ней.

    Ловит мутацию: report продолжает игнорировать колонку `diff_bytes`
    даже после её появления в схеме (читает только `spent_usd`/число
    шагов, как до задачи) — первый subTest покраснеет, а два других
    (уже существовавшее поведение) останутся зелёными, локализуя дефект
    именно на новом значении.
    """

    DIFF_BYTES = 54321
    STEP_COUNT = 6
    SPENT_USD = 17.75

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T900", "Закрытая задача-фикстура AC-12",
                          "done", branch="task/t900-x",
                          target=store.config.DEFAULT_TARGET,
                          budget_usd=25.0)
        store.update_task(conn, "T900", diff_bytes=self.DIFF_BYTES,
                          spent_usd=self.SPENT_USD)
        for i in range(self.STEP_COUNT):
            store.journal(conn, "T900", "developer", f"шаг {i}",
                         session_id="fixture-session")

    def test_ac12_report_shows_diff_bytes_step_count_and_cost(self):
        self.capture(report.cmd_report)
        html = (store.config.ROOT / ".artel" / "report.html").read_text(
            encoding="utf-8")

        with self.subTest(field="diff_bytes"):
            self.assertRegex(
                html, _word_boundary(self.DIFF_BYTES),
                f"отчёт не показывает фактический размер диффа "
                f"({self.DIFF_BYTES}) закрытой задачи T900 (AC-12)")
        with self.subTest(field="step_count"):
            self.assertRegex(
                html, _word_boundary(self.STEP_COUNT),
                f"отчёт не показывает число шагов ({self.STEP_COUNT}) "
                f"закрытой задачи T900 (AC-12)")
        with self.subTest(field="cost"):
            self.assertIn(
                report._usd(self.SPENT_USD), html,
                f"отчёт не показывает стоимость "
                f"({report._usd(self.SPENT_USD)}) закрытой задачи T900 "
                f"(AC-12)")


class ReportShowsDashForTaskClosedBeforeColumnTest(TmpRootTest):
    """Закрытая задача без заполненного `diff_bytes` (NULL — строка
    старше появления колонки) показывает прочерк вместо размера диффа,
    как явно оговорено ANSWER-1 — сравнением ДВУХ отчётов ОДНОЙ и той же
    задачи (сперва без diff_bytes, затем с ним), а не поиском «—» по
    всему документу.

    Поиск голого «—» по всему html ловит СЛУЧАЙНОЕ совпадение: тот же
    символ уже сегодня несут статичные фразы разметки — например,
    заголовок «Борд задач — состояния FSM» и `_gate_queue_html`'s
    «Очередь пуста — ни одна задача не ждёт Оператора» (report.py:258) —
    их количество не зависит от diff_bytes вовсе. Разница числа «—» ДО
    и ПОСЛЕ заполнения diff_bytes у ОДНОЙ и той же задачи убирает весь
    этот шум: всё остальное содержимое отчёта (заголовки, статичные
    фразы, число задач) между двумя вызовами не меняется — меняется
    только значение diff_bytes.

    Ловит мутацию: report показывает `None`/пустую строку/«0» вместо
    прочерка для строки с NULL `diff_bytes` (разница прочерков не равна
    1), путая «диф неизвестен» с «диф нулевого размера».
    """

    SET_DIFF_BYTES = 24680

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T901", "Закрытая задача до колонки diff",
                          "done", branch="task/t901-x",
                          target=store.config.DEFAULT_TARGET,
                          budget_usd=25.0)

    def _report_html(self) -> str:
        self.capture(report.cmd_report)
        return (store.config.ROOT / ".artel" / "report.html").read_text(
            encoding="utf-8")

    def test_ac12_report_shows_dash_for_missing_diff_bytes(self):
        html_before = self._report_html()

        conn = store.db()
        store.update_task(conn, "T901", diff_bytes=self.SET_DIFF_BYTES)
        html_after = self._report_html()

        self.assertNotIn(
            str(self.SET_DIFF_BYTES), html_before,
            "отчёт для задачи без diff_bytes уже содержит число, "
            "предназначенное для случая ПОСЛЕ заполнения — фикстуры "
            "теста перепутаны")
        self.assertIn(
            str(self.SET_DIFF_BYTES), html_after,
            f"отчёт не показывает размер диффа {self.SET_DIFF_BYTES} "
            f"после его заполнения (ANSWER-1, AC-12)")

        dashes_before = html_before.count("—")
        dashes_after = html_after.count("—")
        self.assertEqual(
            dashes_before, dashes_after + 1,
            f"заполнение diff_bytes должно убрать РОВНО один прочерк-"
            f"заглушку из отчёта — прочерков без diff_bytes: "
            f"{dashes_before}, с diff_bytes: {dashes_after}")


if __name__ == "__main__":
    import unittest
    unittest.main()
