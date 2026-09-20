"""AC-5 (tasks/01M2YWRB9HWW99R57HWGP2M7MQ/SPEC.md): `reject` из
`acceptance`, `merge_gate` и `verifying` ведёт себя как до задачи
(состояние-исход, detail записи, счётчики); `reject` в состоянии, где он
неприменим (`in_dev`), по-прежнему отказывает прежним текстом отказа.

Ожидаемые исходы трёх работающих состояний выписаны здесь по ФАКТИЧЕСКОМУ
коду `orchestrator/fsm.py::_cmd_reject` на момент написания планки (а не по
памяти): `acceptance` -> `in_dev`, detail «приёмка отклонена: <причина>»,
`accept_rejects` +1; `merge_gate`/`verifying` -> `in_dev`, detail «возврат
из <состояние>: <причина>», счётчики не трогаются. Это тест сохранения
существующего поведения — планка рефакторинга в чистом виде.

Про отказ в `in_dev`: критерий называет его «прежним текстом отказа», а
требование 7 — «прежним именованным отказом». Перечень состояний внутри
этого текста фиксировать дословно нельзя: требование 1 той же SPEC делает
`spec_gate` применимым, и перечисление законно меняется вместе с ним.
Поэтому проверяется то, в чём обе формулировки сходятся и что видит
Оператор: команда отказывает (состояние прежнее, записи перехода нет),
отказ именованный — того же класса «reject здесь неприменим» и называет
текущее состояние задачи.

Зелёный с рождения: это тест сохранения существующего поведения — все три
возврата и отказ в `in_dev` работают в `_cmd_reject` уже сегодня. Он
покраснеет, если реализация требований 1-4 заденет соседние ветки команды.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

# Состояние -> (исход, detail записи перехода) на момент написания планки.
UNCHANGED_RETURNS = {
    "acceptance": ("in_dev", "приёмка отклонена: {reason}"),
    "merge_gate": ("in_dev", "возврат из merge_gate: {reason}"),
    "verifying": ("in_dev", "возврат из verifying: {reason}"),
}

# Состояние, в котором `reject` неприменим и сегодня, и после задачи.
INAPPLICABLE_STATE = "in_dev"


class RejectElsewhereIsUnchangedTest(_sandbox.SpecGateRejectSandbox):

    def test_ac5_returns_from_acceptance_merge_gate_and_verifying_keep_their_outcome(self):
        """Для каждого из трёх состояний, где `reject` работал до задачи:
        задача уходит в `in_dev`, и detail записи перехода — прежний текст
        этого состояния (у `acceptance` — «приёмка отклонена», у двух
        других — «возврат из <состояние>»).

        Ловит мутацию: ветка `spec_gate` вписана общим циклом по таблице
        «состояние -> возврат» и заодно унифицирует detail соседей (все
        три получают «возврат из <состояние>») — `acceptance` потеряет
        свой текст «приёмка отклонена: …», по которому Оператор отличает
        отказ приёмки от возврата с гейта.
        """
        for state, (target, detail_tmpl) in UNCHANGED_RETURNS.items():
            with self.subTest(состояние=state):
                self.set_columns(accept_rejects=0)
                before = len(self.transition_details(target))

                out = self.reject_from(state, _sandbox.REASON)

                self.assertEqual(
                    self.state(), target,
                    f"reject из {state} привёл не в {target}; вывод "
                    f"команды: {out!r}")
                details = self.transition_details(target)
                self.assertEqual(
                    len(details), before + 1,
                    f"reject из {state} не оставил ровно одной записи "
                    f"«state -> {target}»; вывод команды: {out!r}")
                self.assertEqual(
                    details[-1],
                    detail_tmpl.format(reason=_sandbox.REASON))

    def test_ac5_only_acceptance_counts_the_reject(self):
        """Счётчик `accept_rejects` растёт ровно на отказе приёмки и
        только на нём: возвраты из `merge_gate` и `verifying` его не
        трогают, как и до задачи.

        Ловит мутацию: счётчик перенесён в общий узел возврата (растёт на
        каждом `reject`) — `merge_gate`/`verifying` начнут расходовать
        лимит отказов приёмки, который к ним отношения не имеет.
        """
        expected = {"acceptance": 1, "merge_gate": 0, "verifying": 0}
        for state, growth in expected.items():
            with self.subTest(состояние=state):
                self.set_columns(accept_rejects=0, review_iters=0)

                out = self.reject_from(state, _sandbox.REASON)

                review_iters, accept_rejects = self.counters()
                self.assertEqual(
                    accept_rejects, growth,
                    f"accept_rejects после reject из {state}: "
                    f"{accept_rejects}, ожидалось {growth}; вывод "
                    f"команды: {out!r}")
                self.assertEqual(
                    review_iters, 0,
                    f"reject из {state} тронул review_iters; вывод "
                    f"команды: {out!r}")

    def test_ac5_inapplicable_state_still_refuses_by_name(self):
        """Состояние, где команда неприменима (`in_dev`): задача остаётся
        на месте, записи перехода не появляется, а отказ — прежний
        именованный, того же класса «reject применим только …» и с именем
        текущего состояния в тексте.

        Ловит мутацию: ветка `spec_gate` вписана вместо финального
        `sys.exit` (или после него так, что он стал недостижим) — задача
        в `in_dev` либо уедет в `spec_writing`, либо отказ выродится в
        молчание/безымянный текст без «reject применим только» и без
        имени состояния.
        """
        before = len(self.transition_details("spec_writing"))

        out = self.reject_from(INAPPLICABLE_STATE, _sandbox.REASON)

        self.assertEqual(self.state(), INAPPLICABLE_STATE,
                         f"reject сдвинул задачу из {INAPPLICABLE_STATE}; "
                         f"вывод команды: {out!r}")
        self.assertEqual(
            len(self.transition_details("spec_writing")), before,
            f"reject в {INAPPLICABLE_STATE} оставил запись возврата "
            f"аналитику; вывод команды: {out!r}")
        self.assertIn(_sandbox.INAPPLICABLE_REFUSAL_HEAD, out)
        self.assertIn(INAPPLICABLE_STATE, out)


if __name__ == "__main__":
    unittest.main()
