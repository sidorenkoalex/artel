"""AC-1 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): `orchestrator/gitcmd.py`
несёт функцию `diff_base(branch) -> str | None` — одна точка правды для
базы сравнения: merge-base ветки с `refs/remotes/origin/<MAIN_BRANCH>`,
если такой ref есть, иначе — merge-base с локальным `config.MAIN_BRANCH`;
без сетевых git-команд; `None`, если git не ответил на проверку
существования ref или на саму команду merge-base.

Красен до реализации: `gitcmd.diff_base` ещё не существует — импорт
модуля проходит (`gitcmd.py` не трогается этой планкой до кода задачи),
но обращение к `gitcmd.diff_base` в тестах ниже падает `AttributeError`
(функции нет), а не по какой-то другой причине.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import gitcmd  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MergeBaseFixture  # noqa: E402


class DiffBaseOriginRefPresentTest(MergeBaseFixture):
    """`origin/main` ушёл вперёд локального main; ветка задачи мержит его —
    `diff_base` обязана вернуть merge-base именно с `refs/remotes/origin/
    <MAIN_BRANCH>`, а не с локальным main (они расходятся в этой
    песочнице: local main = commit0, origin = commit0 + правка вне зон)."""

    CREATE_ORIGIN_REF = True

    def test_ac1_prefers_merge_base_with_origin_ref_over_local_main(self):
        """Ловит мутацию: функция всегда берёт `config.MAIN_BRANCH` как базу
        (проверка наличия `refs/remotes/origin/<MAIN_BRANCH>` убрана/
        инвертирована) — тогда вернулся бы sha локального main
        (`self.local_main_sha`), а не sha коммита origin, слитого в
        ветку задачи."""
        base = gitcmd.diff_base(self.BRANCH)

        self.assertEqual(base, self.origin_sha)
        self.assertNotEqual(base, self.local_main_sha)

    def test_ac1_never_invokes_network_git_subcommands(self):
        """Ловит мутацию: реализация зовёт `git fetch`/`git ls-remote` для
        проверки/актуализации `origin/main` вместо чтения уже
        существующего локального ref — нарушение инварианта «тесты не
        выходят в сеть» (01M1QHQ277…), эта проверка ловит именно факт
        сетевого вызова, не его результат.

        `RealGitSandbox` не заводит `SpyRun` (её `setUp` не зовёт
        `TmpRootTest.setUp`, см. её докстринг) — подсматриваем вызовы
        сами, оборачивая настоящий `gitcmd.subprocess.run` (репозиторий
        и так временный, реальному git ничего не грозит)."""
        calls = []
        real_run = gitcmd.subprocess.run

        def spy(cmd, *a, **kw):
            calls.append(list(cmd))
            return real_run(cmd, *a, **kw)

        with mock.patch.object(gitcmd.subprocess, "run", spy):
            gitcmd.diff_base(self.BRANCH)

        subcommands = [c[1] for c in calls if len(c) > 1 and c[0] == "git"]
        self.assertNotIn("fetch", subcommands)
        self.assertNotIn("ls-remote", subcommands)
        self.assertNotIn("clone", subcommands)
        self.assertNotIn("push", subcommands)


class DiffBaseOriginRefAbsentTest(MergeBaseFixture):
    """Тот же коммит origin слит в ветку задачи, но `refs/remotes/origin/
    <MAIN_BRANCH>` в репозитории не заведён (песочница без remote) —
    фолбэк на merge-base с локальным `config.MAIN_BRANCH`."""

    CREATE_ORIGIN_REF = False

    def test_ac1_falls_back_to_local_main_merge_base_when_origin_ref_absent(self):
        """Ловит мутацию: фолбэк на локальный main убран — функция вернула
        бы `None` или упала вместо merge-base с `config.MAIN_BRANCH`,
        хотя ref `origin/main` в этой песочнице сознательно не заведён
        (тот же сценарий AC-8)."""
        base = gitcmd.diff_base(self.BRANCH)

        self.assertEqual(base, self.local_main_sha)


class DiffBaseGitFailureTest(TmpRootTest):
    """Git не ответил (ни на проверку ref, ни на саму команду merge-base) —
    `None`, тем же приёмом деградации, что и у остальных примитивов
    `gitcmd.py` (`tests/test_doctor.py:1016`: `gitcmd.git = lambda *a:
    None` — установившийся в кодовой базе способ смоделировать «git не
    ответил вовсе», не «ответил отказом»)."""

    def test_ac1_returns_none_when_git_does_not_answer_at_all(self):
        """Ловит мутацию: `res is None` (или эквивалентная проверка) после
        вызова `gitcmd.git` убрана — обращение к `.returncode`/`.stdout`
        объекта `None` уронило бы функцию `AttributeError` вместо
        осмысленного `None`."""
        with mock.patch.object(gitcmd, "git", lambda *a: None):
            self.assertIsNone(gitcmd.diff_base("task/t001-x"))

    def test_ac1_returns_none_when_merge_base_command_fails(self):
        """Ловит мутацию: код возврата команды `merge-base` не проверяется
        (её stdout используется как sha независимо от `returncode`) —
        проверка существования ref отвечает успехом (значит эта ветка
        функции точно доходит до самой команды merge-base), а сама
        команда merge-base отказывает ненулевым кодом; функция обязана
        вернуть `None`, а не пустую/мусорную строку из stdout отказа."""
        def fake(*args):
            if args and args[0] == "merge-base":
                return subprocess.CompletedProcess(
                    list(args), 1, "", "fatal: Not a valid commit name")
            # rev-parse --verify (существование ref) — успех, чтобы дойти
            # именно до команды merge-base.
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(gitcmd, "git", fake):
            self.assertIsNone(gitcmd.diff_base("task/t001-x"))


if __name__ == "__main__":
    unittest.main()
