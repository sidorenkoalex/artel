"""AC-7, AC-8: маркер пульта `ARTEL_PULT_GIT=1` в окружении дочернего
процесса git у `gitcmd.git`, `gitcmd.in_repo`, `gitcmd.carpentry` и
`repo_context.git` — и неизменность прочих переменных этого окружения.

Маркер AC-7 проверяется СНАРУЖИ процесса: git-алиас `!echo` печатает то,
что реально увидела оболочка дочернего процесса, — это не зависит от того,
каким приёмом реализация подставила переменную. AC-8 (полный состав
окружения, а не только маркер) смотрит на аргументы `subprocess.run`:
«прочие переменные не изменились» — утверждение обо ВСЁМ словаре, снаружи
его целиком не вычитать.

Красен до реализации: ни `gitcmd`, ни `repo_context` сегодня не задают `env` дочернему git — маркера в его окружении нет.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import gitcmd, repo_context

from _hooks import MARKER_ENV, MARKER_VALUE

# Алиас-проба: `!`-алиас исполняется оболочкой дочернего процесса git и
# печатает значение маркера, как его видит сама оболочка.
PROBE_NAME = "artelplankprobe"
PROBE_ALIAS = '!echo "MARK=${ARTEL_PULT_GIT:-absent}"'
PROBE_ARGS = ("-c", f"alias.{PROBE_NAME}={PROBE_ALIAS}", PROBE_NAME)

SEEN = "MARK=" + MARKER_VALUE


class PultMarkerReachesGitChildProcessTest(unittest.TestCase):
    """AC-7: маркер виден изнутри дочернего процесса git."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)],
                       check=True, capture_output=True)

        # Маркер не должен прийти из окружения самого теста — иначе проба
        # зеленела бы и без реализации.
        env_patcher = mock.patch.dict(os.environ)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        os.environ.pop(MARKER_ENV, None)

    def test_ac7_all_four_entry_points_mark_the_git_child_process(self):
        """`gitcmd.git`, `gitcmd.in_repo`, `gitcmd.carpentry` и
        `repo_context.git` запускают git так, что его оболочка видит
        `ARTEL_PULT_GIT=1`.

        Ловит мутацию: маркер проставлен только в `gitcmd.git`, а
        `carpentry` (плотницкая запись артефактной ветки — собственный
        `subprocess.run` со своим env) осталась без него — её подпроба
        ниже напечатала бы `MARK=absent`.
        """
        ctx = repo_context.RepoContext(path=self.repo, remote="origin",
                                       base="main")
        carpentry_env = {"PATH": os.environ["PATH"],
                         "GIT_INDEX_FILE": str(self.repo / "idx")}

        cases = {
            "gitcmd.git": lambda: gitcmd.git(*PROBE_ARGS),
            "gitcmd.in_repo": lambda: gitcmd.in_repo(self.repo, *PROBE_ARGS),
            "gitcmd.carpentry": lambda: gitcmd.carpentry(
                self.repo, list(PROBE_ARGS), dict(carpentry_env)),
            "repo_context.git": lambda: repo_context.git(ctx, *PROBE_ARGS),
        }
        for name, call in cases.items():
            with self.subTest(entry_point=name):
                res = call()
                self.assertEqual(res.returncode, 0,
                                 f"{name}: проба не отработала: {res.stderr}")
                self.assertIn(SEEN, res.stdout,
                              f"{name}: дочерний git не увидел маркер "
                              f"(вывод пробы: {res.stdout.strip()!r})")


class OtherEnvironmentVariablesAreUntouchedTest(unittest.TestCase):
    """AC-8: маркер добавлен ПОВЕРХ, остальное окружение не тронуто."""

    def setUp(self):
        env_patcher = mock.patch.dict(
            os.environ, {"ARTEL_PLANK_SENTINEL": "не-трогать"})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        os.environ.pop(MARKER_ENV, None)

    @staticmethod
    def capture_env(call) -> dict:
        with mock.patch.object(gitcmd.subprocess, "run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            call()
        return run.call_args.kwargs.get("env")

    def test_ac8_marker_is_added_on_top_of_the_existing_environment(self):
        """`gitcmd.git` отдаёт дочернему процессу окружение пульта плюс
        один маркер — ни одна переменная не пропала и не изменилась; для
        `gitcmd.carpentry` маркер ложится поверх ПЕРЕДАННОГО ей env, и
        `GIT_INDEX_FILE`/`GIT_AUTHOR_*`/`GIT_COMMITTER_*` доживают до git.

        Ловит мутацию: реализация собирает окружение с нуля
        (`env={"ARTEL_PULT_GIT": "1"}` вместо копии переданного/текущего) —
        `carpentry` потеряла бы `GIT_INDEX_FILE` и `GIT_AUTHOR_*`, то есть
        плотницкая запись артефактной ветки писала бы в основной индекс и
        с чужим авторством; обе сверки словарей ниже покраснели бы.
        """
        env = self.capture_env(lambda: gitcmd.git("rev-parse", "HEAD"))
        self.assertIsNotNone(env, "gitcmd.git не задаёт env дочернему git")
        self.assertEqual(dict(env), {**os.environ, MARKER_ENV: MARKER_VALUE})

        passed = {"GIT_INDEX_FILE": "/tmp/plank-index",
                  "GIT_AUTHOR_NAME": "Автор", "GIT_AUTHOR_EMAIL": "a@artel",
                  "GIT_COMMITTER_NAME": "Коммитер",
                  "GIT_COMMITTER_EMAIL": "c@artel"}
        env = self.capture_env(lambda: gitcmd.carpentry(
            Path("/tmp"), ["write-tree"], dict(passed)))
        self.assertIsNotNone(env, "gitcmd.carpentry не задаёт env дочернему git")
        self.assertEqual(dict(env), {**passed, MARKER_ENV: MARKER_VALUE})


if __name__ == "__main__":
    unittest.main()
