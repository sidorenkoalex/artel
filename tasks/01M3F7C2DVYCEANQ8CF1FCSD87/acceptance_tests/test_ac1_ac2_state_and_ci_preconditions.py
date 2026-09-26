"""AC-1/AC-2: предусловие состояния и статуса CI команды `ci-rerun`.

Красен до реализации: команды `ci-rerun` в пульте нет вовсе — `resolve_command`
не находит обработчика ни в таблице команд `orchestrator/artel.py`, ни по
очевидным адресам, и `run_ci_rerun` валит тест этим сообщением.

AC-1 — задача вне `verifying` (сюда же попадает состояние, из которого
Оператор уже вернул задачу разработчику после красного CI: `in_dev`,
`merge_gate`). AC-2 — задача в `verifying`, но статус CI не завершённо-красный:
зелёный, «проверки идут», «проверок нет вовсе» — три исхода, которые
`ci.verifying_status` различает и сегодня.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (BRANCH_GREEN, BRANCH_NO_RUNS, BRANCH_RUNNING,  # noqa: E402
                      REASON, RUN_LIST_EMPTY, CiRerunSandbox)


class StateAndStatusPreconditionsTest(CiRerunSandbox):

    def test_ac1_state_other_than_verifying_refuses_naming_state_and_status(self):
        """Задача не в `verifying` — отказ, называющий состояние и статус CI.

        Разыгрывается живой сценарий: задача стояла в `verifying` с красным
        CI (цикл остановился), Оператор уже увёл её дальше — `in_dev` после
        `reject`, `merge_gate` после `approve`. Команда обязана отказать,
        назвав текущее состояние и статус CI, не перезапуская ничего и не
        меняя состояние в БД.

        Ловит мутацию: предусловие состояния проверяется как «не терминальное»
        (или не проверяется вовсе) вместо «ровно verifying» — тогда для
        `in_dev`/`merge_gate` команда дошла бы до `ci.trigger_rerun`, и
        `trigger_calls` перестал бы быть пустым.
        """
        self.enter_verifying_red()
        for state in ("in_dev", "merge_gate"):
            with self.subTest(state=state):
                # Счётчик повторов обнуляется в НАЧАЛЕ подслучая: провал
                # ассерта внутри `subTest` до конца блока не доходит, и
                # накопленный чужой вызов путал бы следующий подслучай.
                self.trigger_calls.clear()
                self.set_state(state)
                before = self.last_step_id()
                text = self.run_ci_rerun(REASON)

                self.assertEqual(
                    self.trigger_calls, [],
                    f"из состояния {state} команда не имеет права звать "
                    f"ci.trigger_rerun")
                self.assertIn(
                    state, text,
                    f"отказ обязан называть текущее состояние задачи "
                    f"({state}); сказано: {text!r}")
                self.assertTrue(
                    self.names_ci_status(text),
                    f"отказ обязан называть статус CI ветки "
                    f"({self.status_note()}); сказано: {text!r}")
                self.assertEqual(
                    self.state(), state,
                    "команда не имеет права менять состояние задачи в БД")
                self.assertEqual(
                    self.state_transitions_since(before), [],
                    "отказ не имеет права журналировать переход состояния")

    def test_ac2_verifying_with_non_red_ci_refuses_naming_status(self):
        """В `verifying` при не-красном статусе CI — отказ со статусом.

        Все три не-красных исхода: зелёный, «проверки идут» (есть
        незавершённый check-run), «проверок нет вовсе» (ни одного check-run
        и пустой `gh run list`). Красная запись журнала о прошлой остановке
        цикла в фикстуре ЕСТЬ (сверка требования 4 её найдёт) — отказывает
        именно текущий статус, а не отсутствие записи.

        Ловит мутацию: условие красноты записано как «не зелёный» (`outcome
        != ci.VERIFYING_GREEN`) вместо `outcome == ci.VERIFYING_RED` — тогда
        «проверки идут» и «проверок нет вовсе» уехали бы в повтор, то есть
        ре-ран идущего или несуществующего прогона.
        """
        self.enter_verifying_red()
        fixtures = (("зелёный", BRANCH_GREEN, RUN_LIST_EMPTY),
                    ("проверки идут", BRANCH_RUNNING, RUN_LIST_EMPTY),
                    ("проверок нет вовсе", BRANCH_NO_RUNS, RUN_LIST_EMPTY))
        for label, check_runs, run_list in fixtures:
            with self.subTest(status=label):
                self.trigger_calls.clear()
                self.branch_check_runs = check_runs
                self.run_list_json = run_list
                before = self.last_step_id()
                text = self.run_ci_rerun(REASON)

                self.assertEqual(
                    self.trigger_calls, [],
                    f"при статусе «{label}» повторять нечего — "
                    f"ci.trigger_rerun не имеет права быть вызванной")
                self.assertTrue(
                    self.names_ci_status(text),
                    f"отказ обязан называть статус CI ветки "
                    f"({self.status_note()}); сказано: {text!r}")
                self.assertEqual(
                    self.state(), "verifying",
                    "команда не меняет состояние задачи (требование 9)")
                self.assertEqual(
                    self.state_transitions_since(before), [],
                    "отказ не имеет права журналировать переход состояния")


if __name__ == "__main__":
    unittest.main()
