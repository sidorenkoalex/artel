"""Юнит-тесты сверки путей SPEC на гейте `spec_gate`
(`orchestrator/fsm.py::_approve_spec_gate`, SPEC
01M2XJKQNFTWHYAY4KBBQ1NVY7, требования 5-6).

Приёмочная планка задачи закрывает AC-8/AC-9 (отказ с подсказкой,
состояние, колонка `zones`); здесь — то, чего планка не называет: отказ
журналируется записью «approve отклонён» с текстом причины, путь из
«## Критерии приёмки» отказывает так же, как из «## Требования», а
каталог в `zones:` покрывает вложенный файл на гейте.

Песочница — `tests.sandbox.LightTransitionSandbox`: SPEC.md на диске
`config.TASKS/<id>/` читается гейтом через `disk_backed_show`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import fsm, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import LightTransitionSandbox, capture  # noqa: E402

SPEC_TEMPLATE = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 35
---

# SPEC: фикстура гейта

## Контекст

Фикстура.

## Требования

1. {requirement}

## Критерии приёмки

AC-1. {ac}

## Не входит

Ничего.

## Материалы

Нет.
"""

MENTIONED = "orchestrator/advance_gates/zones.py"


class SpecGatePathCheckTest(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        for rel in (MENTIONED, "orchestrator/catalog.py"):
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# фикстура\n", encoding="utf-8")
        self.tdir.mkdir(parents=True, exist_ok=True)

    def arrange(self, *, zones: str, requirement: str = "Фикстура.",
                ac: str = "Фикстура.") -> None:
        (self.tdir / "SPEC.md").write_text(
            SPEC_TEMPLATE.format(task=self.TASK, zones=zones,
                                 requirement=requirement, ac=ac),
            encoding="utf-8")
        self.set_state("spec_gate")

    def journal_actions(self) -> list:
        return [(r["action"], r["detail"])
                for r in store.task_steps(store.db(), self.TASK)]

    def test_refusal_is_journaled_with_the_reason(self):
        """Отказ гейта оставляет запись «approve отклонён» с именем пути
        и подсказкой — тем же действием журнала, что отказы sha в
        `confirm_fixation`.

        Ловит мутацию: отказ только печатается, без `store.journal` —
        `log`/`watch` Оператора не увидели бы причину."""
        self.arrange(zones="orchestrator/catalog.py",
                     requirement=f"Починить {MENTIONED}.")

        capture(fsm.cmd_approve, self.TASK)

        refusals = [d for a, d in self.journal_actions() if a == "approve отклонён"]
        self.assertEqual(len(refusals), 1, self.journal_actions())
        self.assertIn(MENTIONED, refusals[0])
        self.assertIn(guard.UNCLASSIFIED_PATH_HINT, refusals[0])
        self.assertEqual(self.state(), "spec_gate")

    def test_path_in_acceptance_criteria_refuses_too(self):
        """Путь, названный только в «## Критерии приёмки», отказывает так
        же, как из «## Требования».

        Ловит мутацию: гейт сверяет один раздел «## Требования» — путь
        из критериев прошёл бы мимо зон."""
        self.arrange(zones="orchestrator/catalog.py",
                     ac=f"Проверить {MENTIONED}.")

        text = capture(fsm.cmd_approve, self.TASK)

        self.assertIn(MENTIONED, text)
        self.assertEqual(self.state(), "spec_gate")

    def test_directory_zone_covers_the_nested_file_on_the_gate(self):
        """`zones: orchestrator/advance_gates/` покрывает файл под ним —
        approve проходит, задача уходит с гейта, колонка `zones` несёт
        значение SPEC.

        Ловит мутацию: `zone_items`/`_covered_by` на гейте заменены
        буквальным сравнением — честный SPEC с каталогом-зоной получал
        бы отказ."""
        self.arrange(zones="orchestrator/advance_gates/",
                     requirement=f"Починить {MENTIONED}.")

        text = capture(fsm.cmd_approve, self.TASK)

        self.assertNotIn(guard.UNCLASSIFIED_PATH_HINT, text)
        self.assertNotEqual(self.state(), "spec_gate")
        self.assertEqual(self.task_row()["zones"], "orchestrator/advance_gates/")


if __name__ == "__main__":
    unittest.main()
