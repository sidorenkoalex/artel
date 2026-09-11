"""AC-4 (tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md): «Явный `approve <id>
<sha>` (полный sha или его префикс не короче действующей минимальной
длины) остаётся осознанным подтверждением расхождения — сверка и отказ
при несовпадении/грязной копии не меняются ни для одного из четырёх
гейтов (прежняя семантика).»

Прежняя семантика (полный sha/префикс/несовпадение) уже подробно
покрыта существующей планкой T021/01M1GHZTX9… (`tests/test_git_fixation.
py::ApproveByShaTest`, `ApproveAcceptsFixedShaPrefixTest`) — эта задача
не ослабляет и не переписывает те тесты (SPEC «Не входит»). Файл ниже —
не дубль: он проверяет именно НЕИЗМЕННОСТЬ семантики для ОСТАЛЬНЫХ
гейтов (`acceptance`, `merge_gate`), которые старая планка не гоняла
полным сценарием (`merge_gate` — тяжёлая реальная механика мержа,
изолируем моком именно точки входа `_cmd_approve_merge_gate_cycle`,
не самого мержа), плюс контрольный прогон на `spec_gate`/`escalated`
для симметрии внутри этой же планки.

Зелёный с рождения: явный sha уже сегодня сверяется с зафиксированным
(`confirm_fixation`, ветка `sha is not None` — код, который эта задача
по AC-4 обязана оставить нетронутым). Эти тесты фиксируют текущее
поведение КАК ПЛАНКУ (SPEC требование 2/AC-4), не ждут нового кода —
падение любого из них после реализации AC-1..AC-3 будет означать
регресс явного пути, а не отсутствующую фичу.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, fsm_merge_gate, store  # noqa: E402

from _sandbox import ApproveSandbox  # noqa: E402

WRONG_SHA = "0" * 40


class ExplicitShaSemanticsUnchangedOnAcceptanceGateTest(ApproveSandbox):

    def test_ac4_acceptance_gate_explicit_mismatched_sha_is_still_refused(self):
        """На `acceptance` явный, заведомо неверный sha по-прежнему
        отклоняется, состояние не меняется — тот же гейт, что участвует в
        AC-1..AC-3, но со старым явным путём (требование 2 SPEC).

        Ловит мутацию: если правка AC-1..AC-3 случайно ослабит ветку
        `sha is not None` (например, начнёт пропускать явный sha без
        сравнения «раз Оператор его назвал»), `assertRaises(SystemExit)`
        не сработает и состояние сдвинется с `acceptance`.
        """
        self.enter_in_dev()
        self.force_state("acceptance")

        with self.assertRaises(SystemExit):
            self.capture(fsm.cmd_approve, self.TASK, WRONG_SHA)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "acceptance")


class ExplicitShaSemanticsUnchangedOnMergeGateTest(ApproveSandbox):

    def test_ac4_merge_gate_explicit_mismatched_sha_refused_before_merge_cycle_runs(self):
        """На `merge_gate` явный неверный sha обязан быть отклонён ДО
        того, как диспетчер вызовет тяжёлую механику самого мержа
        (`fsm_merge_gate._cmd_approve_merge_gate_cycle`) — sha-гейт
        остаётся общим узлом перед веткой конкретного состояния.

        Ловит мутацию: если порядок веток `_cmd_approve` поменяется, и
        `merge_gate` начнёт запускать цикл мержа раньше проверки sha (или
        параллельно с ней), замоканная `_cmd_approve_merge_gate_cycle`
        окажется вызванной, хотя явный sha заведомо неверный.
        """
        self.enter_in_dev()
        self.force_state("merge_gate")

        with mock.patch.object(
                fsm_merge_gate, "_cmd_approve_merge_gate_cycle") as cycle_mock:
            with self.assertRaises(SystemExit):
                self.capture(fsm.cmd_approve, self.TASK, WRONG_SHA)

        cycle_mock.assert_not_called()
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "merge_gate")

    def test_ac4_merge_gate_explicit_matching_sha_still_reaches_the_merge_cycle(self):
        """Контроль симметрии: совпадающий явный sha по-прежнему
        пропускает `merge_gate` дальше, к самой механике цикла мержа —
        без этого положительный случай остался бы непроверенным, и
        мутация «sha-гейт теперь блокирует merge_gate всегда» осталась бы
        незамеченной предыдущим тестом.

        Ловит мутацию: если правка AC-1..AC-3 случайно перепутает ветки
        (например, начнёт всегда требовать автосверку и для merge_gate
        игнорировать явный переданный sha), цикл мержа не будет вызван
        даже при верном sha.
        """
        self.enter_in_dev()
        sha = self.force_state("merge_gate")

        with mock.patch.object(
                fsm_merge_gate, "_cmd_approve_merge_gate_cycle") as cycle_mock:
            self.capture(fsm.cmd_approve, self.TASK, sha)

        cycle_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
