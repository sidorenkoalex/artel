"""Приёмочные тесты AC-3 и AC-4 (путь закрытия через `kill`) —
tasks/01M3KE80RNBCY9G48E75Z14TA7/SPEC.md, «Критерии приёмки».

Предмет — ретроспектива `tasks/<id>/RETRO.md` внутри снимка
`refs/artifacts/<id>` и сообщение коммита этого снимка у задачи,
ликвидированной командой `kill`.

Зелёный с рождения: AC-3 и killed-половина AC-4 держат СУЩЕСТВУЮЩЕЕ
поведение пути `kill` («поведение этого пути не изменилось», требование
4) — задача правит путь закрытия мержем, а этот тест стережёт, чтобы
правка не задела соседний путь и не выдала ликвидированную задачу за
смерженную.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import cleanup, retro, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ClosingSnapshotSandbox  # noqa: E402

TASK = "01PLANKKILLEDOUTCOME000001"

#: Действие журнала перехода в killed — источник «последней причины из
#: журнала» (AC-3). Читается из БД напрямую, не через `orchestrator/
#: retro.py`: иначе тест сверял бы генератор сам с собой.
KILL_STATE_ACTION = "state -> killed"


class KilledSnapshotOutcomeTest(ClosingSnapshotSandbox):

    def setUp(self):
        super().setUp()
        self.seed_task(TASK, "in_dev")
        self.capture(cleanup.cmd_kill, TASK)

    def journaled_kill_reason(self) -> str:
        steps = store.task_steps(store.db(), TASK)
        reasons = [s["detail"] for s in steps
                   if s["action"] == KILL_STATE_ACTION]
        self.assertTrue(
            reasons, f"журнал задачи не несёт ни одной записи "
                     f"«{KILL_STATE_ACTION}» — сверять причину не с чем")
        return reasons[-1]

    def test_ac3_killed_snapshot_retro_keeps_reason_and_old_address(self):
        """Ликвидированная задача — ретроспектива её снимка несёт «Итог:
        killed — причина: <последняя причина из журнала>» и прежнюю строку
        адреса артефактов.

        Ловит мутацию: исход для публикации снимка вычислен «в лоб» —
        например, всегда `done`, либо по факту существования снимка/ветки,
        а не по состоянию задачи — тогда ретроспектива снимка убитой задачи
        соберётся `retro.build_done`, потеряет строку причины и получит
        адрес по ссылке вместо прежней заметки; обе проверки ниже это видят.
        """
        retro_text = self.snapshot_retro_text(TASK)

        reason = self.journaled_kill_reason()
        self.assertIn(
            f"Итог: killed — причина: {reason}", retro_text,
            f"ретроспектива снимка ликвидированной задачи обязана нести "
            f"исход killed с последней причиной из журнала ({reason!r}), "
            f"AC-3; получено:\n{retro_text}")
        self.assertIn(
            f"Адрес артефактов: {retro.NO_ARTIFACTS_NOTE}", retro_text,
            f"строка адреса артефактов у ликвидированной задачи остаётся "
            f"прежней (AC-3); получено:\n{retro_text}")

    def test_ac4_killed_snapshot_commit_message_names_killed(self):
        """Сообщение коммита снимка ликвидированной задачи называет
        фактический исход — «снапшот закрытия (killed)».

        Ловит мутацию: исход в сообщение коммита снимка подставляется
        безусловным `done` (зеркальная ошибка той, что задача чинит на пути
        мержа) — заголовок коммита `refs/artifacts/<id>` станет «снапшот
        закрытия (done)», и обе проверки ниже разойдутся с ним.
        """
        subject = self.snapshot_commit_subject(TASK)

        self.assertIn(
            "снапшот закрытия (killed)", subject,
            f"сообщение коммита снимка обязано называть исход killed "
            f"(AC-4); получено: {subject!r}")
        self.assertNotIn(
            "(done)", subject,
            f"сообщение коммита снимка ликвидированной задачи не вправе "
            f"называть исход done (AC-4); получено: {subject!r}")


if __name__ == "__main__":
    unittest.main()
