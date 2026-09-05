"""Юнит-тесты `orchestrator/pin.py` (tasks/01M1NGFK3N6MRMYGCC09H975V3/
SPEC.md) — срез, который приёмочные тесты `tasks/
01M1NGFK3N6MRMYGCC09H975V3/acceptance_tests/` не покрывают дословно:
факт, что гейт AC-1 отказывает ДО `merge` (после `fetch` — REVIEW.md
итерации 1, R1-F1: возраст считается `merge-base`/`rev-list`, которым
нужен ЛОКАЛЬНЫЙ объект целевого sha, обычно ещё не принесённый), сам
сценарий R1-F1 (sha, известный только ПОСЛЕ fetch), и отказ самого
`git reset --hard` в `pin --to` (там `reset` во всех сценариях успешен).

Сквозной сценарий гейта `pin-update` (AC-1/AC-2) и отката `pin --to`
(AC-5/AC-6/AC-7, включая журнал) уже исчерпывающе покрыт приёмочными
тестами тем же приёмом песочницы (реальный git, реальный bare origin) —
здесь не дублируется.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd, pin, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402


class PinUpdateGateOrderTest(RealGitSandbox):
    """AC-1 (ANSWER-1 п.4): «отказ не трогает HEAD» — гейт стоит ПОСЛЕ
    `fetch` (fetch сам HEAD не двигает — только remote-tracking ref'ы),
    но ДО `merge`: сам факт, что `git merge` не вызывается вовсе, когда
    гейт отказывает, и HEAD остаётся прежним."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def test_refusal_after_fetch_never_calls_merge(self):
        """Ловит мутацию: гейт передвинут ПОСЛЕ `merge` (или убран
        вовсе) — отказ случился бы уже после того, как HEAD сдвинулся
        `git merge --ff-only`, нарушая ANSWER-1 п.4."""
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
            any(a and a[0] == "merge" for a in calls),
            f"гейт обязан отказать ДО merge, вызовы git: {calls}")
        self.assertEqual(self.git("rev-parse", "HEAD").strip(), target,
                         "отказ не должен двигать HEAD")


class PinUpdateGateAfterFetchTest(RealGitSandbox):
    """Регрессия R1-F1 (REVIEW.md итерации 1, blocker): sha, ради
    которого обычно и вызывают `pin-update`, — коммит main, ушедший
    вперёд origin'а, которого `config.ROOT` ЕЩЁ НЕ ВИДЕЛ локально. Гейт
    AC-1 считает возраст `merge-base`/`rev-list`, которым нужен
    ЛОКАЛЬНЫЙ объект — гейт ДО `fetch` (прежняя реализация) не мог
    резолвить такой sha и ОТКАЗЫВАЛ, даже когда валидный свежий зелёный
    прогон уже был в журнале (воспроизведено эмпирически ревьювером
    итерации 1: bare origin, второй клон пушит новый коммит, `config.
    ROOT` о нём не знает без fetch)."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        bare_tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare_tmp, ignore_errors=True)
        self.origin = Path(bare_tmp) / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "-b", config.MAIN_BRANCH,
             str(self.origin)], check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def _insert_green(self, main_sha: str) -> None:
        store.insert_canary_run(
            self.conn, "20260101T000000Z", "t", "01AAA", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=main_sha, verdict="green")

    def test_pin_update_succeeds_on_a_sha_not_yet_fetched_locally(self):
        """Ловит мутацию: гейт (`canary.merges_since_last_green_run`)
        вызван ДО `git fetch` — sha второго клона ещё не в локальной базе
        `config.ROOT`, `is_ancestor`/`merges_between` не могут его
        резолвить, гейт отказывает вместо ожидаемого успешного
        обновления пина (валидный свежий зелёный прогон в журнале есть,
        AC-2)."""
        old_sha = self.git("rev-parse", "HEAD").strip()
        self._insert_green(old_sha)

        clone_tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_tmp, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", str(self.origin), clone_tmp],
                       check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", clone_tmp, "config", "user.email",
                        "artel@example.invalid"], check=True)
        subprocess.run(["git", "-C", clone_tmp, "config", "user.name",
                        "artel tests"], check=True)
        (Path(clone_tmp) / "new.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", clone_tmp, "add", "-A"], check=True)
        subprocess.run(["git", "-C", clone_tmp, "commit", "-q", "-m",
                        "новый коммит main, ещё не притянутый в ROOT"],
                       check=True)
        subprocess.run(["git", "-C", clone_tmp, "push", "-q", "origin",
                        config.MAIN_BRANCH], check=True)
        new_sha = subprocess.run(
            ["git", "-C", clone_tmp, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()

        pin.cmd_pin_update(new_sha)

        self.assertEqual(self.git("rev-parse", "HEAD").strip(), new_sha)


class PinToResetFailureTest(RealGitSandbox):
    """`pin.cmd_pin_to` — отказ самого `git reset --hard` (край, не
    покрытый приёмочными тестами: там reset всегда успешен) журналируется
    тем же действием «pin откат отклонён», что и прочие отказы (AC-7)."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def test_reset_failure_is_journaled_as_a_refusal(self):
        """Ловит мутацию: отказ `git reset --hard` в `cmd_pin_to`
        обрабатывается тем же путём `sys.exit`, что и прочие отказы, но
        БЕЗ журналирования — AC-7 требует ровно одной записи журнала на
        КАЖДЫЙ вызов, включая отказавший."""
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
