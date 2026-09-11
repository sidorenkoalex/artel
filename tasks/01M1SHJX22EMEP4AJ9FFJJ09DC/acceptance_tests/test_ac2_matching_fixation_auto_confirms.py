"""AC-2 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md): «Живой sha совпадает с
зафиксированным и копия чистая — approve проходит без ввода sha и
журналирует sha, с которым согласован переход.»

Настоящий git self/артели (`ApproveSandbox`/`RealPultGitTest`) — предмет
проверки именно сквозной путь `artel.py approve <id>` без аргумента, а не
изолированная функция сравнения (та — AC-1, отдельным юнит-файлом).

Красен до реализации: сегодня `fsm._cmd_approve` без sha на `spec_gate`
останавливается на `confirm_fixation`, которая безусловно печатает
«approve требует sha» и возвращает `False` — состояние не меняется,
`test_ac2_...` падает на `assertNotEqual(state, "spec_gate")`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, store  # noqa: E402

from _sandbox import ApproveSandbox  # noqa: E402


class ApproveWithoutShaOnMatchingCleanFixationTest(ApproveSandbox):

    def test_ac2_matching_clean_fixation_transitions_without_a_sha_argument(self):
        """На `spec_gate`, сразу после входа (живой sha == `tasks.
        fixed_sha`, копия чистая — ничего не трогали), `approve <id>` БЕЗ
        sha обязан провести переход так же, как если бы Оператор набрал
        зафиксированный sha руками.

        Ловит мутацию: если сверка при `sha is None` продолжит
        безусловно печатать подсказку и возвращать `False` (сегодняшнее
        поведение), состояние останется `spec_gate` и первый assert
        упадёт.
        """
        sha = self.enter_spec_gate()

        out = self.capture(fsm.cmd_approve, self.TASK)

        row = store.get_task(store.db(), self.TASK)
        self.assertNotEqual(row["state"], "spec_gate",
                            "approve без sha обязан провести переход при "
                            "совпадении и чистой копии")
        self.assertNotIn("approve требует sha", out,
                         "живое совпадение не должно требовать ручного ввода")
        # Sha, с которым согласован переход, — тот, что был зафиксирован
        # до approve (ничего не менялось): переход перефиксирует то же
        # значение, и оно обязано быть видно в журнале (AC-2, «журналирует
        # sha, с которым согласован переход»).
        fixed_entries = [r["detail"] for r in store.task_steps(
            store.db(), self.TASK) if r["action"] == "sha зафиксирован"]
        self.assertTrue(any(sha in detail for detail in fixed_entries),
                        f"согласованный sha {sha} не найден в журнале "
                        f"фиксации: {fixed_entries}")

    def test_ac2_approve_without_sha_on_escalated_returns_to_escalated_from(self):
        """Тот же сценарий на состоянии `escalated` (второй из четырёх
        гейтов AC-1): живой sha совпадает, копия чистая — approve без sha
        обязан вернуть задачу в `escalated_from`, а не требовать sha.

        Ловит мутацию: если исправление применили только к ветке
        `spec_gate` диспетчера `_cmd_approve` (например, оставили старый
        безусловный отказ на входе `confirm_fixation` для остальных трёх
        состояний), этот тест поймает асимметрию — здесь по-прежнему
        `False` и состояние не изменится.
        """
        self.enter_in_dev()
        sha = self.force_state("escalated")

        out = self.capture(fsm.cmd_approve, self.TASK)

        row = store.get_task(store.db(), self.TASK)
        self.assertEqual(row["state"], "in_dev",
                         "escalated_from обязан вернуть задачу в in_dev "
                         "без ручного sha")
        self.assertNotIn("approve требует sha", out)
        fixed_entries = [r["detail"] for r in store.task_steps(
            store.db(), self.TASK) if r["action"] == "sha зафиксирован"]
        self.assertTrue(any(sha in detail for detail in fixed_entries),
                        f"согласованный sha {sha} не найден в журнале "
                        f"фиксации: {fixed_entries}")


if __name__ == "__main__":
    unittest.main()
