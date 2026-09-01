"""AC-6 (tasks/T092/SPEC.md): сгенерированный HTML-файл содержит очередь
ожиданий Оператора — задачи, стоящие на ручных гейтах.

`merge_gate` — гейт, ручной всегда (независимо от `gates.yaml`,
`orchestrator/gates.py`: политика применяется только к `acceptance`;
`spec_gate`/`merge_gate` ручные безусловно — `fsm.py`, комментарий у
`_maybe_autogate_acceptance`). Задача в `in_dev` — обычное агентское
состояние, ожиданием Оператора не является ни при какой политике.

Разметку очереди SPEC не фиксирует. Каждая задача и так обязана попасть
в отчёт борд-карточкой (AC-3/AC-4) — само по себе присутствие id задачи
на гейте в документе НЕ доказывает наличие отдельной очереди. Поэтому
проверка — по ЧИСЛУ упоминаний: задача на ручном гейте обязана быть
упомянута в документе БОЛЬШЕ раз, чем сопоставимая задача не на гейте
(та получает только борд/карточку, гейтовая — плюс ещё и запись в
очереди), независимо от того, как именно очередь размечена.

Красен до реализации: `orchestrator/report.py` не существует.
"""
import unittest

from _sandbox import ReportSandboxTest, count_occurrences  # noqa: E402


class ManualGateQueueTest(ReportSandboxTest):

    def setUp(self):
        super().setUp()
        self.gated_task = self.mk_task(
            "T001", "Задача на ручном гейте merge_gate", "merge_gate")
        self.free_task = self.mk_task(
            "T002", "Задача не на гейте", "in_dev")
        _, new_files, _, _ = self.run_report()
        self.path = new_files[0]
        self.html = self.path.read_text(encoding="utf-8")

    def test_ac6_gated_task_mentioned_in_report(self):
        self.assertIn(self.gated_task, self.html)

    def test_ac6_gated_task_appears_more_often_than_non_gated(self):
        gated_count = count_occurrences(self.html, self.gated_task)
        free_count = count_occurrences(self.html, self.free_task)
        self.assertGreater(
            gated_count, free_count,
            "задача на ручном гейте не получает дополнительного "
            "упоминания сверх борда/карточки — похоже, отдельной "
            "очереди ожиданий Оператора нет "
            f"({self.gated_task}: {gated_count} раз, "
            f"{self.free_task}: {free_count} раз)")


if __name__ == "__main__":
    unittest.main()
