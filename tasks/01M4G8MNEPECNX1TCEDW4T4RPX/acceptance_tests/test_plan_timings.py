"""AC-8 — PLAN содержит замер времени двух медленных тестов требования 8 до и после правки; «после» — не больше 40 с.

PLAN.md читается из ссылки документов помощником пульта
(`_pult.artifact_text`). Замер теста узнаётся по строке PLAN, называющей
тест именем метода (`test_ac7_duration_calibrates_and_ignores_worker_changes`,
`test_ac8_temp_tree_absent_after_each_outcome`) или класса
(`DoctorDurationTest`, `TempTreeRemovedTest`). Принимаются две естественные
записи замера:

- строка с именем теста, в которой есть «до … N с» и «после … M с»
  (например «`DoctorDurationTest::test_ac7_…`: до 96 с, после 21 с»);
- строка таблицы Markdown с именем теста, у таблицы в заголовке есть
  столбец со словом «до» и столбец со словом «после»; значения столбцов —
  числа секунд (с единицей «с»/«s»/«сек» или без).

Числа — целые или десятичные (точка или запятая). Слово «параллельн…» в
PLAN планка требует: замер по критерию — при параллельном прогоне.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer после этого шага) — `artifact_text("PLAN.md")` возвращает `None`, замеров нет.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import artifact_text  # noqa: E402

LIMIT_SEC = 40.0
TESTS = {
    "DoctorDurationTest::test_ac7_duration_calibrates_and_ignores_worker_changes":
        ("test_ac7_duration_calibrates_and_ignores_worker_changes",
         "DoctorDurationTest"),
    "TempTreeRemovedTest::test_ac8_temp_tree_absent_after_each_outcome":
        ("test_ac8_temp_tree_absent_after_each_outcome", "TempTreeRemovedTest"),
}
NUMBER = r"(\d+(?:[.,]\d+)?)"
UNIT = r"\s*(?:с|сек\w*|s|sec\w*)\b"
INLINE_BEFORE = re.compile(rf"(?<!\w)до\b[^\d|]{{0,40}}?{NUMBER}{UNIT}",
                           re.IGNORECASE)
INLINE_AFTER = re.compile(rf"(?<!\w)после\b[^\d|]{{0,40}}?{NUMBER}{UNIT}",
                          re.IGNORECASE)
CELL_NUMBER = re.compile(rf"^\D{{0,10}}?{NUMBER}(?:{UNIT})?\s*$",
                         re.IGNORECASE)


def number(text: str) -> float:
    return float(text.replace(",", "."))


def mentions(line: str, names: tuple) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", line) for n in names)


def cells(line: str) -> list:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_measures(lines: list, names: tuple) -> list:
    """(до, после) из строк таблиц Markdown, называющих тест."""
    found = []
    header = None
    for line in lines:
        if not line.strip().startswith("|"):
            header = None
            continue
        row = cells(line)
        if all(re.fullmatch(r":?-{2,}:?", c) for c in row if c):
            continue
        if header is None:
            header = row
            continue
        if not mentions(line, names):
            continue
        before_col = [i for i, c in enumerate(header)
                      if re.search(r"(?<!\w)до\b", c, re.IGNORECASE)]
        after_col = [i for i, c in enumerate(header)
                     if re.search(r"(?<!\w)после\b", c, re.IGNORECASE)]
        if not before_col or not after_col:
            continue
        values = []
        for col in (before_col[0], after_col[0]):
            match = CELL_NUMBER.match(row[col]) if col < len(row) else None
            values.append(number(match.group(1)) if match else None)
        if None not in values:
            found.append(tuple(values))
    return found


def inline_measures(lines: list, names: tuple) -> list:
    found = []
    for line in lines:
        if not mentions(line, names):
            continue
        before, after = INLINE_BEFORE.search(line), INLINE_AFTER.search(line)
        if before and after:
            found.append((number(before.group(1)), number(after.group(1))))
    return found


class PlanTimingsTest(unittest.TestCase):

    def test_ac8_plan_records_before_after_timings_after_within_40s(self):
        """PLAN называет оба теста требования 8 с замером «до» и «после»; «после» ≤ 40 с.

        Сценарий: PLAN.md из ссылки документов; для каждого из
        `DoctorDurationTest::test_ac7_…` и `TempTreeRemovedTest::test_ac8_…`
        ищется строка-замер (строка с «до N с … после M с» или строка
        таблицы со столбцами «до»/«после»); у каждого теста замер найден, и
        во всех его замерах «после» не больше 40 с; в PLAN есть упоминание
        параллельного прогона.

        Ловит мутацию: в PLAN замер только одного из двух тестов — второй
        назван в сообщении; записано только «после» без «до» — замера нет;
        тест ускорен до 55 с (больше трети лимита pytest-timeout) — «после»
        55 > 40, сообщение называет тест и число.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        lines = plan.splitlines()
        self.assertRegex(plan, re.compile(r"параллельн", re.IGNORECASE),
                         "PLAN не говорит, что замер — при параллельном прогоне")
        problems = []
        for label, names in TESTS.items():
            measures = table_measures(lines, names) + inline_measures(lines, names)
            if not measures:
                problems.append(f"{label}: замера «до»/«после» в PLAN нет")
                continue
            slow = [after for _, after in measures if after > LIMIT_SEC]
            if slow:
                problems.append(f"{label}: «после» {slow} с больше "
                                f"{LIMIT_SEC:g} с")
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
