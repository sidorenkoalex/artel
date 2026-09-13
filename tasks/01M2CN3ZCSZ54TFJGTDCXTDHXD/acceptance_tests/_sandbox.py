"""Тонкая песочница планки 01M2CN3ZCSZ54TFJGTDCXTDHXD (SPEC.md, зона
orchestrator/runner.py): прямой вызов `runner.run_agent_once` в
изоляции, без FSM-обвязки `cmd_run`/`_run_developer_step` (пауза,
стоп-кран волны, pre-flight, скилы, сборка промпта) — критерии этой
планки (AC-1, AC-2) описывают декомпозицию именно `run_agent_once`, а
не отказы, случающиеся раньше его вызова.

Задача заводится строкой в БД (`store.insert_task`), без git/worktree:
target — внешний (`EXTERNAL_TARGET` ≠ `config.DEFAULT_TARGET`), поэтому
`role_cwd` идёт веткой `mkdir` рабочего каталога target'а (orchestrator/
runner.py: `role_cwd`, ветка `else`), не веткой `workspace.ensure`,
которая завела бы настоящий git worktree задачи. `materialize_task_dir`
внутри той же ветки деградирует тихо (нет артефактной ветки в
`self.root` песочницы — `gitcmd.branch_head_sha` не отвечает), как и
описано в её собственном докстринге.

Не копия `tests.sandbox.LightTransitionSandbox` (переходы FSM здесь не
разыгрываются вовсе) — только `TmpRootTest` и `keychain.token` поверх
него, тем же приёмом, что и `tests/test_agent_log.py::CmdRunLoggingTest`
и `tests/test_multitarget.py`, но без `cmd_new`/`fake_git`/`doctor.
preflight_checks`, которые тем тестам нужны для похода через `cmd_run`
целиком, а этой планке — нет.
"""
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import runner, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

DEVELOPER_ROLE = "developer"
# ≠ config.DEFAULT_TARGET — см. докстринг модуля: `role_cwd` для внешнего
# target'а не заводит настоящий git worktree, только каталог на диске.
EXTERNAL_TARGET = "acme-ext"
TASK_ID = "01TESTRUNAGENTONCE0000000"


class RunAgentOnceSandbox(TmpRootTest):
    """Задача `TASK_ID` в БД, готовая к прямому вызову `run_agent_once`."""

    def setUp(self):
        super().setUp()
        # `role_env` читает подписочный токен через keychain при отсутствии
        # ambient-переменных (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN) — реальный
        # `security find-generic-password` в песочнице CI недетерминирован
        # и не нужен ни одному сценарию этой планки (тот же приём, что
        # `tests/test_agent_log.py::CmdRunLoggingTest.setUp`).
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        self.conn = store.db()
        store.create_schema(self.conn)
        store.insert_task(self.conn, TASK_ID, "Разбор run_agent_once",
                          "in_dev", "task/run-agent-once-plank",
                          EXTERNAL_TARGET, 10.0)
        self.task_id = TASK_ID

    def run_once(self, attempt: int = 1, role: str = DEVELOPER_ROLE,
                prompt: str = "промпт шага"):
        return runner.run_agent_once(self.conn, self.task_id, role, prompt,
                                     attempt)

    def journal_details(self, action: str) -> list:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? "
            "ORDER BY id", (self.task_id, action))]
