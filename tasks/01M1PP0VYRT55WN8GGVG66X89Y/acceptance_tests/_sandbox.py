"""Общая песочница приёмочных тестов 01M1PP0VYRT55WN8GGVG66X89Y (SPEC:
«Частичная стоимость шага по видам токенов, калибровка курса»).

Не `test_*.py` — guard.py читает AC-разметку и маркер красноты только из
`test_*.py`; этот файл — общая инфраструктура тестов, не сам критерий.

Тот же приём, что `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/
_sandbox.py` (задача, введшая `config.TOKEN_RATES` — прямой
предшественник этой задачи по тому же подмодулю `spend`): ни один
сценарий здесь не проходит через реальный `claude`/`git`
(`spend.partial_cost_usd`, `spend.charge_missing_result`,
`spend.charge_step`, `report.token_rate_divergence` читают/пишут только
`state.db`), поэтому песочница — схема БД плюс одна вставленная напрямую
строка задачи.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class TokenRateTmpRootTest(TmpRootTest):
    """Схема БД + одна задача (`self.TASK`), заведённая напрямую
    `store.insert_task` (без `catalog.cmd_new`/git — механизму учёта
    стоимости шага ветка/worktree задачи не нужны)."""

    TASK = "T901"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Задача для теста частичной стоимости",
                          "in_dev", "task/t901-x", config.DEFAULT_TARGET, 50.0)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def journal_rows(self) -> list:
        """(actor, action, detail) журнала задачи по порядку записи."""
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT * FROM steps WHERE task_id=? ORDER BY id", (self.TASK,))]

    def alerts_of_kind(self, kind: str) -> list:
        return store.db().execute(
            "SELECT * FROM alerts WHERE kind=?", (kind,)).fetchall()
