"""AC-8 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — `PLAN.md` этой задачи в
разделе «Влияние на систему» называет факт: уже развёрнутый `.artel/
home/.claude` не переписывается пультом при этом изменении
(разворачивается только при отсутствии каталога); расхождение с
референсом покажет `doctor role-home-reference`, переразворачивает
Оператор.

Источник PLAN.md — АРТЕФАКТНАЯ ветка задачи (ADR-0016: `tasks/<id>/`
живёт только там; на диске во время прогона планки пультом лежит лишь
`acceptance_tests/`), тем же примитивом, что читает артефакты сам пульт
(`gitcmd.show`). Диск — запасной источник для ручного прогона роли до
автокоммита (правка Оператора 12.09, amend-tests: прежняя версия читала
только диск и краснела на прогоне пультом после подтяжки main).

Красен до реализации: `PLAN.md` этой задачи ещё не написан (пишет его
роль после `test_author`) — ни в ветке, ни на диске файла нет, первый же
assert падает на его отсутствии.
"""
# AC-9: skip — регрессия существующих tests/test_runner*/test_catalog*/test_doctor* без ослабления проверяется полным набором tests/ на гейте (CI и автогейт approve); дубль пометки из markers.py — amend-tests читает разметку только из test_*.py
import unittest
from pathlib import Path

from orchestrator import artifact_branch, gitcmd

TASK_ID = "01M2B6K3EM7F2J72RC2F520Y2K"
PLAN_DISK = Path(__file__).resolve().parents[1] / "PLAN.md"


def _plan_text() -> str | None:
    text, _reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                f"tasks/{TASK_ID}/PLAN.md")
    if text:
        return text
    if PLAN_DISK.is_file():
        return PLAN_DISK.read_text(encoding="utf-8")
    return None


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
        text = _plan_text()
        self.assertIsNotNone(
            text, f"PLAN.md задачи {TASK_ID} должен существовать в "
                  f"артефактной ветке (либо на диске: {PLAN_DISK})")

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
