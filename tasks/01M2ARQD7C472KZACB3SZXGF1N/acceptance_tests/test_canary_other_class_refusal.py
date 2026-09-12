"""Приёмочный тест SPEC 01M2ARQD7C472KZACB3SZXGF1N, AC-5: отказ ДРУГОГО
класса (не «переход отклонён: приёмочные тесты») на выходе `in_dev`
(планка не найдена в источнике, зоны, гейт заявки мутации, лок планки)
не лечится повтором developer — поведение `canary._drive_task` здесь
требование 4 предписывает сохранить байт-в-байт, как до этой задачи.

Зелёный с рождения: сценарий не задействует НИ ОДНОЙ строки кода,
которую эта задача добавляет (ветка повтора developer в `_drive_task`),
— он проверяет, что УЖЕ СУЩЕСТВУЮЩАЯ, не тронутая этой задачей стагнация
(`config.CANARY_MAX_STALL_ITERS`, `_kill_inconclusive`) отрабатывает
как прежде на отказе, который не совпадает с «переход отклонён:
приёмочные тесты»; поведение это уже покрыто `tests/test_canary.py::
DriveTaskStallCapTest` до этой задачи и не меняется её требованием 4.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import canary, config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

OTHER_CLASS_REFUSAL = "переход отклонён: гейт зон"


class DriveTaskOtherClassRefusalDoesNotRetryTest(TmpRootTest):
    """AC-5: отказ другого класса (не «переход отклонён: приёмочные
    тесты») в `in_dev` — повтором developer не лечится, поведение —
    прежняя стагнация до `config.CANARY_MAX_STALL_ITERS`."""

    TASK = "ACDEV5"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача AC-5",
                          "in_dev", "task/acdev5-x", config.DEFAULT_TARGET,
                          50.0, is_canary=True)

        def fake_auto(task_id):
            store.journal(self.conn, task_id, "fsm", OTHER_CLASS_REFUSAL,
                         "зона orchestrator/canary.py занята другой задачей")

        patcher = mock.patch.object(canary.auto, "cmd_auto",
                                    side_effect=fake_auto)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.runner, "cmd_run")
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(canary.cleanup, "cmd_kill")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac5_other_class_refusal_falls_back_to_stagnation_path(self):
        """Отказ гейта зон (пример требования 4, другой класс) повторяется
        подряд — цикл НЕ зовёт `runner.cmd_run` ни разу, задача убивается
        прежним путём стагнации (`config.CANARY_MAX_STALL_ITERS` проходов
        без прогресса), поведение — байт-в-байт как до этой задачи.

        Ловит мутацию: детектор повтора развязан слишком широко (реагирует
        на ЛЮБОЙ `переход отклонён: ...`, не только «приёмочные тесты») —
        тогда `runner.cmd_run` был бы вызван на этом сценарии, а задача
        убита текстом требования 3 вместо стагнации.
        """
        canary._drive_task(self.conn, self.TASK)

        canary.runner.cmd_run.assert_not_called()
        canary.cleanup.cmd_kill.assert_called_once_with(self.TASK)
        rows = store.open_alerts(self.conn, "threshold")
        matching = [r for r in rows if r["target"] == self.TASK]
        self.assertTrue(
            any("проходов подряд без прогресса" in r["message"]
               for r in matching),
            [r["message"] for r in matching])
        self.assertEqual(store.get_task(self.conn, self.TASK)["state"], "in_dev")


if __name__ == "__main__":
    unittest.main()
