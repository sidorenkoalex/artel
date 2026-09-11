"""Приёмочный тест AC-5 (tasks/01M1R5B33CC7E6BZK085XV3ZCX/SPEC.md,
«Критерии приёмки»).

AC-5: `doctor.check_branch_freshness` для target ≠ self сравнивает
ветку задачи с `origin/<base>` контекста target'а, не с локальным
`config.MAIN_BRANCH` `config.ROOT`.

Красен до реализации: сегодня `check_branch_freshness` зовёт
`gitcmd.commits_behind(t["branch"])` без `base=` — сравнение всегда
идёт с локальным `config.MAIN_BRANCH` `config.ROOT`. Ветки внешнего
target там нет вовсе, `commits_behind` отвечает `None`, задача молча
пропускается («git не ответил — сверять не с чем») — предупреждения
не будет НИКОГДА, сколько бы ни отстала ветка от настоящего origin
целевого. Тест ниже заводит отставание, заведомо превышающее
`config.STALE_BRANCH_WARN_COMMITS`, и ждёт `warn` с именем задачи.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, doctor, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402

TASK = "01AC5STALEBRANCHTASK001"


class ExternalTargetBranchFreshnessTest(ExternalTargetGitSandbox):

    def setUp(self):
        super().setUp()
        self.branch = f"task/{TASK.lower()}-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{TASK}: код фичи")

        # main целевого уходит вперёд намного больше потолка
        # предупреждения — отставание заведомое, не пограничное.
        self.wgit("checkout", "-q", config.MAIN_BRANCH)
        for i in range(config.STALE_BRANCH_WARN_COMMITS + 3):
            (self.target_workspace / f"m{i}.txt").write_text(
                "x\n", encoding="utf-8")
            self.wgit("add", "-A")
            self.wgit("commit", "-q", "-m", f"правка main {i}")
        self.wgit("push", "-q", "origin", config.MAIN_BRANCH)
        self.wgit("checkout", "-q", self.branch)

        self.insert_external_task(TASK, self.branch, state="in_dev")

    def test_ac5_external_target_stale_branch_is_flagged(self):
        """Отставание от `origin/main` целевого больше потолка —
        `warn`, называющий задачу и ветку.

        Ловит мутацию: сравнение по-прежнему идёт с `config.MAIN_BRANCH`
        `config.ROOT` (где ветки {branch} нет вовсе) — `commits_behind`
        вернул бы `None`, задача была бы молча пропущена, и единственный
        `Check` в списке остался бы "ok".
        """
        conn = store.db()

        checks = doctor.check_branch_freshness(conn)

        by_status = {c.status for c in checks}
        self.assertIn("warn", by_status,
                     f"нет warn о ветке {self.branch}, отставшей на "
                     f"{config.STALE_BRANCH_WARN_COMMITS + 3} коммитов "
                     f"от origin/{config.MAIN_BRANCH} целевого: {checks}")
        warn_details = " ".join(c.detail for c in checks if c.status == "warn")
        self.assertIn(TASK, warn_details)
        self.assertIn(self.branch, warn_details)

    def test_ac5_does_not_compare_against_the_pult_local_main(self):
        """Отдельно от предыдущего: даже если бы кто-то по ошибке успел
        продвинуть `main` ПУЛЬТА (`self.root`) — сравнение внешнего
        target не имеет к этому отношения. Здесь `self.root` остаётся
        нетронутым (ни одного коммита сверх initial), поэтому warn
        обязан появиться ИМЕННО из-за отставания от origin целевого,
        не из случайного совпадения с пультом."""
        conn = store.db()
        pult_head_before = self.git("rev-parse", config.MAIN_BRANCH)

        doctor.check_branch_freshness(conn)

        self.assertEqual(self.git("rev-parse", config.MAIN_BRANCH),
                         pult_head_before,
                         "doctor изменил main пульта — сверка не имеет "
                         "права ничего коммитить/мержить")


class ExternalTargetFreshBranchIsOkTest(ExternalTargetGitSandbox):
    """Отставание МЕНЬШЕ потолка — по-прежнему `ok` (не любой внешний
    target автоматически подозрителен)."""

    TASK2 = "01AC5FRESHBRANCHTASK001"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK2.lower()}-x"
        self.checkout_task_branch(self.branch)
        (self.target_workspace / "feature.txt").write_text(
            "код фичи\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", f"{self.TASK2}: код фичи")
        self.insert_external_task(self.TASK2, self.branch, state="in_dev")

    def test_ac5_branch_at_head_of_origin_main_is_ok(self):
        conn = store.db()

        checks = doctor.check_branch_freshness(conn)

        self.assertTrue(
            all(c.status == "ok" for c in checks),
            f"ветка {self.branch}, не отставшая от origin/main "
            f"целевого, ошибочно помечена как отставшая: {checks}")


if __name__ == "__main__":
    import unittest
    unittest.main()
