"""Вызывающие функции CI — `ci-rerun` (`orchestrator/ci_rerun.py`) и ре-ран
гейта мержа (`orchestrator/fsm_merge_gate._ci_confirm_red_or_flake`):
передача клона внешнего проекта и запись `flake-rate` при незапущенном
повторе (SPEC 01M55V7WB94C9BZXTXTTH83YWV, требования 3, 5, 7; AC-7, AC-10,
AC-11).

Долгоживущие сторожа этих свойств: планка задачи о них разовая. Ни git, ни
`gh`: функции `ci`, `fsm._origin_main_sha` и `workspace.task_repo` подменены
записывающими заглушками; признак артели — настоящий `repo_context.is_artel`
через `ci._repo_kwargs`.
"""
from unittest import mock

from orchestrator import (ci, ci_rerun, config, fsm, fsm_merge_gate,
                          repo_context, store, workspace)
from tests.sandbox import TmpRootTest

PROJECT = "uchebproj"
BRANCH = "task/x-proj"
HEAD = "1111aaaa" + "0" * 32
MAIN_SHA = "2222bbbb" + "0" * 32
RED = (False, "CI коммита 1111aaaa не зелёный: py=failure")
GREEN = (True, "CI коммита 1111aaaa зелёный (1 проверок)")
STARTED = "ре-ран прогона 7 запущен, ожидание завершения: ок"


class CallersSandbox(TmpRootTest):
    """`workspace.task_repo` отвечает клоном проекта или клоном артели;
    записи журнала копятся в `self.rows`."""

    def setUp(self):
        super().setUp()
        self.rows = []
        self.calls = []
        self.repo = None
        for target, name, value in (
                (workspace, "task_repo", lambda task_id: self.repo),
                (store, "journal", self.journal)):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def journal(self, conn, task_id, actor, action, detail="", **_kw):
        self.rows.append((action, detail))

    def use(self, target: str) -> None:
        self.repo = repo_context.clone_path(target)

    def spy(self, name: str, answer):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return answer(*args) if callable(answer) else answer
        return record

    def repo_of(self, name: str) -> list:
        """`repo=` каждого вызова `name` (`None` — именованного `repo` нет)."""
        return [kw.get("repo") for n, _a, kw in self.calls if n == name]


class FlakeRateNotStartedTest(CallersSandbox):
    """Запись `flake-rate` при незапущенном повторе (требование 7, AC-11)."""

    def confirm(self, rerun_note: str, status: tuple) -> list[str]:
        self.use(config.DEFAULT_TARGET)
        self.rows.clear()
        with mock.patch.object(ci, "trigger_rerun", lambda *a, **k: rerun_note), \
                mock.patch.object(ci, "branch_status",
                                  lambda b, repo=None: status):
            try:
                fsm_merge_gate._ci_confirm_red_or_flake(
                    None, "T1", BRANCH, RED[1])
            except SystemExit:
                pass
        return [d for a, d in self.rows if a == "flake-rate"]

    def test_not_started_rerun_named_with_reason_on_red_and_green(self):
        """Повтор не запущен — «повтор не запущен: <причина>» при красном и
        зелёном статусе после; ни «подтверждённый красный», ни «флейк».

        Ловит мутацию: ветка `not ci.rerun_started(...)` в
        `_ci_confirm_red_or_flake` убрана или стоит только на красном исходе
        — незапущенный повтор пишется «подтверждённым красным», а зелёный —
        «флейком»; либо запись не несёт `note` причины.
        """
        for note in ("ре-ран CI не запущен: нет прогона",
                     "ре-ран прогона 42 не запущен: gh упал"):
            for status in (RED, GREEN):
                with self.subTest(note=note, зелёный=status[0]):
                    rows = self.confirm(note, status)
                    self.assertEqual(len(rows), 1, rows)
                    self.assertIn("повтор не запущен", rows[0])
                    self.assertIn(note, rows[0])
                    for bad in ("подтверждённый красный",
                                "ре-ран тоже красный", "флейк"):
                        self.assertNotIn(bad, rows[0])

    def test_started_rerun_keeps_previous_records(self):
        """Повтор запущен — прежние записи: красный «подтверждённый
        красный», зелёный «флейк».

        Ловит мутацию: признак незапущенного повтора срабатывает и на
        запущенном (например, проверка подстроки «запущен» вместо «не
        запущен») — запись «повтор не запущен» о состоявшемся повторе.
        """
        for status, word in ((RED, "подтверждённый красный"),
                             (GREEN, "флейк")):
            with self.subTest(зелёный=status[0]):
                rows = self.confirm(STARTED, status)
                self.assertEqual(len(rows), 1, rows)
                self.assertIn(word, rows[0])
                self.assertNotIn("повтор не запущен", rows[0])


