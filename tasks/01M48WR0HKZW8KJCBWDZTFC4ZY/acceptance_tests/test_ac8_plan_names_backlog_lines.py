"""AC-8 — раздел «Предложения системе» PLAN называет две строки бэклога 05.10 для снятия Оператором.

PLAN.md читается из ссылки документов помощником пульта
(`_pult.artifact_text`). Раздел — от заголовка `## Предложения системе` до
следующего заголовка второго уровня. Строки бэклога узнаются по их
предмету (`docs/backlog.md`): «Два теста инвариантов по 45 с — перебор на
подтесты для xdist» и «Десять тестов по 15 с: слепок окружения шага в
песочнице»; номер строки файла не утверждается — бэклог правит Оператор.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer после этого шага) — `artifact_text("PLAN.md")` возвращает `None`.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import artifact_text  # noqa: E402

SECTION = "## Предложения системе"


def proposals_section(plan: str) -> str | None:
    """Текст раздела «Предложения системе» без заголовка; `None` — раздела нет."""
    lines = plan.splitlines()
    starts = [i for i, line in enumerate(lines)
              if line.strip().startswith(SECTION)]
    if not starts:
        return None
    body = []
    for line in lines[starts[0] + 1:]:
        if re.match(r"^##\s", line):
            break
        body.append(line)
    return re.sub(r"\s+", " ", "\n".join(body)).lower()


class PlanNamesBacklogLinesTest(unittest.TestCase):

    def test_ac8_proposals_name_split_and_env_snapshot_backlog_lines(self):
        """Раздел «Предложения системе» PLAN называет строку о дроблении перебора инвариантов и строку о «слепке окружения» как неверной причине (TR-1).

        Сценарий: в PLAN.md есть раздел «## Предложения системе»; он
        ссылается на бэклог, называет строку о переборе инвариантов
        (слово «перебор» рядом с «инвариант») и строку о «слепке
        окружения» и ссылается на ревизию TR-1 как на основание.

        Ловит мутацию: разработчик назвал в разделе только строку о
        «слепке окружения», забыв строку о дроблении перебора (или
        положил обе строки в другой раздел PLAN, например «Замер») —
        признак строки в тексте раздела не найден.
        """
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        section = proposals_section(plan)
        self.assertIsNotNone(section, f"в PLAN.md нет раздела «{SECTION}»")

        self.assertRegex(section, r"бэклог|backlog",
                         "раздел не ссылается на бэклог")
        self.assertIn("инвариант", section,
                      "строка о переборе инвариантов не названа")
        self.assertIn("перебор", section,
                      "строка о дроблении перебора инвариантов не названа")
        self.assertRegex(section, r"слеп(ок|ка|ке|ком) окружения",
                         "строка о «слепке окружения» не названа")
        self.assertIn("tr-1", section, "ревизия TR-1 не названа основанием")


if __name__ == "__main__":
    unittest.main()
