"""Приёмочные тесты 01M1SHJZCE0Y4DXAAWQ2W585A7 — AC-12 (повторный `approve`
того же, уже `killed`, родителя не создаёт новых задач и НЕ ДОБАВЛЯЕТ
ВТОРУЮ запись «поделена на:...» в журнал).

Отличие от соседнего `test_ac8_repeat_approve_no_duplicate.py` (AC-8,
общее «не заводит новых подзадач» + текст «нечего подтверждать»): этот
тест бьёт по КОНКРЕТНОМУ побочному эффекту — числу вхождений фразы
«поделена на» в журнале родителя (ровно 1, не 2) — и по числу подзадач в
БД (ровно 2, не 4), а не только по неизменности МНОЖЕСТВА id между двумя
снимками.

Красен до реализации: см. докстринг `test_ac8_repeat_approve_no_duplicate.py`
— тот же класс риска тавтологии до появления ветки деления; assertion
на `state == "killed"` после первого approve делает файл честно красным
по причине отсутствия реализации, не по случайному совпадению путей.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (FIXTURE_ZONE, SplitApproveSandbox,  # noqa: E402
                      spec_text, two_valid_subsections)


class RepeatApproveJournalNotDuplicatedTest(SplitApproveSandbox):
    """Ловит мутацию: ветка деления привязана к наличию заполненной
    секции «## Деление» в SPEC (истина на любом approve этого родителя,
    сколько бы их ни было), а не к состоянию `spec_gate` — второй approve
    добавил бы вторую запись «поделена на» и ещё 2 подзадачи поверх
    первых двух.
    """

    def test_ac12_second_approve_does_not_add_a_second_split_journal_entry(self):
        text = spec_text(zones=FIXTURE_ZONE, subsections=two_valid_subsections())
        sha = self.enter_spec_gate(text)
        self.approve(sha)
        self.assertEqual(
            self.task_row()["state"], "killed",
            f"предпосылка теста AC-12 не выполнена: первый approve не "
            f"перевёл родителя в killed (см. AC-6) — строка "
            f"{self.task_row()}")
        subtask_count_after_first = len(self.all_task_ids()) - 1

        self.approve(None)

        self.assertEqual(
            len(self.all_task_ids()) - 1, subtask_count_after_first,
            f"число подзадач родителя изменилось после повторного approve "
            f"killed-родителя (AC-12): было {subtask_count_after_first}, "
            f"стало {len(self.all_task_ids()) - 1}")
        occurrences = self.journal_text().count("поделена на")
        self.assertEqual(
            occurrences, 1,
            f"журнал родителя несёт {occurrences} записей «поделена на» "
            f"вместо одной после повторного approve (AC-12): "
            f"{self.journal_text()!r}")


if __name__ == "__main__":
    unittest.main()
