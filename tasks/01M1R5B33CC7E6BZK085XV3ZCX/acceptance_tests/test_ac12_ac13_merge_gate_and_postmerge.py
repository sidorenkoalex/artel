"""Приёмочный тест AC-12/AC-13 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-12: `merge_gate` c `merge_gate: operator` для target ≠ self строит
scratch-worktree, выполняет merge и push `refs/heads/<base>` в клоне
контекста target'а и его origin, а не в `config.ROOT`; для self —
плотницкий merge выполняется как прежде, в `config.ROOT`.

AC-13: для target ≠ self после успешного merge вызовы регенерации
`docs/codebase-map.md` и коммита RETRO в main НЕ выполняются вовсе; для
self оба шага выполняются как прежде.

`fsm_merge_gate._cmd_approve_merge_gate` зовётся НАПРЯМУЮ, минуя lease/
мьютекс (тот же приём, что уже применяет `tests/
test_fsm_merge_gate_done_snapshot.py` к соседнему узлу того же гейта) —
предмет проверки этого теста живёт целиком внутри тела гейта.

Красен до реализации: сегодня `_cmd_approve_merge_gate` для ЛЮБОГО
target (`fsm_merge_gate.py::_scratch_worktree`/`_origin_main_sha` не
знают о target вовсе) строит scratch и мержит `origin` ПУЛЬТА — ветка
внешнего target в `config.ROOT` не существует, `git merge --no-ff
<branch>` там либо падает, либо (если каким-то образом отвечает)
коммитит в main ПУЛЬТА, чего требование 4 SPEC прямо запрещает; регенерация
карты и RETRO зовутся безусловно, тоже в main пульта.
"""
import sys
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import ci, config, fsm_merge_gate, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402

TASK = "01AC12AC13MERGEGATETASK"


class ExternalTargetMergeGateTest(ExternalTargetGitSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{TASK}: код фичи")
        self.insert_external_task(TASK, self.branch, state="merge_gate")

        self.pult_main_before = self.pult_main_state()
        self.pult_origin_main_before = self.pult_origin_git(
            "rev-parse", config.MAIN_BRANCH).stdout.strip()

        self.ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        self.ci_patcher.start()
        self.addCleanup(self.ci_patcher.stop)

    def _approve(self):
        conn = store.db()
        t = store.get_task(conn, TASK)
        return fsm_merge_gate._cmd_approve_merge_gate(
            conn, TASK, "merge_gate", t, confirmed_ci_note="зелёный (тест)")

    def test_ac12_merge_lands_in_the_target_origin_not_the_pult(self):
        """Успешный merge регистрируется в origin ЦЕЛЕВОГО
        (`target_origin`), задача переходит в `done`, `main`/origin
        пульта не сдвигаются ни на один коммит.

        Ловит мутацию: плотницкий merge остаётся жёстко привязан к
        `config.ROOT`/origin пульта — `target_origin` не увидел бы
        нового коммита на `main`, а `main пульта` (проверка ниже)
        либо остался бы прежним просто потому, что merge упал, либо
        (хуже) реально сдвинулся бы, приняв код чужого target.
        """
        result = self._approve()

        self.assertEqual(result, ("done",))
        row = store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (TASK,)).fetchone()
        self.assertEqual(row["state"], "done")

        target_origin_main = self.origin_git(
            "rev-parse", config.MAIN_BRANCH).stdout.strip()
        ancestors = self.origin_git(
            "log", "--format=%s", target_origin_main).stdout
        self.assertIn(
            f"{TASK}: код фичи", ancestors,
            f"коммит ветки задачи не найден в истории main origin "
            f"целевого после merge: {ancestors!r}")

    def test_ac12_the_pult_main_is_not_touched(self):
        """`main` пульта (локальный и origin) — байт-в-байт тот же sha
        и то же дерево до и после merge внешнего target."""
        self._approve()

        self.assertEqual(
            self.pult_main_state(), self.pult_main_before,
            "main пульта изменился после merge задачи внешнего target")
        pult_origin_main_after = self.pult_origin_git(
            "rev-parse", config.MAIN_BRANCH).stdout.strip()
        self.assertEqual(
            pult_origin_main_after, self.pult_origin_main_before,
            "origin пульта получил новый коммит main от задачи "
            "внешнего target")

    def test_ac13_no_codebase_map_commit_for_the_external_target(self):
        """После merge внешнего target в его истории main НЕТ коммита
        регенерации карты (`docs/codebase-map.md`) — правило «в
        пульте — только кухня пульта».

        Ловит мутацию: `_regenerate_and_commit_map` зовётся безусловно
        для ЛЮБОГО target — сообщение коммита появится в истории main
        origin целевого, и `assertNotIn` здесь его поймает (если карты
        в дереве целевого нет вовсе — регенерация ещё и упадёт по
        существу, но это тот же класс дефекта: она не имеет права
        звонить вовсе для target ≠ self).
        """
        self._approve()

        target_origin_main = self.origin_git(
            "rev-parse", config.MAIN_BRANCH).stdout.strip()
        messages = self.origin_git(
            "log", "--format=%s", target_origin_main).stdout
        self.assertNotIn("карта кодовой базы", messages)

    def test_ac13_no_retro_commit_for_the_external_target(self):
        """После merge внешнего target в его истории main НЕТ коммита
        RETRO задачи (RETRO внешнего target остаётся только в снапшоте,
        не в main целевого)."""
        self._approve()

        target_origin_main = self.origin_git(
            "rev-parse", config.MAIN_BRANCH).stdout.strip()
        messages = self.origin_git(
            "log", "--format=%s", target_origin_main).stdout
        self.assertNotIn("RETRO", messages)


class SelfTargetMergeGateUnchangedTest(ExternalTargetGitSandbox):
    """Self (`config.DEFAULT_TARGET`): плотницкий merge, карта и RETRO —
    в `config.ROOT`, байт-в-байт как до задачи (SPEC требования 4)."""

    TASK2 = "01AC12SELFMERGEGATE0001"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK2.lower()}-x"
        self.git("checkout", "-q", "-b", self.branch)
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK2}: код фичи")
        self.git("checkout", "-q", config.MAIN_BRANCH)

        conn = store.db()
        store.insert_task(conn, self.TASK2, "Задача self", "merge_gate",
                          self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        from orchestrator import artifact_branch
        artifact_branch.commit_files(
            self.TASK2, {f"tasks/{self.TASK2}/PLAN.md": "план\n"},
            f"{self.TASK2}: план")

        self.ci_patcher = mock.patch.object(
            ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        self.ci_patcher.start()
        self.addCleanup(self.ci_patcher.stop)

    def test_ac12_self_target_merge_still_lands_in_the_pult_origin(self):
        conn = store.db()
        t = store.get_task(conn, self.TASK2)

        result = fsm_merge_gate._cmd_approve_merge_gate(
            conn, self.TASK2, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

        self.assertEqual(result, ("done",))
        pult_origin_main = self.pult_origin_git(
            "rev-parse", config.MAIN_BRANCH).stdout.strip()
        messages = self.pult_origin_git(
            "log", "--format=%s", pult_origin_main).stdout
        self.assertIn(f"{self.TASK2}: код фичи", messages)


if __name__ == "__main__":
    import unittest
    unittest.main()
