"""Приёмочный тест AC-2 задачи 01M3H3JW9XE1THF0HK8RESZ0CV.

AC-2: `budget.count_zone_paths` для ТЗ с переносом внутри пути
возвращает то же число зон, что для того же ТЗ без переноса; кандидаты
упоминаний путей не входят в это число, а результат строк без переноса
не меняется.

Зелёный с рождения: сегодня счёт идёт по запятым и переносом не сбивается — тест держит это свойство при переводе счёта на общий разбор строки зон, где кандидаты упоминаний и обрывки могли бы в него попасть.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import budget  # noqa: E402

# Те же три точки разрыва пути, что у AC-1: (голова, хвост).
WRAPPED_PATHS = {
    "/": ("orchestrator/", "budget.py"),
    "_": ("orchestrator/zone_", "lock.py"),
    "-": ("docs/reference/role-", "home.md"),
}

# Строки зон без переноса и число зон, которое пульт считает по ним
# сегодня, — калибровка бюджета обязана остаться прежней.
UNWRAPPED_COUNTS = (
    (None, 0),
    ("", 0),
    ("tests/", 1),
    ("scripts/guard.py, orchestrator/budget.py, tests/.", 3),
    ("scripts/guard.py.", 1),
    ("a, , b", 2),
)


class CountZonePathsWrappedTest(unittest.TestCase):

    def test_ac2_wrapped_zone_line_counts_as_flat_one(self):
        """Число зон строки с разрывом пути равно числу зон той же
        строки без разрыва.

        Для каждой из трёх точек разрыва («/», «_», «-») строка зон из
        трёх элементов считается дважды: с переносом внутри среднего
        пути и без него — число обязано совпасть и остаться тройкой.

        Ловит мутацию: счёт переведён на «тот же разбор» делением по
        запятым И по переносам строк (`re.split(r"[,\\n]", …)`) — строка
        с переносом внутри пути даёт четыре зоны вместо трёх.
        """
        for brk, (head, tail) in WRAPPED_PATHS.items():
            with self.subTest(разрыв=brk):
                wrapped = f"scripts/guard.py, {head}\n    {tail}, tests/."
                flat = f"scripts/guard.py, {head}{tail}, tests/."

                self.assertEqual(budget.count_zone_paths(wrapped), 3)
                self.assertEqual(budget.count_zone_paths(wrapped),
                                 budget.count_zone_paths(flat))

    def test_ac2_path_mentions_inside_zone_line_are_not_counted(self):
        """Путь, упомянутый в пояснении рядом с зоной, число зон не
        увеличивает.

        Строка зон «scripts/guard.py (см. docs/stack.md), tests/» несёт
        две зоны и одно упоминание пути внутри скобок; в счёт идут
        только элементы перечня — и когда пояснение разорвано переносом,
        тоже.

        Ловит мутацию: `count_zone_paths` переписан на
        `len(guard.zone_items(text))` — кандидаты упоминаний путей
        (`scripts/guard.py`, `docs/stack.md`) попадают в счёт и две зоны
        превращаются в четыре.
        """
        flat = "scripts/guard.py (см. docs/stack.md), tests/"
        wrapped = "scripts/guard.py (см. docs/\n    stack.md), tests/"

        self.assertEqual(budget.count_zone_paths(flat), 2)
        self.assertEqual(budget.count_zone_paths(wrapped), 2)

    def test_ac2_lines_without_wrap_keep_previous_counts(self):
        """Строки зон без переноса считаются ровно как до задачи.

        Вырожденные входы (`None`, пустая строка), завершающая точка
        предложения ТЗ и пустой элемент между запятыми дают те же числа,
        что пульт считал по этим строкам раньше.

        Ловит мутацию: при переходе на общий разбор потерян отсев пустых
        элементов (или снятие завершающей точки) — «a, , b» начинает
        считаться за три зоны.
        """
        for text, expected in UNWRAPPED_COUNTS:
            with self.subTest(строка=text):
                self.assertEqual(budget.count_zone_paths(text), expected)


if __name__ == "__main__":
    unittest.main()
