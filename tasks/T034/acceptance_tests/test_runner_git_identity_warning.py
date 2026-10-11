"""Приёмочные тесты T034: AC-7, AC-8 — предупреждение о git-идентичности.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 5
(ревью T019): `run_agent_once` предупреждает о незаданной
git-идентичности перед стартом шага только по паре `GIT_AUTHOR_*`.
Сценарий «`GIT_AUTHOR_*` экспортированы явно, а `git config` не задал
`user.name`/`user.email`» (то есть нет и committer-идентичности,
`GIT_COMMITTER_*`) проходит молча — предупреждения нет, хотя коммит
шага упадёт с rc=128 («committer identity unknown») ровно как и без
`GIT_AUTHOR_*`.

AC-7 требует предупреждение в этом сценарии; AC-8 — что для окружения
с обеими парами (author и committer) целиком поведение не меняется:
предупреждения по-прежнему нет.

Песочница — тот же приём, что и `CmdRunLoggingTest` в
tests/test_agent_log.py: `subprocess.Popen` подменён, `gitcmd.git`
заглушкой отвечает пусто на `config --get` (идентичности в git-конфиге
нет — весь сценарий держится на переменных окружения процесса роли),
keychain и doctor подменены, чтобы шаг реально стартовал.
"""
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import catalog, config, gitcmd, runner, store  # noqa: E402


def silent_git(*args: str) -> subprocess.CompletedProcess:
    """`git config --get user.*` не отвечает ничем — идентичности в
    git-конфиге нет, весь сценарий держится на переменных окружения."""
    return subprocess.CompletedProcess(list(args), 0, "\n", "")


class FakeStream:
    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.lines)

    def close(self) -> None:
        pass


class FakeProc:
    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


class GitIdentityWarningSandbox(unittest.TestCase):
    TASK = "T001"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude")):
            self.patch_object(config, attr, value)

        self.patch_object(gitcmd, "git", silent_git)
        self.patch_object(runner.keychain, "token", lambda slot: "tok-test")
        self.patch_object_path("orchestrator.doctor.preflight_checks",
                               lambda role, target: [])

        self.capture(catalog.cmd_init)
        self.capture(catalog.cmd_new, "Предупреждение о git-идентичности")
        conn = store.db()
        conn.execute("UPDATE tasks SET state='in_dev' WHERE id=?", (self.TASK,))
        conn.commit()

    def patch_object(self, target, attr: str, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_object_path(self, target: str, value) -> None:
        patcher = mock.patch(target, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def capture(self, fn, *args) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def run_step(self, env: dict) -> str:
        """Один запуск шага с изолированным окружением процесса роли."""
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(runner.subprocess, "Popen") as popen:
            popen.return_value = FakeProc(["готово\n"])
            return self.capture(runner.cmd_run, self.TASK)

    def journal_details(self, action: str) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? ORDER BY id",
            (self.TASK, action))]


class Ac7MissingCommitterIdentityWarnsTest(GitIdentityWarningSandbox):
    """AC-7: GIT_AUTHOR_* заданы, GIT_COMMITTER_* и git config — нет."""

    def test_ac7_warning_is_printed_before_the_step_starts(self):
        out = self.run_step({"GIT_AUTHOR_NAME": "Роль Артели",
                             "GIT_AUTHOR_EMAIL": "role@artel.invalid"})

        self.assertIn("ВНИМАНИЕ", out)
        self.assertIn("git-идентичность роли не задана", out)

    def test_ac7_warning_is_journalled(self):
        self.run_step({"GIT_AUTHOR_NAME": "Роль Артели",
                       "GIT_AUTHOR_EMAIL": "role@artel.invalid"})

        details = self.journal_details("agent env WARNING")
        self.assertEqual(len(details), 1,
                         f"записей предупреждения: {len(details)}")


class Ac8FullIdentityDoesNotWarnTest(GitIdentityWarningSandbox):
    """AC-8: обе пары (author и committer) заданы — поведение не меняется."""

    def test_ac8_no_warning_when_both_pairs_are_present(self):
        out = self.run_step({
            "GIT_AUTHOR_NAME": "Роль Артели",
            "GIT_AUTHOR_EMAIL": "role@artel.invalid",
            "GIT_COMMITTER_NAME": "Роль Артели",
            "GIT_COMMITTER_EMAIL": "role@artel.invalid",
        })

        self.assertNotIn("ВНИМАНИЕ", out)
        self.assertNotIn("git-идентичность роли не задана", out)

    def test_ac8_no_warning_is_journalled(self):
        self.run_step({
            "GIT_AUTHOR_NAME": "Роль Артели",
            "GIT_AUTHOR_EMAIL": "role@artel.invalid",
            "GIT_COMMITTER_NAME": "Роль Артели",
            "GIT_COMMITTER_EMAIL": "role@artel.invalid",
        })

        self.assertEqual(self.journal_details("agent env WARNING"), [])


if __name__ == "__main__":
    unittest.main()
