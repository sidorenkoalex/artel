"""AC-5 (tasks/01M27JPEGCGMDDRX5A98QWJW0Z/SPEC.md): гейт мержа
(`fsm_merge_gate._cmd_approve_merge_gate`) отклоняет `approve` из
`merge_gate` переходом в `escalated` с текстом AC-4, если дифф ветки
задачи против базы сравнения трогает путь из `config.PROTECTED_PATHS`,
— В ТОМ ЧИСЛЕ когда `git merge --no-ff` этой ветки не даёт ни одного
конфликтующего файла (сегодня эскалация по защищённому пути срабатывает
ИСКЛЮЧИТЕЛЬНО внутри разбора конфликта, `_handle_merge_conflict`, и
только когда сам merge конфликтует).

Песочница — настоящий git (`RealGitSandbox`, тот же приём, что
`tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest`), не
мок: сценарий обязан остаться верным независимо от того, ГДЕ в
`_cmd_approve_merge_gate` реализация разместит новую проверку (до
попытки `git merge --no-ff` или отдельным узлом рядом с разбором
бесконфликтного исхода) — ветка задачи несёт НОВЫЙ файл `gates.yaml`,
которого нет на main, так что реальный `git merge --no-ff` этой ветки
гарантированно бесконфликтен (AC-5: «даже когда... не даёт ни одного
конфликтующего файла»).

Красен до реализации: `_perform_carpentry_merge` сегодня не знает о
`config.PROTECTED_PATHS` вовсе — бесконфликтный merge молча доходит до
`done`, задача не эскалирует.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, fsm_merge_gate, store  # noqa: E402
from tests.sandbox import RealGitSandbox, capture  # noqa: E402

TASK = "01M27PROTECTEDMERGETASK"


class MergeGateProtectedPathDiffTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

        # bare origin пульта (тот же приём, что DonePathSnapshotTest):
        # `_ensure_branch_head_published`/`_sync_main_or_wait` требуют
        # настроенный `origin` с main, иначе отказывают раньше, чем тест
        # успевает дойти до защищённого пути в диффе.
        pult_origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pult_origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(pult_origin))
        self.git("remote", "add", "origin", str(pult_origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.pult_origin = pult_origin

        self.branch = f"task/{TASK.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        # `gates.yaml` не существует на main этой песочницы — новый файл
        # на ветке задачи гарантированно НЕ конфликтует при
        # `git merge --no-ff` (AC-5, «даже когда... не даёт ни одного
        # конфликтующего файла»).
        (self.root / "gates.yaml").write_text("task: true\n", encoding="utf-8")
        self.git("add", "gates.yaml")
        self.git("commit", "-q", "-m", f"{TASK}: правка gates.yaml")
        self.git("checkout", "-q", config.MAIN_BRANCH)

        store.insert_task(store.db(), TASK, "Задача", "merge_gate",
                          self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def _origin_main_sha(self) -> str:
        res = subprocess.run(
            ["git", "-C", str(self.pult_origin), "rev-parse",
             config.MAIN_BRANCH], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    def test_ac5_protected_path_diff_escalates_without_merge_conflict(self):
        """`approve` из `merge_gate` на ветке, чей БЕСКОНФЛИКТНЫЙ дифф
        трогает `gates.yaml`, обязан эскалировать с текстом AC-4, а не
        доводить merge до `done`; main обязан остаться нетронутым.

        Ловит мутацию: проверка защищённых путей подключена ТОЛЬКО
        внутри `_handle_merge_conflict` (разбор конфликта) — при
        бесконфликтном `git merge --no-ff` (ровно этот сценарий) она
        никогда не вызывается, и задача уходит в `done` вместо
        `escalated`.
        """
        pre_merge_sha = self._origin_main_sha()
        t = store.get_task(store.db(), TASK)

        outcome = fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

        self.assertNotEqual(
            outcome, ("done",),
            "merge не имеет права завершиться при защищённом пути в диффе")
        row = store.db().execute("SELECT state FROM tasks WHERE id=?",
                                 (TASK,)).fetchone()
        self.assertEqual(row["state"], "escalated")

        details = [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=?", (TASK,))]
        expected = ("защищённый путь gates.yaml — правит только Оператор "
                   "коммитом в main; предложи правку приложением к PLAN "
                   "(unified-дифф)")
        self.assertTrue(any(expected in d for d in details), details)

        self.assertEqual(
            self._origin_main_sha(), pre_merge_sha,
            "main обязан остаться нетронутым — публикация merge не имеет "
            "права состояться при защищённом пути в диффе")


if __name__ == "__main__":
    unittest.main()
