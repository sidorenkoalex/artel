"""Юнит-тесты правила завершённости check-run'а и состояния «проверка
зависла» (SPEC 01M3Y75C9TY76083CG1PK00EM4): границы, не покрытые
долгоживущим файлом задачи `tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py`.

`gh` и голова ветки подменены (`ci.gh`, `ci.head_sha`): сети и git нет.
"""
import json
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from orchestrator import ci, ci_rerun, config, store

HEAD = "6cb9b55e" + "0" * 32


def iso_ago(minutes: float) -> str:
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def answer(returncode: int, stdout: str = "",
           stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["gh"], returncode, stdout, stderr)


def green(name: str) -> dict:
    return {"id": 1, "name": name, "status": "completed",
            "conclusion": "success", "started_at": iso_ago(30),
            "completed_at": iso_ago(25)}


class CiStand(unittest.TestCase):
    """`ci.gh` отвечает check-runs из `self.runs`, остальное — `self.extra`."""

    def stand(self, runs: list, extra=None) -> None:
        self.runs = runs
        self.calls: list[tuple] = []

        def fake_gh(*args, **kwargs):
            self.calls.append(args)
            if "check-runs" in " ".join(args):
                return answer(0, json.dumps({"total_count": len(self.runs),
                                             "check_runs": self.runs}))
            if extra is not None:
                return extra(*args)
            return answer(0, "[]")

        for target, value in (("gh", fake_gh),
                              ("head_sha", lambda b, repo=None: (HEAD, ""))):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)


class CompletionRuleTest(CiStand):

    def test_conclusion_without_completed_at_is_still_running(self):
        """`in_progress` с `conclusion`, но без `completed_at` — идёт.

        Ловит мутацию: правило требует только `conclusion` (без
        `completed_at`) — проверка станет завершённой, и исход
        `verifying_status` будет `green` вместо `running`.
        """
        self.stand([green("python"),
                    {"id": 7, "name": "guard", "status": "in_progress",
                     "conclusion": "success", "completed_at": None,
                     "started_at": iso_ago(1)}])
        outcome, note = ci.verifying_status("task/x")
        self.assertEqual(outcome, ci.VERIFYING_RUNNING, note)
        self.assertNotIn("считаю завершённой", note)

    def test_completed_at_without_conclusion_is_still_running(self):
        """`in_progress` с `completed_at`, но без `conclusion` — не зелёная
        и на гейте мержа.

        Ловит мутацию: правило требует только `completed_at` — проверка
        без исхода станет завершённой, `branch_status` отдаст красный
        `note` (`None` не в GREEN) вместо «ещё идёт».
        """
        self.stand([green("python"),
                    {"id": 7, "name": "guard", "status": "in_progress",
                     "conclusion": None, "completed_at": iso_ago(1),
                     "started_at": iso_ago(2)}])
        ok, note = ci.branch_status("task/x")
        self.assertFalse(ok)
        self.assertEqual(ci.status_kind(note), "running", note)

    def test_reread_line_is_separate_and_keeps_summary_first(self):
        """Строка о прочтении вопреки `status` — своей строкой после итога.

        Ловит мутацию: строка приклеена в начало `note` — первая строка
        перестанет быть итогом «CI коммита … не зелёный», и разбор
        `red_status_sha`, на котором стоит `ci-rerun`, потеряет sha.
        """
        self.stand([green("python"),
                    {"id": 7, "name": "guard", "status": "in_progress",
                     "conclusion": "failure", "completed_at": iso_ago(1),
                     "started_at": iso_ago(3)}])
        outcome, note = ci.verifying_status("task/x")
        self.assertEqual(outcome, ci.VERIFYING_RED, note)
        first, *rest = note.split("\n")
        self.assertEqual(ci.red_status_sha(first), HEAD[:8])
        self.assertTrue(rest and rest[0].startswith(
            "guard: GitHub отдаёт status=in_progress при conclusion=failure"),
            note)

    def test_branch_status_has_no_stuck_state(self):
        """На гейте мержа старая проверка без исхода — «ещё идёт».

        Ловит мутацию: `branch_status` переводит зависшую проверку в
        красный `note` — гейт мержа запустил бы ре-ран и счёт флейков по
        проверке, которая не падала (SPEC, «Не входит»).
        """
        self.stand([green("python"),
                    {"id": 7, "name": "guard", "status": "in_progress",
                     "conclusion": None, "completed_at": None,
                     "started_at": iso_ago(config.CI_STUCK_CHECK_MINUTES + 30)}])
        ok, note = ci.branch_status("task/x")
        self.assertFalse(ok)
        self.assertEqual(ci.status_kind(note), "running", note)