class MergeGateRerunRepoTest(CallersSandbox):
    """`_ci_confirm_red_or_flake` передаёт клон проекта в `trigger_rerun`
    (требование 3, AC-7)."""

    def test_project_clone_reaches_trigger_rerun_artel_keeps_form(self):
        """Проект — `trigger_rerun(branch, repo=<клон>)`; артель — без `repo`.

        Ловит мутацию: `ci.trigger_rerun(branch)` гейта мержа без клона —
        ре-ран задачи проекта уходит в репозиторий артели; либо `repo=`
        передаётся и артели — вызов артели не прежней формы.
        """
        for target, expected in ((PROJECT, repo_context.clone_path(PROJECT)),
                                 (config.DEFAULT_TARGET, None)):
            with self.subTest(проект=target):
                self.use(target)
                self.calls.clear()
                with mock.patch.object(ci, "trigger_rerun",
                                       self.spy("trigger_rerun", STARTED)), \
                        mock.patch.object(ci, "branch_status",
                                          lambda b, repo=None: GREEN):
                    fsm_merge_gate._ci_confirm_red_or_flake(
                        None, "T1", BRANCH, RED[1])
                self.assertEqual(self.repo_of("trigger_rerun"), [expected])


class CiRerunRepoTest(CallersSandbox):
    """`ci-rerun` передаёт клон проекта во все вызовы `ci` и в
    `fsm._origin_main_sha` (требования 3, 5; AC-7, AC-10)."""

    def red_rerun(self, target: str) -> None:
        self.use(target)
        self.calls.clear()
        names = {HEAD: {"py"}, MAIN_SHA: {"lint"}}
        with mock.patch.object(ci, "head_sha", lambda b, repo=None: (HEAD, "")), \
                mock.patch.object(ci_rerun, "_last_red_status_sha",
                                  lambda conn, task_id: HEAD[:8]), \
                mock.patch.object(ci, "failed_check_names", self.spy(
                    "failed_check_names", lambda sha: (names[sha], ""))), \
                mock.patch.object(fsm, "_origin_main_sha",
                                  self.spy("_origin_main_sha", MAIN_SHA)), \
                mock.patch.object(ci, "trigger_rerun",
                                  self.spy("trigger_rerun", STARTED)):
            ci_rerun._red_rerun(None, "T1", {"target": target}, BRANCH)

    def stuck_rerun(self, target: str) -> None:
        self.use(target)
        self.calls.clear()
        with mock.patch.object(ci, "stuck_check_ids", lambda note: ["5", "6"]), \
                mock.patch.object(ci, "check_run_workflow_run", self.spy(
                    "check_run_workflow_run", ("77", ""))), \
                mock.patch.object(ci, "trigger_rerun",
                                  self.spy("trigger_rerun", STARTED)):
            ci_rerun._stuck_rerun(None, "T1", BRANCH, "зависла")

    def test_red_path_passes_project_clone_everywhere(self):
        """Красный путь: `failed_check_names` (голова и вершина),
        `fsm._origin_main_sha` и `trigger_rerun` — с `repo=<клон проекта>`;
        у артели — все без `repo`.

        Ловит мутацию: в `_red_rerun` снят `**project` у любого из вызовов
        (`failed_check_names(head)`, `failed_check_names(main_sha)`,
        `fsm._origin_main_sha(target)`, `trigger_rerun(branch)`) — запрос
        задачи проекта уходит в репозиторий артели (или `git fetch` по
        адресу проекта идёт в главной копии пульта); либо `repo=`
        передаётся и артели.
        """
        clone = repo_context.clone_path(PROJECT)
        for target, expected in ((PROJECT, clone), (config.DEFAULT_TARGET, None)):
            with self.subTest(проект=target):
                self.red_rerun(target)
                self.assertEqual(self.repo_of("failed_check_names"),
                                 [expected, expected])
                self.assertEqual(self.repo_of("_origin_main_sha"), [expected])
                self.assertEqual(self.repo_of("trigger_rerun"), [expected])

    def test_stuck_path_passes_project_clone_everywhere(self):
        """Путь зависшей проверки: `check_run_workflow_run` каждой проверки и
        `trigger_rerun(…, run_id=…)` — с `repo=<клон проекта>`; у артели — без.

        Ловит мутацию: в `_stuck_rerun` снят `**project` у
        `check_run_workflow_run(check_id)` или `trigger_rerun(branch,
        run_id=…)` — задание и повтор задачи проекта спрашиваются у
        репозитория артели; либо `repo=` передаётся и артели.
        """
        clone = repo_context.clone_path(PROJECT)
        for target, expected in ((PROJECT, clone), (config.DEFAULT_TARGET, None)):
            with self.subTest(проект=target):
                self.stuck_rerun(target)
                self.assertEqual(self.repo_of("check_run_workflow_run"),
                                 [expected, expected])
                self.assertEqual(self.repo_of("trigger_rerun"), [expected])
