"""Юнит-тесты доставки через MR проекта с `merge_gate: target-human` (SPEC 01M5XZ9Z68XE2EKPDHYCAK25KF): свойства вне долгоживущего файла задачи.

Сквозные сценарии (гейт мержа, черновой MR на входе в `verifying`,
пределы) держит `tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py`.
Здесь — узлы в изоляции: описание MR с изменёнными защищёнными путями
(положительная половина AC-15, недостижимая сквозным путём при действующих
гейтах — ANSWER-1), разбор исполнителя, путь «ссылка на MR есть» без
числового исполнителя (ANSWER-2 п. 3), отказ пределом отправок на черновом
MR GitHub без алерта (ANSWER-2 п. 4), выключенный путь `gh` для
`target-human` (ANSWER-2 п. 1) и добавка строки `status`.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (catalog, forge, fsm_merge_gate, github_adapter,  # noqa: E402
                          gitcmd)


class MrDescriptionTest(unittest.TestCase):

    def test_names_changed_protected_paths_only(self):
        """Описание называет защищённые пути, изменённые веткой, и только их.

        Ловит мутацию: в описании перечислен весь перечень защищённых путей
        проекта (есть `secret/`), либо изменённый защищённый путь не назван
        (нет `conf/app.yaml`), либо названы незащищённые изменённые файлы
        (есть `app.py`).
        """
        with mock.patch.object(github_adapter.gitcmd, "diff_base",
                               lambda branch, repo=None: "b" * 40), \
                mock.patch.object(github_adapter.gitcmd, "diff_names",
                                  lambda a, b, repo=None: ["conf/app.yaml",
                                                           "app.py"]):
            text = github_adapter.mr_description(
                "T1", "task/t1", "c" * 40, None, ("conf/", "secret/"))
        self.assertIn("conf/app.yaml", text)
        self.assertNotIn("secret/", text)
        self.assertNotIn("app.py", text)

    def test_no_protected_changes_no_warning(self):
        """Ветка без правки защищённых путей — в описании нет подсветки.

        Ловит мутацию: подсветка печатается всегда (строка «защищённые
        пути» при пустом перечне изменённых).
        """
        with mock.patch.object(github_adapter.gitcmd, "diff_base",
                               lambda branch, repo=None: "b" * 40), \
                mock.patch.object(github_adapter.gitcmd, "diff_names",
                                  lambda a, b, repo=None: ["app.py"]):
            text = github_adapter.mr_description(
                "T1", "task/t1", "c" * 40, None, ("conf/",))
        self.assertNotIn("защищённые пути", text)


class MrAssigneeTest(unittest.TestCase):

    def test_only_integer_id_is_assigned(self):
        """Исполнитель уходит в `forge` только целым; булево, имя и отсутствие — без исполнителя с записью.

        Ловит мутацию: `True` (подкласс `int`) уходит исполнителем 1; либо
        имя `alice` уходит исполнителем; либо отсутствие поля не даёт
        записи журнала.
        """
        self.assertEqual(github_adapter.mr_assignee({"mr_assignee": 42}),
                         (42, ""))
        for value in (True, "alice", None):
            with self.subTest(value=value):
                assignee, note = github_adapter.mr_assignee(
                    {"mr_assignee": value})
                self.assertIsNone(assignee)
                self.assertIn(github_adapter.ASSIGNEE_NOT_NUMERIC, note)


class ExistingLinkTest(unittest.TestCase):

    def _ready(self, policy: dict, assign=None):
        undraft = mock.Mock(return_value=forge.MergeRequest(iid=7))
        assign = assign or mock.Mock(return_value=forge.MergeRequest(iid=7))
        journal = mock.Mock()
        with mock.patch.object(fsm_merge_gate.forge, "undraft_mr", undraft), \
                mock.patch.object(fsm_merge_gate.forge, "assign_mr", assign), \
                mock.patch.object(fsm_merge_gate.targets, "target",
                                  lambda name: {"merge_gate": "target-human",
                                                **policy}), \
                mock.patch.object(fsm_merge_gate.store, "journal", journal):
            ok = fsm_merge_gate._ready_existing_mr(mock.Mock(), "T1", "p", 7)
        return ok, undraft, assign, journal

    def test_without_numeric_assignee_assign_mr_is_not_called(self):
        """Ссылка на MR есть, исполнитель не числовой или не задан — черновик снят, `assign_mr` не зван, запись журнала.

        Ловит мутацию: `assign_mr` зовётся с `None` или именем; либо
        неназначение молчит — записи «исполнитель не числовой id — не
        назначен» нет.
        """
        for policy in ({}, {"mr_assignee": "alice"}):
            with self.subTest(policy=policy):
                ok, undraft, assign, journal = self._ready(policy)
                self.assertTrue(ok)
                undraft.assert_called_once_with("p", 7)
                assign.assert_not_called()
                text = " ".join(str(c.args) for c in journal.call_args_list)
                self.assertIn(github_adapter.ASSIGNEE_NOT_NUMERIC, text)

    def test_assign_refusal_keeps_the_gate(self):
        """Отказ `assign_mr` — `False` (задача остаётся на гейте), причина хостинга в журнале.

        Ловит мутацию: результат `assign_mr` не проверяется на `reason` —
        `True` и переход в `awaiting_human` без исполнителя.
        """
        failing = mock.Mock(return_value=forge.MergeRequest(reason="403 нет"))
        ok, _undraft, assign, journal = self._ready({"mr_assignee": 42},
                                                    failing)
        self.assertFalse(ok)
        assign.assert_called_once_with("p", 7, 42)
        self.assertIn("403 нет", " ".join(str(c.args)
                                         for c in journal.call_args_list))


class GithubDraftMrTest(unittest.TestCase):

    def setUp(self):
        self.conn = mock.Mock()
        self.row = {"target": "proj", "branch": "task/t1-x", "title": "T",
                    "draft_mr_created": 0, "is_canary": 0}
        for patcher in (
                mock.patch.object(github_adapter, "_commits_over_base",
                                  lambda *a, **k: None),
                mock.patch.object(github_adapter.repo_context, "resolve",
                                  lambda name: None),
                mock.patch.object(github_adapter.artifact_branch,
                                  "send_pending", lambda *a: None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.gh = mock.Mock()
        self.alert = mock.Mock()
        for patcher in (mock.patch.object(github_adapter.ci, "gh", self.gh),
                        mock.patch.object(github_adapter.alerts, "raise_alert",
                                          self.alert),
                        mock.patch.object(github_adapter.store, "journal")):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_in_flight_refusal_is_not_an_incident(self):
        """Отказ первой отправки пределом `max_in_flight` на черновом MR GitHub — без алерта и без `gh`.

        Ловит мутацию: отказ пределом идёт веткой сбоя отправки —
        `alerts.raise_alert` зван (инцидент `github_adapter`).
        """
        refusal = subprocess.CompletedProcess(
            [], 1, "", f"{gitcmd.PUSH_REFUSED_ACTION} (проект proj): "
                       f"{gitcmd.IN_FLIGHT_LIMIT_REASON}: 2 из 2")
        with mock.patch.object(github_adapter.targets, "target",
                               lambda name: {"forge": "github",
                                             "base": "main",
                                             "merge_gate": "operator"}), \
                mock.patch.object(github_adapter.gitcmd, "in_repo",
                                  lambda *a, **k: refusal):
            github_adapter.ensure_draft_mr(self.conn, "T1", self.row)
        self.alert.assert_not_called()
        self.gh.assert_not_called()

    def test_target_human_never_uses_gh(self):
        """Запись `target-human` — путь чернового PR через `gh` выключен: ни отправки, ни `gh`.

        Ловит мутацию: проверка гейта людей проекта убрана — `gh pr create`
        зван для записи `target-human`.
        """
        push = mock.Mock()
        with mock.patch.object(github_adapter.targets, "target",
                               lambda name: {"forge": "github",
                                             "base": "main",
                                             "merge_gate": "target-human"}), \
                mock.patch.object(github_adapter.gitcmd, "in_repo", push):
            github_adapter.ensure_draft_mr(self.conn, "T1", self.row)
        push.assert_not_called()
        self.gh.assert_not_called()


class DeliverySuffixTest(unittest.TestCase):

    def _suffix(self, actions: list) -> str:
        steps = [{"action": a, "detail": d} for a, d in actions]
        with mock.patch.object(catalog.store, "task_steps",
                               lambda conn, task_id: steps):
            return catalog._delivery_suffix(mock.Mock(), {"id": "T1"})

    def test_current_refusals_are_shown(self):
        """Последний отказ доставки после смены состояния — в строке `status`.

        Ловит мутацию: добавка не читает одну из трёх причин — пустая
        строка при отказе пределом `max_awaiting`, `max_in_flight` или
        черновым MR.
        """
        cases = (
            (github_adapter.AWAITING_LIMIT_ACTION, "x", "предел awaiting_human"),
            (gitcmd.PUSH_REFUSED_ACTION,
             f"{gitcmd.IN_FLIGHT_LIMIT_REASON}: 3 из 3", "max_in_flight"),
            (github_adapter.DRAFT_MR_REFUSAL_ACTION,
             "черновой MR не открыт: 403", "черновой MR не открыт"),
        )
        for action, detail, expected in cases:
            with self.subTest(action=action):
                self.assertIn(expected, self._suffix(
                    [("state -> in_dev", ""), (action, detail),
                     ("lease снят", "")]))

    def test_refusal_before_a_transition_or_push_is_stale(self):
        """Отказ раньше смены состояния или успешной отправки в строке `status` не показывается.

        Ловит мутацию: добавка берёт любой отказ журнала, а не последний
        после смены состояния — устаревшая «очередь» у задачи, уже
        прошедшей дальше.
        """
        refusal = (gitcmd.PUSH_REFUSED_ACTION,
                   f"{gitcmd.IN_FLIGHT_LIMIT_REASON}: 3 из 3")
        self.assertEqual(self._suffix([refusal, ("state -> verifying", "")]),
                         "")
        self.assertEqual(self._suffix([refusal,
                                       (gitcmd.PUSH_SENT_ACTION, "abc b")]), "")
        self.assertEqual(self._suffix([(gitcmd.PUSH_REFUSED_ACTION,
                                        "отправка в base main")]), "")


class ConfirmedHeadTest(unittest.TestCase):

    def test_code_head_of_the_confirmed_fixation(self):
        """Подтверждённая голова — `код=` записи фиксации с sha `fixed_sha`, не последней записи с иным sha.

        Ловит мутацию: берётся `код=` последней записи фиксации без сверки
        sha — голова чужой (более поздней) фиксации считается подтверждённой.
        """
        head, other = "a" * 40, "b" * 40
        steps = [
            {"action": "sha зафиксирован",
             "detail": f"target=p, sha=d1, чисто=True, код={head}, артефакты=d1"},
            {"action": "sha зафиксирован",
             "detail": f"target=p, sha=d2, чисто=True, код={other}, артефакты=d2"},
        ]
        with mock.patch.object(fsm_merge_gate.store, "get_task",
                               lambda conn, task_id: {"fixed_sha": "d1"}), \
                mock.patch.object(fsm_merge_gate.store, "task_steps",
                                  lambda conn, task_id: steps):
            self.assertEqual(fsm_merge_gate._confirmed_code_head(None, "T1"),
                             head)


if __name__ == "__main__":
    unittest.main()
