"""AC-1 (tasks/01M2YWRB9HWW99R57HWGP2M7MQ/SPEC.md): задача в `spec_gate`,
`reject <id> "причина"` — состояние становится `spec_writing`, а в журнале
шагов появляется запись `state -> spec_writing` с detail «возврат из
spec_gate: причина».

Наблюдается через настоящий `fsm.cmd_reject` в лёгкой песочнице переходов:
критерий говорит о команде Оператора целиком (резолвинг id, lease, CAS),
а не о внутреннем узле, и поверхность у него ровно та, что читает Оператор
в `artel.py log` — состояние и запись журнала.

Красен до реализации: `_cmd_reject` (orchestrator/fsm.py, ветка `state !=
"acceptance"`) на `spec_gate` отвечает `sys.exit` «reject применим только в
acceptance, merge_gate или verifying» — задача остаётся в `spec_gate`,
записи `state -> spec_writing` не появляется вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class RejectOnSpecGateTest(_sandbox.SpecGateRejectSandbox):

    def test_ac1_reject_on_spec_gate_returns_the_task_to_the_analyst(self):
        """Задача песочницы стоит на `spec_gate`; Оператор отклоняет её с
        причиной — задача оказывается в `spec_writing`, и переход
        зажурналирован записью `state -> spec_writing`, чей detail несёт
        причину в форме «возврат из spec_gate: <причина>».

        Ловит мутацию: обработчик `spec_gate` скопирован с ветки
        `verifying` без правки целевого состояния (возврат уводит задачу в
        `in_dev`, как это делает reject из `verifying`/`merge_gate`) —
        состояние станет `in_dev`, а записи `state -> spec_writing` не
        будет ни одной.
        """
        out = self.reject_from("spec_gate", _sandbox.REASON)

        self.assertEqual(
            self.state(), "spec_writing",
            f"reject на spec_gate обязан вернуть задачу аналитику; "
            f"вывод команды: {out!r}")
        details = self.transition_details("spec_writing")
        self.assertTrue(
            details,
            f"нет записи «state -> spec_writing» в журнале: "
            f"{self.journal_rows()!r}")
        self.assertEqual(
            details[-1],
            _sandbox.RETURN_DETAIL_TMPL.format(state="spec_gate",
                                                reason=_sandbox.REASON))

    def test_ac1_return_record_carries_the_operator_reason_verbatim(self):
        """Причина Оператора попадает в detail записи дословно — вместе с
        кавычками и двоеточием, без обрезки и переформулирования: именно
        этот текст читает Оператор в журнале и получает аналитик (AC-6).

        Ловит мутацию: detail собран по фиксированному тексту («SPEC
        отклонён на гейте») с причиной в отдельной колонке/без неё вовсе
        — запись появится, состояние сменится, но текст причины в detail
        не найдётся.
        """
        out = self.reject_from("spec_gate", _sandbox.REASON)

        details = self.transition_details("spec_writing")
        self.assertTrue(
            details,
            f"нет записи «state -> spec_writing» в журнале; вывод "
            f"команды: {out!r}")
        detail = details[-1]
        self.assertIn(_sandbox.REASON, detail)
        self.assertTrue(
            detail.startswith("возврат из spec_gate:"),
            f"detail не назван возвратом из spec_gate: {detail!r}")


if __name__ == "__main__":
    unittest.main()
