"""Юнит-тесты `checkpoint.commit_timeout_checkpoint` (tasks/T041/SPEC.md).

Приёмочные тесты (tasks/T041/acceptance_tests) проверяют критерии
приёмки целиком через `cmd_run` с подложным процессом агента; здесь —
изолированные случаи самой функции чекпоинта: пустое дерево, отказ git
на любом из шагов, повторная фиксация sha (`store.record_fixation`) и
чтение результата `fixation.check_integrity` сразу после коммита.

Песочница — `RealPultGitTest` (tests/test_git_fixation.py): чекпоинт —
это реальные `git add`/`git diff`/`git commit`, заглушкой `gitcmd.git`
эту механику не проверить (тот же довод, что в acceptance_tests T041).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import checkpoint, fixation, gitcmd, store, workspace  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402


class _WorktreeCheckpointTest(RealPultGitTest):
    """Три WIP-чекпоинта (`commit_timeout_checkpoint`/`commit_abnormal_
    checkpoint`/`commit_pause_now_checkpoint`) явно НЕ генерализованы A7
    (PLAN «Подход», Б1: «структурно неприменимо ... корректная
    генерализация — отдельная задача») — они по-прежнему коммитят
    worktree КОДОВОЙ ветки задачи (`workspace.path`), не репо фиксации
    self/артели (`RealPultGitTest.task_dir()`/`repo()`, теперь —
    `config.PROJECTS/artel`). До A7 `cmd_new` заводил этот worktree сам;
    generic-путь этой задачи (AC-5) его больше не создаёт — эта
    песочница заводит его явно (`workspace.ensure`), тем же способом,
    каким и раньше worktree доводился до состояния «есть» (сама механика
    чекпоинта от способа появления worktree не зависит, только от его
    наличия).

    `store.record_fixation`, которую чекпоинт зовёт ПОСЛЕ своего коммита
    (SPEC T041), сама теперь идёт через generic `fixation.fix()` — репо
    ФИКСАЦИИ (`config.PROJECTS/artel`), не worktree, куда чекпоинт только
    что закоммитил: это два РАЗНЫХ репозитория (тот же класс расхождения,
    что PLAN «Предложения системе» — «два параллельных механизма для
    одного понятия» — уже отмечает для внешнего target в целом, не
    создан и не решён этой песочницей). Проверка «check_integrity чист
    после коммита» поэтому сверяется с `self.head()` (репо фиксации), не
    с головой worktree.
    """

    def setUp(self):
        super().setUp()
        branch = store.get_task(store.db(), self.TASK)["branch"]
        wt_path, error = workspace.ensure(self.TASK, branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt = wt_path

    def worktree_task_dir(self) -> Path:
        d = self.wt / "tasks" / self.TASK
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_code_file(self, rel: str, text: str) -> Path:
        """Файл кодовой ветки ВНЕ `tasks/<id>/` — путь мандата `developer`
        (SPEC 01M1NBWTSXEJB24PXR417YF1VA, ANSWER-1): без него сценарии
        `developer` ниже, где меняется только `tasks/<id>/`, не имеют ни
        одного пути в мандате кода и код-коммит закономерно не
        случается — тестам failure-веток `add`/`diff`/`commit` нужна
        реальная правка вне `tasks/<id>/`, чтобы дойти до проверяемого
        шага, а не выйти раньше по «нечего коммитить»."""
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def worktree_git(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(self.wt), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def worktree_head(self) -> str:
        return gitcmd.head_sha(self.wt)

    def orchestrator_steps(self) -> list:
        """Записи журнала САМОГО чекпоинта — не любые действия actor=
        'orchestrator': generic-approve self/артели (A7) теперь пытается
        Draft-MR (github forge, AC-1) и при отказе (нет origin в
        песочнице) журналит `actor='orchestrator'` под именем «Draft MR
        FAILED» — тот же actor, но другой предмет, не про чекпоинт."""
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"
               and r["action"].startswith("WIP-чекпоинт")]


class CommitTimeoutCheckpointTest(_WorktreeCheckpointTest):

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.worktree_head()

        detail = checkpoint.commit_timeout_checkpoint(
            store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_with_message_sha_and_journal_entry(self):
        """Мандат `developer` — все пути кроме `tasks/<id>/`
        (SPEC 01M1NBWTSXEJB24PXR417YF1VA, ANSWER-1): правка ВНЕ
        `tasks/<id>/` нужна здесь, чтобы код-коммит вообще состоялся —
        WIP, оставленный ТОЛЬКО в `tasks/<id>/`, из этого коммита
        исключён (переносится в артефактную ветку отдельно, см.
        `tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/
        test_ac1_developer_mandate_all_paths_but_task_dir.py`)."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = checkpoint.commit_timeout_checkpoint(
            store.db(), self.TASK, "developer")

        # Коммит чекпоинта — в worktree кодовой ветки задачи, не в ROOT
        # (тот остаётся на main, SPEC T048); `git log` читается там же.
        subject = self.worktree_git("log", "-1", "--format=%s").strip()
        self.assertEqual(subject,
                         f"{self.TASK}: WIP-чекпоинт после таймаута шага developer")
        self.assertIn(subject, detail)
        self.assertIn(self.worktree_head(), detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("таймаут", entries[0]["action"].lower())

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        checkpoint.commit_timeout_checkpoint(store.db(), self.TASK, "developer")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def _run_with_failing_step(self, failing_subcommand: str, rc: int):
        """Заглушка `gitcmd.git`: заданный git-подкоманде отвечает `rc`,
        остальные проходят настоящим `gitcmd.git` (тот же приём, что и
        существующий `test_git_add_failure_...` — только параметризован
        по шагу, чтобы закрыть класс целиком: `add`/`diff`/`commit`)."""
        real_git = gitcmd.git

        def side_effect(*args):
            if failing_subcommand in args:
                return subprocess.CompletedProcess(list(args), rc, "", "boom")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=side_effect):
            return checkpoint.commit_timeout_checkpoint(
                store.db(), self.TASK, "developer")

    def test_git_add_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.worktree_head()

        detail = self._run_with_failing_step("add", 1)

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_git_diff_failure_commits_nothing_and_journals_nothing(self):
        """REVIEW.md T041 итерация 1, замечание minor: тот же класс отказа
        (`git diff --cached --quiet` вне {0,1} — git не ответил), что и у
        `git add`, отдельным кейсом. Правка ВНЕ `tasks/<id>/` обязательна
        (SPEC 01M1NBWTSXEJB24PXR417YF1VA, ANSWER-1, мандат `developer`) —
        иначе после исключения `tasks/<id>/` стейджить нечего, и `git
        diff` вообще не вызывается, а тест перестаёт проверять то, что
        называет."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.worktree_head()

        detail = self._run_with_failing_step("diff", 2)

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_git_commit_failure_commits_nothing_and_journals_nothing(self):
        """REVIEW.md T041 итерация 1, замечание minor: та же деградация
        для отказа самого `git commit`. Правка ВНЕ `tasks/<id>/` —
        тем же доводом, что у `test_git_diff_failure_...` выше: без неё
        `git diff --cached --quiet` сам вернул бы «нечего коммитить», и
        `git commit` не вызвался бы даже без мока."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.worktree_head()

        detail = self._run_with_failing_step("commit", 1)

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_non_dogfood_target_skips_checkpoint(self):
        """REVIEW.md T041 итерация 1, замечание major: для target'а,
        отличного от догфуда, чекпоинт — тихий no-op ДО первого `git
        add` (см. докстринг `commit_timeout_checkpoint` и PLAN «Риски») —
        `gitcmd.git` вообще не должен быть вызван."""
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.worktree_head()
        conn = store.db()
        store.update_task(conn, self.TASK, target="another-target")

        with mock.patch.object(gitcmd, "git") as git_mock:
            detail = checkpoint.commit_timeout_checkpoint(
                conn, self.TASK, "developer")

        git_mock.assert_not_called()
        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_developer_mandate_excludes_task_dir_from_code_commit(self):
        """SPEC 01M1NBWTSXEJB24PXR417YF1VA, AC-1 — изолированная версия:
        полное сценарное покрытие (правка отслеживаемого пути, новый
        путь, `tasks/<id>/` одновременно) уже несёт `tasks/
        01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/
        test_ac1_developer_mandate_all_paths_but_task_dir.py` — здесь
        только сама изоляция мандата `developer` как юнит-случай функции
        чекпоинта, тем же приёмом, что у соседних тестов файла."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописанный артефакт\n", encoding="utf-8")

        checkpoint.commit_timeout_checkpoint(store.db(), self.TASK, "developer")

        after = self.worktree_head()
        committed = self.worktree_git("show", "--name-only", "--format=", after)
        committed_paths = [p for p in committed.splitlines() if p]
        self.assertIn("orchestrator/new_module.py", committed_paths)
        task_paths = [p for p in committed_paths
                     if p.startswith(f"tasks/{self.TASK}/")]
        self.assertEqual(task_paths, [],
                         f"tasks/<id>/ не входит в мандат кода developer — "
                         f"фактически закоммичено: {task_paths}")

    def test_non_developer_role_discards_change_outside_task_dir(self):
        """SPEC 01M1NBWTSXEJB24PXR417YF1VA, AC-2/AC-3 — изолированная
        версия (полный сценарий — `tasks/01M1NBWTSXEJB24PXR417YF1VA/
        acceptance_tests/test_ac2_*.py`/`test_ac3_*.py`): правка
        отслеживаемого `CLAUDE.md` откачена, HEAD не сдвинут, детальный
        `commit_timeout_checkpoint` пуст (нечего коммитить в кодовую
        ветку), журнал называет путь и число отброшенных строк."""
        self.enter_in_dev()
        claude_md = self.wt / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(original + "строка 1\nстрока 2\n",
                             encoding="utf-8")
        before = self.worktree_head()

        detail = checkpoint.commit_timeout_checkpoint(
            store.db(), self.TASK, "reviewer")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(claude_md.read_text(encoding="utf-8"), original)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        marker = f"{entries[0]['action']} {entries[0]['detail']}"
        self.assertIn("CLAUDE.md", marker)
        self.assertIn("2", marker)


class CommitAbnormalCheckpointTest(_WorktreeCheckpointTest):
    """Юнит-тесты `checkpoint.commit_abnormal_checkpoint` (SPEC T074, требование
    3 — расширение правила T041: чекпоинт не только на таймауте, но и на
    аварийном завершении шага, rc != 0/обрыв потока)."""

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.worktree_head()

        detail = checkpoint.commit_abnormal_checkpoint(
            store.db(), self.TASK, "developer", "rc=1")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_with_cause_marker_in_message_and_journal(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = checkpoint.commit_abnormal_checkpoint(
            store.db(), self.TASK, "developer", "rc=1")

        subject = self.worktree_git("log", "-1", "--format=%s").strip()
        self.assertIn("чекпоинт", subject.lower())
        self.assertIn("rc=1", subject)
        self.assertIn(subject, detail)
        self.assertIn(self.worktree_head(), detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("чекпоинт", entries[0]["action"].lower())

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        checkpoint.commit_abnormal_checkpoint(
            store.db(), self.TASK, "developer", "обрыв потока")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def test_non_dogfood_target_skips_checkpoint(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.worktree_head()
        conn = store.db()
        store.update_task(conn, self.TASK, target="another-target")

        with mock.patch.object(gitcmd, "git") as git_mock:
            detail = checkpoint.commit_abnormal_checkpoint(
                conn, self.TASK, "developer", "rc=1")

        git_mock.assert_not_called()
        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])


class CommitPauseNowCheckpointTest(_WorktreeCheckpointTest):
    """Юнит-тесты `checkpoint.commit_pause_now_checkpoint` (SPEC T074,
    требования 1, 3 — чекпоинт `pause --now`, вызванный самой командой
    `orchestrator.pause.cmd_pause_now` из ДРУГОГО процесса, не из того,
    что исполняло прерванный шаг)."""

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.worktree_head()

        detail = checkpoint.commit_pause_now_checkpoint(
            store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_with_pause_now_marker(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = checkpoint.commit_pause_now_checkpoint(
            store.db(), self.TASK, "developer")

        subject = self.worktree_git("log", "-1", "--format=%s").strip()
        self.assertIn("pause --now", subject)
        self.assertIn(subject, detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("pause --now", entries[0]["action"])

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        checkpoint.commit_pause_now_checkpoint(store.db(), self.TASK, "developer")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def test_non_dogfood_target_skips_checkpoint(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.worktree_head()
        conn = store.db()
        store.update_task(conn, self.TASK, target="another-target")

        with mock.patch.object(gitcmd, "git") as git_mock:
            detail = checkpoint.commit_pause_now_checkpoint(
                conn, self.TASK, "developer")

        git_mock.assert_not_called()
        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])


if __name__ == "__main__":
    unittest.main()
