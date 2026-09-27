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
from tests.sandbox import (ConnRealGitSandbox, RealGitSandbox,  # noqa: E402
                           SyncedOriginConnSandbox)


class PinUpdateGateOrderTest(ConnRealGitSandbox):
    """AC-1 (ANSWER-1 п.4): «отказ не трогает HEAD» — гейт стоит ПОСЛЕ
    `fetch` (fetch сам HEAD не двигает — только remote-tracking ref'ы),
    но ДО `merge`: сам факт, что `git merge` не вызывается вовсе, когда
    гейт отказывает, и HEAD остаётся прежним."""

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


class PinUpdateRefusalMessageTest(SyncedOriginConnSandbox):
    """SPEC 01M2B6K02YVJBWE1JDWP85EJH0, требование 2/AC-6: отказ
    `pin-update` называет sha и команду с `--sha <sha>` для его
    получения — не старую `canary --k 1` без привязки к целевому sha."""

    def test_refusal_names_sha_and_the_canary_command_with_sha_flag(self):
        """Ловит мутацию: текст отказа сохраняет старую команду `canary
        --k 1` без `--sha <sha>` — Оператор получил бы команду,
        прогоняющую канарейку на случайном шаблоне без привязки к
        нужному целевому sha (регрессия к тупику, который эта задача
        устраняет, см. `canary.py`)."""
        target = self.git("rev-parse", "HEAD").strip()

        with self.assertRaises(SystemExit) as ctx:
            pin.cmd_pin_update(target)

        message = str(ctx.exception)
        self.assertIn(target[:7], message)
        self.assertIn(f"canary --k 1 --sha {target}", message)


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


class PinToResetFailureTest(ConnRealGitSandbox):
    """`pin.cmd_pin_to` — отказ самого `git reset --hard` (край, не
    покрытый приёмочными тестами: там reset всегда успешен) журналируется
    тем же действием «pin откат отклонён», что и прочие отказы (AC-7)."""

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


class AlreadyAtRunShaTest(unittest.TestCase):
    """`pin._already_at_run_sha` (SPEC 01M3GKJFN90ATK2KECNDZXPPP6,
    требование 9): `canary_runs.main_sha` живой БД несёт короткие строки
    прогонов 26.09, и миграция их не дописывает — сравнение с текущим
    пином обязано читать их по префиксу."""

    HEAD = "3f2a9c1d8e7b6a5f4e3d2c1b0a99887766554433"

    def test_short_main_sha_prefixing_head_counts_as_already_pinned(self):
        """Ловит мутацию: префиксное сравнение написано в другую сторону
        (`main_sha.startswith(head)`) — короткая запись перестала бы
        узнаваться, и `pin --to` снова выполнял бы `git reset --hard` на
        семисимвольную строку."""
        self.assertTrue(pin._already_at_run_sha(self.HEAD, self.HEAD[:7]))
        self.assertTrue(pin._already_at_run_sha(self.HEAD, self.HEAD))

    def test_foreign_sha_and_empty_main_sha_are_not_already_pinned(self):
        """Пустой `main_sha` (в живой БД такие строки есть) — не «уже на
        пине»: префиксом пустой строки является любой HEAD.

        Ловит мутацию: проверка непустоты снята (`return head.startswith(
        main_sha)`) — прогон без записанного sha читался бы как совпавший
        с ЛЮБЫМ пином, и откат на последний зелёный прогон перестал бы
        работать вовсе."""
        self.assertFalse(pin._already_at_run_sha(self.HEAD, ""))
        self.assertFalse(pin._already_at_run_sha(self.HEAD, None))
        self.assertFalse(pin._already_at_run_sha(self.HEAD, "0" * 40))


class PinToShortGreenShaTest(ConnRealGitSandbox):
    """`pin --to` без аргумента на коротком `main_sha` последнего зелёного
    прогона (AC-11): отказ «пин уже на sha последнего зелёного прогона» и
    ни одного `git reset --hard`."""

    def test_short_green_sha_prefixing_head_refuses_before_any_reset(self):
        """Ловит мутацию: сравнение оставлено строгим (`target == old_sha`)
        — короткая строка пину не равна, отказа нет, и команда доходит до
        `git reset --hard` семисимвольной строки."""
        head = self.git("rev-parse", "HEAD").strip()
        store.insert_canary_run(
            self.conn, "20260926T101500Z", "t", "01AAA", steps=1,
            cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=head[:7], verdict="green")
        real_git = gitcmd.git
        calls = []

        def spy(*args):
            calls.append(args)
            return real_git(*args)

        with mock.patch.object(gitcmd, "git", side_effect=spy):
            with self.assertRaises(SystemExit) as ctx:
                pin.cmd_pin_to(None)

        self.assertIn("пин уже на sha последнего зелёного прогона",
                     str(ctx.exception))
        self.assertEqual(
            [], [a for a in calls if a[:2] == ("reset", "--hard")],
            f"git reset --hard выполнен после отказа: {calls}")


if __name__ == "__main__":
    unittest.main()
