"""AC-7, AC-8 задачи 01M3FQ3JVC3DGGM33XCX8TC7ME — `approve` в состоянии
`acceptance` гоняет полный набор tests/ и различает «набор красный» от
«worktree не заведён».

Красен до реализации: `fsm._approve_acceptance` полный набор tests/ не
гоняет вовсе — красный набор проводит приёмку молча, а записи «полный
набор не проверен — worktree не заведён» в журнале не появляется ни при
каком состоянии рабочей копии.

Зелёный с рождения: два метода этого файла — тесты сохранения, и это
корректно. `test_ac7_green_full_suite_still_passes_acceptance` (зелёный
набор приёмку не задерживает) и
`test_ac8_missing_worktree_does_not_run_the_suite_at_all` (без worktree
pytest не запускается) держат поведение, которое сегодня верно по той
причине, что прогона нет вовсе, а после реализации — по той, что ветвь
выбрана правильно; именно они ловят перевёрнутое условие и прогон по
чужому дереву.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _fixtures import FAILED_NODEIDS, SUMMARY_LINE, red_output  # noqa: E402
from _sandbox import ApproveAcceptanceSandbox  # noqa: E402


class ApproveRefusesRedFullSuiteTest(ApproveAcceptanceSandbox):

    def test_ac7_red_full_suite_keeps_the_task_in_acceptance(self):
        """`approve` из `acceptance` при красном полном наборе tests/ не
        проводит приёмку: задача остаётся в `acceptance`, в `merge_gate`
        не уезжает.

        Ловит мутацию: прогон набора заведён, но его исход не влияет на
        переход (результат посчитан и выброшен, `store.set_state` зовётся
        безусловно) — красный набор снова проходит приёмку молча, как
        26.09.
        """
        self.set_red_run(red_output())

        self.approve_cli()

        self.assertEqual(self.state(), "acceptance",
                         "красный полный набор tests/ провёл приёмку")

    def test_ac7_refusal_text_and_journal_name_failed_tests_and_summary(self):
        """Отказ `approve` называет причину, имена упавших тестов и
        итоговую строку pytest — и в выводе команды Оператору, и записью
        журнала задачи.

        Ловит мутацию: отказ печатается, но не журналируется (или
        наоборот) — одна из двух поверхностей остаётся без имён упавших
        тестов, и разбор красноты после закрытия терминала опять
        восстанавливается по времени событий.
        """
        self.set_red_run(red_output())

        out, exit_text = self.approve_cli()
        printed = out + exit_text
        journal = self.journal_blob()

        for surface, name in ((printed, "вывод approve"),
                              (journal, "журнал задачи")):
            self.assertIn(SUMMARY_LINE, surface,
                          f"{name} без итоговой строки pytest: {surface!r}")
            for nodeid in FAILED_NODEIDS:
                self.assertIn(nodeid, surface,
                              f"{name} не назвал упавший тест {nodeid}")
        self.assertIn("approve", journal,
                      "отказ приёмки не назван в журнале действием approve")

    def test_ac7_green_full_suite_still_passes_acceptance(self):
        """Зелёный полный набор tests/ приёмку не задерживает: `approve`
        из `acceptance` по-прежнему уводит задачу в `merge_gate`.

        Ловит мутацию: отказ по набору написан с перевёрнутым условием
        (`if green: refuse`) — приёмка встанет навсегда при полностью
        зелёном наборе.
        """
        self.set_green_run()

        self.approve_cli()

        self.assertEqual(self.state(), "merge_gate")


class ApproveWithoutWorktreeTest(ApproveAcceptanceSandbox):

    def test_ac8_missing_worktree_passes_with_a_named_journal_record(self):
        """Worktree задачи стоит не на её ветке (`workspace.on_task_branch`
        вернула не `True`) — прогон полного набора пропускается: задача
        уходит в `merge_gate`, а в журнал ложится именованная запись
        «полный набор не проверен — worktree не заведён».

        Ловит мутацию: пропуск прогона сделан молча (без записи) —
        приёмка выглядит как проверенная полным набором, хотя не гонялось
        ничего; либо пропуск заменён отказом, и `approve` в песочнице без
        worktree встаёт насмерть (инвариантный тест
        `test_operator_approve_passes_each_gate` краснеет).
        """
        self.on_task_branch = False
        self.set_red_run(red_output())

        self.approve_cli()

        self.assertEqual(self.state(), "merge_gate",
                         "approve без заведённого worktree обязан провести "
                         "приёмку, а не отказать")
        journal = self.journal_blob()
        self.assertIn("полный набор не проверен", journal,
                      f"в журнале нет записи о пропуске прогона: {journal!r}")
        self.assertIn("worktree", journal,
                      f"запись о пропуске не называет причину (worktree): "
                      f"{journal!r}")

    def test_ac8_missing_worktree_does_not_run_the_suite_at_all(self):
        """Пропуск — именно пропуск: pytest полного набора не
        запускается ни разу, когда worktree задачи не стоит на её ветке.

        Ловит мутацию: прогон запускается всё равно (по `config.ROOT`
        вместо worktree задачи) — в песочнице это молча гоняет чужое
        дерево, а у Оператора красит приёмку чужой краснотой.
        """
        self.on_task_branch = False
        self.set_red_run(red_output())

        self.approve_cli()

        self.assertEqual(self.pytest_run.calls, [],
                         "полный набор запускался без заведённого worktree")


if __name__ == "__main__":
    unittest.main()
