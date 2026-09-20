"""AC-3 (tasks/01M2YWRB9HWW99R57HWGP2M7MQ/SPEC.md): после возврата AC-1
`tasks.zones` и `budget_usd` задачи равны значениям до команды — содержимое
отклонённого SPEC в них не записано.

Чтобы «не записано» было наблюдаемо, SPEC.md на ветке-источнике задачи
несёт ДРУГИЕ `zones`/`budget_usd`, чем стоят в колонках: совпади они, тест
проходил бы и при реализации, которая честно перечитывает отклонённый SPEC
и применяет его значения (`_approve_spec_gate` делает именно это — но
только на `approve`).

Красен до реализации: reject на `spec_gate` ещё отказывает целиком
(`_cmd_reject`) — предпосылка критерия «после возврата AC-1» не наступает,
задача остаётся в `spec_gate`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

# Зоны, стоящие в колонке до команды, и зоны отклонённого SPEC — разные
# строки: подхват содержимого SPEC виден по подмене одной другой.
ZONES_BEFORE = "orchestrator/fsm.py"
ZONES_IN_REJECTED_SPEC = "orchestrator/auto.py, orchestrator/brief.py"


class ZonesAndBudgetUntouchedByTheSpecGateReturnTest(
        _sandbox.SpecGateRejectSandbox):

    def test_ac3_zones_of_the_rejected_spec_are_not_written(self):
        """У задачи на `spec_gate` в колонке `zones` стоят зоны прошлой,
        уже принятой редакции; отклоняемый SPEC на ветке называет другие
        зоны. После возврата в колонке остаются прежние: зоны пишет
        `approve`, не `reject`.

        Ловит мутацию: обработчик `spec_gate` в `_cmd_reject` собран
        копированием `_approve_spec_gate` (читает SPEC с ветки и зовёт
        `store.update_task(..., zones=meta.get("zones"))`) с заменой
        одного лишь целевого состояния — в колонке окажутся зоны
        отклонённого SPEC.
        """
        self.write_spec(zones=ZONES_IN_REJECTED_SPEC,
                        budget=self.spec_budget_value())
        self.set_columns(zones=ZONES_BEFORE)
        before = self.zones_and_budget()

        out = self.reject_from("spec_gate", _sandbox.REASON)

        self.assertEqual(
            self.state(), "spec_writing",
            f"возврат AC-1 не состоялся — предпосылка AC-3 не проверена; "
            f"вывод команды: {out!r}")
        self.assertEqual(self.zones_and_budget()[0], before[0],
                         "reject переписал tasks.zones содержимым "
                         "отклонённого SPEC")

    def test_ac3_budget_of_the_rejected_spec_is_not_applied(self):
        """Тот же возврат при потолке из отклонённого SPEC, отличном от
        потолка задачи (оба значения считаются от `config`, не литералами):
        `budget_usd` задачи после команды тот же, что до неё.

        Ловит мутацию: обработчик `spec_gate` зовёт `budget.
        apply_spec_budget(conn, t, meta)` — тот же второй вызов, что делает
        `approve` на этом же гейте, — и потолок задачи подтянется к
        значению отклонённого SPEC.
        """
        spec_budget = self.spec_budget_value()
        self.write_spec(zones=ZONES_IN_REJECTED_SPEC, budget=spec_budget)
        self.set_columns(zones=ZONES_BEFORE)
        before = self.zones_and_budget()
        self.assertNotEqual(
            before[1], spec_budget,
            "фикстура вырождена: потолок задачи совпал с потолком "
            "отклонённого SPEC — подхват значения был бы не виден")

        out = self.reject_from("spec_gate", _sandbox.REASON)

        self.assertEqual(
            self.state(), "spec_writing",
            f"возврат AC-1 не состоялся — предпосылка AC-3 не проверена; "
            f"вывод команды: {out!r}")
        self.assertEqual(self.zones_and_budget()[1], before[1],
                         "reject применил budget_usd отклонённого SPEC")


if __name__ == "__main__":
    unittest.main()
