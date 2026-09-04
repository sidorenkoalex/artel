"""AC-3, AC-7 (tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/SPEC.md): артефакты
задачи (`SPEC.md`, `PLAN.md`, `TZ.md`, `QUESTIONS.md`, `ANSWER-n.md` и
прочие файлы `tasks/<id>/`) продолжают читаться С ВЕТКИ ЗАДАЧИ — эта
задача меняет источник чтения ТОЛЬКО для компонентов-правил (скилы,
CLAUDE.md), не для артефактов задачи (SPEC «Не входит»).

Зелёный с рождения: инвариант 28 (docs/invariants.md) — ветко-корректное
чтение артефактов задачи с ветки задачи — уже реализован (`orchestrator/
artifact_source.py::resolve`, `brief._developer_spec_text`, `brief.
_branch_or_disk_text`) и подтверждён `tasks/T031/acceptance_tests/
test_branch_correct_reads.py`; эта задача его не трогает (SPEC «Не
входит», требование 2). Оба теста здесь — РЕГРЕССИЯ: они обязаны
оставаться зелёными и после реализации этой задачи (SPEC AC-3/AC-7),
проверяя, что фикс чтения скилов/CLAUDE.md из main НЕ переносится по
ошибке (и не расширяется) на чтение артефактов задачи.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import TaskSandbox  # noqa: E402
from orchestrator import brief, store  # noqa: E402

QUESTIONS_MD = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: {task}

1. МАРКЕР-QUESTIONS-ВЕТКА-ЗАДАЧИ?
"""

ANSWER_MD = """---
task: {task}
type: answer
author_role: operator
status: final
schema_version: 2
---

# ANSWER-1: {task}

1. МАРКЕР-ANSWER-ВЕТКА-ЗАДАЧИ.
"""


class TaskArtifactsStillReadFromTaskBranchTest(TaskSandbox):

    def test_ac3_questions_and_answer_artifacts_still_read_from_task_branch(self):
        """`QUESTIONS.md`/`ANSWER-1.md` существуют ТОЛЬКО в ветке задачи
        (main их вообще не несёт — `tasks/<id>/` не рождается на main,
        `orchestrator/catalog.py::_new_dogfood`) — бриф analyst обязан
        всё равно нести их содержимое, читая с ветки задачи, как и до
        этой задачи.

        Ловит мутацию: если фикс AC-1/AC-2 (чтение компонентов-правил из
        main) по ошибке распространить на `_branch_or_disk_text`/
        `_answer_component` (общий код для скилов/CLAUDE.md и артефактов
        задачи вместо раздельных путей), QUESTIONS/ANSWER исчезнут из
        брифа — main их не несёт вовсе.
        """
        self.write_and_commit_in_worktree(
            "QUESTIONS.md", QUESTIONS_MD.format(task=self.TASK),
            "QUESTIONS.md от analyst")
        self.write_and_commit_in_worktree(
            "ANSWER-1.md", ANSWER_MD.format(task=self.TASK),
            "ANSWER-1.md от Оператора")

        text = brief.analyst_map_component(store.db(), self.TASK)

        self.assertIn(
            "МАРКЕР-QUESTIONS-ВЕТКА-ЗАДАЧИ", text,
            "бриф analyst обязан нести QUESTIONS.md с ветки задачи "
            "(SPEC AC-3) — main не содержит tasks/<id>/ вовсе")
        self.assertIn(
            "МАРКЕР-ANSWER-ВЕТКА-ЗАДАЧИ", text,
            "бриф analyst обязан нести последний ANSWER-n.md с ветки "
            "задачи (SPEC AC-3) — main не содержит tasks/<id>/ вовсе")


class SpecMdDiffersOnlyOnTaskBranchTest(TaskSandbox):

    def test_ac7_spec_md_differing_only_in_branch_from_main_uses_branch_version(self):
        """`tasks/<id>/SPEC.md` существует И на main (стаб-содержимое,
        специально закоммиченное туда этим тестом), И на ветке задачи
        (настоящее содержимое `cmd_new`) — с РАЗНЫМ содержимым. Бриф
        разработчика обязан нести версию ВЕТКИ ЗАДАЧИ.

        Ловит мутацию: если реализация AC-1 читает SPEC.md (как и скилы)
        через `git show main:...` вместо ветки задачи, бриф унесёт
        стаб-содержимое main, а не настоящий SPEC.md задачи.
        """
        self.write_and_commit(
            f"tasks/{self.TASK}/SPEC.md",
            "---\ntype: spec\n---\n\n# SPEC main-заглушка\n\n"
            "МАРКЕР-SPEC-НА-MAIN\n",
            "main: заглушка SPEC.md (не должна попасть в бриф)")

        text = brief.developer_brief(store.db(), self.TASK)

        self.assertNotIn(
            "МАРКЕР-SPEC-НА-MAIN", text,
            "бриф не должен нести содержимое SPEC.md с main, когда оно "
            "расходится с веткой задачи (SPEC AC-7)")
        self.assertIn(
            "Скилы и правила в бриф роли из main", text,
            "бриф обязан нести настоящее содержимое SPEC.md ветки задачи "
            "(SPEC AC-7) — тут узнаваемо по названию задачи из шаблона "
            "cmd_new")


if __name__ == "__main__":
    unittest.main()
