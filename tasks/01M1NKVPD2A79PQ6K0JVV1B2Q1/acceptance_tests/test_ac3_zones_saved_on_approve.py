"""Приёмочные тесты 01M1NKVPD2A79PQ6K0JVV1B2Q1 — AC-3 (при `approve` на
гейте SPEC значение `zones` сохраняется в БД задачи).

Два уровня: (1) таблица `tasks` свежесозданной схемы несёт колонку
`zones` (тот же приём, что `tasks/01M1KS8K9RXWHX2PW3ZKB0P903/
acceptance_tests/test_ac12_report_split_assessment_column.py` уже
применяет к колонке `split_assessment`); (2) сквозной сценарий — задача
входит в `spec_gate` с заполненным `zones:` во frontmatter SPEC (на
артефактной ветке пульта — `orchestrator/artifact_source.resolve`
сегодня всегда `foreign=True`, диск не читается), `approve` переводит её
дальше, и строка `tasks` после этого несёт то же значение `zones`,
которое было в SPEC.

`_sandbox.py::ZonesApproveSandbox` — общая песочница; фикстура использует
`schema_version: 1` (минимальная, точно проходит guard независимо от
версии-гейтинга AC-1, требование поля `zones` тестирует отдельно
`test_ac1_...py`) — AC-3 проверяет момент СОХРАНЕНИЯ значения, а не
момент его ОБЯЗАТЕЛЬНОСТИ, эти два свойства не должны зависеть друг от
друга в тесте.

Красен до реализации: `orchestrator/store.py::SCHEMA` сегодня не несёт
колонку `zones` в таблице `tasks` (проверено `grep -n "zones" -r
orchestrator/store.py` — пусто); `orchestrator/fsm.py::_cmd_approve` на
`spec_gate` читает `meta` из SPEC.md, но нигде не зовёт `store.
update_task(..., zones=...)` (проверено чтением тела ветки `state ==
"spec_gate"`, orchestrator/fsm.py:616-657) — оба теста ниже покраснеют,
пока разработчик не добавит колонку и её заполнение.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZonesApproveSandbox, spec_text  # noqa: E402
from orchestrator import store  # noqa: E402


class TasksTableHasZonesColumnTest(unittest.TestCase):
    """Таблица `tasks` свежесозданной схемы несёт колонку `zones`.

    Ловит мутацию: колонка не добавлена ни в `SCHEMA`, ни в `migrate()`
    (миграция для БД, созданной ДО этой задачи) — множество имён колонок
    не содержит `zones`, assertion падает.
    """

    def test_ac3_tasks_table_has_zones_column(self):
        conn = store.db()
        store.create_schema(conn)

        columns = store.table_columns(conn, "tasks")

        self.assertIn(
            "zones", columns,
            f"таблица tasks не несёт колонку zones (AC-3): колонки "
            f"{sorted(columns)}")


class ApproveSavesZonesValueTest(ZonesApproveSandbox):
    """SPEC с заполненным `zones: orchestrator/store.py` доходит до
    `spec_gate` и проходит `approve` — после этого строка задачи в БД
    несёт то же значение `zones`, которое было в SPEC на артефактной
    ветке.

    Ловит мутацию: `zones` читается из meta, но нигде не пишется в store
    (значение теряется — колонка остаётся `NULL`/значение по умолчанию
    независимо от содержимого SPEC), либо пишется не тем полем, не при
    approve на `spec_gate`, а при каком-то другом переходе, либо
    записывается искажённым значением (например только первый путь из
    нескольких, потерянные пробелы/регистр).
    """

    ZONES_VALUE = "orchestrator/store.py"

    def test_ac3_approve_on_spec_gate_saves_zones_to_the_task_row(self):
        text = spec_text(version=1, zones=self.ZONES_VALUE)
        sha = self.enter_spec_gate(text)

        self.approve(sha)

        row = self.task_row()
        self.assertEqual(
            row.get("zones"), self.ZONES_VALUE,
            f"после approve на spec_gate строка задачи не несёт значение "
            f"zones={self.ZONES_VALUE!r} из SPEC (AC-3): строка {row}")


if __name__ == "__main__":
    unittest.main()
