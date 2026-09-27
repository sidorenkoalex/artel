"""AC-4 — 01M3H1Z489CKJ8FHSRS4TYTPX2: предупреждение о пересечении зон
берёт target подзадачи и заведение подзадачи отказом не становится.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Предупреждение о пересечении использует target подзадачи и не
превращает её заведение в отказ; план обосновывает размещение записи зон
и предупреждения относительно `update_task(parent_task_id)` в
`spawn_subtask`.

Наблюдаемое следствие «использует target подзадачи» — асимметрия двух
заведений с ОДНИМ И ТЕМ ЖЕ пересечением: подзадача чужого target'а
предупреждения не получает (замок зон — механика только основного
target'а, очереди для такой задачи не будет никогда), подзадача
основного — получает. Одного отрицательного ассерта мало: он зеленел бы
и на сверке, сломанной целиком.

Вторую половину критерия — обоснование в плане — проверяет
`test_ac4_plan_justifies_the_placement.py` (PLAN.md живёт в артефактной
ветке, отдельный предмет и отдельный источник).

Красен до реализации: сегодня `spawn_subtask` о пересечении зон не
предупреждает ни при каком target'е, поэтому контрольное заведение на
основном target'е id родителя не называет — ассерт асимметрии падает;
падает и ассерт «предупреждение напечатано, а подзадача заведена».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import catalog, config  # noqa: E402


class WarningUsesSubtaskTargetTest(_sandbox.SubtaskZoneSandbox):

    def setUp(self):
        super().setUp()
        self.set_parent_zones(_sandbox.SHARED_ZONE)
        self.assertNotEqual(
            config.DEFAULT_TARGET, _sandbox.FOREIGN_TARGET,
            "фикстурный чужой target совпал с основным — сценарий "
            "критерия не воспроизводится")

    def test_ac4_subtask_of_a_foreign_target_gets_no_warning(self):
        """Две подзадачи с одним и тем же пересечением (зона родителя):
        заведённая с чужим target'ом ни строки о родителе не печатает, ни
        записи о пересечении не пишет, а заведённая с основным — печатает.

        Ловит мутацию: target подзадачи в сверку не передан (вызов
        `_warn_zone_overlap(conn, task_id, tz)` без четвёртого аргумента,
        то есть с дефолтом «основной») — подзадача внешнего target'а
        уносила бы в журнал обещание очереди замка зон, которой для её
        target'а не бывает; асимметрия с парной механикой `cmd_new`
        осталась бы незамеченной.
        """
        out_foreign, foreign = self.spawn(
            _sandbox.tz_body(_sandbox.SHARED_ZONE), title="Часть чужого",
            target=_sandbox.FOREIGN_TARGET)

        self.assertEqual(
            [], _sandbox.overlap_lines(out_foreign, _sandbox.PARENT_ID,
                                       _sandbox.SHARED_ZONE),
            f"подзадача чужого target'а {foreign} получила предупреждение "
            f"о пересечении:\n{out_foreign}")
        self.assertNotIn(
            catalog.ZONE_OVERLAP_ACTION, self.journal_actions(foreign),
            f"в журнале подзадачи чужого target'а {foreign} появилась "
            f"запись о пересечении зон")

        out_main, main_part = self.spawn(
            _sandbox.tz_body(_sandbox.SHARED_ZONE), title="Часть основного")

        self.assertTrue(
            _sandbox.overlap_lines(out_main, _sandbox.PARENT_ID,
                                   _sandbox.SHARED_ZONE),
            f"подзадача основного target'а {main_part} с тем же "
            f"пересечением предупреждения не получила — сверка молчит для "
            f"любого target'а, а не только для чужого:\n{out_main}")

    def test_ac4_overlap_does_not_turn_the_spawn_into_a_refusal(self):
        """Заведение части с пересечением печатает предупреждение и при
        этом остаётся заведением: id возвращён, строка задачи стоит в
        `spec_writing`, привязка к родителю на месте, а зоны записаны.

        Ловит мутацию: сверка оформлена отказом по образцу соседнего
        `_tz_path_refusal` (`sys.exit`) — заведение подняло бы `SystemExit`
        посреди деления, оставив родителя поделённым на часть подзадач;
        либо запись зон слита с привязкой к родителю в один
        `store.update_task` и поле `parent_task_id` из него выпало — часть
        деления потеряла бы ссылку на родителя.
        """
        _control_out, control = self.spawn(
            _sandbox.tz_body(_sandbox.OTHER_ZONE), title="Часть без пересечения")
        self.assertNotIn(
            catalog.ZONE_OVERLAP_ACTION, self.journal_actions(control),
            f"контрольная часть {control} с зоной {_sandbox.OTHER_ZONE} с "
            f"зонами родителя не пересекается, но запись о пересечении в её "
            f"журнале есть")

        out, sub_id = self.spawn(_sandbox.tz_body(_sandbox.SHARED_ZONE),
                                 title="Часть с пересечением")

        self.assertTrue(
            _sandbox.overlap_lines(out, _sandbox.PARENT_ID,
                                   _sandbox.SHARED_ZONE),
            f"часть {sub_id} с зоной родителя предупреждения не получила:\n"
            f"{out}")
        row = self.row(sub_id)
        self.assertEqual(
            "spec_writing", row["state"],
            f"часть {sub_id} с пересечением обязана быть заведена так же, "
            f"как контрольная {control}: {dict(row)}")
        self.assertEqual(
            _sandbox.PARENT_ID, row["parent_task_id"],
            f"часть {sub_id} потеряла привязку к родителю деления")
        self.assertEqual(
            {_sandbox.SHARED_ZONE}, _sandbox.zone_set(row["zones"]),
            f"часть {sub_id} с пересечением осталась без предварительных "
            f"зон: {row['zones']!r}")


if __name__ == "__main__":
    unittest.main()
