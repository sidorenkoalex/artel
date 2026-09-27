"""AC-4 — 01M3HJQV2QV9BXNXSH3F8STAYH: первая строка вывода прогона называет
выбранные шаблоны в порядке прогона и печатается до первого клона.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Первая строка вывода прогона содержит имена выбранных шаблонов в
порядке прогона и печатается до создания первого эфемерного клона.

«До создания первого эфемерного клона» снимается наблюдателем
`canary.subprocess.run` (`_util.PoolSandbox.output_before_first_clone`):
на первом `git clone` он фотографирует уже напечатанное и прерывает
прогон — то есть сверяется именно то, что Оператор успевает увидеть ДО
самой долгой операции прогона.

Красен до реализации: без флага `--template` его вовсе нет, а первая строка
прогона называет только число задач и пул (`canary.py`, «прогон <штамп>: N
задач из пула …») — имён шаблонов в ней нет ни в каком порядке.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

#: Порядок прогона, заведомо не совпадающий с алфавитным порядком пула:
#: иначе «в порядке прогона» было бы неотличимо от «как отсортировано».
ORDER = ["plank-gamma", "plank-alpha"]


class FirstLineNamesTemplatesTest(_util.PoolSandbox):

    def _argv(self) -> list:
        return ["--k", str(len(ORDER)), "--template", ",".join(ORDER),
                "--sha", self.head]

    def test_ac4_first_line_lists_the_chosen_templates_in_run_order(self):
        """Самая первая строка вывода называет оба выбранных шаблона, и
        именно в порядке прогона.

        Ловит мутацию: имена печатаются в отчёте КАЖДОЙ задачи (строка
        «заведена из …» уже есть сегодня), а первая строка прогона оставлена
        прежней — Оператор узнавал бы состав прогона только по мере того, как
        задачи одна за другой доходят до конца, то есть через десятки минут.
        """
        _titles, out = self.run_templates(self._argv())

        first = out.splitlines()[0]
        for title in ORDER:
            self.assertIn(title, first,
                          f"первая строка вывода не называет {title}: {first}")
        self.assertLess(first.index(ORDER[0]), first.index(ORDER[1]),
                        f"порядок имён в первой строке не порядок прогона: "
                        f"{first}")

    def test_ac4_the_line_is_printed_before_the_first_ephemeral_clone(self):
        """К моменту первого `git clone` первая строка с именами шаблонов уже
        напечатана.

        Ловит мутацию: строка собирается и печатается внутри цикла по
        задачам (или после разрешения целевого sha и входа в клон) — при
        падении первого же клона Оператор не знал бы даже, что именно
        запускалось, а ровно за этим состав прогона и печатается.
        """
        printed = self.output_before_first_clone(self._argv())

        self.assertTrue(printed.strip(),
                        "к моменту первого клона не напечатано ничего")
        first = printed.splitlines()[0]
        for title in ORDER:
            self.assertIn(title, first,
                          "первая строка, напечатанная до первого клона, не "
                          f"называет {title}: {first}")


if __name__ == "__main__":
    unittest.main()
