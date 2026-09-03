"""AC-6 (tasks/01M1KT0792125J9ZNJNZJ86E9Q/SPEC.md): «Роль удалила
`tasks/<id>/QUESTIONS.md` в рабочем каталоге — после автокоммита
артефактов шага файла нет в артефактной ветке; следующий `advance` из
`spec_writing` не заводит эскалацию по отсутствующему батчу».

Красен до реализации: `orchestrator/checkpoint.py::
_commit_external_step_artifacts` (SPEC, «Материалы») собирает `files` из
того, что РЕАЛЬНО лежит на диске рабочего каталога роли на этом шаге, и
коммитит их поверх артефактной ветки через `artifact_branch.commit_files`
-> `write_commit`, которая делает `git read-tree <parent>` (грузит ВЕСЬ
предыдущий снимок) и только ДОБАВЛЯЕТ/обновляет записи `files` —
`update-index --add`. Запись, отсутствующая в `files`, потому что роль
удалила файл на диске, никогда не убирается из проиндексированного
дерева: удаление молча не переносится. Инцидент 03.09
(01M1HNNHDMP2C1AJTH5QF1BTN2) — Оператору пришлось вручную «мостить»
удаление QUESTIONS.md в артефактную ветку в обход автокоммита.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import checkpoint, config, fsm, gitcmd, store  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

QUESTIONS_MD = """---
task: {task}
type: questions
author_role: analyst
status: draft
schema_version: 2
---

# QUESTIONS: батч

## Вопросы

1. **Какой вариант выбрать?** — варианты: A) первый; B) второй — дефолт: A.
"""

SPEC_WITH_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: с AC-разметкой

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Критерий, размеченный корректно.

## Не входит
"""


class _Ac6Sandbox(RealPultGitTest):
    """`RealPultGitTest.setUp` заводит `self.TASK` (target — self/артель)
    в `spec_writing`. Рабочий каталог роли этого шага для self —
    `workspace.path(task_id)/tasks/<id>` (докстрока `checkpoint.
    _commit_external_step_artifacts`, «Источник для self/артели»,
    пересмотр планки 03.09) — тот же путь, каким реально пишет роль;
    здесь он материализуется напрямую (без реального агента), тем же
    приёмом, что `tests/test_checkpoint_external_step_artifacts.py`
    делает для внешнего target."""

    def setUp(self):
        super().setUp()
        from orchestrator import workspace
        self.task_dir = workspace.path(self.TASK) / "tasks" / self.TASK
        self.task_dir.mkdir(parents=True)

    def write(self, rel: str, text: str) -> None:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def artifact_branch_files(self) -> list:
        from orchestrator import artifact_branch
        branch = artifact_branch.branch_name(self.TASK)
        return gitcmd.ls_tree_files(branch, f"tasks/{self.TASK}") or []


class DeletionPropagatesToArtifactBranchTest(_Ac6Sandbox):

    def test_ac6_file_deleted_by_the_role_disappears_from_the_artifact_branch(self):
        """Шаг 1: analyst пишет `QUESTIONS.md` — автокоммит кладёт его в
        артефактную ветку (уже работающее поведение, не предмет этой
        задачи). Шаг 2: analyst получил ответ, удалил `QUESTIONS.md` (skil
        analyst) и написал `SPEC.md` вместо него — после автокоммита ЭТОГО
        шага `QUESTIONS.md` обязан пропасть из артефактной ветки, а не
        просто перестать обновляться.

        Ловит мутацию: `_commit_external_step_artifacts`, коммитящая
        `files` поверх родительского дерева без явного удаления пропавших
        записей (`git read-tree <parent>` + только `update-index --add`)
        — тогда `QUESTIONS.md` из шага 1 останется в дереве артефактной
        ветки навсегда, даже когда на диске его больше нет.
        """
        self.write("QUESTIONS.md", QUESTIONS_MD.format(task=self.TASK))
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "analyst")
        self.assertIn(f"tasks/{self.TASK}/QUESTIONS.md",
                      self.artifact_branch_files(),
                      "предпосылка сценария: файл шага 1 обязан быть закоммичен")

        self.task_dir.mkdir(parents=True)
        self.write("SPEC.md", SPEC_WITH_AC.format(task=self.TASK))
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "analyst")

        files = self.artifact_branch_files()
        self.assertIn(f"tasks/{self.TASK}/SPEC.md", files)
        self.assertNotIn(
            f"tasks/{self.TASK}/QUESTIONS.md", files,
            "удалённый ролью файл обязан исчезнуть из артефактной ветки")

    def test_ac6_advance_after_deletion_does_not_re_escalate_on_missing_batch(self):
        """После сценария удаления выше следующий `advance` из
        `spec_writing` видит на артефактной ветке только новый `SPEC.md`
        (готовый, с AC-разметкой) и переходит в `spec_gate` — не заводит
        повторную эскалацию по батчу, которого на диске/ветке уже нет.

        Ловит мутацию: та же неубранная запись `QUESTIONS.md` в дереве
        артефактной ветки (см. тест выше) — `fsm_advance.spec_writing`
        снова увидел бы «батч вопросов» и эскалировал повторно вместо
        перехода в `spec_gate`.
        """
        self.write("QUESTIONS.md", QUESTIONS_MD.format(task=self.TASK))
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "analyst")
        self.task_dir.mkdir(parents=True)
        self.write("SPEC.md", SPEC_WITH_AC.format(task=self.TASK))
        checkpoint.commit_step_artifacts(store.db(), self.TASK, "analyst")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertNotIn("эскалация", out)
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "spec_gate")


if __name__ == "__main__":
    unittest.main()
