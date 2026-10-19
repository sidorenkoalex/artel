"""Факты задачи: прежние утверждения разбора `new` и замер на волне G в PLAN.md.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан — раздела «Замер на волне G» нет; метод о неизменности `tests/test_new_argv_parsing.py` зелёный с рождения (ветка этот файл пока не трогала).

Дифф задачи — `branch_diff()` помощника пульта `_pult.py` (от точки
расхождения с `origin`), PLAN.md — `artifact_text("PLAN.md")` из ссылки
документов задачи.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import artifact_text, branch_diff  # noqa: E402

ARGV_TEST = "tests/test_new_argv_parsing.py"
WAVE_G = ("01M58FNWBV25FF26E7AZ9Q9912", "01M58PG72PG64GS790XM2EWS61",
          "01M590GJAF0EDV4NBC4C99MFVH")


def file_diff(diff: str, rel: str) -> str:
    """Часть unified-диффа `diff`, относящаяся к файлу `rel`."""
    parts = re.split(r"(?m)^diff --git ", diff)
    return "".join(p for p in parts
                   if p.split("\n", 1)[0].startswith(f"a/{rel} ")
                   or p.split("\n", 1)[0].endswith(f" b/{rel}"))


class ArgvParsingAssertionsTest(unittest.TestCase):

    def test_ac11_argv_parsing_assertions_not_changed(self):
        """Прежние утверждения `tests/test_new_argv_parsing.py` не меняются — только добавление.

        Сценарий: дифф задачи по `tests/test_new_argv_parsing.py` не несёт
        ни одной удалённой строки (`-` вне заголовка `---`); файл не
        удалён и не переименован.

        Ловит мутацию: разработчик правит прежний `assertEqual` на
        `(title, tz_path)` под третий элемент `_parse_new_args` или
        переписывает утверждение справки — в диффе появляются удалённые
        строки файла.
        """
        part = file_diff(branch_diff(), ARGV_TEST)
        self.assertNotIn("deleted file mode", part, part)
        self.assertNotIn("rename from", part, part)
        removed = [line for line in part.splitlines()
                   if line.startswith("-") and not line.startswith("---")]
        self.assertEqual(removed, [], part)


class WaveGMeasureTest(unittest.TestCase):

    def test_ac15_plan_has_wave_g_measure_table(self):
        """PLAN.md несёт раздел «Замер на волне G» с таблицей по трём задачам волны G.

        Сценарий: в PLAN.md задачи есть заголовок раздела со словами
        «Замер на волне G»; в теле раздела — таблица Markdown, шапка
        которой называет «задача», «предупреждений» и «совпало»; у каждой
        из трёх задач волны G (01M58FNW…, 01M58PG7…, 01M590GJ…) — строка
        таблицы с её идентификатором и числом предупреждений.

        Ловит мутацию: раздел не написан или назван иначе; таблица без
        одной из задач волны G; вместо числа предупреждений — пусто.
        Верность чисел и совпадений с вопросами аналитика сверяет
        Оператор на приёмке по самим ТЗ и QUESTIONS.md.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        match = re.search(r"(?m)^#+[^\n]*Замер на волне G[^\n]*\n(.*?)(?=^#{1,2} |\Z)",
                          plan, re.S)
        self.assertIsNotNone(match, "нет раздела «Замер на волне G»")
        rows = [line for line in match.group(1).splitlines()
                if line.strip().startswith("|")]
        self.assertTrue(rows, match.group(1))
        header = rows[0].lower()
        for word in ("задача", "предупреждений", "совпало"):
            self.assertIn(word, header, rows[0])
        for task in WAVE_G:
            with self.subTest(task=task):
                found = [row for row in rows[1:] if task in row]
                self.assertTrue(found, f"нет строки {task}: {rows}")
                cells = [c.strip() for c in found[0].strip().strip("|").split("|")]
                self.assertTrue(any(re.fullmatch(r"\d+", c) for c in cells[1:]),
                                found[0])


if __name__ == "__main__":
    unittest.main()
