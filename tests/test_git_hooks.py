"""Юнит-тесты защиты main главной копии (SPEC 01M2XMCC837R5CX9M58VARK85G):
git-хуки `scripts/git-hooks/pre-commit`/`pre-push`, маркер пульта
`ARTEL_PULT_GIT=1` в окружении дочерних git-процессов `orchestrator/gitcmd.py`
и `orchestrator/repo_context.py`, проверка doctor «git-hooks» и её починка
под `doctor --fix` (`orchestrator/doctor/git_hooks.py`).

Хуки гоняются настоящим git во временном репозитории с включённым
`core.hooksPath` — заглушкой поведение хука не изобразить; doctor —
в `tests.sandbox.RealGitSandbox`, где `config.ROOT` — настоящий репозиторий.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import doctor, gitcmd, repo_context, runner, stack  # noqa: E402
from tests.sandbox import (RealGitSandbox, TmpRootTest, capture,  # noqa: E402
                           fake_git, resilient_tmp_cleanup)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "scripts" / "git-hooks"
HOOK_NAMES = ("pre-commit", "pre-push")
HOOKS_PATH_VALUE = "scripts/git-hooks"
MARKER = "ARTEL_PULT_GIT"

# Общая часть именованного текста отказа (требование 2 SPEC) — без ведущего
# «коммит»/«push», которым хуки различаются.
REFUSAL_CORE = ("в main главной копии — только командой пульта "
                "(note, doc-commit, pin-update, approve на merge_gate); "
                "обход по решению Оператора: ARTEL_PULT_GIT=1")


def squeeze(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def env_without_marker(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k != MARKER}
    env.update(extra)
    return env


class _HookedRepoTest(unittest.TestCase):
    """Временный репозиторий с веткой main, одним коммитом и включёнными
    хуками задачи (копии из `scripts/git-hooks/`, `core.hooksPath` —
    репозиторный)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.repo = Path(tmp.name).resolve() / "repo"
        self.repo.mkdir()
        self.git_ok("init", "-q", "-b", "main")
        self.git_ok("config", "user.email", "hooks@artel.invalid")
        self.git_ok("config", "user.name", "hooks test")
        self.write("marker.txt", "main\n")
        self.git_ok("add", "marker.txt")
        self.git_ok("commit", "-q", "-m", "init")
        dest = self.repo / HOOKS_PATH_VALUE
        dest.mkdir(parents=True)
        for name in HOOK_NAMES:
            shutil.copy2(HOOKS_DIR / name, dest / name)
            os.chmod(dest / name, 0o755)
        self.git_ok("config", "core.hooksPath", HOOKS_PATH_VALUE)

    def run_git(self, *args: str, env: dict | None = None
                ) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.repo,
                              env=env_without_marker() if env is None else env,
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def git_ok(self, *args: str) -> str:
        res = self.run_git(*args, env=env_without_marker(ARTEL_PULT_GIT="1"))
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def head(self) -> str:
        return self.git_ok("rev-parse", "HEAD").strip()

    def stage(self, rel: str) -> None:
        self.write(rel, f"{rel}\n")
        self.git_ok("add", rel)

    def add_origin(self) -> None:
        origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, origin, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "--bare", str(origin)],
                       check=True, capture_output=True)
        self.git_ok("remote", "add", "origin", str(origin))

    def remote_ref(self, ref: str) -> str:
        out = self.git_ok("ls-remote", "origin", ref)
        return out.split()[0] if out.strip() else ""

    @staticmethod
    def output(res: subprocess.CompletedProcess) -> str:
        return squeeze(f"{res.stdout}\n{res.stderr}")


