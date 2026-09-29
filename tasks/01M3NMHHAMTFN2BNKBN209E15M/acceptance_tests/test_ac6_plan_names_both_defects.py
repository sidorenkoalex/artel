"""PLAN.md называет причину отказа канарейки 20260929T004220Z — оба
дефекта с местом кода (SPEC 01M3NMHHAMTFN2BNKBN209E15M, AC-6).

Группа: разовый
Красен до реализации: PLAN.md задачи в артефактной ветке ещё не написан разработчиком — чтение через gitcmd.show возвращает None.

Источник — только артефактная ветка (`gitcmd.show` по
`artifact_branch.branch_name`). Тест проверяет форму ответа: канарейка
названа, у каждого из дефектов А и Б рядом с упоминанием есть ссылка на
файл `orchestrator/…py`. Верность самой причины (совпадает ли названное
место с диагностикой канарейки или с краснотой варианта (а)/(б) сквозного
теста на коде до исправления) сверяет ревьювер по PLAN и диффу.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import artifact_branch, gitcmd  # noqa: E402

TASK_ID = "01M3NMHHAMTFN2BNKBN209E15M"
CANARY_MARKS = ("20260929T004220Z", "01M3N9SNEZSNC2G4X2Y2DGEY4R")
CODE_REF = re.compile(r"orchestrator/[\w/]+\.py")
# Окно строк после упоминания дефекта, в котором ищется место кода.
WINDOW = 15


def defect_mention(letter: str) -> re.Pattern:
    """«дефект А»/«Дефекта Б»/«дефект (Б)» — кириллица и латиница."""
    latin = {"А": "A", "Б": "B"}[letter]
    return re.compile(rf"[Дд]ефект\w*\W{{0,3}}[{letter}{latin}](?![\wа-яА-Я])")


class PlanNamesBothDefects(unittest.TestCase):

    def plan(self) -> str:
        text, reason = gitcmd.show(artifact_branch.branch_name(TASK_ID),
                                   f"tasks/{TASK_ID}/PLAN.md")
        self.assertIsNotNone(text, f"PLAN.md нет в артефактной ветке: {reason}")
        return text

    def test_ac6_plan_names_both_defects_with_code_places(self):
        """PLAN.md в артефактной ветке называет канарейку и оба дефекта.

        Канарейка названа (прогон 20260929T004220Z или задача
        01M3N9SNEZSNC2G4X2Y2DGEY4R); у дефекта А и у дефекта Б в пределах
        окна строк после упоминания есть ссылка на `orchestrator/…py`.

        Ловит мутацию: PLAN разбирает только один дефект (например, лишь
        чекпоинт) или называет дефект без места кода — у второго дефекта
        нет упоминания либо рядом нет ссылки на файл.
        """
        lines = self.plan().splitlines()
        text = "\n".join(lines)
        self.assertTrue(any(mark in text for mark in CANARY_MARKS),
                        f"PLAN не называет канарейку ({', '.join(CANARY_MARKS)})")
        for letter in ("А", "Б"):
            with self.subTest(defect=letter):
                pattern = defect_mention(letter)
                hits = [i for i, line in enumerate(lines) if pattern.search(line)]
                self.assertTrue(hits, f"PLAN не упоминает дефект {letter}")
                placed = any(CODE_REF.search("\n".join(lines[i:i + WINDOW]))
                             for i in hits)
                self.assertTrue(placed, f"у дефекта {letter} нет места кода "
                                        f"(ссылки на orchestrator/…py) рядом "
                                        f"с упоминанием")


if __name__ == "__main__":
    unittest.main()