class StuckStateTest(CiStand):

    def old_check(self, **fields) -> dict:
        check = {"id": 4242, "name": "guard", "status": "in_progress",
                 "conclusion": None, "completed_at": None,
                 "started_at": iso_ago(config.CI_STUCK_CHECK_MINUTES + 20)}
        check.update(fields)
        return check

    def test_other_status_is_never_stuck(self):
        """Старая проверка в статусе вне `in_progress`/`queued` — идёт.

        Ловит мутацию: «зависла» решается по одному возрасту без статуса —
        проверка `waiting` (ждёт ручного одобрения окружения) станет
        «зависшей», и `ci-rerun` перезапускал бы то, что ждёт человека.
        """
        self.stand([self.old_check(status="waiting")])
        outcome, note = ci.verifying_status("task/x")
        self.assertEqual(outcome, ci.VERIFYING_RUNNING, note)

    def test_unparsable_timestamps_are_running_not_stuck(self):
        """Отметки времени не разобраны — проверка идёт, а не зависла.

        Ловит мутацию: неразобранный возраст считается бесконечным — сбой
        формата GitHub API превращал бы любую идущую проверку в зависшую.
        """
        self.stand([self.old_check(started_at="вчера", created_at=None)])
        outcome, note = ci.verifying_status("task/x")
        self.assertEqual(outcome, ci.VERIFYING_RUNNING, note)

    def test_stuck_note_ids_are_parsed_back(self):
        """`stuck_check_ids` достаёт из `note` id всех зависших проверок.

        Ловит мутацию: в `note` попадает только первая зависшая проверка —
        id второй не найдётся, и её прогон `ci-rerun` не перезапустит.
        """
        self.stand([self.old_check(id=111, name="guard"),
                    self.old_check(id=222, name="lint", status="queued"),
                    green("python")])
        outcome, note = ci.verifying_status("task/x")
        self.assertEqual(outcome, ci.VERIFYING_STUCK, note)
        self.assertEqual(ci.stuck_check_ids(note), ["111", "222"])
        self.assertEqual(ci.stuck_check_ids("CI коммита abc ещё идёт: x"), [])


class RerunTargetTest(CiStand):

    def test_workflow_run_of_check_comes_from_its_job(self):
        """`check_run_workflow_run` берёт `run_id` задания check-run'а.

        Ловит мутацию: функция отдаёт `id` ответа (id задания) вместо
        `run_id` — `gh run rerun` получил бы id задания и промахнулся.
        """
        def extra(*args):
            if "actions/jobs/555" in " ".join(args):
                return answer(0, json.dumps({"id": 555, "run_id": 9001}))
            return answer(1, "", "HTTP 404")

        self.stand([], extra)
        self.assertEqual(ci.check_run_workflow_run("555"), ("9001", ""))
        run_id, why = ci.check_run_workflow_run("556")
        self.assertEqual(run_id, "")
        self.assertIn("HTTP 404", why)

    def test_given_run_is_rerun_whole_without_sha_lookup(self):
        """`trigger_rerun(branch, run_id=…)` перезапускает именно этот прогон.

        Ловит мутацию: заданный `run_id` игнорируется и прогон ищется по
        sha (`find_run_id`) — в argv появится запрос `actions/runs?head_sha`,
        либо перезапуск идёт с `--failed`, которому в зависшем прогоне
        нечего перезапускать.
        """
        self.stand([], lambda *args: answer(0, "ok"))
        note = ci.trigger_rerun("task/x", run_id="9001")
        reruns = [a for a in self.calls if a[:2] == ("run", "rerun")]
        self.assertEqual(reruns, [("run", "rerun", "9001")])
        self.assertFalse([a for a in self.calls if "head_sha=" in " ".join(a)])
        self.assertTrue(ci.rerun_started(note), note)


class StuckRerunRefusalTest(unittest.TestCase):

    def test_unknown_workflow_run_is_named_refusal_without_rerun(self):
        """Прогон зависшей проверки не найден — именованный отказ.

        Ловит мутацию: при ненайденном прогоне `ci-rerun` откатывается к
        `trigger_rerun(branch)` без `run_id` — перезапустился бы
        «самый свежий прогон коммита», не тот, где висит проверка.
        """
        journal = []
        note = ("CI коммита 6cb9b55e: проверка зависла (порог 45 мин) — "
                "guard (check-run id 777, status=in_progress) висит 60 мин "
                "без исхода; перезапуск — ci-rerun")
        rerun = mock.Mock(return_value="ре-ран")
        with mock.patch.object(ci, "check_run_workflow_run",
                               lambda cid: ("", "gh не ответил: 502")), \
                mock.patch.object(ci, "trigger_rerun", rerun), \
                mock.patch.object(store, "journal",
                                  lambda *a: journal.append(a)):
            with self.assertRaises(SystemExit) as ctx:
                ci_rerun._stuck_rerun(None, "T001", "task/x", note)
        self.assertIn("777", str(ctx.exception))
        self.assertIn("502", str(ctx.exception))
        rerun.assert_not_called()
        self.assertEqual([a[3] for a in journal],
                         [ci_rerun.CI_RERUN_REFUSED_ACTION])


if __name__ == "__main__":
    unittest.main()
