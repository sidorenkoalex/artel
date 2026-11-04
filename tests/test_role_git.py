"""Механизм границы git роли `orchestrator/role_git.py`, снятие обёртки
диспетчером `artel.py`, команда `task-rm` (`orchestrator/task_files.py`),
абзац миссии о ней и строка doctor `role-git-boundary` (SPEC
01M6JJ4J4NBV2Y1Q4XHE3C3FVT, требования 2–5, 7, 10).

Планка задачи — «разовая»; сквозные проверки ядра здесь держат его после
мержа. Всё, что исполняет git, идёт только против временного дублёра корня
пульта вне настоящего репозитория, и только читающими командами или
`clean -n`."""
import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, doctor, role_git, role_prompt, runner, task_files

TASK = "01MOWNTASK"
# Переменные, меняющие исход git вызова: снимаются в сквозных тестах, чтобы
# исход не зависел от окружения процесса тестов (в том числе окружения роли).
GIT_ENV_NOISE = ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_PARAMETERS",
                 "GIT_CONFIG_COUNT", "GIT_PAGER", "PAGER",
                 "GIT_CEILING_DIRECTORIES", role_git.GUARD_ROOT_ENV,
                 role_git.TASK_ENV)


def quiet_git_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in GIT_ENV_NOISE}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", **extra)
    return env


class ExecCalled(Exception):
    """Подмена `os.execv`: вызов пропущен к настоящему git."""


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

    def test_config_options_in_alias_body_are_not_the_subcommand(self):
        """Тело псевдонима с `-c k=v` перед `clean` и с pager/`!`-псевдонимом в `-c` — отказ.

        Ловит мутацию: разбор тела выкидывает только слова с `-`, значение
        `-c` (`a.b=c`) принимается за подкоманду — `cl = -c a.b=c clean -fX`
        проходит, а pager, fsmonitor и `!`-псевдоним, заданные `-c` в теле,
        не проверяются (R1-F1 ревью).
        """
        with mock.patch.dict(os.environ, {"CL_VAL": "core.pager"}, clear=False):
            for name in ("GIT_PAGER", "PAGER"):
                os.environ.pop(name, None)
            refused = {
                "a": "-c a.b=c clean -fX",
                "b": "--config-env=a.b=CL_VAL clean",
                "c": "-c 'core.pager=git clean -fX' log",
                "d": "-c 'core.fsmonitor=git clean -fX' status",
                "e": "-c 'alias.y=!echo ok' y",
                "f": "-c alias.y=clean y",
                "g": "-c core.worktree=/elsewhere status",
            }
            for name, body in refused.items():
                self.assertIsNotNone(
                    role_git._alias_refusal(name, [(f"alias.{name}", body)]), body)
            self.assertIsNone(role_git._alias_refusal(
                "lg", [("alias.lg", "-c color.ui=never log --oneline")]))

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


