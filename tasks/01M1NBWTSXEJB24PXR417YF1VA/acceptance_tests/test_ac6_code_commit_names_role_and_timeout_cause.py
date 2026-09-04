"""Приёмочный тест AC-6 — 01M1NBWTSXEJB24PXR417YF1VA: сообщение и журнал
WIP-коммита кодовой ветки называют роль и причину.

Источник — tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md, «Критерии приёмки»:

AC-6. Сообщение WIP-коммита в кодовую ветку (AC-1) и соответствующая
запись в журнал называют роль, чей шаг истёк таймаутом, и причину —
таймаут.

Единственная роль, чей WIP реально попадает в коммит кодовой ветки
(AC-1/AC-2), — `developer`; сценарий этого критерия — её.

Зелёный с рождения: сообщение `commit_timeout_checkpoint` уже сегодня —
`f"{task_id}: WIP-чекпоинт после таймаута шага {role}"`, и журнал уже
несёт то же действие/деталь (`orchestrator/checkpoint.py`, докстринг
функции, не тронутый мандатом роли этой задачи) — правка мандата по
AC-1/AC-2 меняет, ЧТО именно закоммичено, но не формат самого сообщения
для роли `developer`, которая продолжает коммитить свои пути кодовой
ветки как и раньше. Тест ниже фиксирует эту формулировку как критерий,
а не как деталь реализации — правка сообщения без причины и роли
покраснит его наравне с любой другой правкой мандата.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MandateCheckpointTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import checkpoint, store  # noqa: E402


class CodeCommitNamesRoleAndTimeoutCauseTest(MandateCheckpointTest):

    def test_ac6_code_branch_commit_and_journal_name_role_and_timeout(self):
        """Таймаут шага `developer` с правкой пути кодовой ветки — и
        подпись коммита кодовой ветки, и запись журнала называют роль
        `developer` и причину «таймаут».

        Ловит мутацию: сообщение/журнал коммита кодовой ветки лишились
        имени роли или слова «таймаут» при переписывании
        `commit_timeout_checkpoint` под мандат (например, унификация
        текста с `commit_abnormal_checkpoint`, где причина — `rc=N`/
        «обрыв потока», не «таймаут»).
        """
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")

        checkpoint.commit_timeout_checkpoint(
            store.db(), self.TASK, "developer")

        subject = self.worktree_git("log", "-1", "--format=%s").strip()
        self.assertIn("developer", subject,
                      f"AC-6: подпись коммита обязана называть роль — "
                      f"фактическая: {subject!r}")
        self.assertIn("таймаут", subject.lower(),
                      f"AC-6: подпись коммита обязана называть причину "
                      f"«таймаут» — фактическая: {subject!r}")

        entries = self.orchestrator_checkpoint_steps()
        self.assertTrue(entries, "AC-6: запись журнала о код-коммите "
                                 "обязана появиться")
        marker = " ".join(f"{r['action']} {r['detail']}" for r in entries)
        self.assertIn("developer", marker,
                      f"AC-6: журнал обязан называть роль — фактически: "
                      f"{marker!r}")
        self.assertIn("таймаут", marker.lower(),
                      f"AC-6: журнал обязан называть причину «таймаут» "
                      f"— фактически: {marker!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
