"""Приёмочный тест AC-9 (канареечный прогон снимок не публикует) —
tasks/01M3KE80RNBCY9G48E75Z14TA7/SPEC.md, «Критерии приёмки».

Наблюдаемое свойство — отсутствие ссылки `refs/artifacts/<id>` в origin
целевого после закрытия канареечной задачи; проверяется на обоих путях
закрытия, как их и называет требование 8.

Зелёный с рождения: исключение канарейки существует сегодня
(`cleanup._publish_snapshot_if_pending`, ранний возврат по `is_canary`), и
критерий требует его сохранить — «как сегодня». Тест стережёт, чтобы
вычисление фактического исхода не втащило канарейку в публикацию: исход
задачи и право на снимок — разные вопросы, и чинить первый, задев второй,
проще всего.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import cleanup  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ClosingSnapshotSandbox  # noqa: E402

MERGED_CANARY = "01PLANKCANARYMERGEDTASK001"
KILLED_CANARY = "01PLANKCANARYKILLEDTASK001"


class CanaryCloseTest(ClosingSnapshotSandbox):

    def test_ac9_canary_merge_publishes_no_snapshot_ref(self):
        """Канареечная задача закрыта мержем — ссылка
        `refs/artifacts/<id>` в origin целевого не появляется.

        Ловит мутацию: вычисление исхода по состоянию задачи поставлено
        ПЕРЕД проверкой канарейки и заодно публикует снимок (например,
        ранний возврат по `is_canary` заменён на передачу исхода дальше) —
        ссылка появится, и проверка ниже её увидит.
        """
        # Артефактная ветка у канарейки песочницей всё же заводится:
        # тогда `snapshot.pending` истинно и единственное, что удерживает
        # публикацию, — само исключение канарейки, то есть предмет AC-9.
        self.seed_merge_gate_task(MERGED_CANARY, is_canary=True)

        self.approve_merge(MERGED_CANARY)

        self.assertFalse(
            self.snapshot_ref_exists(MERGED_CANARY),
            f"канареечный прогон не публикует снимок: ссылки "
            f"{self.snapshot_ref(MERGED_CANARY)} в origin целевого быть не "
            f"должно (AC-9)")

    def test_ac9_canary_kill_publishes_no_snapshot_ref(self):
        """То же на пути `kill`.

        Ловит мутацию: исключение канарейки снято на пути `kill` (он
        зовёт публикацию первым и правится в этой задаче первым) — ссылка
        `refs/artifacts/<id>` появится в origin целевого.
        """
        self.seed_task(KILLED_CANARY, "in_dev", is_canary=True)

        self.capture(cleanup.cmd_kill, KILLED_CANARY)

        self.assertFalse(
            self.snapshot_ref_exists(KILLED_CANARY),
            f"канареечный прогон не публикует снимок: ссылки "
            f"{self.snapshot_ref(KILLED_CANARY)} в origin целевого быть не "
            f"должно (AC-9)")


if __name__ == "__main__":
    unittest.main()
