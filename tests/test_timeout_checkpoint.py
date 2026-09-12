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
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import checkpoint, config, fixation, gitcmd, runner, store, workspace  # noqa: E402
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
        # `workspace.ensure` заводящий НОВУЮ ветку задачи делает `git
        # fetch origin <MAIN_BRANCH>` (SPEC 01M297HFSKV3GVZJ9YF20FZEZE) —
        # `RealPultGitTest.config.ROOT` не несёт origin вовсе, локальный
        # (не Draft-MR-related) bare origin здесь нужен только затем,
        # чтобы fetch не отказывал.
        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        self.git("init", "-q", "--bare", str(origin))
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "origin",
                f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
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
        """Ловит мутацию: коммит чекпоинта пишется без сообщения/sha в
        `detail` или без записи в журнал — следующий `run` не смог бы
        объяснить Оператору, откуда взялся сдвиг HEAD ветки задачи после
        обрыва по таймауту (AC-6).

        Мандат `developer` — все пути кроме `tasks/<id>/`
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
        """Ловит мутацию: возврат `git diff --cached --quiet` вне {0,1}
        трактуется как «нечего коммитить» вместо «git не ответил» — код
        пошёл бы на `git commit` вслепую, не зная, застейджено ли что-то
        реально.

        REVIEW.md T041 итерация 1, замечание minor: тот же класс отказа
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
        """Ловит мутацию: отказ `git commit` (код возврата != 0) не
        проверяется — функция вернула бы `detail`/писала бы в журнал
        коммит, которого на самом деле нет, и следующий `check_integrity`
        сверялся бы с несуществующим sha.

        REVIEW.md T041 итерация 1, замечание minor: та же деградация
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
        """Ловит мутацию: `exclude` не передаётся в `_commit_worktree_
        change` (или передаётся, но `reset -q -- exclude` не вызывается) —
        `tasks/<id>/` попал бы в кодовый коммит `developer` наравне с
        `orchestrator/new_module.py`, нарушая AC-1.

        SPEC 01M1NBWTSXEJB24PXR417YF1VA, AC-1 — изолированная версия:
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
        """Ловит мутацию: `_discard_out_of_mandate_changes` не вызывается
        для не-`developer` роли (или вызывается, но не реально откатывает
        трекенный путь через `checkout --`) — правка `CLAUDE.md` осталась
        бы в рабочем дереве незамеченной, AC-2 не выполняется.

        SPEC 01M1NBWTSXEJB24PXR417YF1VA, AC-2/AC-3 — изолированная
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

    def test_discard_of_renamed_file_out_of_mandate_restores_the_source(self):
        """Ловит мутацию: git-статус `R` (staged rename) обрабатывается как
        трекенный путь (`checkout --` по НЕСУЩЕСТВУЮЩЕМУ в HEAD пути
        назначения) вместо как новый — REVIEW.md итерация 3, R1-F1,
        независимо воспроизведено там же: `git mv tasks/<id>/foo.py
        orchestrator_new.py` → путь назначения остаётся на диске
        незамеченным (`checkout` молча проваливается на pathspec без
        истории), а путь ИСТОЧНИК внутри `tasks/<id>/` физически теряется
        (git mv переместил файл, и без отдельного восстановления назад
        он не возвращается) — порча самого каталога задачи в придачу к
        невыполненному AC-2. Проверяется саму функцию `_discard_out_of_
        mandate_changes` напрямую (изолированно, тем же приёмом, что и
        REVIEW.md итерация 3, R1-F1 репро) — вызов через
        `commit_timeout_checkpoint` следом отдельным шагом переносит
        `tasks/<id>/` в артефактную ветку (AC-4, для любой роли) и
        замёл бы восстановленный файл с локального диска, что не имеет
        отношения к самому предмету этого замечания."""
        self.enter_in_dev()
        foo = self.worktree_task_dir() / "foo.py"
        original = "# файл артефактов роли\n"
        foo.write_text(original, encoding="utf-8")
        self.worktree_git("add", f"tasks/{self.TASK}/foo.py")
        self.worktree_git("commit", "-q", "-m", "seed foo.py")

        self.worktree_git("mv", f"tasks/{self.TASK}/foo.py",
                          "orchestrator_new.py")

        discarded = checkpoint._discard_out_of_mandate_changes(
            self.wt, self.TASK)

        self.assertFalse((self.wt / "orchestrator_new.py").exists(),
                         "путь назначения переименования вне мандата "
                         "обязан быть отброшен")
        self.assertTrue(foo.is_file(),
                        "путь-источник внутри tasks/<id>/ обязан быть "
                        "восстановлен, а не потерян физически")
        self.assertEqual(foo.read_text(encoding="utf-8"), original)
        self.assertIn("orchestrator_new.py", discarded)
        self.assertNotIn("foo.py", discarded,
                         "источник восстановлен, а не отброшен — не должен "
                         "числиться в журнальной строке отброшенных путей")


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
        """Мандат `developer` — все пути кроме `tasks/<id>/` (см. докстринг
        `commit_timeout_checkpoint`, тот же приём здесь: R1-F1, REVIEW.md
        итерация 2): правка ВНЕ `tasks/<id>/` нужна, чтобы код-коммит
        вообще состоялся — WIP, оставленный только в `tasks/<id>/`,
        переносится в артефактную ветку отдельно (см. тест ниже)."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
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

    def test_developer_mandate_excludes_task_dir_from_code_commit(self):
        """Ловит мутацию: `exclude` не передаётся `_commit_worktree_change`
        (REVIEW.md 01M1NKTF173WV5CPDZ1C3WW69K итерация 2, R1-F1 —
        переоткрыт: правка `commit_timeout_checkpoint` не была применена
        к этой функции, `tasks/<id>/` попадал в кодовый коммит `developer`
        на аварийном завершении шага)."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописанный артефакт\n", encoding="utf-8")

        checkpoint.commit_abnormal_checkpoint(
            store.db(), self.TASK, "developer", "rc=1")

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
        """Ловит мутацию: `_discard_out_of_mandate_changes` не вызывается
        для не-`developer` роли на аварийном завершении шага (тот же класс
        R1-F1, что и у `commit_timeout_checkpoint`, теперь и здесь)."""
        self.enter_in_dev()
        claude_md = self.wt / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(original + "строка 1\nстрока 2\n",
                             encoding="utf-8")
        before = self.worktree_head()

        detail = checkpoint.commit_abnormal_checkpoint(
            store.db(), self.TASK, "reviewer", "rc=1")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(claude_md.read_text(encoding="utf-8"), original)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        marker = f"{entries[0]['action']} {entries[0]['detail']}"
        self.assertIn("CLAUDE.md", marker)
        self.assertIn("2", marker)

    def test_materialized_spec_is_absent_from_the_code_branch_after_abnormal_end(self):
        """Регресс-тест точного репро ревьювера (REVIEW.md итерация 2,
        R1-F1, «Проверено исполнением»): материализованный `role_cwd`
        SPEC.md роли `reviewer` (нет мандата кода) не обязан попасть в
        кодовую ветку на аварийном завершении шага."""
        self.enter_in_dev()

        materialized_path = runner.role_cwd(store.db(), self.TASK,
                                            config.DEFAULT_TARGET)
        self.assertEqual(materialized_path, self.wt)
        self.assertTrue(
            (self.wt / "tasks" / self.TASK / "SPEC.md").exists(),
            "role_cwd обязан материализовать SPEC.md из артефактной ветки")

        checkpoint.commit_abnormal_checkpoint(
            store.db(), self.TASK, "reviewer", "rc=1")

        tracked = self.worktree_git("ls-tree", "-r", "--name-only", "HEAD")
        self.assertNotIn(f"tasks/{self.TASK}/SPEC.md", tracked.splitlines())


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
        """Мандат `developer` — все пути кроме `tasks/<id>/` (см. докстринг
        `commit_timeout_checkpoint`, тот же приём здесь: R1-F1, REVIEW.md
        итерация 2): правка ВНЕ `tasks/<id>/` нужна, чтобы код-коммит
        вообще состоялся."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
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

    def test_developer_mandate_excludes_task_dir_from_code_commit(self):
        """Ловит мутацию: `exclude` не передаётся `_commit_worktree_change`
        (REVIEW.md 01M1NKTF173WV5CPDZ1C3WW69K итерация 2, R1-F1 —
        переоткрыт: `tasks/<id>/` попадал в кодовый коммит `developer` на
        `pause --now`)."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописанный артефакт\n", encoding="utf-8")

        checkpoint.commit_pause_now_checkpoint(
            store.db(), self.TASK, "developer")

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
        """Ловит мутацию: `_discard_out_of_mandate_changes` не вызывается
        для не-`developer` роли на `pause --now` (тот же класс R1-F1, что
        и у `commit_timeout_checkpoint`, теперь и здесь)."""
        self.enter_in_dev()
        claude_md = self.wt / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(original + "строка 1\nстрока 2\n",
                             encoding="utf-8")
        before = self.worktree_head()

        detail = checkpoint.commit_pause_now_checkpoint(
            store.db(), self.TASK, "reviewer")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(claude_md.read_text(encoding="utf-8"), original)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        marker = f"{entries[0]['action']} {entries[0]['detail']}"
        self.assertIn("CLAUDE.md", marker)
        self.assertIn("2", marker)

    def test_materialized_spec_is_absent_from_the_code_branch_after_pause_now(self):
        """Регресс-тест точного репро ревьювера (REVIEW.md итерация 2,
        R1-F1, «Проверено исполнением»): материализованный `role_cwd`
        SPEC.md роли `reviewer` (нет мандата кода) не обязан попасть в
        кодовую ветку на `pause --now`."""
        self.enter_in_dev()

        materialized_path = runner.role_cwd(store.db(), self.TASK,
                                            config.DEFAULT_TARGET)
        self.assertEqual(materialized_path, self.wt)
        self.assertTrue(
            (self.wt / "tasks" / self.TASK / "SPEC.md").exists(),
            "role_cwd обязан материализовать SPEC.md из артефактной ветки")

        checkpoint.commit_pause_now_checkpoint(
            store.db(), self.TASK, "reviewer")

        tracked = self.worktree_git("ls-tree", "-r", "--name-only", "HEAD")
        self.assertNotIn(f"tasks/{self.TASK}/SPEC.md", tracked.splitlines())


class RoleCwdMaterializationSurvivesTimeoutCheckpointTest(_WorktreeCheckpointTest):
    """Регресс-тест на точную репродукцию R1-F1 (REVIEW.md итерации 1,
    blocker): `artifact_branch.commit_files` сеет SPEC.md в артефактную
    ветку → `runner.role_cwd` материализует его в worktree self-target'а
    → `checkpoint.commit_timeout_checkpoint` — материализованный, ещё
    ничем не изменённый ролью артефакт не обязан попасть в кодовую ветку
    `task/*` этим коммитом (SPEC 01M1NKTF173WV5CPDZ1C3WW69K, требование
    3/AC-9). До фикса `git ls-tree -r HEAD` этого worktree после
    чекпоинта содержал `tasks/<TASK>/SPEC.md` — ровно тот сценарий,
    которым дефект был живьём воспроизведён при ревью."""

    def test_materialized_spec_is_absent_from_the_code_branch_after_timeout(self):
        self.enter_in_dev()

        materialized_path = runner.role_cwd(store.db(), self.TASK,
                                            config.DEFAULT_TARGET)
        self.assertEqual(materialized_path, self.wt)
        self.assertTrue(
            (self.wt / "tasks" / self.TASK / "SPEC.md").exists(),
            "role_cwd обязан материализовать SPEC.md из артефактной ветки")
        # Настоящий WIP вне tasks/<id>/, чтобы чекпоинт реально что-то
        # закоммитил — иначе тест доказывал бы только «ничего не
        # закоммичено», не саму фильтрацию (см. следующий коммент теста).
        (self.wt / "wip.md").write_text("недописано\n", encoding="utf-8")

        detail = checkpoint.commit_timeout_checkpoint(store.db(), self.TASK,
                                                       "developer")

        self.assertTrue(detail, "чекпоинт обязан закоммитить wip.md")
        tracked = self.worktree_git("ls-tree", "-r", "--name-only", "HEAD")
        self.assertNotIn(f"tasks/{self.TASK}/SPEC.md", tracked.splitlines())
        self.assertIn("wip.md", tracked.splitlines())


class CommitPullCheckpointTest(_WorktreeCheckpointTest):
    """Юнит-тесты `checkpoint.commit_pull_checkpoint` (SPEC
    01M1RA0R9AH9RBAHD4A2Z5SEWQ, требование 2): WIP-чекпоинт worktree
    задачи перед `git merge` в `fsm._pull_main_or_escalate` — сценарное
    покрытие целиком (очистка карты + классификация отказа merge) уже
    несут `tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/acceptance_tests/`; здесь —
    изолированные случаи самой функции чекпоинта, тем же приёмом, что и
    соседние классы файла."""

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.worktree_head()

        detail = checkpoint.commit_pull_checkpoint(store.db(), self.TASK, self.wt)

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])

    def test_dirty_tree_commits_with_message_sha_and_journal_entry(self):
        """Мандат `developer` — все пути кроме `tasks/<id>/` (тот же приём,
        что у `commit_timeout_checkpoint`): правка ВНЕ `tasks/<id>/` нужна,
        чтобы код-коммит вообще состоялся."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = checkpoint.commit_pull_checkpoint(store.db(), self.TASK, self.wt)

        subject = self.worktree_git("log", "-1", "--format=%s").strip()
        self.assertEqual(subject, f"{self.TASK}: WIP-чекпоинт перед подтяжкой main")
        self.assertIn(subject, detail)
        self.assertIn(self.worktree_head(), detail)

        entries = self.orchestrator_steps()
        self.assertEqual(len(entries), 1)
        self.assertIn("подтяжк", entries[0]["action"].lower())

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        checkpoint.commit_pull_checkpoint(store.db(), self.TASK, self.wt)

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def test_excludes_task_dir_from_code_commit(self):
        """Ловит мутацию: `exclude` не передаётся `_commit_worktree_change` —
        `tasks/<id>/` попал бы в кодовый коммит перед подтяжкой наравне с
        `orchestrator/new_module.py`."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописанный артефакт\n", encoding="utf-8")

        checkpoint.commit_pull_checkpoint(store.db(), self.TASK, self.wt)

        after = self.worktree_head()
        committed = self.worktree_git("show", "--name-only", "--format=", after)
        committed_paths = [p for p in committed.splitlines() if p]
        self.assertIn("orchestrator/new_module.py", committed_paths)
        task_paths = [p for p in committed_paths
                     if p.startswith(f"tasks/{self.TASK}/")]
        self.assertEqual(task_paths, [],
                         f"tasks/<id>/ не входит в мандат кода — "
                         f"фактически закоммичено: {task_paths}")

    def test_git_add_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.worktree_head()
        real_git = gitcmd.git

        def side_effect(*args):
            if "add" in args:
                return subprocess.CompletedProcess(list(args), 1, "", "boom")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=side_effect):
            detail = checkpoint.commit_pull_checkpoint(store.db(), self.TASK, self.wt)

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.orchestrator_steps(), [])


class CommitSuccessCheckpointTest(_WorktreeCheckpointTest):
    """Юнит-тесты `checkpoint.commit_success_checkpoint` (SPEC
    01M283NC4JJXK7QS68Y9ET8TBK, требования 1-5): WIP-коммит кода пультом
    за роль `developer` на обычном успешном (`rc=0`) завершении шага —
    сценарное покрытие целиком (весь шаг через `run_faked()`) уже несут
    `tasks/01M283NC4JJXK7QS68Y9ET8TBK/acceptance_tests/`; здесь —
    изолированные случаи самой функции чекпоинта, тем же приёмом, что и
    соседние классы файла.

    `orchestrator_steps()` родителя фильтрует по действию, начинающемуся
    с «WIP-чекпоинт» — действие этого чекпоинта другое (буквально «код
    закоммичен пультом за роль», AC-3), поэтому здесь свой фильтр."""

    def success_checkpoint_steps(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"
               and r["action"] == "код закоммичен пультом за роль"]

    def test_clean_tree_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        before = self.worktree_head()

        detail = checkpoint.commit_success_checkpoint(
            store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.success_checkpoint_steps(), [])

    def test_dirty_tree_commits_with_literal_message_and_journal_entry(self):
        """Ловит мутацию: сообщение коммита переиспользует текст соседнего
        WIP-чекпоинта вместо буквальной строки AC-2, или `detail`/журнал
        не называют закоммиченный файл и число строк (AC-3)."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "строка 1\nстрока 2\nстрока 3\nстрока 4\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")

        detail = checkpoint.commit_success_checkpoint(
            store.db(), self.TASK, "developer")

        subject = self.worktree_git("log", "-1", "--format=%s").strip()
        expected = (f"{self.TASK}: код закоммичен пультом за роль "
                   "developer — шаг завершён с незакоммиченным кодом")
        self.assertEqual(subject, expected)
        self.assertIn(self.worktree_head(), detail)
        self.assertIn("orchestrator/new_module.py", detail)
        self.assertIn("4", detail)

        entries = self.success_checkpoint_steps()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["actor"], "orchestrator")
        self.assertIn("orchestrator/new_module.py", entries[0]["detail"])
        self.assertIn("4", entries[0]["detail"])

    def test_excludes_task_dir_from_code_commit(self):
        """Ловит мутацию: `exclude` не передаётся `_commit_worktree_change` —
        `tasks/<id>/` попал бы в кодовый коммит наравне с
        `orchestrator/new_module.py`."""
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописанный артефакт\n", encoding="utf-8")

        checkpoint.commit_success_checkpoint(store.db(), self.TASK, "developer")

        after = self.worktree_head()
        committed = self.worktree_git("show", "--name-only", "--format=", after)
        committed_paths = [p for p in committed.splitlines() if p]
        self.assertIn("orchestrator/new_module.py", committed_paths)
        task_paths = [p for p in committed_paths
                     if p.startswith(f"tasks/{self.TASK}/")]
        self.assertEqual(task_paths, [],
                         f"tasks/<id>/ не входит в мандат кода — "
                         f"фактически закоммичено: {task_paths}")

    def test_refixation_keeps_check_integrity_clean_after_the_commit(self):
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")

        checkpoint.commit_success_checkpoint(store.db(), self.TASK, "developer")

        conn = store.db()
        self.assertIsNone(fixation.check_integrity(conn, self.TASK))
        self.assertEqual(store.get_task(conn, self.TASK)["fixed_sha"],
                         self.head())

    def test_non_developer_role_is_left_untouched_not_discarded(self):
        """AC-5: в отличие от трёх аварийных WIP-чекпоинтов, роль без
        мандата кода не получает здесь НИ отката, НИ коммита — «прежнее
        поведение» для обычного успешного пути было полным отсутствием
        эффекта (ни один из аварийных чекпоинтов не срабатывает вне
        таймаута/rc!=0/обрыва потока)."""
        self.enter_in_dev()
        claude_md = self.wt / "CLAUDE.md"
        original = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(original + "строка 1\nстрока 2\n",
                             encoding="utf-8")
        before = self.worktree_head()

        detail = checkpoint.commit_success_checkpoint(
            store.db(), self.TASK, "reviewer")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(claude_md.read_text(encoding="utf-8"),
                         original + "строка 1\nстрока 2\n",
                         "AC-5: правка вне мандата не должна быть откачена")
        self.assertEqual(self.success_checkpoint_steps(), [])

    def test_non_dogfood_target_skips_checkpoint(self):
        self.enter_in_dev()
        (self.worktree_task_dir() / "wip.md").write_text(
            "недописано\n", encoding="utf-8")
        before = self.worktree_head()
        conn = store.db()
        store.update_task(conn, self.TASK, target="another-target")

        with mock.patch.object(gitcmd, "git") as git_mock:
            detail = checkpoint.commit_success_checkpoint(
                conn, self.TASK, "developer")

        git_mock.assert_not_called()
        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.success_checkpoint_steps(), [])

    def test_git_add_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        before = self.worktree_head()
        real_git = gitcmd.git

        def side_effect(*args):
            if "add" in args:
                return subprocess.CompletedProcess(list(args), 1, "", "boom")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=side_effect):
            detail = checkpoint.commit_success_checkpoint(
                store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.success_checkpoint_steps(), [])

    def test_git_commit_failure_commits_nothing_and_journals_nothing(self):
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        before = self.worktree_head()
        real_git = gitcmd.git

        def side_effect(*args):
            if "commit" in args:
                return subprocess.CompletedProcess(list(args), 1, "", "boom")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=side_effect):
            detail = checkpoint.commit_success_checkpoint(
                store.db(), self.TASK, "developer")

        self.assertEqual(detail, "")
        self.assertEqual(self.worktree_head(), before)
        self.assertEqual(self.success_checkpoint_steps(), [])


if __name__ == "__main__":
    unittest.main()
