"""AC-8 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — `PLAN.md` этой задачи в
разделе «Влияние на систему» называет факт: уже развёрнутый `.artel/
home/.claude` не переписывается пультом при этом изменении
(разворачивается только при отсутствии каталога); расхождение с
референсом покажет `doctor role-home-reference`, переразворачивает
Оператор.

Красен до реализации: `PLAN.md` этой задачи ещё не написан (пишет его
роль после `test_author`) — файла нет вовсе, первый же assert падает
на отсутствии файла.
"""
import unittest
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "PLAN.md"


class PlanNamesRoleHomeNotRewrittenTest(unittest.TestCase):

    def test_ac8_plan_influence_section_names_role_home_not_rewritten(self):
        """`PLAN.md` несёт раздел «Влияние на систему» и в нём — факт о
        том, что развёрнутый `.artel/home/.claude` не переписывается
        автоматически, а расхождение с референсом ловит `doctor
        role-home-reference` (переразворачивает его Оператор вручную).

        Ловит мутацию: раздел «Влияние на систему» есть, но пуст по
        существу (общие слова без факта про `.claude` и `doctor
        role-home-reference`) — либо раздел называется иначе и не
        совпадает с требуемым заголовком буквально.
        """
        self.assertTrue(PLAN.is_file(), f"{PLAN} должен существовать")
        text = PLAN.read_text(encoding="utf-8")

        self.assertIn("Влияние на систему", text)
        self.assertIn(".claude", text)
        self.assertIn("role-home-reference", text)
        self.assertTrue(
            "не переписыва" in text or "не разворачивает" in text
            or "только если" in text or "только при отсутств" in text,
            "PLAN.md должен явно называть, что дом не переписывается "
            "автоматически")


if __name__ == "__main__":
    unittest.main()
