"""Механизм границы git роли `orchestrator/role_git.py` и проверка набора
`task-rm` (`orchestrator/task_files.py`) — чистые функции, без запуска git
(SPEC 01M6JJ4J4NBV2Y1Q4XHE3C3FVT, требования 2–4, 10). Исход настоящих
вызовов git под окружением роли проверяет планка задачи."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import role_git, task_files

TASK = "01MOWNTASK"


class RepoPathsTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(os.path.realpath(tmp.name))
        (self.base / "a" / "b").mkdir(parents=True)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.base)

    def paths(self, args, env=None):
        with mock.patch.dict(os.environ, env or {}, clear=False):
            for name in ("GIT_DIR", "GIT_WORK_TREE"):
                if not env or name not in env:
                    os.environ.pop(name, None)
            opts, _idx = role_git.parse(args)
            return role_git.repo_paths(opts, role_git.command_line_config(opts))

    def test_each_relative_dash_c_is_relative_to_the_previous_one(self):
        """`-C a -C b` — `<cwd>/a/b`, как цепочка `chdir` у git.

        Ловит мутацию: учитывается только первый `-C` либо относительный
        `-C` разрешается от исходного каталога — путь вызова `<cwd>/a` или
        `<cwd>/b`.
        """
        self.assertEqual(self.paths(["-C", "a", "-C", "b", "status"])[0],
                         str(self.base / "a" / "b"))

    def test_git_dir_and_work_tree_are_resolved_after_dash_c(self):
        """`--git-dir`/`--work-tree` и `GIT_WORK_TREE` — пути вызова, от каталога после `-C`.

        Ловит мутацию: механизм не читает `--git-dir`/`GIT_WORK_TREE` — пути
        вызова только текущий каталог.
        """
        paths = self.paths(["-C", "a", "--git-dir=b", "status"],
                           {"GIT_WORK_TREE": "../x"})
        self.assertIn(str(self.base / "a" / "b"), paths)
        self.assertIn(str(self.base / "x"), paths)

    def test_core_worktree_from_config_parameters_is_a_path(self):
        """`core.worktree` из `GIT_CONFIG_PARAMETERS` — путь вызова.

        Ловит мутацию: `core.worktree` читается только из `-c` — значение из
        переменной окружения в путях вызова отсутствует.
        """
        paths = self.paths(["status"], {
            "GIT_CONFIG_PARAMETERS": f"'core.worktree'='{self.base / 'a'}'"})
        self.assertIn(str(self.base / "a"), paths)


class ClassifyTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = os.path.realpath(tmp.name)
        self.projects = os.path.join(self.root, ".artel", "projects", "p")
        for sub in ("repo", f"worktrees/{TASK}", "worktrees/OTHER", "tasks"):
            os.makedirs(os.path.join(self.projects, sub))

    def kind(self, rel, task=TASK):
        return role_git.classify(os.path.join(self.root, rel), [self.root], task)[0]

    def test_own_copy_and_its_clone_pass_other_paths_refused(self):
        """Своя копия и клон её проекта — «own», чужая копия — «foreign», прочее в корне — «pult».

        Ловит мутацию: путь сравнивается с корнем на равенство, а не на
        вложенность (`docs` и `.artel` — «outside»); своя копия не исключена
        («pult»); клон проекта не признан своим.
        """
        self.assertEqual(self.kind(f".artel/projects/p/worktrees/{TASK}/sub"), "own")
        self.assertEqual(self.kind(".artel/projects/p/repo/.git"), "own")
        self.assertEqual(self.kind(".artel/projects/p/worktrees/OTHER/x"), "foreign")
        self.assertEqual(self.kind(".artel/projects/p/tasks"), "pult")
        self.assertEqual(self.kind("docs"), "pult")
        self.assertEqual(self.kind(""), "pult")
        self.assertEqual(role_git.classify("/nonexistent-outside", [self.root], TASK)[0],
                         "outside")

    def test_without_task_every_copy_is_foreign_and_clone_is_pult(self):
        """Без `ARTEL_TASK` своей копии нет: копия — «foreign», клон — «pult».

        Ловит мутацию: отсутствие задачи открывает все рабочие копии и клон
        (fail-open) — вид «own».
        """
        self.assertEqual(self.kind(f".artel/projects/p/worktrees/{TASK}", None), "foreign")
        self.assertEqual(self.kind(".artel/projects/p/repo", None), "pult")

    def test_env_root_only_adds_to_the_wrapper_root(self):
        """`ARTEL_GIT_GUARD_ROOT` добавляет корень, корень обёртки остаётся.

        Ловит мутацию: переменная заменяет корень от расположения обёртки —
        в перечне нет корня `role_bin/../..`.
        """
        wrapper_dir = os.path.join(self.root, "orchestrator", "role_bin")
        with mock.patch.dict(os.environ, {role_git.GUARD_ROOT_ENV: "/elsewhere"}):
            roots = role_git.protected_roots(wrapper_dir)
        self.assertIn(self.root, roots)
        self.assertIn(os.path.realpath("/elsewhere"), roots)


class ConfigRefusalTest(unittest.TestCase):

    def test_alias_chain_to_clean_and_bang_alias_are_refused(self):
        """Псевдоним, раскрывающийся в `clean` через цепочку, и любой `!`-псевдоним — отказ.

        Ловит мутацию: раскрывается только один уровень псевдонима (`a → b →
        clean` проходит) либо отказ `!`-псевдонима только при `clean` в его
        теле (`!echo ok` проходит).
        """
        config = [("alias.a", "--paginate b"), ("alias.b", "clean -fX"),
                  ("alias.x", "!echo ok"), ("alias.st", "status")]
        self.assertIsNotNone(role_git._alias_refusal("a", config))
        self.assertIsNotNone(role_git._alias_refusal("x", config))
        self.assertIsNone(role_git._alias_refusal("st", config))
        self.assertIsNone(role_git._alias_refusal("log", config))

    def test_pager_calling_git_refused_plain_pager_passes(self):
        """`core.pager`/`pager.<cmd>`/`GIT_PAGER` с вызовом git — отказ; `less`, `cat` — нет.

        Ловит мутацию: отказ по любому заданному pager (`less` отклоняется)
        либо значение без вызова git не отличается от `git clean -fX`.
        """
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GIT_PAGER", None)
            os.environ.pop("PAGER", None)
            self.assertIsNone(role_git._command_refusal(
                [("core.pager", "less -R"), ("core.fsmonitor", "true")]))
            for key in ("core.pager", "core.fsmonitor", "pager.log"):
                self.assertIsNotNone(role_git._command_refusal(
                    [(key, "/usr/bin/git clean -fX")]), key)
            os.environ["GIT_PAGER"] = "git clean -fX"
            self.assertIsNotNone(role_git._command_refusal([]))


class TaskRmCheckTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(os.path.realpath(tmp.name))
        self.wt, self.docs, self.out = base / "wt", base / "docs", base / "out"
        for d in (self.wt, self.docs, self.out):
            d.mkdir()
        self.roots = [self.wt, self.docs]

    def check(self, path, in_branch=frozenset()):
        return task_files._check(str(path), self.roots, TASK, set(in_branch))

    def test_dotdot_and_link_parent_resolve_before_the_root_test(self):
        """`../` и каталог-ссылка наружу проверяются после разрешения родителя.

        Ловит мутацию: путь сверяется с корнями до `realpath` — `wt/../out/f`
        и `wt/link/f` (ссылка на `out`) сошли бы за файлы рабочей копии.
        """
        (self.out / "f").write_text("x", encoding="utf-8")
        (self.wt / "link").symlink_to(self.out, target_is_directory=True)
        self.assertIsNotNone(self.check(f"{self.wt}/../out/f")[1])
        self.assertIsNotNone(self.check(self.wt / "link" / "f")[1])

    def test_link_itself_is_removed_not_its_target(self):
        """Ссылка внутри копии на файл копии — удаляется сама ссылка.

        Ловит мутацию: путь к удалению — разрешённая цель ссылки (`realpath`
        самого пути) — удалилась бы цель.
        """
        target = self.wt / "target.txt"
        target.write_text("x", encoding="utf-8")
        (self.wt / "ln").symlink_to(target)
        item, reason = self.check(self.wt / "ln")
        self.assertIsNone(reason)
        self.assertEqual(item, self.wt / "ln")

    def test_doc_in_artifact_ref_and_nested_dot_git_refused(self):
        """Файл ссылки документов и путь внутри вложенного `.git` — отказ; новый документ — нет.

        Ловит мутацию: файлы каталога документов не сверяются со ссылкой
        документов; `.git` проверяется только верхним уровнем.
        """
        (self.docs / "SPEC.md").write_text("x", encoding="utf-8")
        (self.docs / "new.md").write_text("x", encoding="utf-8")
        (self.wt / "n" / ".git").mkdir(parents=True)
        (self.wt / "n" / ".git" / "HEAD").write_text("x", encoding="utf-8")
        branch = {f"tasks/{TASK}/SPEC.md"}
        self.assertIsNotNone(self.check(self.docs / "SPEC.md", branch)[1])
        self.assertIsNone(self.check(self.docs / "new.md", branch)[1])
        self.assertIsNotNone(self.check(self.wt / "n" / ".git" / "HEAD")[1])


if __name__ == "__main__":
    unittest.main()