class PreCommitHookTest(_HookedRepoTest):

    def test_commit_on_main_without_marker_is_refused(self):
        """Ловит мутацию: хук печатает отказ, но завершается `exit 0`
        (предупреждение вместо запрета) — код возврата стал бы нулевым,
        коммит создался бы, и сверки кода/неподвижности HEAD покраснели бы.
        """
        before = self.head()
        self.stage("docs/backlog.md")

        res = self.run_git("commit", "-q", "-m", "ручной коммит")

        self.assertNotEqual(res.returncode, 0, self.output(res))
        self.assertEqual(self.head(), before)
        self.assertIn(squeeze(REFUSAL_CORE), self.output(res))
        self.assertIn("pre-commit: коммит в main", self.output(res))

    def test_commit_on_main_with_marker_passes(self):
        """Ловит мутацию: чтение маркера из окружения выпало из условия
        хука (проверяется только имя ветки) — команды пульта (`note`,
        push мержа) тоже получали бы отказ, коммит ниже не создался бы.
        """
        before = self.head()
        self.stage("docs/backlog.md")

        res = self.run_git("commit", "-q", "-m", "коммит пульта",
                           env=env_without_marker(ARTEL_PULT_GIT="1"))

        self.assertEqual(res.returncode, 0, self.output(res))
        self.assertNotEqual(self.head(), before)

    def test_marker_with_another_value_does_not_bypass(self):
        """Ловит мутацию: хук проверяет лишь наличие переменной (`-n`), а
        не значение `1` — `ARTEL_PULT_GIT=0` из чужого окружения снимал бы
        защиту, коммит ниже прошёл бы.
        """
        before = self.head()
        self.stage("docs/backlog.md")

        res = self.run_git("commit", "-q", "-m", "ручной коммит",
                           env=env_without_marker(ARTEL_PULT_GIT="0"))

        self.assertNotEqual(res.returncode, 0, self.output(res))
        self.assertEqual(self.head(), before)

    def test_commit_on_task_branch_without_marker_passes(self):
        """Ловит мутацию: условие ветки перепутано (отказ, когда ветка НЕ
        main) или потеряно вовсе — коммит разработчика на `task/x` без
        маркера перестал бы проходить.
        """
        self.git_ok("checkout", "-q", "-b", "task/x")
        before = self.head()
        self.stage("orchestrator/probe.py")

        res = self.run_git("commit", "-q", "-m", "правка роли")

        self.assertEqual(res.returncode, 0, self.output(res))
        self.assertNotEqual(self.head(), before)

    def test_commit_on_artifact_branch_without_marker_passes(self):
        """Ловит мутацию: хук сравнивает ветку по подстроке/префиксу
        вместо точного `main` (например, отказывает всему, что не
        `task/*`) — ветка `artifact/x` попала бы под отказ.
        """
        self.git_ok("checkout", "-q", "-b", "artifact/x")
        before = self.head()
        self.stage("tasks/x/PLAN.md")

        res = self.run_git("commit", "-q", "-m", "артефакты шага")

        self.assertEqual(res.returncode, 0, self.output(res))
        self.assertNotEqual(self.head(), before)


class PrePushHookTest(_HookedRepoTest):

    def setUp(self):
        super().setUp()
        self.add_origin()

    def test_push_to_refs_heads_main_is_refused_without_marker(self):
        """Ловит мутацию: хук читает из пары на stdin локальный ref, а не
        целевой — при push `<sha>:refs/heads/main` локальная сторона это
        голый sha, отказ не сработал бы, main опубликовалась бы.
        """
        sha = self.head()

        res = self.run_git("push", "origin", f"{sha}:refs/heads/main")

        self.assertNotEqual(res.returncode, 0, self.output(res))
        self.assertIn(squeeze(REFUSAL_CORE), self.output(res))
        self.assertIn("pre-push: push в main", self.output(res))
        self.assertEqual(self.remote_ref("refs/heads/main"), "")

    def test_push_to_main_with_marker_passes(self):
        """Ловит мутацию: маркер в `pre-push` не читается (проверка только
        по ref) — push мержа пульта (`fsm_merge_gate`) отказывал бы на
        первом же `approve` на merge_gate.
        """
        sha = self.head()

        res = self.run_git("push", "origin", f"{sha}:refs/heads/main",
                           env=env_without_marker(ARTEL_PULT_GIT="1"))

        self.assertEqual(res.returncode, 0, self.output(res))
        self.assertEqual(self.remote_ref("refs/heads/main"), sha)

    def test_task_artifact_and_artifact_refs_pass_without_marker(self):
        """Ловит мутацию: хук отказывает по подстроке `main` в любом ref
        или любому push без маркера — публикация ветки задачи,
        артефактной ветки и `refs/artifacts/*` перестала бы работать.
        """
        sha = self.head()
        self.git_ok("branch", "task/x")
        self.git_ok("branch", "artifact/x")

        for refspec, published in (("task/x", "refs/heads/task/x"),
                                   ("artifact/x", "refs/heads/artifact/x"),
                                   (f"{sha}:refs/artifacts/01ABC",
                                    "refs/artifacts/01ABC")):
            with self.subTest(refspec=refspec):
                res = self.run_git("push", "origin", refspec)
                self.assertEqual(res.returncode, 0, self.output(res))
                self.assertEqual(self.remote_ref(published), sha)

    def test_main_among_several_refs_refuses_the_whole_push(self):
        """Ловит мутацию: цикл `read` хука останавливается на первой
        строке stdin (нет `while`) — main второй парой в одном push прошла
        бы мимо сторожа.
        """
        sha = self.head()
        self.git_ok("branch", "task/x")

        res = self.run_git("push", "origin", "task/x", f"{sha}:refs/heads/main")

        self.assertNotEqual(res.returncode, 0, self.output(res))
        self.assertEqual(self.remote_ref("refs/heads/main"), "")


