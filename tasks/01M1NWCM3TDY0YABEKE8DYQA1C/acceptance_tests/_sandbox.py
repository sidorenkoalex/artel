"""Общая песочница приёмочных тестов 01M1NWCM3TDY0YABEKE8DYQA1C (SPEC:
«Стоимость частичного шага при таймауте: курс токенов вместо тишины»).

Не `test_*.py` — guard.py читает AC-разметку и маркер красноты только из
`test_*.py` (scripts/guard.py::scan_acceptance_tests/scan_redness_markers,
docstring обеих функций: «вспомогательные файлы (_sandbox.py, __init__.py)
маркером не размечаются»); этот файл — общая инфраструктура тестов, не сам
критерий.

Ни один сценарий этой задачи не проходит через реальный `claude`/`git`
(`spend.charge_missing_result`, `budget.enforce_budget`/`budget_block`,
`report.cmd_report`, `retro.build_done` — все читают/пишут только
`state.db` и диск `config.TASKS`/`config.ROOT`), поэтому песочница легче,
чем `tests/test_step_cost.py::CmdRunCostTest` (там нужен фейковый агент и
`gitcmd`): только схема БД и одна вставленная напрямую строка задачи —
тем же приёмом, что `tests/test_retro.py::RetroGenerationTest`.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class CostTmpRootTest(TmpRootTest):
    """Схема БД + одна задача (`self.TASK`), заведённая напрямую
    `store.insert_task` (без `catalog.cmd_new`/git — самому механизму
    учёта стоимости шага ветка/worktree задачи не нужны)."""

    TASK = "T900"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача для теста стоимости",
                          "in_dev", "task/t900-x", config.DEFAULT_TARGET, 50.0)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def journal_rows(self) -> list:
        """(actor, action, detail) журнала задачи по порядку записи."""
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT * FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]

    def set_task(self, **fields) -> None:
        conn = store.db()
        assignments = ", ".join(f"{k}=?" for k in fields)
        conn.execute(f"UPDATE tasks SET {assignments} WHERE id=?",
                     (*fields.values(), self.TASK))
        conn.commit()
