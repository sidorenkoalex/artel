"""AC-1, AC-2 — 01M31ZHWJWRSACYMRWTCPBC0DM: строка `status` несёт суммарные
токены задачи рядом с «$spent/budget», а задача без записей токенов —
прочерк вместо нуля.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `status` печатает по каждой задаче суммарное число токенов рядом с
«$spent/budget», и на задачу приходится ровно одна строка вывода.

AC-2. Задача без записей токенов показывает в строке `status` прочерк, а
не ноль.

Красен до реализации: `catalog.cmd_status` печатает строку задачи одним
`print` с «${spent}/{budget}» и заголовком, числа токенов в ней нет вовсе
(`orchestrator/catalog.py:551-556`) — ни суммы 180 у задачи с записями,
ни прочерка у задачи без них.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tokens  # noqa: E402
from orchestrator import catalog  # noqa: E402
from tests.sandbox import capture  # noqa: E402


class StatusShowsTotalTokensTest(_tokens.TokensSandbox):

    def setUp(self):
        super().setUp()
        self.charge_two_roles()
        self.charge_without_tokens(self.SILENT, _tokens.DEV_ROLE,
                                   _tokens.SILENT_USD)
        self.out = capture(catalog.cmd_status)

    def line_for(self, task_id: str) -> str:
        lines = [ln for ln in self.out.splitlines() if task_id in ln]
        self.assertEqual(1, len(lines),
                         f"на задачу {task_id} ожидалась ровно одна строка "
                         f"`status`, получено {len(lines)}:\n{self.out}")
        return lines[0]

    def test_ac1_task_line_carries_the_total_token_count_next_to_money(self):
        """Задача с двумя оплаченными шагами (`developer` 60 токенов,
        `reviewer` 120) показана в `status` одной строкой, где рядом с
        «$3.75/25.00» стоит суммарное число 180.

        Ловит мутацию: показ складывает токены не по задаче, а берёт
        число последнего шага (или суммирует только строки «agent cost
        KNOWN» одной роли) — в строке окажется 120 или 60, а не 180, и
        `assertIn` покраснеет. Проверка «ровно одна строка» ловит
        встречную мутацию: разбивку печатают дополнительной строкой на
        задачу, и `status` перестаёт быть однострочным по задаче.
        """
        line = self.line_for(self.TASK)

        self.assertIn(f"${_tokens.DEV_USD + _tokens.REV_USD:.2f}/", line)
        self.assertIn(str(_tokens.TASK_TOTAL), line,
                      f"суммарного числа токенов {_tokens.TASK_TOTAL} нет в "
                      f"строке задачи: {line}")

    def test_ac1_every_task_takes_exactly_one_line(self):
        """Обе задачи пульта — и с записями токенов, и без них — занимают
        в выводе `status` по одной строке каждая.

        Ловит мутацию: прочерк (или разбивка по видам) печатается
        отдельной строкой под задачей — число строк на задачу станет
        двумя, и `line_for` покраснеет на любой из двух задач.
        """
        for task_id in (self.TASK, self.SILENT):
            with self.subTest(task=task_id):
                self.assertTrue(self.line_for(task_id).strip())

    def test_ac2_task_without_token_records_shows_a_dash_not_zero(self):
        """Задача, у которой шаг завершился без разбивки usage (деньги
        списаны, токенов не записано), показана прочерком; в её строке нет
        ни одного «голого» нуля, а у задачи с записями прочерка нет.

        Ловит мутацию: сумма токенов считается `sum(...)` по пустому
        списку и печатается как есть — в строке появится «0 токенов»
        (голый ноль) вместо прочерка, и обе проверки ниже покраснеют.
        """
        silent = self.line_for(self.SILENT)
        known = self.line_for(self.TASK)

        self.assertTrue(
            _tokens.has_dash(silent),
            f"задача без записей токенов показана без прочерка: {silent}")
        self.assertEqual(
            [], _tokens.bare_zeros(silent),
            f"ноль вместо прочерка в строке задачи без токенов: {silent}")
        self.assertFalse(
            _tokens.has_dash(known),
            f"задача С записями токенов не должна показывать прочерк: {known}")


if __name__ == "__main__":
    unittest.main()
