"""Приёмочный тест AC-5 — 01M1NBWTSXEJB24PXR417YF1VA: пометка «WIP после
таймаута» в сообщении коммита артефактной ветки.

Источник — tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md, «Критерии приёмки»:

AC-5. Коммит в артефактную ветку по AC-4 несёт в сообщении пометку «WIP
после таймаута».

Отличает этот коммит от ОБЫЧНОГО автокоммита артефактов шага
(`checkpoint.commit_step_artifacts`, штатное завершение rc=0), чьё
сообщение — «артефакты шага {role} (автокоммит оркестратора)», без слова
«таймаут» (SPEC T059) — иначе следующий читатель истории артефактной
ветки не отличил бы «роль успела сама» от «оркестратор подобрал WIP
после обрыва».

Красен до реализации: до этой задачи `commit_timeout_checkpoint` вообще
не создаёт коммит в артефактной ветке для `tasks/<id>/` (см. AC-4) —
`artifact_branch_subject()` для этого сценария либо падает (нет ни
одного коммита артефактной ветки этой задачи), либо возвращает
сообщение от другого действия. Тест ниже проверяет, что подпись
СУЩЕСТВУЮЩЕГО коммита несёт буквальную пометку.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MandateCheckpointTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import checkpoint, store  # noqa: E402


class ArtifactCommitCarriesWipAfterTimeoutMarkerTest(MandateCheckpointTest):

    def test_ac5_artifact_branch_commit_message_carries_the_marker(self):
        """Таймаут шага `test_author` с артефактом в `tasks/<id>/` —
        сообщение коммита артефактной ветки несёт буквальную пометку
        «WIP после таймаута».

        Ловит мутацию: коммит артефактной ветки при таймауте использует
        то же сообщение, что и обычный автокоммит успешного шага
        (`f"{task_id}: артефакты шага {role} (автокоммит оркестратора)"`,
        без пометки) — тогда `assertIn("WIP после таймаута", subject)`
        покраснел бы, хотя AC-4 (сам факт переноса) уже мог быть зелёным.
        """
        self.enter_in_dev()
        self.worktree_task_dir().joinpath("wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")

        checkpoint.commit_timeout_checkpoint(
            store.db(), self.TASK, "test_author")

        subject = self.artifact_branch_subject()
        self.assertIn(
            "WIP после таймаута", subject,
            f"AC-5: сообщение коммита артефактной ветки обязано нести "
            f"пометку «WIP после таймаута» — фактическое: {subject!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
