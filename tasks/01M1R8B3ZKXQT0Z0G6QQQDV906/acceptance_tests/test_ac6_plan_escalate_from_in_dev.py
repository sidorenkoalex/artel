"""AC-6 (SPEC 01M1R8B3ZKXQT0Z0G6QQQDV906): PLAN.md со `status: escalate`
на `advance` из состояния `in_dev` переводит задачу в `escalated` с
текстом раздела «Эскалация» PLAN.md в журнале задачи, не запуская шаг
developer.

Красен до реализации: нынешний `orchestrator/fsm_advance.py::in_dev`
понимает только `plan_meta.get("status") in ("ready", "approved")` —
любой другой статус (в т.ч. `escalate`) падает в `else: print("PLAN.md
не ready — разработчик ещё работает")`, задача остаётся в `in_dev`, и
`auto` продолжает звать `developer` заново вместо остановки на
эскалации.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests.test_auto_cycle import AutoCycleTest  # noqa: E402


class Ac6PlanEscalateFromInDevTest(AutoCycleTest):

    ESCALATION_QUESTION = ("можно ли одобрить бюджет вдвое больше "
                          "выделенного потолка задачи")

    def write_plan_escalate(self) -> None:
        (self.tdir / "PLAN.md").write_text(
            "---\n"
            f"task: {self.TASK}\n"
            "type: plan\n"
            "author_role: developer\n"
            "status: escalate\n"
            "schema_version: 1\n"
            "---\n\n"
            "# PLAN: цикл auto\n\n"
            "## Подход\n\n## Шаги\n\n## Покрытие требований\n\n"
            "## Влияние на систему\n\n"
            "## Эскалация\n\n"
            f"- **Вопросы** — {self.ESCALATION_QUESTION}? Дефолт — нет, "
            f"эскалировать снижение объёма.\n"
            "- **Контекст** — реализация требует бюджет вдвое больше "
            "выделенного.\n"
            "- **Блокирует** — дальнейшую разработку.\n",
            encoding="utf-8")

    def test_ac6_plan_escalate_moves_to_escalated_and_journals_the_section(self):
        """Ловит мутацию: обработчик `in_dev`, у которого ветка `status
        == "escalate"` не добавлена (видит только `ready`/`approved`) —
        задача осталась бы в `in_dev`, `auto` запустил бы `developer`
        снова, и текст раздела «Эскалация» не попал бы в журнал вовсе.
        """
        self.write_plan_escalate()
        self.set_state("in_dev")

        self.auto()

        self.assertEqual(self.state(), "escalated")
        self.assertEqual(
            self.agent.calls, [],
            "auto запустил шаг developer вместо остановки на эскалации")
        rows = self.journal_rows()
        joined = "\n".join(f"{a} {d}" for _, a, d in rows)
        self.assertIn(self.ESCALATION_QUESTION, joined,
                      f"текст раздела «Эскалация» не найден в журнале: {rows}")

    def test_ac6_plan_escalate_does_not_move_to_review(self):
        """Негативный край: эскалация — не альтернативный путь в
        `review`, конечная точка именно `escalated`.

        Ловит мутацию: обработчик, спутавший `status: escalate` с
        `status: ready` (например, проверка `!= "ready"` вместо явного
        сравнения) — задача уехала бы в `review`, минуя эскалацию.
        """
        self.write_plan_escalate()
        self.set_state("in_dev")

        self.auto()

        self.assertNotEqual(self.state(), "review")


if __name__ == "__main__":
    unittest.main()
