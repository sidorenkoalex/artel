"""AC-7/AC-8 — сдвинувшийся main на push'е merge-окна ведёт к повтору тела
гейта в том же вызове `approve`, а не к `sys.exit`; общий потолок ожидания
CI при этом не сбрасывается, иные отказы push ведут себя как раньше
(задача 01M2XFSE8G3MBRHHQR38H53J1M).

Красен до реализации: `fsm_merge_gate._push_merged_main` (`orchestrator/
fsm_merge_gate.py:578-585`) трактует ЛЮБОЙ ненулевой код `git push` как
инфраструктурный сбой — пишет «merge FAILED» и завершает процесс
`sys.exit`'ом, поэтому отказ класса «cannot lock ref»/«non-fast-forward»
до реализации даёт `SystemExit` вместо записи «main сдвинулся во время
окна — повтор подтяжки» и второго захода в тело гейта. Часть AC-8 про
иные отказы push (сеть/права) — сохранение сегодняшнего поведения.

Тело гейта здесь разобрано на замоканные шаги (защищённые пути, публикация
головы, подтяжка, готовность CI, плотницкий merge, публикация артефактов),
живым остаётся ровно один узел — сам push и реакция на его отказ: тем же
приёмом, что `tests/test_merge_gate_ci_wait.py::OuterCycleDeadlineTest`
(настоящие git-операции merge-окна кроют приёмочные планки задач T087/
01M1R5B33CC7E6BZK085XV3ZCX на настоящем git).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, fsm_merge_gate, repo_context, store  # noqa: E402

from _sandbox import MergeOwnerSandbox  # noqa: E402

REMOTE = "github.com:example/artel.git"

CANNOT_LOCK_REF = (
    f"To {REMOTE}\n"
    " ! [remote rejected] deadbeef -> main (cannot lock ref "
    "'refs/heads/main': is at 8772115e but expected cd979106)\n"
    f"error: failed to push some refs to '{REMOTE}'\n")

NON_FAST_FORWARD = (
    f"To {REMOTE}\n"
    " ! [rejected]        deadbeef -> main (non-fast-forward)\n"
    f"error: failed to push some refs to '{REMOTE}'\n"
    "hint: Updates were rejected because a pushed branch tip is behind its "
    "remote counterpart.\n")

NETWORK_FAILURE = (
    "ssh: connect to host github.com port 22: Operation timed out\n"
    "fatal: Could not read from remote repository.\n")


def push_result(stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["git", "push"], returncode=returncode, stdout="", stderr=stderr)


class MovedMainPushSandbox(MergeOwnerSandbox):
    """Цикл `approve` гейта merge с живым push'ем и замоканными соседями."""

    SCRATCH_SHA = "deadbeefcafe0001"

    def setUp(self):
        super().setUp()
        self.clock = self.fake_clock()
        self.sync_outcomes: list = []
        self.push_results: list = []
        self.sync_calls: list = []
        self.push_args: list = []
        self.ci_waits: list = []
        self.patch(fsm_merge_gate, "_protected_path_diff_gate",
                   lambda *a, **k: False)
        self.patch(fsm_merge_gate, "_ensure_branch_head_published",
                   lambda *a, **k: "ok")
        self.patch(fsm_merge_gate, "_sync_main_or_wait", self.fake_sync)
        self.patch(fsm_merge_gate, "_ci_ready_or_wait", lambda *a, **k: "ok")
        self.patch(fsm_merge_gate, "_perform_carpentry_merge",
                   lambda *a, **k: ("ok", self.root / "scratch"))
        self.patch(fsm_merge_gate, "_publish_merge_artifacts",
                   lambda *a, **k: self.SCRATCH_SHA)
        self.patch(fsm_merge_gate, "_publish_closing_snapshot_or_wait",
                   lambda *a, **k: "ok")
        self.patch(fsm_merge_gate, "_cleanup_merged_task",
                   lambda *a, **k: None)
        self.patch(fsm_merge_gate, "_wait_for_branch_ci_green",
                   self.fake_ci_wait)
        self.patch(repo_context, "git", self.fake_git)

    def patch(self, target, attr: str, replacement) -> None:
        patcher = mock.patch.object(target, attr, replacement)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_sync(self, conn, task_id, t, state, branch, ctx):
        self.sync_calls.append(branch)
        return self.sync_outcomes.pop(0) if self.sync_outcomes else "fresh"

    def fake_ci_wait(self, conn, task_id, branch, start, deadline):
        self.ci_waits.append((start, deadline))
        self.clock.value += 100.0
        return "CI коммита deadbeef зелёный (тест)"

    def fake_git(self, ctx, *args):
        if args and args[0] == "push":
            self.push_args.append(args)
            if not self.push_results:
                self.fail(f"push вызван {len(self.push_args)} раз(а) — "
                          f"больше, чем предусмотрел сценарий теста")
            return self.push_results.pop(0)
        return push_result()

    def run_cycle(self) -> None:
        conn = store.db()
        fsm_merge_gate._cmd_approve_merge_gate_cycle(
            conn, self.TASK_A, "sess-a", store.get_task(conn, self.TASK_A),
            "merge_gate")

    def journal_blob(self) -> str:
        return "\n".join(self.journal_records(self.TASK_A))

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK_A)["state"]


