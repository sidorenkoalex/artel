"""Юнит-тесты ветки `spec_gate` команды `orchestrator/fsm.py::_cmd_reject`
(SPEC 01M2YWRB9HWW99R57HWGP2M7MQ, требования 1-4, 7).

Приёмочные тесты задачи (`tasks/01M2YWRB9HWW99R57HWGP2M7MQ/
acceptance_tests/`, залоченные tasks/T023) кроют те же критерии сквозным
путём через `fsm.cmd_reject` в лёгкой песочнице переходов; здесь — сам
узел в изоляции, без резолва id/lease/CAS-обвязки, тем же приёмом, каким
`tests/test_fsm_draft_mr_reentry.py` смотрит на соседние ветки этой же
команды.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"
REASON = "SPEC разошёлся с кодом: класс отказа требует зоны, которой нет"

# Состояния, где `reject` работал до задачи, и detail их записи перехода
# — ветка `spec_gate` не имеет права их задеть (требование 7).
NEIGHBOUR_RETURNS = {
    "acceptance": "приёмка отклонена: {reason}",
    "merge_gate": "возврат из merge_gate: {reason}",
    "verifying": "возврат из verifying: {reason}",
}


class SpecGateRejectTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        ensure_patcher = mock.patch.object(fsm.github_adapter,
                                           "ensure_draft_mr")
        self.ensure_draft_mr = ensure_patcher.start()
        self.addCleanup(ensure_patcher.stop)

    def insert(self, state: str, task_id: str = TASK, **overrides) -> None:
        """Задача в заданном состоянии. Отдельный `task_id` — для случаев,
        где сценарий гоняется по нескольким состояниям: чистить строку
        между подтестами нельзя (соединения `store.db()` живут дольше
        подтеста, и DELETE упирается в замок БД), а новая задача — тот же
        чистый лист без гонки."""
        store.insert_task(store.db(), task_id, "Задача", state,
                          f"task/{task_id.lower()}-zadacha",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        if overrides:
            store.update_task(store.db(), task_id, **overrides)

    def state(self, task_id: str = TASK) -> str:
        return store.get_task(store.db(), task_id)["state"]

    def transition_details(self, state: str,
                           task_id: str = TASK) -> list[str]:
        return [row["detail"] or "" for row in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=? "
            "ORDER BY id", (task_id, f"state -> {state}"))]

    def reject(self, reason: str = REASON, task_id: str = TASK) -> None:
        fsm._cmd_reject(store.db(), task_id, reason)

    # ------------------------------------------------- требования 1, 3, 7

    def test_reject_on_spec_gate_returns_the_task_to_the_analyst(self):
        """Ловит мутацию: ветка `spec_gate` скопирована с ветки
        `verifying` без правки целевого состояния — задача уедет в
        `in_dev`, а записи `state -> spec_writing` не появится ни одной.
        """
        self.insert("spec_gate")

        self.reject()

        self.assertEqual(self.state(), "spec_writing")
        self.assertEqual(self.transition_details("spec_writing"),
                         [f"возврат из spec_gate: {REASON}"])

    def test_reject_on_spec_gate_does_not_open_a_draft_mr(self):
        """Ловит мутацию: в ветку `spec_gate` скопирован и вызов
        `_maybe_ensure_draft_mr` соседей — Draft MR заводился бы на
        задаче, которая до кода ещё не дошла (узел — побочный эффект
        входа ИМЕННО в `in_dev`, SPEC T079, требование 1).
        """
        self.insert("spec_gate")

        self.reject()

        self.ensure_draft_mr.assert_not_called()

    def test_reject_on_spec_gate_keeps_both_counters(self):
        """Требование 2. Счётчики взяты ненулевыми: на нулях «остались
        прежними» и «обнулены» неотличимы.

        Ловит мутацию: ветка `spec_gate` поставлена ПОСЛЕ проверки
        `state != "acceptance"` (или слита с ней) — исполнение дойдёт до
        `rejects = t["accept_rejects"] + 1`, и `accept_rejects` вырастет.
        """
        self.insert("spec_gate", review_iters=2, accept_rejects=1)

        self.reject()

        row = store.get_task(store.db(), TASK)
        self.assertEqual((row["review_iters"], row["accept_rejects"]), (2, 1))

    def test_reject_on_spec_gate_keeps_zones_and_budget(self):
        """Требование 3: содержимое отклонённого SPEC в колонки не
        попадает — их пишет только `_approve_spec_gate`.

        Ловит мутацию: ветка собрана копированием `_approve_spec_gate`
        (чтение SPEC с ветки + `update_task(zones=...)`/
        `budget.apply_spec_budget`) с заменой одного целевого состояния —
        колонки подтянутся к значениям отклонённой редакции.
        """
        self.insert("spec_gate", zones="orchestrator/fsm.py",
                    budget_usd=config.DEFAULT_BUDGET_USD)

        self.reject()

        row = store.get_task(store.db(), TASK)
        self.assertEqual(row["zones"], "orchestrator/fsm.py")
        self.assertEqual(row["budget_usd"], config.DEFAULT_BUDGET_USD)

    # ---------------------------------------------------------- требование 4

    def test_empty_reason_on_spec_gate_refuses_without_a_transition(self):
        """Требование 4: пустая причина (пустая строка и строка из одних
        пробелов) — отказ команды, состояние прежнее, записи перехода нет.

        Ловит мутацию: проверка написана как `if reason is None` или
        `if not reason` (без снятия пробелов) — строка из пробелов
        пройдёт, и задача уедет в `spec_writing` с пустой причиной в
        detail, которую аналитику нечего читать.
        """
        # Одна задача на оба подтеста: отказ состояния не меняет, чистить
        # между ними нечего.
        self.insert("spec_gate")
        for name, reason in (("пустая строка", ""), ("пробелы", "  \t ")):
            with self.subTest(причина=name):
                with self.assertRaises(SystemExit) as caught:
                    self.reject(reason)

                self.assertIn("причин", str(caught.exception))
                self.assertEqual(self.state(), "spec_gate")
                self.assertEqual(self.transition_details("spec_writing"), [])

    def test_reason_is_required_only_on_the_spec_gate(self):
        """SPEC «Не входит»: проверка причины вводится ТОЛЬКО на
        `spec_gate` — в `acceptance`/`merge_gate`/`verifying` `reject`
        причину не проверял и не проверяет (требование 7 «как сегодня»).

        Ловит мутацию: проверка пустой причины вынесена в голову
        `_cmd_reject` «для всех состояний разом» — три соседних возврата
        перестанут работать без причины, то есть команда изменит
        поведение там, где SPEC его менять запрещает.
        """
        for n, state in enumerate(NEIGHBOUR_RETURNS):
            task_id = f"T1{n:02d}"
            with self.subTest(состояние=state):
                self.insert(state, task_id)

                self.reject("", task_id)

                self.assertEqual(self.state(task_id), "in_dev")

    # ---------------------------------------------------------- требование 7

    def test_neighbour_returns_keep_their_outcome_and_detail(self):
        """Требование 7: три состояния, где `reject` работал до задачи,
        ведут себя как раньше — исход `in_dev` и СВОЙ текст detail.

        Ловит мутацию: ветка `spec_gate` вписана общим циклом по таблице
        «состояние -> возврат», заодно унифицировавшим detail соседей —
        `acceptance` потеряет свой текст «приёмка отклонена: …», по
        которому Оператор отличает отказ приёмки от возврата с гейта.
        """
        for n, (state, detail_tmpl) in enumerate(NEIGHBOUR_RETURNS.items()):
            task_id = f"T2{n:02d}"
            with self.subTest(состояние=state):
                self.insert(state, task_id)

                self.reject(task_id=task_id)

                self.assertEqual(self.state(task_id), "in_dev")
                self.assertEqual(self.transition_details("in_dev", task_id),
                                 [detail_tmpl.format(reason=REASON)])

    def test_inapplicable_state_refuses_and_names_spec_gate_as_applicable(self):
        """Требование 7: в состоянии, где команда неприменима (`in_dev`),
        остаётся прежний именованный отказ — и его перечисление называет
        `spec_gate`, ставший применимым требованием 1.

        Ловит мутацию: ветка `spec_gate` вписана ПОСЛЕ финального
        `sys.exit` (стала недостижимой) либо вместо него — задача в
        `in_dev` уедет в `spec_writing`, а отказ выродится в молчание.
        """
        self.insert("in_dev")

        with self.assertRaises(SystemExit) as caught:
            self.reject()

        message = str(caught.exception)
        self.assertIn("reject применим только", message)
        self.assertIn("spec_gate", message)
        self.assertIn("in_dev", message)
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.transition_details("spec_writing"), [])


if __name__ == "__main__":
    unittest.main()
