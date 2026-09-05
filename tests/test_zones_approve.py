"""Юнит-тесты сохранения `zones` при `approve` на `spec_gate`
(01M1NKVPD2A79PQ6K0JVV1B2Q1, часть 1 нарезки «Механика зон», требование 1,
AC-3).

Приёмочный тест задачи (`tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/
test_ac3_zones_saved_on_approve.py`) уже закрывает AC-3 сквозным сценарием
(SPEC с заполненным `zones` доходит до `spec_gate` и после `approve` строка
задачи несёт то же значение) — не дублируется здесь. Этот файл — граничные
случаи, которые приёмочная планка не обязана перечислять поимённо: SPEC без
поля `zones` не роняет approve и оставляет колонку `NULL` (частый путь,
version-gating AC-1 делает поле необязательным для старых версий), и
колонка добавляется миграцией схемы, созданной ДО этой задачи (та же
проверка, что `tests/test_spec_budget.py::LegacyDbMigrationTest` делает для
`budget_source`).

Песочница — `tests.sandbox.RealGitSandbox`, тем же приёмом, что
`tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/_sandbox.py::
ZonesApproveSandbox` (артефактная ветка пульта — единственный источник,
с которого `fsm._cmd_approve` на `spec_gate` читает SPEC.md).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, config, fsm, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
{zones_line}---

# SPEC: фикстура approve zones

## Контекст
Фикстура.

## Требования
1. Первое требование.

## Критерии приёмки
AC-1. Первый критерий.

## Не входит
- Всё остальное.
"""


class ZonesApproveTest(RealGitSandbox):
    """`_cmd_approve` на `spec_gate` (01M1NKVPD2A79PQ6K0JVV1B2Q1, AC-3)."""

    TASK = "01ZONESUNITTASKAPPROVE01"

    def enter_spec_gate(self, zones: str | None) -> str:
        zones_line = f"zones: {zones}\n" if zones is not None else ""
        text = SPEC_TEMPLATE.format(task=self.TASK, zones_line=zones_line)
        store.insert_task(store.db(), self.TASK, "Zones approve unit",
                          "spec_writing", f"task/{self.TASK.lower()}-x",
                          config.DEFAULT_TARGET, 15.0)
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/SPEC.md": text},
            f"{self.TASK}: SPEC готов")
        capture(fsm.cmd_advance, self.TASK)
        return store.get_task(store.db(), self.TASK)["fixed_sha"]

    def task_row(self) -> dict:
        return dict(store.get_task(store.db(), self.TASK))

    def test_spec_without_zones_field_leaves_the_column_null(self):
        """Ловит мутацию: `meta.get("zones")` заменён на `meta.get("zones",
        "")`/подобный дефолт — отсутствие поля стало бы пустой строкой
        вместо `NULL`, и `spec_zones_errors`-подобные читатели не отличили
        бы «поле не задано» от «поле задано пустым»."""
        sha = self.enter_spec_gate(zones=None)

        capture(fsm.cmd_approve, self.TASK, sha)

        self.assertIsNone(self.task_row()["zones"])

    def test_approve_does_not_touch_zones_on_other_states(self):
        """Значение `zones` пишется ровно на переходе `spec_gate` —
        задача, заведённая напрямую в другом состоянии (без прохода через
        `_cmd_approve` на `spec_gate`), не несёт стороннего значения."""
        store.insert_task(store.db(), "01ZONESUNITTASKOTHER01",
                          "Другое состояние", "in_dev",
                          "task/01zonesunittaskother01-x",
                          config.DEFAULT_TARGET, 15.0)

        self.assertIsNone(
            store.get_task(store.db(), "01ZONESUNITTASKOTHER01")["zones"])


class ZonesColumnMigrationTest(RealGitSandbox):
    """Колонка `zones` таблицы `tasks` — миграция БД, созданной ДО этой
    задачи (тот же приём, что `tests/test_spec_budget.py::
    LegacyDbMigrationTest` для `budget_source`)."""

    def test_migrate_adds_the_zones_column_to_a_legacy_tasks_table(self):
        conn = store.db()
        conn.executescript(
            "DROP TABLE tasks;"
            "CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, "
            "state TEXT, branch TEXT, target TEXT);")

        store.migrate(conn)

        self.assertIn("zones", store.table_columns(conn, "tasks"))

    def test_migrate_is_idempotent_for_the_zones_column(self):
        conn = store.db()

        store.migrate(conn)  # уже есть в свежей схеме — не должно упасть
        store.migrate(conn)

        self.assertIn("zones", store.table_columns(conn, "tasks"))
