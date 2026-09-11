"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-8 (повторный `approve`
родителя, уже находящегося в `killed`, не заводит новых подзадач и не
изменяет журнал — ветка обработки состояния `_cmd_approve` не срабатывает
вне `spec_gate`).

`killed` не входит в `APPROVE_NEEDS_SHA` (`orchestrator/fsm.py`) — второй
`approve` зовётся БЕЗ sha, тем же приёмом, что уже проверяет требование 3
SPEC («повторный approve того же родителя не заводит дублей: код
`_cmd_approve` обрабатывает ветку деления только при входе в состоянии
spec_gate ... для killed срабатывает существующая ветка else: печатает
«нечего подтверждать»») — это существующее сообщение, байт-в-байт то же,
что уже печатает `_cmd_approve` для ЛЮБОГО состояния без своей ветки
обработки (`orchestrator/fsm.py:898`), не текст, который пишет
разработчик заново для этой задачи.

Красен до реализации: до появления ветки деления первый `approve` НЕ
переводит родителя в `killed` вовсе (см. докстринг
`test_ac6_parent_killed_with_journal.py`) — без промежуточного assertion
на `state == "killed"` после ПЕРВОГО approve второй approve этого теста
стартовал бы сегодня из `in_dev` (существующий фолбэк-переход
`spec_gate -> in_dev` для SPEC без AC-разметки), где уже сегодня
срабатывает та же ветка `else: нечего подтверждать» — тест был бы зелёным
ДО реализации по ПОСТОРОННЕЙ причине, не проверяя AC-8 вовсе (запрещённая
тавтология, `skills/test-authoring.md`). Промежуточный assertion делает
файл красным по ПРАВИЛЬНОЙ причине уже на первом approve, тем же путём,
что `test_ac6_parent_killed_with_journal.py`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FIXTURE_ZONE, SplitApproveSandbox,  # noqa: E402
                      spec_text, two_valid_subsections)


class RepeatApproveDoesNotDuplicateTest(SplitApproveSandbox):
    """Второй `approve` того же (уже `killed`) родителя — без нового
    заведения задач.

    Ловит мутацию: ветка деления `_cmd_approve` привязана к проверке
    секции «## Деление» в SPEC, а не к состоянию `spec_gate` (например
    `if division_section:` без `if state == "spec_gate"`) — повторный
    `approve` завёл бы ещё 2 подзадачи поверх первых двух.
    """

    def test_ac8_second_approve_on_killed_parent_creates_no_new_tasks(self):
        text = spec_text(zones=FIXTURE_ZONE, subsections=two_valid_subsections())
        sha = self.enter_spec_gate(text)
        self.approve(sha)
        self.assertEqual(
            self.task_row()["state"], "killed",
            f"предпосылка теста AC-8 не выполнена: первый approve не "
            f"перевёл родителя в killed (см. AC-6) — строка "
            f"{self.task_row()}")
        ids_after_first_approve = self.all_task_ids()

        output = self.approve(None)

        self.assertEqual(
            self.all_task_ids(), ids_after_first_approve,
            f"второй approve родителя изменил набор задач в БД (AC-8): "
            f"было {ids_after_first_approve}, стало {self.all_task_ids()}")
        self.assertIn(
            "нечего подтверждать", output,
            f"второй approve killed-родителя не сообщил «нечего "
            f"подтверждать» (AC-8, требование 3 SPEC): {output!r}")


if __name__ == "__main__":
    unittest.main()
