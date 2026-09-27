"""AC-11 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME (часть про текст) — запись
«приёмка: что проверит approve» перечисляет как автоматическое при
`approve` ровно то, что `approve` делает, а прогон планки и потолок
бюджета называет местами их фактической проверки.

Красен до реализации: группа «автоматически при approve» перечисляет
четыре пункта, из которых прогон планки на самом деле гонялся на
переходе `review -> verifying`, а потолок бюджета проверяется
`budget.budget_block` на старте шага роли — оба названы там, где не
проверяются, и перехода `review -> verifying` запись не упоминает вовсе.

Зелёный с рождения:
`test_ac11_approve_group_lists_exactly_what_approve_does` и
`test_ac11_record_is_still_one_journal_entry` — тесты сохранения: полный
набор tests/ и свежесть ветки в записи уже названы, и запись уже одна;
критерий требует не потерять это при переписывании текста.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import FullSuiteSandbox  # noqa: E402

# Место, где прогон планки приёмочных тестов действительно гонялся.
PLANK_PLACE = "review -> verifying"
# Место фактической проверки потолка бюджета: `budget.budget_block` на
# старте шага роли — годится любое из двух написаний адреса.
BUDGET_PLACE = ("budget_block", "шага роли")
# Что `approve` в acceptance проверяет автоматически на самом деле.
FULL_SUITE_ITEM = "полный набор tests/"
FRESHNESS_ITEM = "свежесть"


def _normalized(detail: str) -> str:
    """Стрелка перехода в одном написании: `→` и `->` — одно и то же
    место, различать их незачем."""
    return detail.replace("→", "->")


def _approve_group_items(detail: str) -> list[str]:
    """Пункты группы «что approve проверит автоматически»: часть записи
    до разделителя групп ` | ` (за ним стоит то, что остаётся человеку),
    разрезанная по `;`. Разделителя нет — вся запись целиком."""
    head = _normalized(detail).split(" | ")[0]
    return [item.strip() for item in head.split(";") if item.strip()]


class ChecklistNamesRealChecksTest(FullSuiteSandbox):

    def detail(self) -> str:
        return _normalized(self.checklist_detail())

    def test_ac11_plank_run_is_named_at_the_verifying_transition(self):
        """Прогон планки приёмочных тестов назван местом, где он гонялся —
        переходом `review -> verifying`, а не проверкой `approve`.

        Ловит мутацию: пункт про планку оставлен в группе «автоматически
        при approve» как был (только переписана формулировка вокруг
        источника планки) — Оператор продолжает читать запись как
        обещание прогнать планку на приёмке.
        """
        detail = self.detail()

        self.assertIn(PLANK_PLACE, detail,
                      f"запись не называет переход {PLANK_PLACE} — место, где "
                      f"прогон планки действительно гонялся: {detail!r}")
        misplaced = [item for item in _approve_group_items(detail)
                     if "планк" in item and "verifying" not in item]
        self.assertEqual(
            misplaced, [],
            f"планка всё ещё обещана как автоматическая проверка approve: "
            f"{misplaced}")

    def test_ac11_budget_cap_is_named_at_its_real_check(self):
        """Потолок бюджета назван местом фактической проверки
        (`budget.budget_block` на старте шага роли), а не проверкой
        `approve`: новой проверки бюджета в `approve` задача не заводит.

        Ловит мутацию: пункт про бюджет остался в группе approve — запись
        обещает проверку, которой в `approve` нет ни до задачи, ни после.
        """
        detail = self.detail()

        misplaced = [item for item in _approve_group_items(detail)
                     if "бюджет" in item
                     and not any(place in item for place in BUDGET_PLACE)]
        self.assertEqual(
            misplaced, [],
            f"потолок бюджета назван проверкой approve, хотя проверяется "
            f"{BUDGET_PLACE[0]}: {misplaced}")
        self.assertTrue(
            any(place in detail for place in BUDGET_PLACE),
            f"запись не называет место фактической проверки бюджета "
            f"{BUDGET_PLACE}: {detail!r}")

    def test_ac11_approve_group_lists_exactly_what_approve_does(self):
        """Группа «автоматически при approve» перечисляет ровно то, что
        `approve` в acceptance делает: полный набор tests/ в worktree и
        свежесть кодовой ветки — и ничего сверх.

        Ловит мутацию: текст записи переписан, но один из двух реальных
        пунктов из него выпал (например, полный набор назван только в
        части «остаётся человеку») — запись снова расходится с фактом, уже
        в другую сторону.
        """
        items = _approve_group_items(self.detail())
        joined = "; ".join(items)

        self.assertIn(FULL_SUITE_ITEM, joined,
                      f"группа approve не называет полный набор tests/: "
                      f"{items}")
        self.assertIn(FRESHNESS_ITEM, joined,
                      f"группа approve не называет свежесть кодовой ветки: "
                      f"{items}")

    def test_ac11_record_is_still_one_journal_entry(self):
        """Запись остаётся ОДНОЙ записью журнала «приёмка: что проверит
        approve» — приведение текста в соответствие с фактом не разносит
        её на несколько событий.

        Ловит мутацию: текст разложен на запись про approve и отдельную
        запись про то, что гонялось раньше — гейт приёмки снова читается
        в двух местах вместо одного.
        """
        self.set_green_run()
        self.autogate()

        actions = [r["action"] for r in self.journal_rows()
                   if "приёмка" in r["action"] and "approve" in r["action"]]

        self.assertEqual(len(actions), 1,
                         f"ожидалась одна запись «что проверит approve», "
                         f"найдено {actions}")
        self.assertTrue(
            re.search(r"\S", self.checklist_detail()),
            "detail записи «что проверит approve» пуст")


if __name__ == "__main__":
    unittest.main()
