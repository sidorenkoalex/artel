"""AC-4 (tasks/01M2YWRB9HWW99R57HWGP2M7MQ/SPEC.md): задача в `spec_gate`,
`reject <id> ""` (причина пустая или из одних пробелов) — команда
отказывает, состояние остаётся `spec_gate`, записи `state -> spec_writing`
в журнале нет.

Механизм отказа критерий не называет («команда отказывает»), поэтому
проверяется именно названное им: состояние и отсутствие записи перехода.
Форма отказа приводится к тексту в `_sandbox.run_reject` — см. докстринг
того модуля.

Красен до реализации: ветки `spec_gate` в `_cmd_reject` ещё нет вовсе, и
пустая причина отказывает по ДРУГОЙ причине — общим «reject применим только
в acceptance, merge_gate или verifying». Состояние при этом случайно
совпадает с ожидаемым, поэтому оба теста ниже требуют ещё и того, чего
сегодня нет: отказа, который наступает ИМЕННО из-за пустой причины —
непустая причина в том же состоянии обязана сработать (контроль в
`test_ac4_non_empty_reason_on_the_same_gate_passes`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

# Пустая причина в двух формах, названных критерием.
EMPTY_REASONS = {"пустая строка": "", "одни пробелы": "   \t  "}


class EmptyReasonOnSpecGateTest(_sandbox.SpecGateRejectSandbox):

    def test_ac4_empty_reason_leaves_the_task_on_the_gate(self):
        """Оператор нажал `reject` без причины (пустая строка и строка из
        пробелов) — задача остаётся на `spec_gate`, и в журнале не
        появляется ни одной записи `state -> spec_writing`: возврат без
        причины не состоялся, а не состоялся молча.

        Ловит мутацию: проверка причины написана как `if reason is None`
        (или `if not reason`, не снимающее пробелы) — строка из пробелов
        пройдёт, задача уедет в `spec_writing` с пустой причиной в detail.
        """
        for name, reason in EMPTY_REASONS.items():
            with self.subTest(причина=name):
                self.enter_state("spec_gate",
                                 _sandbox.SPEC_GATE_ENTRY_DETAIL)
                before = len(self.transition_details("spec_writing"))

                out = self.run_reject(reason)

                self.assertEqual(
                    self.state(), "spec_gate",
                    f"пустая причина увела задачу с гейта; вывод "
                    f"команды: {out!r}")
                self.assertEqual(
                    len(self.transition_details("spec_writing")), before,
                    f"пустая причина оставила в журнале запись перехода; "
                    f"вывод команды: {out!r}")

    def test_ac4_non_empty_reason_on_the_same_gate_passes(self):
        """Контроль: в том же состоянии той же задачи непустая причина
        возвращает её аналитику — отказ AC-4 наступает из-за пустой
        причины, а не из-за того, что `reject` на `spec_gate` отказывает
        вообще всегда (сегодняшнее поведение, на котором тест выше был бы
        зелёным по неверному основанию).

        Ловит мутацию: проверка причины написана слишком широко
        (например, отказ на любой причине короче N символов или
        безусловный отказ, оставшийся от старой ветки) — законный возврат
        с причиной тоже не состоится.
        """
        out = self.reject_from("spec_gate", _sandbox.REASON)

        self.assertEqual(
            self.state(), "spec_writing",
            f"непустая причина не вернула задачу аналитику; вывод "
            f"команды: {out!r}")
        self.assertTrue(self.transition_details("spec_writing"))


if __name__ == "__main__":
    unittest.main()
