"""AC-7 (tasks/01M1THKWFXFYNW28HDJGYHQWH6/SPEC.md, требование 7):
`docs/invariants.md`, инвариант 10, несёт формулировку: потолок задачи в
пределах `ROLE_BUDGET_CAP` вправе задать один раз и PLAN при первой сдаче
— не только SPEC на гейте SPEC; подъём потолка ВЫШЕ `ROLE_BUDGET_CAP`
остаётся исключительно действием Оператора командой `budget`.

Красен до реализации: сегодняшняя строка инварианта 10 —
«Поднять потолок может только Оператор командой `budget`» — не называет
ни `ROLE_BUDGET_CAP`, ни PLAN, ни SPEC как канал потолка задачи в его
пределах: часть 1 ADR-0014 (правка того же ряда под SPEC) ещё не
смержена, часть 2 (PLAN) — предмет этой задачи. Падают
`test_ac7_invariant_ten_names_role_budget_cap`,
`test_ac7_invariant_ten_names_plan_as_a_channel`,
`test_ac7_invariant_ten_names_spec_as_a_channel_too`.

Зелёный с рождения: `test_ac7_invariant_ten_keeps_the_operator_only_
above_cap_rule` — сегодняшняя строка уже называет и «Оператор», и
`budget` (единственный канал сегодня), так что обе под-проверки этого
метода проходят буквально уже сейчас; метод ловит будущую РЕГРЕССИЮ (при
добавлении PLAN как канала разработчик случайно вычёркивает оговорку об
исключительности Оператора выше потолка ролей), не сегодняшний дефект.

Тест читает `docs/invariants.md` напрямую (не защищённый путь — обычный
документ, зона этой задачи по SPEC), без стаба кода: проверено вручную
построением ожидаемой итоговой строки по формулировке AC-7 и прогоном
теста против неё (временная правка файла, не закоммичена) — все четыре
под-проверки проходят одновременно.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


def _invariant_10_row(text: str) -> str:
    match = re.search(r"^\| *10 *\|(.*)$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(
            "строка инварианта 10 не найдена в docs/invariants.md — "
            "таблица должна нести ряд, начинающийся с '| 10 |'")
    return match.group(1)


class Ac7InvariantTenMentionsPlanChannelTest(unittest.TestCase):

    def setUp(self):
        self.text = (REPO_ROOT / "docs" / "invariants.md").read_text(
            encoding="utf-8")
        self.row = _invariant_10_row(self.text)

    def test_ac7_invariant_ten_names_role_budget_cap(self):
        """Строка инварианта 10 называет константу `ROLE_BUDGET_CAP` —
        без неё формулировка «в пределах потолка ролей» непроверяема.

        Ловит мутацию: правка ряда 10, которая переписывает часть про
        Оператора, но забывает добавить границу `ROLE_BUDGET_CAP` (ряд
        остаётся такой же безусловной, как сегодня).
        """
        self.assertIn("ROLE_BUDGET_CAP", self.row,
                     f"инвариант 10 обязан называть ROLE_BUDGET_CAP: {self.row!r}")

    # AC-7: manual — формулировка инварианта 10 с каналом PLAN (amend-tests
    # 11.09): с 11.09 docs/invariants.md правит только Оператор своим
    # коммитом, код-ветка задачи файл не несёт; предлагаемая строка —
    # приложение «## Приложение: инвариант 10» PLAN.md, Оператор вносит
    # после мержа. Бывший test_ac7_invariant_ten_names_plan_as_a_channel
    # (assertIn("PLAN", строка инварианта 10)) исполняется Оператором
    # по тексту приложения; остальные три метода проверяют формулировку,
    # уже присутствующую в main, и остаются исполняемыми.

    def test_ac7_invariant_ten_names_spec_as_a_channel_too(self):
        """Формулировка explicit «не только SPEC на гейте SPEC» — ряд
        обязан продолжать называть и SPEC (существующий канал части 1),
        не подменять его формулировку про PLAN.

        Ловит мутацию: правка, которая при добавлении PLAN случайно
        стирает упоминание SPEC как канала (регрессия части 1).
        """
        self.assertIn("SPEC", self.row,
                     f"инвариант 10 обязан продолжать называть SPEC: {self.row!r}")

    def test_ac7_invariant_ten_keeps_the_operator_only_above_cap_rule(self):
        """Подъём потолка ВЫШЕ `ROLE_BUDGET_CAP` остаётся исключительно
        действием Оператора командой `budget` — ряд обязан продолжать
        называть и Оператора, и команду `budget`.

        Ловит мутацию: правка, которая, добавляя PLAN как канал В
        ПРЕДЕЛАХ потолка ролей, случайно ослабляет или убирает
        оговорку об исключительности Оператора ВЫШЕ потолка ролей —
        именно то расширение полномочий, которое ADR-0014 запрещает.
        """
        self.assertIn("Оператор", self.row,
                     f"инвариант 10 обязан называть Оператора: {self.row!r}")
        self.assertIn("budget", self.row,
                     f"инвариант 10 обязан называть команду budget: {self.row!r}")


if __name__ == "__main__":
    unittest.main()
