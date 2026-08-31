"""Тесты уборки хвостов убитой задачи (см. tasks/T008/SPEC.md).

Git тут настоящий, но не рабочий: ROOT уводится во временный репозиторий
с копией templates/ и .gitignore, задачи в нём создаёт сам оркестратор.
Так проверяются реальные ответы git (`ls-tree`, `branch --merged`), а
рабочее дерево репозитория остаётся нетронутым.

С SPEC T048 `catalog.cmd_new` сам заводит ветку и worktree задачи (T045)
и сразу коммитит в них SPEC.md (и TZ.md, если был) — main эти файлы
никогда не видит (требование 4). Поэтому сразу после `new` в `self.root`
(main) `tasks/<id>/` не существует вовсе, а ветка и worktree задачи уже
на месте с одним коммитом; сценарии ниже, которым нужны артефакты НА
MAIN (симуляция инцидента T002 — каталог подобран в чужую ветку/индекс,
или задача убита до слияния), заводят их сами явной записью на диск, а
сценариям, которым нужен ДОПОЛНИТЕЛЬНЫЙ коммит поверх того, что уже
сделал `new`, коммитят его В WORKTREE задачи (`git -C <worktree>`), а не
чекаутом ветки задачи в ROOT — ветку и так держит worktree, второй
чекаут той же ветки git не даст сделать (SPEC T045).

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002, принцип целостности): кодируют инварианты
«kill switch срабатывает всегда» и «артефакты, попавшие в main, — история
и не удаляются» (docs/design.md §6). Ослабить, заскипать или удалить их
может только Оператор отдельным ADR; перечень «инвариант → тест →
откуда» — docs/invariants.md.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (agent_log, catalog, cleanup, config,  # noqa: E402
                          gitcmd, store, workspace)
from tests.sandbox import capture, resilient_tmp_cleanup  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


class TmpRepoTest(unittest.TestCase):
    """Задача T001 в свежем временном репозитории с веткой main; `new`
    уже завела ветку/worktree задачи и закоммитила в них SPEC.md (SPEC
    T048) — main остаётся чистым."""

    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        # resolve(): на macOS /var — симлинк на /private/var, а `git
        # rev-parse` и Path сравниваются как строки.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-m", "init")

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("WORKTREES", self.root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Очистка хвостов задачи")
        self.branch = self.task_row()["branch"]

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res.stdout

    def git_wt(self, *args: str) -> str:
        """git прямо в worktree задачи — не чекаутом её ветки в ROOT
        (ветку и так держит worktree, SPEC T045)."""
        res = subprocess.run(["git", "-C", str(workspace.path(self.TASK)),
                              *args], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git -C worktree {' '.join(args)} упал: {res.stderr}")
        return res.stdout

    def commit_more_in_worktree(self, rel: str, text: str, message: str) -> None:
        """Ещё один коммит поверх того, что уже сделал `new` — как если
        бы роль продолжила работу в своём worktree (SPEC T045)."""
        p = workspace.path(self.TASK) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        self.git_wt("add", "-A")
        self.git_wt("commit", "-m", message)

    def seed_main_task_dir(self, name: str = "SPEC.md",
                           text: str = "подобрано") -> None:
        """Кладёт файл в `tasks/<id>/` НА MAIN напрямую — симуляция
        инцидента T002 (каталог убитой задачи оказался в main руками
        Оператора или роли), не через `new` (он туда больше не пишет,
        требование 4)."""
        self.task_dir().mkdir(parents=True, exist_ok=True)
        (self.task_dir() / name).write_text(text, encoding="utf-8")

    capture = staticmethod(capture)

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def task_dir(self) -> Path:
        return config.TASKS / self.TASK

    def cleanup_note(self) -> str:
        """Последняя запись журнала об уборке."""
        rows = store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action='уборка'"
            " ORDER BY id", (self.TASK,)).fetchall()
        self.assertTrue(rows, "уборка не попала в журнал")
        return rows[-1]["detail"]

    def branches(self) -> list[str]:
        return self.git("branch", "--format=%(refname:short)").split()


class KillCleanupTest(TmpRepoTest):
    """`kill <id>` убирает worktree, каталог артефактов в main и локальную
    ветку задачи."""

    def test_task_killed_before_commit_leaves_no_trace(self):
        """Критерий приёмки 1: сценарий T002 — new, kill, чистое дерево
        main. С SPEC T048 `new` уже коммитит SPEC.md сразу в ветку/
        worktree задачи, не в main (требование 4) — main тут нечего
        подчищать, он и так чист."""
        self.assertFalse(self.task_dir().exists(), "new не трогает main")
        self.assertTrue(workspace.path(self.TASK).exists(), "new завела worktree")

        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertFalse(self.task_dir().exists())
        self.assertFalse(workspace.path(self.TASK).exists())
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.task_row()["state"], "killed")
        self.assertNotIn(self.branch, self.branches())

    def test_branch_only_artifacts_and_branch_are_removed(self):
        # Черновик, написанный агентом после коммита `new`: не отслеживается, и
        # каталог задачи переживает переключение на main вместе с ним.
        self.seed_main_task_dir("PLAN.md", "черновик")

        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertFalse(self.task_dir().exists())
        self.assertNotIn(self.branch, self.branches())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_kill_removes_task_worktree_before_the_branch(self):
        """SPEC T045, требование 5, AC-5: `-D` не удалит ветку, пока её
        держит worktree — уборка обязана снести worktree первой. `new`
        (SPEC T048) уже завела worktree сама — незачем заводить второй."""
        wt_path = workspace.path(self.TASK)
        self.assertTrue(wt_path.exists())

        out = self.capture(cleanup.cmd_kill, self.TASK)

        self.assertFalse(wt_path.exists(), "worktree обязан быть убран")
        self.assertNotIn(str(wt_path), self.git("worktree", "list"))
        self.assertNotIn(self.branch, self.branches(),
                         "ветку не убрать, пока её держит worktree")
        self.assertIn(f"убран worktree {wt_path}", out)

    def test_merged_task_keeps_artifacts_and_branch(self):
        """Критерий приёмки 2: артефакты в main — не трогаем ничего."""
        self.git("merge", "--no-ff", self.branch, "-m", "merge")

        out = self.capture(cleanup.cmd_kill, self.TASK)

        self.assertTrue((self.task_dir() / "SPEC.md").exists())
        self.assertIn(self.branch, self.branches())
        self.assertIn("артефакты в main", out)
        self.assertIn(f"ветка {self.branch} оставлена: смержена в main", out)

    def test_unmerged_branch_is_removed_even_when_artifacts_are_in_main(self):
        """Условия требования 1 независимы: ветка ушла вперёд после мержа."""
        self.git("merge", "--no-ff", self.branch, "-m", "merge")
        self.commit_more_in_worktree("tasks/T001/PLAN.md", "после мержа",
                                     f"{self.TASK}: PLAN")

        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertTrue((self.task_dir() / "SPEC.md").exists(), "история в main")
        self.assertNotIn(self.branch, self.branches())

    def test_dir_committed_into_a_foreign_branch_is_left_alone(self):
        """Инцидент из SPEC: каталог убитой задачи уехал в чужую ветку."""
        self.seed_main_task_dir()
        self.git("checkout", "-b", "task/t042-chuzhaya")
        self.git("add", "-A")
        self.git("commit", "-m", "T042: подобрал чужой каталог")

        out = self.capture(cleanup.cmd_kill, self.TASK)

        self.assertTrue((self.task_dir() / "SPEC.md").exists())
        self.assertEqual(self.git("status", "--porcelain"), "",
                         "снести отслеживаемый каталог — оставить грязное дерево")
        self.assertIn("отслеживается в task/t042-chuzhaya", out)
        self.assertIn("перейди на main и повтори kill", out)

    def test_dir_staged_on_main_is_left_alone(self):
        """Тот же риск без коммита: каталог задачи добавлен в индекс main."""
        self.seed_main_task_dir()
        self.git("add", "-A")

        out = self.capture(cleanup.cmd_kill, self.TASK)

        self.assertTrue((self.task_dir() / "SPEC.md").exists())
        self.assertIn("отслеживается в main — сними его из индекса", out)

    def test_cleanup_is_listed_in_the_journal(self):
        """Требование 2: по журналу видно, что именно убрано."""
        self.seed_main_task_dir()

        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(
            self.cleanup_note(),
            f"убран worktree {workspace.path(self.TASK)}; удалён каталог "
            f"tasks/{self.TASK}/; удалена ветка {self.branch}")
        self.assertIn("удалён каталог", self.capture(catalog.cmd_log, self.TASK))

    def test_run_logs_survive_the_kill(self):
        """Требование 4: история наблюдаемости переживает задачу."""
        log = agent_log.new_agent_log(self.TASK, "developer")
        log.write_text("шаг разработчика\n", encoding="utf-8")

        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertTrue(log.exists())
        self.assertEqual(log.read_text(encoding="utf-8"), "шаг разработчика\n")

    def test_repeated_kill_finds_nothing_and_does_not_fail(self):
        """Требование 3: повтор — это пустая уборка, а не падение."""
        self.capture(cleanup.cmd_kill, self.TASK)

        out = self.capture(cleanup.cmd_kill, self.TASK)

        self.assertEqual(self.task_row()["state"], "killed")
        self.assertIn(f"каталога tasks/{self.TASK}/ нет", out)
        self.assertIn(f"локальной ветки {self.branch} нет", out)

    def test_unknown_task_is_reported(self):
        with self.assertRaises(SystemExit) as exit_:
            self.capture(cleanup.cmd_kill, "T404")

        self.assertIn("не найдена", str(exit_.exception))

    def test_checked_out_branch_is_left_alone_until_the_next_kill(self):
        # Ветку держит worktree, заведённый `new` (SPEC T045/T048) — снять
        # его первым, иначе второй чекаут той же ветки в ROOT git не даст
        # сделать; дальше воспроизводим ровно сценарий «Оператор руками
        # зачекаутил ветку задачи в главной копии».
        self.git("worktree", "remove", "--force", str(workspace.path(self.TASK)))
        self.git("checkout", self.branch)

        out = self.capture(cleanup.cmd_kill, self.TASK)

        self.assertTrue((self.task_dir() / "SPEC.md").exists(),
                        "снести закоммиченный каталог — оставить грязное дерево")
        self.assertIn(self.branch, self.branches())
        self.assertIn("перейди на main и повтори kill", out)
        self.assertIn("checked out", self.cleanup_note())

        self.git("checkout", config.MAIN_BRANCH)
        self.capture(cleanup.cmd_kill, self.TASK)

        self.assertNotIn(self.branch, self.branches(), "повтор доводит уборку")
        self.assertFalse(self.task_dir().exists())


class CleanupWithoutGitTest(TmpRepoTest):
    """git промолчал — уборка ничего не трогает и говорит об этом."""

    def test_missing_main_stops_the_cleanup(self):
        self.seed_main_task_dir()
        self.git("checkout", "-b", "other")
        self.git("branch", "-D", config.MAIN_BRANCH)

        out = self.capture(cleanup.cmd_kill, self.TASK)

        self.assertTrue(self.task_dir().exists(), "сверять не с чем — не трогаем")
        self.assertIn("уборка пропущена: ветки main нет", out)

    def test_unreadable_main_tree_keeps_the_dir(self):
        """main на месте, но `ls-tree` ответил ошибкой: сверять по-прежнему не с чем."""
        self.seed_main_task_dir()

        out = self.capture_with_failing_git("ls-tree", cleanup.cmd_kill, self.TASK)

        self.assertTrue(self.task_dir().exists())
        self.assertIn(f"каталог tasks/{self.TASK}/ оставлен: main не прочитан",
                      out)

    def test_unreadable_index_keeps_the_dir(self):
        """`ls-files` промолчал — отслеживается каталог или нет, неизвестно."""
        self.seed_main_task_dir()

        out = self.capture_with_failing_git("ls-files", cleanup.cmd_kill, self.TASK)

        self.assertTrue(self.task_dir().exists())
        self.assertIn(f"каталог tasks/{self.TASK}/ оставлен: индекс не прочитан",
                      out)

    def capture_with_failing_git(self, subcommand: str, fn, *args) -> str:
        """Прогон, в котором одна git-подкоманда отвечает ошибкой."""
        real_git = gitcmd.git

        def flaky(*git_args: str):
            if git_args and git_args[0] == subcommand:
                return subprocess.CompletedProcess(
                    git_args, 128, "", f"fatal: {subcommand} не отвечает")
            return real_git(*git_args)

        with mock.patch.object(gitcmd, "git", flaky):
            return self.capture(fn, *args)

    def test_unavailable_git_stops_the_cleanup(self):
        self.seed_main_task_dir()

        with mock.patch.object(gitcmd.subprocess, "run",
                               side_effect=OSError("git не найден")):
            out = self.capture(cleanup.cmd_kill, self.TASK)

        self.assertTrue(self.task_dir().exists())
        self.assertIn("git не найден", out, "в журнале видно настоящую причину")
        self.assertEqual(self.task_row()["state"], "killed",
                         "kill switch срабатывает и без git")


if __name__ == "__main__":
    unittest.main()
