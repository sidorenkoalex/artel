"""AC-4 (вторая половина) — 01M3H1Z489CKJ8FHSRS4TYTPX2: план обосновывает
размещение записи предварительных зон и предупреждения относительно
`update_task(parent_task_id)` в `spawn_subtask`.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. Предупреждение о пересечении использует target подзадачи и не
превращает её заведение в отказ; план обосновывает размещение записи зон
и предупреждения относительно `update_task(parent_task_id)` в
`spawn_subtask`.

Проверяется НАЛИЧИЕ обоснования, привязанного к тому месту кода, которое
назвал критерий: абзац плана, называющий `parent_task_id`, говорит о
расположении («до»/«после»/«перед»/«порядок») и о двух предметах —
записи зон и предупреждении о пересечении. Содержательность самого
обоснования судят ревьювер и Оператор; механически проверяемо то, что
абзац есть и привязан к `parent_task_id`, а не растворён в общем
пересказе диффа.

PLAN.md читается ТОЛЬКО из артефактной ветки задачи (`gitcmd.show`): в
среде прогона планки на диске лежит один `acceptance_tests/`
(`orchestrator/acceptance.py::materialize_from_branch`), и тест,
заглядывающий в рабочую копию, зелен у автора и красен на гейте
(прецеденты 12.09 и 13.09, skills/test-authoring.md).

Красен до реализации: `PLAN.md` этой задачи ещё не написан — его создаёт
роль developer, и до её шага `gitcmd.show` артефактной ветки не отдаёт
ничего. Разбор обоснования проверен стабом отдельно от прогона планки:
`justification_blocks` прогнан на образце абзаца (правильный отвечает
непустым списком, абзац без слова о расположении — пустым), потому что
стаб самого `PLAN.md` потребовал бы коммита в артефактную ветку задачи.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402
from orchestrator import artifact_branch, gitcmd  # noqa: E402

#: Место кода, относительно которого критерий требует обоснования.
ANCHOR = "parent_task_id"

#: Слова о РАСПОЛОЖЕНИИ вызова относительно якоря.
PLACEMENT_WORDS = ("до ", "после", "перед", "раньше", "позже", "порядк")

#: Два предмета размещения из формулировки критерия.
SUBJECTS = {
    "запись предварительных зон": ("зон",),
    "предупреждение о пересечении": ("предупрежд", "пересеч"),
}


def plan_text():
    """Текст PLAN.md из ГОЛОВЫ артефактной ветки задачи; `None` — ветки
    нет либо файла в ней нет."""
    text, _reason = gitcmd.show(artifact_branch.branch_name(_sandbox.TASK_ID),
                                f"tasks/{_sandbox.TASK_ID}/PLAN.md")
    return text or None


def justification_blocks(text: str) -> list:
    """Абзацы плана, называющие `parent_task_id` И хотя бы одно слово о
    расположении относительно него: обоснование размещения — это абзац о
    том, где стоят вызовы, а не любое упоминание якоря."""
    blocks = [block for block in re.split(r"\n[ \t]*\n", text)
              if ANCHOR in block]
    return [block for block in blocks
            if any(word in block.lower() for word in PLACEMENT_WORDS)]


def uncovered_subjects(blocks: list) -> list:
    """Предметы размещения, не названные ни одним из абзацев-обоснований."""
    joined = " ".join(blocks).lower()
    return [name for name, markers in sorted(SUBJECTS.items())
            if not any(marker in joined for marker in markers)]


class PlanJustifiesThePlacementTest(unittest.TestCase):

    def test_ac4_plan_justifies_placement_relative_to_the_parent_link(self):
        """PLAN задачи несёт абзац, называющий `update_task(parent_task_id)`
        и расположение относительно него, и этот абзац (вместе с такими же
        абзацами, если их несколько) говорит о двух предметах: записи
        предварительных зон и предупреждении о пересечении.

        Ловит мутацию: разработчик перечислил внесённые вызовы, не сказав,
        где они стоят относительно привязки к родителю («добавлены запись
        зон и предупреждение») — ревьювер остаётся без заявленного
        порядка, а именно порядок и есть предмет AC-3, который он обязан
        сверить по диффу; `justification_blocks` вернёт пустой список.
        """
        text = plan_text()
        self.assertIsNotNone(
            text,
            f"PLAN.md задачи {_sandbox.TASK_ID} не найден в артефактной "
            f"ветке {artifact_branch.branch_name(_sandbox.TASK_ID)}")

        blocks = justification_blocks(text)
        self.assertTrue(
            blocks,
            f"PLAN не несёт абзаца, который называл бы {ANCHOR} и "
            f"расположение относительно него (одно из слов: "
            f"{', '.join(PLACEMENT_WORDS)})")
        self.assertEqual(
            [], uncovered_subjects(blocks),
            "обоснование размещения не говорит о: "
            + "; ".join(uncovered_subjects(blocks)))


if __name__ == "__main__":
    unittest.main()
