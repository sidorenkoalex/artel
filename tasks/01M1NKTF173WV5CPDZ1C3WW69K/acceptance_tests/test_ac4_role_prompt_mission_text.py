"""Приёмочный тест AC-4 (tasks/01M1NKTF173WV5CPDZ1C3WW69K/SPEC.md): текст
миссии роли (`orchestrator/role_prompt.py`) не инструктирует «прочитай
tasks/<id>/SPEC.md» — для test_author (SPEC.md вообще); для developer —
и аналогично для PLAN.md/REVIEW.md (те входят в его бриф по AC-3).
Вместо этого миссия называет бриф источником актуального текста.

Красен до реализации: для test_author `role_prompt.mission_brief_package`
сегодня буквально формирует миссию со строкой «Прочитай {task_ref}/
SPEC.md, раздел «Критерии приёмки»» — регэксп находит инструкцию
«прочитай ... SPEC.md», тест падает на этой находке.

Зелёный с рождения: для developer миссия уже сегодня НЕ несёт
инструкции «прочитай PLAN.md»/«прочитай REVIEW.md» — раздел 3 её
текста упоминает REVIEW.md только как проверку статуса («Если есть
tasks/<id>/REVIEW.md со статусом changes_requested»), не как команду
читать файл с диска; этот тест закрепляет уже верное поведение
регрессионным контролем на случай, если правка AC-3 (добавление
PLAN/REVIEW в бриф) случайно вернёт инструкцию читать их напрямую.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd, role_prompt, store  # noqa: E402
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show, fake_git,
                           seed_developer_brief_fixtures)

TASK = "01AC4MISSIONTEXTNORE1"

READ_INSTRUCTION_RE = re.compile(r"прочитай[^.\n]*\b(SPEC|PLAN|REVIEW)\.md",
                                 re.IGNORECASE)


class MissionTextNoDirectReadInstructionTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        seed_developer_brief_fixtures(self.root)
        task_dir = config.TASKS / TASK
        task_dir.mkdir(parents=True)
        (task_dir / "SPEC.md").write_text("# SPEC\nМаркер SPEC.\n",
                                          encoding="utf-8")
        store.create_schema(store.db())
        store.insert_task(store.db(), TASK, "Текст миссии роли", "in_dev",
                          f"task/{TASK.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

    def mission_for(self, role: str) -> str:
        conn = store.db()
        t = store.get_task(conn, TASK)
        mission, _brief_text, _package = role_prompt.mission_brief_package(
            conn, TASK, t, role)
        return mission

    def test_ac4_test_author_mission_does_not_instruct_reading_spec_from_disk(self):
        mission = self.mission_for("test_author")

        self.assertIsNone(
            READ_INSTRUCTION_RE.search(mission),
            f"миссия test_author всё ещё инструктирует «прочитай ... "
            f"SPEC.md» напрямую с диска вместо ссылки на бриф:\n{mission}")

    def test_ac4_developer_mission_does_not_instruct_reading_plan_or_review_from_disk(self):
        mission = self.mission_for("developer")

        self.assertIsNone(
            READ_INSTRUCTION_RE.search(mission),
            f"миссия developer инструктирует «прочитай ... PLAN.md/"
            f"REVIEW.md» напрямую с диска вместо ссылки на бриф:\n{mission}")


if __name__ == "__main__":
    unittest.main()