class DoubleRootTest(unittest.TestCase):
    """Временный дублёр корня пульта вне настоящего репозитория: репозиторий
    в корне, клон проекта и две рабочие копии — своя и чужая."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.projects = self.root / ".artel" / "projects" / "p"
        self.own = self.projects / "worktrees" / TASK
        self.foreign = self.projects / "worktrees" / "01MOTHERTASK"
        for d in (self.own, self.foreign, self.projects / "repo"):
            d.mkdir(parents=True)
        self.git_init(self.root)
        self.git_init(self.own)
        (self.root / "junk.txt").write_text("x", encoding="utf-8")
        (self.own / "junk.txt").write_text("x", encoding="utf-8")

    def git_init(self, where: Path) -> None:
        subprocess.run(["git", "init", "-q", str(where)], check=True,
                       env=quiet_git_env(), capture_output=True, timeout=30)


class WrapperMainTest(DoubleRootTest):

    def run_main(self, args, cwd=None, **env):
        """(код, stderr, аргументы `execv` | None) вызова `role_git.main`."""
        environ = quiet_git_env(**{role_git.GUARD_ROOT_ENV: str(self.root),
                                   role_git.TASK_ENV: TASK}, **env)
        saved = os.getcwd()
        self.addCleanup(os.chdir, saved)
        os.chdir(cwd or self.own)
        err = io.StringIO()
        execv = mock.Mock(side_effect=ExecCalled)
        with mock.patch.dict(os.environ, environ, clear=True), \
                mock.patch.object(role_git.os, "execv", execv), \
                contextlib.redirect_stderr(err):
            try:
                code = role_git.main(["role_git.py", str(runner.ROLE_GIT_BIN), *args])
            except ExecCalled:
                return None, err.getvalue(), execv.call_args.args[1]
        return code, err.getvalue(), None

    def test_clean_in_own_copy_refused_status_passes(self):
        """`git clean` в своей копии — отказ с `task-rm`; `git status` — настоящему git.

        Ловит мутацию: отказ `clean` выключен — и проверка подкоманды
        `sub == "clean"`, и слово `clean` в `_alias_refusal` (каждое из двух
        мест в одиночку держит отказ) — `clean -fX` уходит к настоящему git;
        либо своя копия отклоняется целиком (`status` не исполняется).
        """
        code, err, passed = self.run_main(["clean", "-fX", "--", "junk.txt"])
        self.assertEqual((code, passed), (role_git.REFUSAL_EXIT, None))
        self.assertIn("task-rm", err)
        code, _err, passed = self.run_main(["status"])
        self.assertIsNone(code)
        self.assertIn("help.autocorrect=0", passed)
        self.assertEqual(passed[-1], "status")

    def test_foreign_copy_and_pult_root_refused_with_own_reason(self):
        """Чужая копия — «рабочая копия другой задачи», корень дублёра — «репозиторий пульта».

        Ловит мутацию: отказ «рабочая копия другой задачи» выключен — `-C
        <чужая копия>` даёт строку «репозиторий пульта» или проходит к git.
        """
        code, err, passed = self.run_main(["-C", str(self.foreign / "sub"), "status"])
        self.assertEqual((code, passed), (role_git.REFUSAL_EXIT, None))
        self.assertIn("рабочая копия другой задачи", err)
        code, err, passed = self.run_main(["status"], cwd=self.root / ".artel")
        self.assertEqual((code, passed), (role_git.REFUSAL_EXIT, None))
        self.assertIn("репозиторий пульта", err)
        self.assertIn("task-rm", err)

    def test_pager_and_alias_with_dash_c_in_body_refused(self):
        """Pager с git и псевдоним `-c a.b=c clean` из конфигурации вызова — отказ до исполнения.

        Ловит мутацию: отказ по pager/псевдониму выключен (`reason = None`)
        либо тело псевдонима принимает значение `-c` за подкоманду — вызов
        уходит к настоящему git, который исполнил бы `clean`.
        """
        for args in (["-c", "core.pager=git clean -fX", "log"],
                     ["-c", "alias.cl=-c a.b=c clean -fX", "cl"],
                     ["-c", "alias.x=!echo ok", "x"]):
            code, err, passed = self.run_main(args)
            self.assertEqual((code, passed), (role_git.REFUSAL_EXIT, None), args)
            self.assertIn("task-rm", err, args)
        code, _err, passed = self.run_main(["-c", "core.pager=cat", "log"])
        self.assertIsNone(code)

    def test_outside_roots_and_version_go_straight_to_git(self):
        """Репозиторий вне корней и `--version` внутри корня — настоящему git без проверки.

        Ловит мутацию: отказ по любому каталогу (вне корней `clean` не
        проходит) либо `--version` проверяется как обращение к репозиторию.
        """
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        code, _err, passed = self.run_main(["clean", "-n"], cwd=outside.name)
        self.assertIsNone(code)
        self.assertEqual(passed[1:], ["clean", "-n"])
        code, _err, passed = self.run_main(["--version"], cwd=self.root)
        self.assertIsNone(code)


class DispatcherPathTest(unittest.TestCase):

    def test_role_command_runs_without_wrapper_and_environ_restored(self):
        """Под признаком роли команда пульта идёт с PATH без каталога обёртки; PATH возвращается.

        Ловит мутацию: диспетчер не снимает обёртку из PATH (дочерние git
        пульта шли бы через неё) либо не восстанавливает PATH после
        исключения команды.
        """
        path = os.pathsep.join(["/a", str(runner.ROLE_GIT_BIN), "/b"])
        seen = []

        def command():
            seen.append(os.environ["PATH"])
            raise RuntimeError("команда упала")

        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer",
                                          "PATH": path}):
            with self.assertRaises(RuntimeError):
                artel._run_without_role_git(command)
            self.assertEqual(os.environ["PATH"], path)
        self.assertEqual(seen, [os.pathsep.join(["/a", "/b"])])


class TaskRmCommandTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "f.txt"
        self.file.write_text("x", encoding="utf-8")

    def test_role_with_foreign_or_missing_task_refused_before_anything(self):
        """Процесс роли: `<id>` ≠ `ARTEL_TASK` и нет `ARTEL_TASK` — отказ, файл цел.

        Ловит мутацию: `<id>`, отличный от `ARTEL_TASK`, не отклоняется —
        команда идёт к БД и удалению файлов чужой задачи.
        """
        task = mock.Mock(side_effect=AssertionError("дошло до БД"))
        for env in ({config.ARTEL_TASK_ENV: "01MSOMEOTHER"}, {}):
            with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer", **env}), \
                    mock.patch.object(task_files, "_task", task):
                if not env:
                    os.environ.pop(config.ARTEL_TASK_ENV, None)
                with self.assertRaises(SystemExit) as caught:
                    task_files.cmd_task_rm([TASK, str(self.file)])
            self.assertIn("не удалены", str(caught.exception.code))
            self.assertTrue(self.file.exists())

    def test_repeated_path_removed_once(self):
        """Один файл дважды в наборе (`f`, `./f`) — удалён один раз, без трассировки.

        Ловит мутацию: повтор пути не отсекается — второй `unlink` падает
        `FileNotFoundError` после удаления (R1-F3 ревью).
        """
        root = self.file.parent.resolve()
        saved = os.getcwd()
        self.addCleanup(os.chdir, saved)
        os.chdir(root)
        with mock.patch.dict(os.environ, {config.ARTEL_TASK_ENV: TASK}), \
                mock.patch.object(task_files.runner, "in_role_environment",
                                  return_value=False), \
                mock.patch.object(task_files, "_task", return_value=(TASK, "p")), \
                mock.patch.object(task_files.workspace, "path", return_value=root), \
                mock.patch.object(task_files.artifact_branch, "docs_dir",
                                  return_value=root / "docs"), \
                mock.patch.object(task_files, "_artifact_files", return_value=set()), \
                contextlib.redirect_stdout(io.StringIO()):
            task_files.cmd_task_rm([TASK, "f.txt", "./f.txt"])
        self.assertFalse(self.file.exists())


class MissionTaskRmTest(unittest.TestCase):

    def test_docs_dir_note_names_task_rm_with_task_id(self):
        """Абзац миссии о каталоге документов называет `task-rm <id>`.

        Ловит мутацию: `task-rm` убран из абзаца `docs_dir_note` — роль не
        узнаёт штатного способа убрать свой файл.
        """
        note = role_prompt.docs_dir_note(TASK, "/docs")
        self.assertIn(f"task-rm {TASK}", note)


class DoctorBoundaryTest(DoubleRootTest):

    def check(self, env):
        with mock.patch.object(config, "ROOT", self.root), \
                mock.patch.object(doctor.runner, "role_env", return_value=env):
            return doctor.check_role_git_boundary()

    def env(self, *, ceiling=True, wrapper=True):
        path = os.environ.get("PATH", "")
        path = runner.path_without_role_git(path)
        if wrapper:
            path = os.pathsep.join([str(runner.ROLE_GIT_BIN), path])
        env = quiet_git_env(PATH=path, **{role_git.GUARD_ROOT_ENV: str(self.root)})
        if ceiling:
            env["GIT_CEILING_DIRECTORIES"] = str(self.root)
        return env

    def test_ok_only_with_both_ceiling_and_wrapper(self):
        """`ok` на исправном окружении; без потолка и без обёртки — `fail`; дублёр цел.

        Ловит мутацию: строка не отдаёт `fail` (пропавший потолок или
        обёртка проходят как `ok`) либо проба оставляет временный каталог в
        `<ROOT>/.artel`.
        """
        self.assertEqual(self.check(self.env()).status, "ok")
        self.assertEqual(self.check(self.env(ceiling=False)).status, "fail")
        self.assertEqual(self.check(self.env(wrapper=False)).status, "fail")
        self.assertTrue((self.root / "junk.txt").exists())
        self.assertEqual(sorted(p.name for p in (self.root / ".artel").iterdir()),
                         ["projects"])


if __name__ == "__main__":
    unittest.main()
