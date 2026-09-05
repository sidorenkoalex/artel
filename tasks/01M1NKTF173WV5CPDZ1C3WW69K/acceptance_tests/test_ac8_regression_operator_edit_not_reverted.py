"""Приёмочный тест AC-8 (tasks/01M1NKTF173WV5CPDZ1C3WW69K/SPEC.md):
регресс-тест инцидента 04.09 из «Контекста» SPEC — правка SPEC.md в
артефактной ветке МЕЖДУ двумя шагами (без участия роли, чей шаг
стартует вторым) доходит и до брифа, и до диска рабочего каталога
следующей роли; автокоммит этого следующего шага не откатывает правку
обратно к старой версии.

Красен до реализации: без материализации `role_cwd` (AC-1) диск шага
N+1 несёт версию SPEC.md, оставшуюся от шага N (или не несёт её
вовсе) — сегодняшний `checkpoint._commit_external_step_artifacts`
закоммитил бы именно её поверх правки Оператора, ровно инцидент из
«Контекста» SPEC; тест падает на том, что артефактная ветка после
второго шага не несёт текста правки Оператора.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, brief, checkpoint, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import RealGitSandbox, seed_developer_brief_fixtures  # noqa: E402

TASK = "01AC8REGRESSIONOPEDIT"


class OperatorEditBetweenStepsNotRevertedTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        seed_developer_brief_fixtures(self.root)
        self.git("add", "CLAUDE.md")
        self.git("commit", "-q", "-m", "CLAUDE.md для брифа")

        store.insert_task(store.db(), TASK, "Регресс инцидента 04.09",
                          "in_dev", f"task/{TASK.lower()}-x",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "SPEC v1"},
            f"{TASK}: SPEC исходная версия")
        self.assertTrue(sha)

    def artifact_text(self, rel: str):
        branch = artifact_branch.branch_name(TASK)
        text, _ = gitcmd.show(branch, rel)
        return text

    def test_ac8_operator_edit_between_steps_survives_the_next_autocommit(self):
        # Шаг N: роль материализует диск, читает старую версию, SPEC.md не
        # меняет, шаг завершается правкой другого файла.
        cwd = runner.role_cwd(store.db(), TASK, config.DEFAULT_TARGET)
        self.assertEqual(
            (cwd / "tasks" / TASK / "SPEC.md").read_text(encoding="utf-8"),
            "SPEC v1")
        (cwd / "tasks" / TASK / "PLAN.md").write_text("PLAN шага N",
                                                       encoding="utf-8")
        checkpoint.commit_step_artifacts(store.db(), TASK, "developer")

        # Между шагами: Оператор правит SPEC.md на гейте — без участия
        # роли, чей шаг стартует вторым.
        sha = artifact_branch.commit_files(
            TASK, {f"tasks/{TASK}/SPEC.md": "SPEC v2 (правка Оператора)"},
            f"{TASK}: правка Оператора на гейте")
        self.assertTrue(sha)

        # Шаг N+1: и бриф, и диск обязаны нести v2 — и оставаться v2 после
        # автокоммита ЭТОГО следующего шага.
        text = brief.developer_brief(store.db(), TASK)
        self.assertIn("SPEC v2 (правка Оператора)", text,
                      "бриф следующего шага не несёт правку Оператора")

        cwd2 = runner.role_cwd(store.db(), TASK, config.DEFAULT_TARGET)
        self.assertEqual(
            (cwd2 / "tasks" / TASK / "SPEC.md").read_text(encoding="utf-8"),
            "SPEC v2 (правка Оператора)",
            "диск следующего шага не несёт правку Оператора")
        (cwd2 / "tasks" / TASK / "REVIEW.md").write_text("REVIEW шага N+1",
                                                          encoding="utf-8")
        checkpoint.commit_step_artifacts(store.db(), TASK, "reviewer")

        self.assertEqual(
            self.artifact_text(f"tasks/{TASK}/SPEC.md"),
            "SPEC v2 (правка Оператора)",
            "автокоммит следующего шага откатил правку Оператора к "
            "старой версии")


if __name__ == "__main__":
    unittest.main()