class PushRetryOnMovedMainTest(MovedMainPushSandbox):

    def assert_retried_after(self, stderr: str) -> None:
        """Отказ push с текстом `stderr` не завершает процесс: тело гейта
        заходит второй раз в ТОМ ЖЕ вызове `approve`, push повторяется,
        задача доходит до `done`, а в журнале — именованная запись про
        сдвинувшийся main вместо ложного «merge FAILED»."""
        self.push_results = [push_result(stderr, returncode=1),
                             push_result()]

        self.run_cycle()

        self.assertEqual(len(self.push_args), 2,
                         "push обязан быть повторён после сдвига main")
        self.assertEqual(len(self.sync_calls), 2,
                         "тело гейта обязано зайти заново в том же вызове "
                         "approve (подтяжка второго захода)")
        blob = self.journal_blob()
        self.assertIn("main сдвинулся", blob)
        self.assertIn("повтор подтяжки", blob)
        self.assertNotIn(
            "merge FAILED", blob,
            "сдвинувшийся main — штатный исход окна, а не сбой: ложный "
            "сигнал «merge FAILED» был потерей инцидента 13.09")
        self.assertEqual(self.state(), "done",
                         "повторный заход обязан доводить задачу до done "
                         "без нового ручного approve")

    def test_ac7_cannot_lock_ref_rejection_repeats_the_gate_body(self):
        """Push отклонён с «cannot lock ref 'refs/heads/main': is at … but
        expected …» — буквально текст отказа origin из инцидента 13.09.

        Ловит мутацию: разбор класса отказа сведён к подстроке
        «non-fast-forward» — реальный текст «cannot lock ref» не
        распознается, и процесс снова завершится `sys.exit`'ом с «merge
        FAILED»; `run_cycle` упадёт `SystemExit`.
        """
        self.assert_retried_after(CANNOT_LOCK_REF)

    def test_ac7_non_fast_forward_rejection_repeats_the_gate_body(self):
        """Push отклонён классическим «! [rejected] … (non-fast-forward)» —
        второй текст того же класса «main сдвинулся».

        Ловит мутацию: разбор класса отказа сведён к подстроке «cannot lock
        ref» (только текст инцидента) — обычный non-fast-forward снова
        завершит процесс вместо повтора подтяжки.
        """
        self.assert_retried_after(NON_FAST_FORWARD)


class RetryKeepsCeilingTest(MovedMainPushSandbox):

    def test_ac8_retry_does_not_reset_the_ci_wait_ceiling(self):
        """Первый заход в тело уходит в ожидание CI после подтяжки (исход
        `("wait", branch)`) — с этого момента отсчёт потолка запущен.
        Второй заход доходит до push'а, получает «main сдвинулся» и уходит
        в ожидание CI снова: `start`/`deadline` обязаны прийти в цикл
        ожидания теми же, что и в первый раз, хотя часы за это время
        ушли вперёд.

        Ловит мутацию: повтор по AC-7 реализован через сброс `deadline`/
        `start` (например `deadline = None` перед новым заходом, чтобы
        «дать задаче полный потолок») — второй вызов ожидания получит
        `start`, сдвинутый на 100 секунд первого ожидания, и сверка
        `ci_waits[0] == ci_waits[1]` покраснеет.
        """
        self.sync_outcomes = [("wait", self.BRANCH[self.TASK_A])]
        self.push_results = [push_result(CANNOT_LOCK_REF, returncode=1),
                             push_result()]

        self.run_cycle()

        self.assertEqual(len(self.ci_waits), 2,
                         "повтор подтяжки обязан идти тем же путём, что "
                         "исход («wait», branch): подтяжка, push, "
                         "ожидание CI")
        self.assertEqual(self.ci_waits[0], self.ci_waits[1],
                         "потолок ожидания CI отсчитывается от первого "
                         "пуша вызова approve и повтором не сбрасывается")
        start, deadline = self.ci_waits[0]
        self.assertEqual(deadline - start,
                         config.MERGE_GATE_CI_WAIT_CEILING_SEC)
        self.assertGreater(
            self.clock.value, start,
            "часы обязаны уйти вперёд между заходами — иначе сверка "
            "start'ов ничего не различает")
        self.assertEqual(self.state(), "done")


class OtherPushFailureStillFailsTest(MovedMainPushSandbox):

    def test_ac8_network_push_failure_keeps_merge_failed_and_exits(self):
        """Отказ push иного класса (сеть/права) — прежнее поведение: запись
        «merge FAILED», завершение процесса, задача остаётся на
        `merge_gate` и повтора тела гейта нет.

        Ловит мутацию: реакция «повтор подтяжки» применена к ЛЮБОМУ
        отказу push (класс не разбирается вовсе) — недоступный origin
        уведёт цикл в бесконечный повтор вместо отказа: `SystemExit` не
        будет, а второй push упрётся в `self.fail` исчерпанного сценария.
        """
        self.push_results = [push_result(NETWORK_FAILURE, returncode=128)]

        with self.assertRaises(SystemExit):
            self.run_cycle()

        blob = self.journal_blob()
        self.assertIn("merge FAILED", blob)
        self.assertNotIn("main сдвинулся", blob)
        self.assertEqual(len(self.sync_calls), 1)
        self.assertEqual(self.state(), "merge_gate")


if __name__ == "__main__":
    unittest.main()
