"""Гейт приёмки использует зелёный CI дерева, которое он проверяет.

Группа: долгоживущий
Красен до реализации: приёмка пока безусловно вызывает локальный полный набор.
"""

import json
import random
import subprocess
import unittest
from unittest import mock

from orchestrator import (acceptance, ci, config, fixation, fsm, gates,
                          github_adapter, pull, store, workspace)
from tests.sandbox import LightTransitionSandbox, RealGitSandbox


class CiAcceptanceTest(RealGitSandbox):
    """Публичный `approve` в отдельном git-репозитории с подменённым `gh`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        rng = random.Random(self.seed)
        self.add_synced_origin()
        self.TASK = f"T{rng.getrandbits(72):018X}"
        self.branch = f"task/{self.TASK.lower()}"
        self.git("checkout", "-q", "-b", self.branch)
        self.sha = self.git("rev-parse", "HEAD").strip()
        store.insert_task(store.db(), self.TASK, "Приёмка CI", "acceptance",
                          self.branch, config.DEFAULT_TARGET, 10.0)
        self.run_id = rng.randrange(10000, 1000000)
        self.tree = self.git("rev-parse", "HEAD^{tree}").strip()
        self.gate_tree = self.tree
        self.head_tree = self.tree
        self.ci_answer = "success"
        self.full_suite_done = True
        self.gh_answers = True
        self.local = mock.Mock(return_value=acceptance.FullSuiteRun(
            True, acceptance.FULL_SUITE_GREEN, "зелёный", None,
            "локальный полный набор зелёный"))
        def fake_gh(*args, **kwargs):
            if not self.gh_answers:
                return subprocess.CompletedProcess(args, 1, "", "нет ответа")
            if "check-runs" in " ".join(args):
                checks = [{"name": name, "status": "completed",
                           "conclusion": ("success" if self.full_suite_done
                                          else "skipped"),
                           "details_url": f"https://example.test/actions/runs/{self.run_id}/job/1",
                           "check_suite": {"id": self.run_id}}
                          for name in sorted(ci.FULL_SUITE_CHECKS)]
                if self.ci_answer != "success":
                    checks.append({"name": "other",
                                   "status": ("in_progress" if
                                              self.ci_answer == "running" else
                                              "completed"),
                                   "conclusion": (None if
                                                  self.ci_answer == "running"
                                                  else self.ci_answer)})
                body = {"total_count": len(checks), "check_runs": checks}
            else:
                body = {"total_count": 1, "workflow_runs": [{
                    "id": self.run_id, "databaseId": self.run_id,
                    "check_suite_id": self.run_id, "head_sha": self.sha,
                    "status": ("in_progress" if self.ci_answer == "running"
                               else "completed"),
                    "conclusion": (None if self.ci_answer == "running"
                                   else self.ci_answer),
                    "event": "push"}]}
            return subprocess.CompletedProcess(args, 0, json.dumps(body), "")

        self.gh = mock.Mock(side_effect=fake_gh)
        for target, name, kwargs in (
            (pull, "evaluate", {"return_value": pull.Fresh()}),
            (fsm, "confirm_fixation", {"return_value": True}),
            (fixation, "approve_sha_hint", {"return_value": ""}),
            (github_adapter, "undraft_mr", {"return_value": None}),
            (workspace, "on_task_branch", {"return_value": True}),
            (workspace, "path", {"return_value": self.root}),
            (ci, "head_sha", {"return_value": (self.sha, "")}),
            (ci, "gh", {"side_effect": self.gh}),
            (acceptance, "full_suite", {"side_effect": self.local}),
            (acceptance, "suite_tree_hash", {"side_effect":
                lambda *a, **kw: self.head_tree if kw.get("ref") not in
                (None, "HEAD") or kw.get("worktree") is False else self.gate_tree}),
        ):
            patcher = mock.patch.object(target, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def approve(self, *, fresh_suite=False):
        return self.capture(lambda: fsm.cmd_approve(
            self.TASK, fresh_suite=fresh_suite))

    def journal(self):
        return "\n".join(f"{r['action']} {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), self.TASK))

    def state(self):
        return store.get_task(store.db(), self.TASK)["state"]

    def set_state(self, state):
        store.update_task(store.db(), self.TASK, state=state)

    def test_ac1_matching_green_ci_skips_local_suite(self):
        """Совпавшее дерево и выполненный зелёный CI проводят приёмку без pytest.

        Ловит мутацию: гейт игнорирует годный CI и вызывает локальный полный
        набор; счётчик локального прогона становится ненулевым.
        """
        self.approve()
        self.assertEqual(self.state(), "merge_gate", f"зерно: {self.seed}")
        self.local.assert_not_called()
        self.gh.assert_called()

    def test_ac2_accepted_ci_is_recorded_on_transition_and_card(self):
        """Принятый CI проводит задачу и оставляет SHA с ID прогона.

        Ловит мутацию: при пропуске локального прогона запись о доказательстве
        зелёности теряется; журнал не содержит SHA или ID CI.
        """
        self.approve()
        record = self.journal()
        self.assertEqual(self.state(), "merge_gate", f"зерно: {self.seed}")
        self.assertIn(f"полный набор: принят итог CI {self.sha}", record)
        self.assertIn(str(self.run_id), record)
        cards = [r["detail"] or "" for r in
                 store.task_steps(store.db(), self.TASK)
                 if "приёмка" in r["action"]]
        self.assertTrue(any(self.sha in card and str(self.run_id) in card
                            for card in cards), f"зерно: {self.seed}; {cards}")

    def test_ac3_different_tree_runs_local_suite_with_one_line_reason(self):
        """Несовпавший снимок дерева требует локального набора и причины.

        Ловит мутацию: сравнение деревьев убрано; гейт принимает чужой CI,
        и локальный прогон не вызывается.
        """
        self.gate_tree = "0" * 40 if self.tree != "0" * 40 else "1" * 40
        self.approve()
        self.local.assert_called_once()
        reasons = [r["detail"] or "" for r in
                   store.task_steps(store.db(), self.TASK)
                   if "дерев" in (r["detail"] or "").lower()]
        self.assertEqual(len(reasons), 1, f"зерно: {self.seed}; {reasons}")
        self.assertNotIn("\n", reasons[0])

    def test_ac4_bad_ci_or_stale_branch_runs_local_suite(self):
        """Незелёный CI, пропуск набора и отставшая ветка требуют pytest.

        Ловит мутацию: одно из трёх условий годности CI забыто; в этом
        сценарии соответствующий локальный прогон исчезает.
        """
        for condition in ("red", "running", "suite_skipped", "stale"):
            with self.subTest(condition=condition, seed=self.seed):
                self.ci_answer = ("failure" if condition == "red" else
                                  "running" if condition == "running" else
                                  "success")
                self.full_suite_done = condition != "suite_skipped"
                if condition == "stale":
                    self.git("checkout", "-q", config.MAIN_BRANCH)
                    (self.root / "later.txt").write_text("новый main\n",
                                                           encoding="utf-8")
                    self.git("add", "later.txt")
                    self.git("commit", "-q", "-m", "новый main")
                    self.git("push", "-q", "origin", config.MAIN_BRANCH)
                    self.git("checkout", "-q", self.branch)
                self.local.reset_mock()
                before = len(store.task_steps(store.db(), self.TASK))
                try:
                    self.approve()
                    self.local.assert_called_once()
                    added = store.task_steps(store.db(), self.TASK)[before:]
                    terms = (("ci", "красн") if condition == "red" else
                             ("ci", "заверш") if condition == "running" else
                             ("набор", "исполн") if condition == "suite_skipped"
                             else ("ветк", "свеж"))
                    reasons = [r["detail"] or "" for r in added
                               if r["action"] == "полный набор локально"
                               and any(term in (r["detail"] or "").lower()
                                       for term in terms)]
                    self.assertEqual(len(reasons), 1,
                                     f"зерно: {self.seed}; {condition}; {added}")
                    self.assertNotIn("\n", reasons[0])
                finally:
                    self.set_state("acceptance")

    def test_ac5_ci_no_answer_runs_local_suite_with_reason(self):
        """Неответивший `gh` заставляет проверить дерево локально.

        Ловит мутацию: сетевой сбой считается зелёным CI; локальный прогон
        не вызывается и запись причины не появляется.
        """
        self.gh_answers = False
        self.approve()
        self.local.assert_called_once()
        reasons = [r["detail"] or "" for r in
                   store.task_steps(store.db(), self.TASK)
                   if "ответ" in (r["detail"] or "").lower()]
        self.assertEqual(len(reasons), 1, f"зерно: {self.seed}; {reasons}")
        self.assertNotIn("\n", reasons[0])

    def test_ac6_fresh_suite_always_runs_locally(self):
        """Явный запрос свежего прогона сильнее готового зелёного CI.

        Ловит мутацию: флаг `fresh_suite` не доезжает до решения гейта;
        локальный прогон остаётся невызванным.
        """
        self.approve(fresh_suite=True)
        self.local.assert_called_once()
        self.assertEqual(self.state(), "merge_gate", f"зерно: {self.seed}")


class CiAutogateTest(LightTransitionSandbox):
    """Переход в приёмку с готовой планкой и автоматической политикой."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        rng = random.Random(self.seed)
        self.sha = f"{rng.getrandbits(160):040x}"
        run_id = rng.randrange(10000, 1000000)
        self.local = mock.Mock(return_value=acceptance.FullSuiteRun(
            True, acceptance.FULL_SUITE_GREEN, "зелёный", None, "зелёный"))
        checks = [{"name": name, "status": "completed",
                   "conclusion": "success",
                   "details_url": f"https://example.test/actions/runs/{run_id}/job/1",
                   "check_suite": {"id": run_id}}
                  for name in sorted(ci.FULL_SUITE_CHECKS)]
        response = {"total_count": len(checks), "check_runs": checks}
        gh = mock.Mock(return_value=subprocess.CompletedProcess(
            ["gh"], 0, json.dumps(response), ""))
        for target, name, kwargs in (
            (gates, "policy", {"return_value": gates.AUTO}),
            (workspace, "on_task_branch", {"return_value": True}),
            (workspace, "path", {"return_value": self.wt_path}),
            (ci, "head_sha", {"return_value": (self.sha, "")}),
            (ci, "gh", {"side_effect": gh}),
            (acceptance, "full_suite", {"side_effect": self.local}),
            (acceptance, "suite_tree_hash", {"return_value":
                                            f"{rng.getrandbits(160):040x}"}),
            (fixation, "approve_sha_hint", {"return_value": ""}),
        ):
            patcher = mock.patch.object(target, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_ac1_autogate_accepts_matching_green_ci(self):
        """Автогейт проводит тот же зелёный CI без локального pytest.

        Ловит мутацию: `approve` научился принимать CI, а автогейт оставлен
        на локальном прогоне; счётчик прогона становится ненулевым.
        """
        self.write_acceptance_plank()
        (self.tdir / "REVIEW.md").write_text(
            "---\n" + f"task: {self.TASK}\n" +
            "type: review\nauthor_role: reviewer\nstatus: approved\n"
            "iteration: 1\nschema_version: 2\n---\n\n"
            "# REVIEW: проверка CI\n\n## Соответствие SPEC\n"
            "Критерии выполнены.\n\n## Замечания\nНет.\n\n"
            "## Вердикт\napproved\n\n"
            "## Проверено исполнением\nПланка зелёная.\n",
            encoding="utf-8")
        self.set_state("review")
        out = self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.state(), "merge_gate", f"зерно: {self.seed}; {out}")
        self.local.assert_not_called()
