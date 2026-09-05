"""Юнит-тесты `orchestrator/pin.py` (tasks/01M1NGFK3N6MRMYGCC09H975V3/
SPEC.md) — срез, который приёмочные тесты `tasks/
01M1NGFK3N6MRMYGCC09H975V3/acceptance_tests/` не покрывают дословно:
факт, что гейт AC-1 отказывает ДО единого вызова `fetch`/`merge`
(ANSWER-1 п.4 — там проверен только итоговый эффект, HEAD не двигается),
и отказ самого `git reset --hard` в `pin --to` (там `reset` во всех
сценариях успешен).

Сквозной сценарий гейта `pin-update` (AC-1/AC-2) и отката `pin --to`
(AC-5/AC-6/AC-7, включая журнал) уже исчерпывающе покрыт приёмочными
тестами тем же приёмом песочницы (реальный git, реальный bare origin) —
здесь не дублируется.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd, pin, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class PinUpdateGateOrderTest(RealGitSandbox):
    """AC-1 (ANSWER-1 п.4): «проверка — до fetch/merge» — не только
    итоговый эффект (HEAD не двигается), но и сам факт, что `git
    fetch`/`merge` не вызываются вовсе, когда гейт отказывает."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def test_refusal_calls_neither_fetch_nor_merge(self):
        target = self.git("rev-parse", "HEAD").strip()
        real_git = gitcmd.git
        calls = []

        def spy(*args):
            calls.append(args)
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=spy):
            with self.assertRaises(SystemExit):
                pin.cmd_pin_update(target)

        self.assertFalse(
            any(a and a[0] in ("fetch", "merge") for a in calls),
            f"гейт обязан отказать ДО fetch/merge, вызовы git: {calls}")


class PinToResetFailureTest(RealGitSandbox):
    """`pin.cmd_pin_to` — отказ самого `git reset --hard` (край, не
    покрытый приёмочными тестами: там reset всегда успешен) журналируется
    тем же действием «pin откат отклонён», что и прочие отказы (AC-7)."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def test_reset_failure_is_journaled_as_a_refusal(self):
        old_sha = self.git("rev-parse", "HEAD").strip()
        self.checkout("feature", create=True)
        (self.root / "f.txt").write_text("x\n", encoding="utf-8")
        self.git("add", "f.txt")
        self.git("commit", "-q", "-m", "работа")
        self.checkout(config.MAIN_BRANCH)
        self.git("merge", "--no-ff", "-q", "-m", "merge feature", "feature")
        real_git = gitcmd.git

        def fake_git(*args):
            if args and args[0] == "reset":
                return subprocess.CompletedProcess(args, 1, "", "отказ теста")
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=fake_git):
            with self.assertRaises(SystemExit):
                pin.cmd_pin_to(old_sha)

        rows = self.conn.execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "AND action=?",
            (config.PIN_UPDATE_JOURNAL_TASK_ID, "pin откат отклонён")).fetchall()
        self.assertTrue(rows, "отказ reset обязан журналироваться")
        self.assertEqual(rows[0]["actor"], "operator")


if __name__ == "__main__":
    unittest.main()
