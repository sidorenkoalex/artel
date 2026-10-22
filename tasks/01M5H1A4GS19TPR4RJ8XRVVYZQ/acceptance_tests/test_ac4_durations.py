"""AC-4: методы разбиения и старые имена — не дольше 10 с (у `test_ac20` — 20 с) на свободной машине; замеры в PLAN.md.

Группа: разовый
Красен до реализации: PLAN.md с замерами `--durations` «до»/«после» ещё нет; на свободной машине старые имена длятся дольше порога (замеры ТЗ: 14–26 с, `test_ac20` — 32 с), под нагрузкой замер по условию критерия не берётся. Стабом не провалидирован: при написании загрузка была 17–61 (замер по условию критерия невозможен), PLAN.md читается из ссылки документов.

Замер — настоящий прогон каждого кандидата файла (старые имена и новые
методы) из копии модуля головы, время `TestCase.run` вместе с `setUp`.
Условие критерия «на свободной машине» проверяется в начале каждой части:
средняя загрузка за минуту ниже 4 — пороги утверждаются; иначе замер по
условию критерия невозможен и часть ничего не гоняет (загрузка печатается).
Ловит мутацию у частей — одна на файл: метод со старым именем или доля
исполняет слишком много подслучаев и длится дольше порога.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _split as S  # noqa: E402


# AC-4: manual — замеры длительностей идут только на свободной машине (загрузка ниже 4) и одни занимают около 258 с, вся планка около 390 с — больше предела прогона планки 300 с (ACCEPTANCE_TIMEOUT_SEC); исполнено Оператором 22.10.2026 при загрузке 1,72 на голове 58f05286: прежние 13 частей замера, 14 passed, 63 подслучая зелёные за 257,6 с (решение Оператора 22.10)


class DurationTest(unittest.TestCase):

    def test_ac4_plan_has_durations_before_and_after(self):
        """PLAN.md несёт замеры `--durations` «до» и «после» по каждому из четырёх файлов и загрузку.

        Сценарий: PLAN.md из ссылки документов задачи называет
        `--durations`, «до» и «после», имя каждого из четырёх файлов зоны,
        неразбиваемые `test_ac17_reject_does_not_reset_return_counter` и
        `test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit` и
        значение загрузки (слово «загрузк…» рядом с числом).

        Ловит мутацию: замер сделан по одному файлу или без значения
        загрузки — имени файла или загрузки в PLAN нет.
        """
        plan = S.plan_text()
        self.assertIn("--durations", plan)
        self.assertRegex(plan, r"(?i)\bдо\b")
        self.assertRegex(plan, r"(?i)\bпосле\b")
        for rel in S.ZONE:
            self.assertIn(Path(rel).stem, plan, rel)
        for name in ("test_ac17_reject_does_not_reset_return_counter",
                     "test_ac6_red_kinds_rerun_twice_per_side_own_files_with_limit"):
            self.assertIn(name, plan)
        self.assertRegex(plan, r"(?is)загрузк.{0,80}?\d+[.,]\d+")


if __name__ == "__main__":
    unittest.main()
