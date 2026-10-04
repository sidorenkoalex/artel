"""Юнит-тесты подтяжки `main` перед шагом разработчика и выбора ответов
брифа разработчика (SPEC 01M443BPQEA9ZMJ3R50THNB1MF, требования 4, 6).

Долгоживущие файлы задачи (`tests/test_01m443bpqea9zmj3r50thnb1mf_*.py`)
кроют сквозной путь `run`/`answer`/`developer_brief`; здесь — углы, которых
они не касаются: пропуск подтяжки, пока конфликт прошлой подтяжки ждёт
шага роли; подтяжка перед шагом без прогона планки; граница «старт
прошлого шага разработчика» до первого шага.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import brief, fsm, pull, runner, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402


class PreStepPullTest(TaskSeededTmpRootTest):

    def task(self):
        return store.get_task(store.db(), self.TASK)

    def journal(self, actor: str, action: str, detail: str = "") -> None:
        store.journal(store.db(), self.TASK, actor, action, detail)

    def actions(self) -> list:
        return [r["action"] for r in store.task_steps(store.db(), self.TASK)]

    def pre_step(self, outcome: str = "fresh"):
        with mock.patch.object(fsm, "_pull_main_or_escalate",
                               return_value=outcome) as spy:
            result = runner._pull_before_developer_step(
                store.db(), self.TASK, self.task())
        return result, spy

    def test_pending_conflict_marker_skips_the_pull(self):
        """Метка конфликта подтяжки после старта последнего шага
        разработчика — подтяжка пропущена с записью, шаг идёт.

        Ловит мутацию: пропуск по метке убран — подтяжка перед шагом снова
        ловит тот же конфликт и эскалирует, роль не получает ни одного шага
        (узел подтяжки вызван)."""
        self.journal("developer", "agent run started")
        self.journal("fsm", pull.PULL_CONFLICT_ROLE_STEP_MARKER, "конфликт")

        result, spy = self.pre_step()

        self.assertEqual(("continue", None), result)
        spy.assert_not_called()
        self.assertIn(runner.PRE_STEP_PULL_SKIPPED_ACTION, self.actions())

    def test_marker_already_handed_to_a_role_step_does_not_skip(self):
        """Метка, после которой шаг разработчика уже стартовал, —
        подтяжка идёт как обычно, без режима планки.

        Ловит мутацию: пропуск срабатывает на любую метку в журнале, а не
        только на не отданную роли — подтяжка перед шагом отключается
        навсегда после первого конфликта; либо подтяжка зовётся с прогоном
        планки (`run_plank` не `False`)."""
        self.journal("fsm", pull.PULL_CONFLICT_ROLE_STEP_MARKER, "конфликт")
        self.journal("developer", "agent run started")

        result, spy = self.pre_step()

        self.assertEqual(("continue", None), result)
        spy.assert_called_once()
        self.assertIs(False, spy.call_args.kwargs.get("run_plank"))
        self.assertNotIn(runner.PRE_STEP_PULL_SKIPPED_ACTION, self.actions())

    def test_outcomes_map_to_step_decisions(self):
        """Исход подтяжки решает судьбу шага: эскалация — шаг не начат
        (`return`), отказ — `exit` с текстом, слияние — запись журнала.

        Ловит мутацию: исход `escalated`/`refused` игнорируется и шаг
        идёт дальше («continue»); запись о состоявшейся подтяжке не
        пишется."""
        self.assertEqual(("return", None), self.pre_step("escalated")[0])
        action, text = self.pre_step("refused")[0]
        self.assertEqual("exit", action)
        self.assertIn("подтяжка main", text)
        self.assertNotIn(runner.PRE_STEP_PULL_ACTION, self.actions())
        self.assertEqual(("continue", None), self.pre_step("pulled")[0])
        self.assertIn(runner.PRE_STEP_PULL_ACTION, self.actions())


class EvaluateWithoutPlankTest(TaskSeededTmpRootTest):

    def evaluate(self, run_plank: bool):
        t = store.get_task(store.db(), self.TASK)
        plank = mock.Mock(return_value=pull.Conflict([], "планка красная"))
        with mock.patch.object(pull.gitcmd, "commits_behind", return_value=2), \
                mock.patch.object(pull, "_doc_only_main_advance", return_value=None), \
                mock.patch.object(pull.workspace, "ensure",
                                  return_value=(Path(self.root), None)), \
                mock.patch.object(pull, "_clean_worktree_before_merge",
                                  return_value=None), \
                mock.patch.object(pull, "_run_merge",
                                  return_value=SimpleNamespace(returncode=0)), \
                mock.patch.object(pull, "_materialize_and_run_plank", plank):
            outcome = pull.evaluate(
                store.db(), self.TASK, t, "in_dev",
                origin_main_source=lambda name: ("origin", "main"),
                origin_main_sha=lambda name: "a" * 40,
                read_branch_text_or_refuse=lambda *args: None,
                repo_path=Path(self.root), run_plank=run_plank)
        return outcome, plank

    def test_merge_without_plank_is_pulled(self):
        """`run_plank=False`: слияние состоялось — `Pulled`, планка не
        гоняется; по умолчанию планка гоняется, как прежде.

        Ловит мутацию: флаг не доходит до узла — красная планка после
        подтяжки перед шагом эскалирует задачу (исход `Conflict`); либо
        флаг выключил планку и на прежних точках подтяжки."""
        outcome, plank = self.evaluate(run_plank=False)
        self.assertEqual(pull.Pulled("a" * 40), outcome)
        plank.assert_not_called()

        outcome, plank = self.evaluate(run_plank=True)
        self.assertIsInstance(outcome, pull.Conflict)
        plank.assert_called_once()


class DeveloperAnswerBoundaryTest(unittest.TestCase):

    def rows(self, *pairs):
        return [{"id": i + 1, "actor": actor, "action": action}
                for i, (actor, action) in enumerate(pairs)]

    def test_boundary_is_last_developer_start_else_entry_into_in_dev(self):
        """Граница — старт последнего шага разработчика; до первого шага —
        последний вход в `in_dev`; без обоих — `None`.

        Ловит мутацию: граница берётся по первому старту шага, а не по
        последнему — бриф снова несёт давно отработанные ответы; без шага
        разработчика граница `None` — два указания, данные до первого
        шага, сводятся к последнему."""
        rows = self.rows(("fsm", "state -> in_dev"),
                         ("developer", "agent run started"),
                         ("operator", "ANSWER создан, ждёт approve"),
                         ("developer", "agent run started"),
                         ("fsm", "state -> in_dev"))
        self.assertEqual(4, brief._developer_answer_boundary(rows))
        rows = self.rows(("fsm", "state -> in_dev"),
                         ("test_author", "agent run started"),
                         ("fsm", "state -> in_dev"))
        self.assertEqual(3, brief._developer_answer_boundary(rows))
        self.assertIsNone(brief._developer_answer_boundary(
            self.rows(("analyst", "agent run started"))))


if __name__ == "__main__":
    unittest.main()