class PultMarkerInGitEnvTest(unittest.TestCase):
    """Маркер пульта в окружении дочернего git у `gitcmd.git`/`in_repo`/
    `carpentry`/`repo_context.git` (требования 6-7)."""

    def setUp(self):
        env_patcher = mock.patch.dict(os.environ, {"ARTEL_TEST_SENTINEL": "x"})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        os.environ.pop(MARKER, None)

    @staticmethod
    def captured_env(call) -> dict | None:
        with mock.patch.object(gitcmd.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            call()
        return run.call_args.kwargs.get("env")

    def test_git_passes_environment_plus_marker(self):
        """Ловит мутацию: `gitcmd.git` зовёт `subprocess.run` без `env=`
        (или собирает окружение с нуля из одного маркера) — либо маркера
        нет, либо пропали PATH/идентичность Оператора; сверка словаря
        ниже покраснеет в обоих случаях.
        """
        env = self.captured_env(lambda: gitcmd.git("rev-parse", "HEAD"))

        self.assertIsNotNone(env)
        self.assertEqual(dict(env), {**os.environ, MARKER: "1"})

    def test_in_repo_passes_marker_too(self):
        """Ловит мутацию: `in_repo` обходит `git()` собственным
        `subprocess.run` без маркера — плотницкий merge в scratch-worktree
        и push из клона внешнего target упирались бы в хук.
        """
        env = self.captured_env(lambda: gitcmd.in_repo(Path("/tmp"), "status"))

        self.assertIsNotNone(env)
        self.assertEqual(env.get(MARKER), "1")

    def test_carpentry_adds_marker_on_top_of_the_given_env(self):
        """Ловит мутацию: `carpentry` подменяет переданный `env` копией
        `os.environ` с маркером — `GIT_INDEX_FILE`/`GIT_AUTHOR_*`
        плотницкой записи пропали бы, запись пошла бы в основной индекс
        с чужим авторством.
        """
        passed = {"GIT_INDEX_FILE": "/tmp/idx", "GIT_AUTHOR_NAME": "Автор",
                  "GIT_AUTHOR_EMAIL": "a@artel", "GIT_COMMITTER_NAME": "К",
                  "GIT_COMMITTER_EMAIL": "c@artel"}

        env = self.captured_env(lambda: gitcmd.carpentry(
            Path("/tmp"), ["write-tree"], dict(passed)))

        self.assertEqual(dict(env), {**passed, MARKER: "1"})

    def test_marker_does_not_leak_into_the_pult_process_environment(self):
        """Ловит мутацию: `pult_env` пишет маркер прямо в `os.environ`
        вместо копии — маркер унаследовал бы любой посторонний процесс
        пульта (в том числе оболочка сессии), защита стала бы бумажной.
        """
        self.captured_env(lambda: gitcmd.git("rev-parse", "HEAD"))

        self.assertNotIn(MARKER, os.environ)

    def test_repo_context_git_reaches_a_real_child_with_the_marker(self):
        """Ловит мутацию: `repo_context.git` для внешнего клона зовёт
        `subprocess.run` сам, минуя `gitcmd.in_repo` — настоящий дочерний
        git ниже (`!`-алиас печатает переменную своей оболочки) не увидел
        бы маркер.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        repo = Path(tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(repo)], check=True,
                       capture_output=True)
        ctx = repo_context.RepoContext(path=repo, remote="origin", base="main")
        probe = ("-c", 'alias.probe=!echo "MARK=${ARTEL_PULT_GIT:-absent}"',
                 "probe")

        res = repo_context.git(ctx, *probe)

        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("MARK=1", res.stdout)


class RoleEnvWithoutMarkerTest(TmpRootTest):
    """Требование 8: `runner.role_env` маркер не несёт."""

    def role_env(self) -> dict:
        with mock.patch.object(runner.gitcmd, "git", fake_git), \
                mock.patch.object(runner.keychain, "token", lambda slot: None):
            return runner.role_env("developer", "01HOOKSTASK")

    def test_marker_from_the_pult_environment_is_filtered_out(self):
        """Ловит мутацию: `ARTEL_PULT_GIT` внесён в
        `stack.ROLE_ENV_ALLOWLIST` — выставленная у пульта переменная
        прошла бы в окружение роли, и роль обходила бы хук в worktree.
        """
        with mock.patch.dict(os.environ, {MARKER: "1"}):
            env = self.role_env()

        self.assertNotIn(MARKER, env)
        self.assertNotIn(MARKER, stack.ROLE_ENV_ALLOWLIST)


class _DoctorGitHooksSandbox(RealGitSandbox):
    """`config.ROOT` — настоящий репозиторий с копией `scripts/git-hooks`."""

    def setUp(self):
        super().setUp()
        dest = self.root / HOOKS_PATH_VALUE
        dest.mkdir(parents=True)
        self.hook_files = []
        for name in HOOK_NAMES:
            shutil.copy2(HOOKS_DIR / name, dest / name)
            self.hook_files.append(dest / name)

    def chmod_hooks(self, mode: int) -> None:
        for path in self.hook_files:
            os.chmod(path, mode)

    def hooks_path_config(self) -> str:
        res = subprocess.run(["git", "config", "--get", "core.hooksPath"],
                             cwd=self.root, capture_output=True, text=True)
        return res.stdout.strip()

    def executable(self) -> list:
        return [bool(p.stat().st_mode & 0o111) for p in self.hook_files]


class CheckGitHooksTest(_DoctorGitHooksSandbox):

    def test_fail_when_hookspath_is_not_set(self):
        """Ловит мутацию: проверка смотрит только на файлы хуков и не
        сверяет `core.hooksPath` — репозиторий с файлами, но без
        включения, считался бы защищённым.
        """
        self.chmod_hooks(0o755)

        check = doctor.check_git_hooks()

        self.assertEqual(check.name, "git-hooks")
        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("core.hooksPath", check.detail)
        self.assertIn("doctor --fix", check.detail)

    def test_fail_when_hookspath_points_elsewhere(self):
        """Ловит мутацию: сверка `core.hooksPath` сводится к «задан хоть
        какой-то» вместо точного `scripts/git-hooks` — чужой путь без
        наших хуков сходил бы за включённую защиту.
        """
        self.chmod_hooks(0o755)
        self.git("config", "core.hooksPath", ".githooks")

        check = doctor.check_git_hooks()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(".githooks", check.detail)

    def test_ok_when_hookspath_set_and_hooks_executable(self):
        """Ловит мутацию: проверка возвращает `fail` и при полном порядке
        (например, инвертировано условие бита исполнения) — `doctor`
        главной копии красился бы всегда.
        """
        self.chmod_hooks(0o755)
        self.git("config", "core.hooksPath", HOOKS_PATH_VALUE)

        check = doctor.check_git_hooks()

        self.assertEqual(check.status, "ok", check.detail)

    def test_fail_when_a_hook_is_not_executable(self):
        """Ловит мутацию: бит исполнения не сверяется — git молча
        пропускает неисполняемый хук, защиты бы не было, а проверка
        говорила бы `ok`.
        """
        self.git("config", "core.hooksPath", HOOKS_PATH_VALUE)
        self.chmod_hooks(0o755)
        os.chmod(self.hook_files[1], 0o644)

        check = doctor.check_git_hooks()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("pre-push", check.detail)
        self.assertIn("doctor --fix", check.detail)

    def test_fail_when_a_hook_file_is_missing(self):
        """Ловит мутацию: отсутствующий файл хука пропускается циклом
        (`continue` вместо ошибки) — `core.hooksPath` на пустой каталог
        считался бы защитой.
        """
        self.git("config", "core.hooksPath", HOOKS_PATH_VALUE)
        self.chmod_hooks(0o755)
        self.hook_files[0].unlink()

        check = doctor.check_git_hooks()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("pre-commit", check.detail)

    def test_skip_when_root_is_not_a_repository(self):
        """Ловит мутацию: проверка не различает «не репозиторий» и «путь не
        задан» — песочницы doctor без `git init` (`tests/test_doctor.py`,
        «здоровый репо») получали бы `fail` и `sys.exit(1)` вместо
        честного пропуска.
        """
        def no_repo(*args):
            return subprocess.CompletedProcess(list(args), 128, "",
                                               "fatal: not a git repository")

        with mock.patch.object(doctor.gitcmd, "git", no_repo):
            check = doctor.check_git_hooks()

        self.assertEqual(check.status, "skip", check.detail)

    def test_check_is_wired_into_all_checks(self):
        """Ловит мутацию: `check_git_hooks` написана, но не добавлена в
        `all_checks` — `doctor` молчал бы о выключенной защите.
        """
        import inspect
        self.assertIn("check_git_hooks", inspect.getsource(doctor.all_checks))


class FixGitHooksTest(_DoctorGitHooksSandbox):

    def test_fix_sets_hookspath_and_executable_bits(self):
        """Ловит мутацию: `_fix_git_hooks` выставляет только
        `core.hooksPath`, без `chmod` файлов — неисполняемый хук git тихо
        пропустил бы, проверка после починки осталась бы `fail`.
        """
        self.chmod_hooks(0o644)
        self.assertEqual(self.hooks_path_config(), "")

        out = capture(doctor._fix_git_hooks)

        self.assertEqual(self.hooks_path_config(), HOOKS_PATH_VALUE)
        self.assertEqual(self.executable(), [True, True])
        self.assertEqual(doctor.check_git_hooks().status, "ok")
        self.assertIn("[FIX] git-hooks", out)

    def test_fix_is_repository_local_not_global(self):
        """Ловит мутацию: включение сделано `git config --global` — каждый
        временный репозиторий тестов унаследовал бы сторожа главной копии
        (требование 9), а сверка глобального слоя ниже покраснела бы.
        """
        capture(doctor._fix_git_hooks)

        res = subprocess.run(["git", "config", "--global", "--get",
                              "core.hooksPath"], capture_output=True, text=True)
        self.assertEqual(res.stdout.strip(), "")
        self.assertEqual(self.hooks_path_config(), HOOKS_PATH_VALUE)

    def test_fix_is_idempotent(self):
        """Ловит мутацию: повторная починка на уже включённых хуках
        падает или сбрасывает бит исполнения (`chmod 0o644` перед
        установкой) — второй `doctor --fix` ломал бы первый.
        """
        capture(doctor._fix_git_hooks)
        capture(doctor._fix_git_hooks)

        self.assertEqual(self.hooks_path_config(), HOOKS_PATH_VALUE)
        self.assertEqual(self.executable(), [True, True])
        self.assertEqual(doctor.check_git_hooks().status, "ok")

    def test_fix_outside_a_repository_writes_nothing(self):
        """Ловит мутацию: `_fix_git_hooks` зовёт `git config` не проверив,
        что `config.ROOT` — репозиторий, — в песочницах без `git init`
        писал бы конфиг куда попало (или падал), вместо честной строки
        о пропуске.
        """
        calls = []

        def no_repo(*args):
            calls.append(args)
            return subprocess.CompletedProcess(list(args), 128, "",
                                               "fatal: not a git repository")

        with mock.patch.object(doctor.gitcmd, "git", no_repo):
            out = capture(doctor._fix_git_hooks)

        self.assertNotIn(("config", "core.hooksPath", HOOKS_PATH_VALUE), calls)
        self.assertIn("не включены", out)

    def test_cmd_doctor_fix_runs_the_hooks_fix(self):
        """Ловит мутацию: `_fix_git_hooks` не подключена к ветке `if fix:`
        в `cmd_doctor` — `doctor --fix` не включал бы защиту (AC-11).
        """
        self.chmod_hooks(0o644)
        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor, "_remote_artifact_branch_names",
                                  return_value=set()), \
                mock.patch.object(doctor, "_fix_ignored_artifact_files",
                                  lambda conn: None), \
                mock.patch.object(doctor, "_fix_dead_lease_groups",
                                  lambda conn: None), \
                mock.patch.object(doctor, "_fix_hung_test_runs",
                                  lambda conn: None):
            capture(lambda: doctor.cmd_doctor(fix=True))

        self.assertEqual(self.hooks_path_config(), HOOKS_PATH_VALUE)
        self.assertEqual(self.executable(), [True, True])
        self.assertEqual(doctor.check_git_hooks().status, "ok")

    def test_cmd_doctor_without_fix_does_not_enable_hooks(self):
        """Ловит мутацию: включение хуков вызывается безусловно, не под
        `if fix:` — обычный `doctor` менял бы конфиг репозитория, хотя
        без `--fix` он ничего не чинит.
        """
        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor, "_remote_artifact_branch_names",
                                  return_value=set()):
            capture(doctor.cmd_doctor)

        self.assertEqual(self.hooks_path_config(), "")


if __name__ == "__main__":
    unittest.main()
