"""Приёмочный тест AC-7 (SPEC 01M2B6K02YVJBWE1JDWP85EJH0):
`doctor.check_canary_trigger` берёт целевой sha тем же источником
(`origin/<MAIN_BRANCH>`), что и `canary` по умолчанию (AC-1), не
`gitcmd.head_sha()` главной копии; текст проверки называет сам sha.

Красен до реализации: `orchestrator/doctor/canary_pool.py::
check_canary_trigger` сегодня безусловно читает `head =
doctor.gitcmd.head_sha()` (строка ~162) — целевой sha, относительно
которого считается возраст, остаётся HEAD главной копии независимо от
`origin/<MAIN_BRANCH>`; ни в одном ветвлении текст проверки/алерта не
несёт сам sha вовсе (сегодняшний текст — общие фразы «ни разу не
прогонялась»/«устарел», без конкретного значения sha).
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor, store  # noqa: E402
from tests.sandbox import resilient_tmp_cleanup  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import TargetShaCanarySandbox  # noqa: E402


class DoctorCanaryTriggerUsesOriginMainHeadTest(TargetShaCanarySandbox):

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def _insert_green(self, main_sha: str) -> None:
        store.insert_canary_run(
            self.conn, f"run-{main_sha[:7]}", "t", f"01{main_sha[:7]}",
            steps=1, cost_usd=0.1, review_iterations=0, escalations=0,
            outcome="killed", expected_escalation=None,
            actual_escalation=False, marker_mismatch=False,
            main_sha=main_sha, verdict="green")

    def _advance_origin_with_merges(self, count: int) -> str:
        """`count` настоящих merge-коммитов, пушащихся прямо в
        `self.origin` через отдельный клон — origin/<MAIN_BRANCH> уходит
        вперёд без изменения локального `main` (см. `_sandbox.py::
        TargetShaCanarySandbox.advance_origin_only`, здесь — партия из
        нескольких мержей вместо одного файла)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        clone_dir = Path(tmp.name) / "upstream-clone"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(clone_dir)],
                       check=True, capture_output=True, text=True)
        for i in range(count):
            branch = f"m{i}"
            subprocess.run(["git", "checkout", "-q", "-b", branch],
                           cwd=clone_dir, check=True, capture_output=True,
                           text=True)
            (clone_dir / f"{branch}.txt").write_text("x\n", encoding="utf-8")
            subprocess.run(["git", "add", f"{branch}.txt"], cwd=clone_dir,
                           check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-q", "-m", f"работа {branch}"],
                           cwd=clone_dir, check=True, capture_output=True,
                           text=True)
            subprocess.run(["git", "checkout", "-q", config.MAIN_BRANCH],
                           cwd=clone_dir, check=True, capture_output=True,
                           text=True)
            subprocess.run(["git", "merge", "--no-ff", "-q", "-m",
                            f"merge {branch}", branch], cwd=clone_dir,
                           check=True, capture_output=True, text=True)
        subprocess.run(["git", "push", "-q", "origin", config.MAIN_BRANCH],
                       cwd=clone_dir, check=True, capture_output=True, text=True)
        res = subprocess.run(["git", "-C", str(clone_dir), "rev-parse", "HEAD"],
                             capture_output=True, text=True)
        return res.stdout.strip()

    def test_ac7_ok_verdict_tracks_origin_main_head_not_stale_local_pin_head(self):
        """Локальный `main` (пин) отстал от `origin/<MAIN_BRANCH>`:
        зелёный прогон записан РОВНО на новой голове `origin/main`
        (возраст 0 относительно неё) — `check_canary_trigger` обязан
        признать порог не достигнутым (`status == "ok"`), считая возраст
        относительно `origin/<MAIN_BRANCH>`, а не относительно
        устаревшего локального `main`.

        Ловит мутацию: возраст по-прежнему считается относительно
        `gitcmd.head_sha()` локального `main` — зелёный прогон (main_sha
        = новая голова origin/main) не был бы предком СТАРОГО локального
        HEAD (он от него, наоборот, ушёл вперёд), `merges_since_last_
        green_run` вернул бы `None` («ни разу не прогонялась»,
        `status == "warn"`) вместо `"ok"`.
        """
        new_origin_head = self._advance_origin_with_merges(1)
        self._insert_green(new_origin_head)

        check = doctor.check_canary_trigger(self.conn)

        self.assertEqual(check.status, "ok")

    def test_ac7_check_text_names_the_target_sha(self):
        """Порог достигнут (журнал зелёных прогонов пуст) — текст
        проверки (`Check.detail`) называет сам целевой sha (голову
        `origin/<MAIN_BRANCH>`), не только общую фразу без значения.

        Ловит мутацию: текст проверки остаётся жёстко зашитой фразой без
        подстановки sha — ни полный, ни сокращённый (`sha[:7]`) целевой
        sha не появился бы нигде в `check.detail`.
        """
        target = self.origin_head_sha()

        check = doctor.check_canary_trigger(self.conn)

        self.assertTrue(
            target in check.detail or target[:7] in check.detail,
            check.detail)


if __name__ == "__main__":
    import unittest
    unittest.main()
