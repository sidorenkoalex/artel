"""AC-14 — 01M31ZHWJWRSACYMRWTCPBC0DM: PLAN несёт перечень ожиданий
существующих `tests/test_report.py` и `tests/test_retro.py`, обновлённых
этой задачей.

Источник — SPEC.md, «Критерии приёмки»:

AC-14. PLAN несёт перечень ожиданий существующих `tests/test_report.py` и
`tests/test_retro.py`, обновлённых этой задачей.

PLAN читается ТОЛЬКО из артефактной ветки задачи (`gitcmd.show`): на
диске в среде прогона планки лежит один `acceptance_tests/`
(`orchestrator/acceptance.py::materialize_from_branch`), и тест,
заглядывающий в рабочую копию, зелен у автора и красен на гейте
(прецеденты 12.09 и 13.09, skills/test-authoring.md).

Красен до реализации: `PLAN.md` этой задачи ещё не написан — его
создаёт роль developer, и до её шага `gitcmd.show` артефактной ветки
не отдаёт ничего.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tokens  # noqa: E402
from orchestrator import artifact_branch, gitcmd  # noqa: E402

NAMED_FILES = ("tests/test_report.py", "tests/test_retro.py")

#: Пункт перечня — маркированный («- », «* ») или нумерованный («1. »)
#: элемент списка Markdown, с любым отступом вложенности.
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")


def plan_text():
    """Текст PLAN.md из ГОЛОВЫ артефактной ветки задачи; `None` — ветки
    нет либо файла в ней нет."""
    text, _reason = gitcmd.show(artifact_branch.branch_name(_tokens.TASK_ID),
                                f"tasks/{_tokens.TASK_ID}/PLAN.md")
    return text or None


def enumeration_for(text: str, name: str) -> list:
    """Пункты перечня, привязанные к имени файла: сам пункт назвал файл,
    либо пункт идёт следом за строкой, назвавшей его (заголовок раздела
    или вводная строка), до конца этого списка."""
    lines = text.splitlines()
    items = []
    for index, line in enumerate(lines):
        if name not in line:
            continue
        if LIST_ITEM.match(line):
            items.append(line.strip())
            continue
        for follow in lines[index + 1:]:
            if LIST_ITEM.match(follow):
                items.append(follow.strip())
            elif follow.strip():
                break
    return items


class PlanListsUpdatedExpectationsTest(unittest.TestCase):

    def test_ac14_plan_enumerates_updated_expectations_of_both_files(self):
        """PLAN задачи называет оба существующих файла тестов и для
        каждого несёт хотя бы один пункт перечня — то, что в нём
        обновлено этой задачей.

        Ловит мутацию: разработчик упоминает файлы одной фразой («тесты
        report и retro поправлены под новый формат») без перечня — ревьюер
        и Оператор остаются без списка того, какие ожидания сдвинулись, и
        сверять диф им не с чем; `enumeration_for` вернёт пустой список
        по такому файлу.
        """
        text = plan_text()
        self.assertIsNotNone(
            text,
            f"PLAN.md задачи {_tokens.TASK_ID} не найден в артефактной "
            f"ветке {artifact_branch.branch_name(_tokens.TASK_ID)}")

        gaps = [name for name in NAMED_FILES
                if not enumeration_for(text, name)]
        self.assertEqual(
            [], gaps,
            f"PLAN не несёт перечня обновлённых ожиданий по: {gaps}")


if __name__ == "__main__":
    unittest.main()
