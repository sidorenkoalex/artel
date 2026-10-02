"""Юнит-тесты прогона полного набора tests/ на `approve` из `acceptance`
и разбора аргументов команды `approve` (SPEC 01M3FQ3JVC3DGGM33XCX8TC7ME,
требования 6-8).

Приёмочные тесты задачи гоняют тот же путь целиком — командной строкой
пульта и через настоящую `acceptance.run_full_suite` с поддельным
`subprocess.run`. Здесь уровень юнита: подменена сама `run_full_suite`
(хвостом настоящего вида, требование 11), что даёт углы, которых планка
не бьёт напрямую, — отсутствие вызова прогона без worktree, разбор
аргументов диспетчера по отдельности и доезд основания флага до
`fsm.cmd_approve`.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance, artel, config, fsm, store, workspace  # noqa: E402
from tests.sandbox import LightTransitionSandbox, TmpRootTest  # noqa: E402

SUMMARY_LINE = "2 failed, 305 passed in 71.23s"
FAILED_NODEID = "tests/test_fsm_autogate.py::SomeCase::test_some_scenario"
RED_OUTPUT = (
    "============================= test session starts ==================\n"
    "8 workers [307 items]\n"
    "=========================== short test summary info ================\n"
    f"FAILED {FAILED_NODEID} - AssertionError: маркер\n"
    f"=============== {SUMMARY_LINE} ===============\n"
)
GREEN_OUTPUT = "307 passed in 70.11s\n"
REASON = "красный main 22-26.09, к задаче не относится"
SHA = "abcdef1234567890abcdef1234567890abcdef12"


class ApproveAcceptanceSandbox(LightTransitionSandbox):
    """Задача в `acceptance` и `approve` над ней.

    Сверка фиксации и подтяжка main замоканы: их поведение держат
    `tests/test_git_fixation.py`/`tests/test_branch_freshness_gate.py`, а
    предмет здесь — что `approve` делает с полным набором tests/.
    Побочные эффекты входа в `merge_gate` (снимок объёма, undraft Draft
    MR, подсказка sha) замоканы тем же доводом: они не условия перехода.
    """

    TASK_TITLE = "Прогон полного набора на приёмке"

    def setUp(self):
        super().setUp()
        for target, attr, kwargs in (
                (fsm, "confirm_fixation", {"return_value": True}),
                (fsm, "_pull_main_or_escalate", {"return_value": "fresh"}),
                (fsm, "_snapshot_split_assessment", {}),
                (fsm.github_adapter, "undraft_mr", {}),
                (fsm.fixation, "approve_sha_hint", {"return_value": ""}),
        ):
            patcher = mock.patch.object(target, attr, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.on_task_branch = True
        for attr, side in (
                ("on_task_branch", lambda *a, **kw: self.on_task_branch),
                ("path", lambda *a: self.wt_path)):
            patcher = mock.patch.object(workspace, attr, side_effect=side)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.full_suite_result = (False, RED_OUTPUT)
        patcher = mock.patch.object(
            acceptance, "run_full_suite",
            side_effect=lambda root: self.full_suite_result)
        self.run_full_suite = patcher.start()
        self.addCleanup(patcher.stop)

        self.set_state("acceptance")

    def approve(self, accept_red: str | None = None) -> str:
        return self.capture(
            lambda: fsm.cmd_approve(self.TASK, accept_red=accept_red))

    def journal_blob(self) -> str:
        return "\n".join(f"{r['action']} {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), self.TASK))


class ApproveRedFullSuiteTest(ApproveAcceptanceSandbox):

    def test_red_suite_refuses_and_keeps_the_task_in_acceptance(self):
        """Не-зелёный полный набор — отказ `approve`: задача остаётся в
        `acceptance`, а имена упавших тестов и итоговая строка pytest
        уходят и в вывод команды, и в журнал задачи.

        Ловит мутацию: исход прогона посчитан и выброшен (`set_state`
        зовётся безусловно) — красный набор снова проводит приёмку молча,
        как 26.09; либо отказ только печатается, и после закрытия
        терминала разбор красноты опять восстанавливают по времени
        событий.
        """
        out = self.approve()
        journal = self.journal_blob()

        self.assertEqual(self.state(), "acceptance")
        for surface, name in ((out, "вывод approve"), (journal, "журнал")):
            self.assertIn(SUMMARY_LINE, surface, f"{name}: {surface!r}")
            self.assertIn(FAILED_NODEID, surface, f"{name}: {surface!r}")
        self.assertIn("approve отклонён", journal)
        self.assertIn("fullsuite", journal,
                      f"журнал не называет файл лога прогона: {journal!r}")

    def test_refusal_names_the_flag_as_the_way_out(self):
        """Текст отказа называет флаг осознанного принятия красноты —
        иначе о выходе Оператор узнаёт только из кода.

        Ловит мутацию: подсказка про `--accept-red` выпала из отказа —
        Оператор при красном main застревает на приёмке и идёт править БД
        руками, ровно тот обход, который флаг и закрывает.
        """
        out = self.approve()

        self.assertIn("--accept-red", out)

    def test_green_suite_passes_to_merge_gate(self):
        """Зелёный полный набор приёмку не задерживает.

        Ловит мутацию: условие отказа перевёрнуто (`if green: refuse`) —
        приёмка встанет навсегда при полностью зелёном наборе.
        """
        self.full_suite_result = (True, GREEN_OUTPUT)

        self.approve()

        self.assertEqual(self.state(), "merge_gate")
        self.assertIn(fsm.ACCEPTANCE_SUITE_GREEN_ACTION, self.journal_blob())


class ApproveAcceptRedFlagTest(ApproveAcceptanceSandbox):

    def test_flag_with_reason_passes_and_journals_the_reason(self):
        """`accept_red` с основанием проводит приёмку при красном наборе,
        а в журнал уходят основание, имена упавших тестов и итоговая
        строка pytest.

        Ловит мутацию: основание принято, но до решения об отказе не
        доходит (или в журнал уходит только факт принятия) — либо выхода у
        Оператора нет вовсе, либо через неделю по записи не восстановить,
        какие тесты были красными в момент приёмки.
        """
        self.approve(accept_red=REASON)
        journal = self.journal_blob()

        self.assertEqual(self.state(), "merge_gate")
        self.assertIn(REASON, journal)
        self.assertIn(SUMMARY_LINE, journal)
        self.assertIn(FAILED_NODEID, journal)

    def test_flag_is_not_needed_and_not_recorded_on_a_green_suite(self):
        """Зелёный набор с флагом — обычный проход: записи об осознанном
        принятии красноты в журнале нет.

        Ловит мутацию: флаг проверяется ДО исхода прогона — приёмка с
        флагом перестала бы гонять набор вовсе, и журнал сообщал бы о
        принятой красноте там, где всё зелено.
        """
        self.full_suite_result = (True, GREEN_OUTPUT)

        self.approve(accept_red=REASON)

        self.assertEqual(self.state(), "merge_gate")
        self.assertNotIn(fsm.ACCEPTANCE_RED_ACCEPTED_ACTION,
                         self.journal_blob())
        self.run_full_suite.assert_called_once()


class ApproveWithoutWorktreeTest(ApproveAcceptanceSandbox):

    def test_missing_worktree_skips_the_run_with_a_named_record(self):
        """Worktree задачи не на её ветке — прогон не запускается вовсе,
        приёмка проходит, а в журнал ложится именованная запись «полный
        набор не проверен — worktree не заведён».

        Ловит мутацию: прогон запускается всё равно (по `config.ROOT`
        вместо worktree задачи) — приёмка красится чужой краснотой; либо
        пропуск сделан молча, и приёмка выглядит проверенной набором,
        которого никто не гонял (инвариантный тест
        `test_operator_approve_passes_each_gate` при отказе покраснел бы).
        """
        self.on_task_branch = False

        self.approve()

        self.assertEqual(self.state(), "merge_gate")
        self.run_full_suite.assert_not_called()
        journal = self.journal_blob()
        self.assertIn(fsm.ACCEPTANCE_SUITE_SKIPPED_ACTION, journal)
        self.assertIn("worktree", journal)


class ApproveArgvTest(unittest.TestCase):
    """Разбор аргументов команды `approve` в диспетчере
    (`orchestrator/artel.py`, требование 8)."""

    def test_positional_sha_is_parsed_as_before(self):
        """`approve <id> <sha>` — sha остаётся вторым позиционным
        аргументом.

        Ловит мутацию: разбор флага съел позиционный аргумент — approve на
        гейтах с фиксацией перестаёт принимать sha, и весь ручной
        протокол Оператора ломается.
        """
        self.assertEqual(artel._approve_sha_arg(["T001", SHA]), SHA)
        self.assertIsNone(artel._approve_sha_arg(["T001"]))

    def test_flag_and_its_reason_are_not_taken_for_the_sha(self):
        """Ни сам флаг, ни его основание не разбираются как sha — в любом
        порядке аргументов.

        Ловит мутацию: `rest[1]` по-прежнему читается как sha —
        `approve <id> --accept-red "<основание>"` уехал бы в сверку
        фиксации с sha `--accept-red` и отказал бы приёмке до прогона.
        """
        self.assertIsNone(
            artel._approve_sha_arg(["T001", "--accept-red", REASON]))
        self.assertEqual(
            artel._approve_sha_arg(["T001", "--accept-red", REASON, SHA]), SHA)
        self.assertEqual(
            artel._approve_sha_arg(["T001", SHA, "--accept-red", REASON]), SHA)

    def test_reason_of_the_flag_is_returned_as_is(self):
        """Основание флага возвращается дословно; флага нет — `None`.

        Ловит мутацию: основание берётся не следующим за флагом
        аргументом (например, последним в строке) — в журнал уходит не то,
        что Оператор написал.
        """
        self.assertEqual(
            artel._accept_red_arg(["T001", "--accept-red", REASON]), REASON)
        self.assertIsNone(artel._accept_red_arg(["T001", SHA]))

    def test_flag_without_a_reason_is_a_named_refusal(self):
        """Флаг без основания (в конце строки либо пустой строкой) —
        именованный отказ, называющий сам флаг.

        Ловит мутацию: флаг без значения разобран как «основание пустая
        строка» — красный набор принимается без всякого основания в
        журнале, ровно то, что флаг и должен был сделать невозможным.
        """
        for rest in (["T001", "--accept-red"], ["T001", "--accept-red", "  "]):
            with self.subTest(rest=rest):
                with self.assertRaises(SystemExit) as caught:
                    artel._accept_red_arg(rest)
                self.assertIn("--accept-red", str(caught.exception.code))


class ApproveDispatchArgsTest(TmpRootTest):
    """Аргументы, с которыми диспетчер зовёт `fsm.cmd_approve` (требование
    8). Песочница `TmpRootTest` — ради `config.ROOT`: `artel.main`
    отказывает, если корень пульта оказался git-worktree (инвариант T056),
    а тесты гоняются как раз в worktree задачи. Признак роли (`ARTEL_ROLE`,
    `HOME`) из окружения вызова снят: `approve` под ролью отказывает в
    диспетчере (SPEC 01M3XTF5506GF43HD51ECE230T, требование 10)."""

    TASK = "T001"

    def call(self, *args):
        argv = ["artel.py", "approve", self.TASK, *args]
        operator_env = {k: v for k, v in os.environ.items()
                        if k not in (config.ARTEL_ROLE_ENV, "HOME")}
        with mock.patch.dict(os.environ, operator_env, clear=True), \
             mock.patch.object(sys, "argv", argv), \
             mock.patch.object(fsm, "cmd_approve") as cmd_approve:
            artel.main()
        return cmd_approve

    def test_flag_reaches_cmd_approve_and_leaves_the_sha_empty(self):
        """`approve <id> --accept-red "<основание>"` доезжает до
        `fsm.cmd_approve` основанием, а sha остаётся пустым.

        Ловит мутацию: основание принято диспетчером и не передано дальше
        — приёмка отказывает и при осознанном принятии красноты, и выхода
        у Оператора нет.
        """
        cmd_approve = self.call("--accept-red", REASON)

        cmd_approve.assert_called_once()
        args, kwargs = cmd_approve.call_args
        self.assertEqual(kwargs.get("accept_red"), REASON)
        self.assertIsNone(args[1] if len(args) > 1 else kwargs.get("sha"))

    def test_sha_reaches_cmd_approve_without_the_flag(self):
        """`approve <id> <sha>` доезжает до `fsm.cmd_approve` тем же
        вторым позиционным аргументом, `accept_red` пуст.

        Ловит мутацию: диспетчер всегда передаёт `accept_red` непустым
        (например, литералом флага) — любая приёмка начала бы принимать
        красный набор без основания Оператора.
        """
        cmd_approve = self.call(SHA)

        args, kwargs = cmd_approve.call_args
        self.assertEqual(args[1] if len(args) > 1 else kwargs.get("sha"), SHA)
        self.assertIsNone(kwargs.get("accept_red"))


if __name__ == "__main__":
    unittest.main()
