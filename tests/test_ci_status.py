"""Тесты статуса CI ветки задачи (см. tasks/T017/SPEC.md, требование 6).

Здесь — разбор ответа `gh` и правило «зелёный / не зелёный»: какие
заключения проходят, какие нет и почему любое отсутствие ответа считается
запретом. Сам гейт merge (что при не-зелёном CI merge не выполняется)
кодирован инвариантом `test_invariants.MergeNeedsGreenCiTest`.

Ни git, ни `gh` не запускаются: обе команды подменены.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import ci, config  # noqa: E402

SHA = "0123456789abcdef0123456789abcdef01234567"


def run(name: str, status: str = "completed", conclusion: str = "success") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion}


class BranchStatusTest(unittest.TestCase):
    """Решение о зелёности: и по составу проверок, и по способности спросить."""

    def setUp(self):
        patcher = mock.patch.object(ci, "head_sha", lambda branch: (SHA, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def answer(self, stdout: str, returncode: int = 0) -> None:
        patcher = mock.patch.object(
            ci, "gh",
            lambda *a: subprocess.CompletedProcess(list(a), returncode,
                                                   stdout, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def status(self, runs: list) -> tuple[bool, str]:
        self.answer(json.dumps({"check_runs": runs}))
        return ci.branch_status("task/t001-x")

    def test_all_green_is_green(self):
        green, note = self.status([run("guard"), run("python")])

        self.assertTrue(green)
        self.assertIn(SHA[:8], note, "в журнале виден коммит, признанный годным")
        self.assertIn("2", note, "и число проверок")

    def test_skipped_and_neutral_are_green(self):
        """`protected-paths` на push пропускается — иначе зелёного не бывает."""
        for conclusion in ("skipped", "neutral"):
            with self.subTest(заключение=conclusion):
                green, _ = self.status(
                    [run("guard"), run("protected-paths", conclusion=conclusion)])

                self.assertTrue(green)

    def test_failed_conclusions_are_not_green(self):
        for conclusion in ("failure", "cancelled", "timed_out",
                           "action_required", "stale", None):
            with self.subTest(заключение=conclusion):
                green, note = self.status(
                    [run("guard"), run("python", conclusion=conclusion)])

                self.assertFalse(green)
                self.assertIn("python", note, "названа непрошедшая проверка")

    def test_unfinished_check_is_not_green(self):
        for status in ("queued", "in_progress", "waiting"):
            with self.subTest(состояние=status):
                green, note = self.status(
                    [run("guard", status=status, conclusion=None)])

                self.assertFalse(green)
                self.assertIn("ещё идёт", note)

    def test_no_checks_at_all_is_unknown_and_not_green(self):
        """Проверок нет — статус неизвестен; неизвестный не значит хороший."""
        green, note = self.status([])

        self.assertFalse(green)
        self.assertIn("неизвестен", note)

    def test_gh_that_does_not_answer_is_not_green(self):
        cases = {
            "gh не установлен или упал": ("", 1),
            "ответ не JSON": ("fatal: not a repository", 0),
            "в ответе нет check_runs": (json.dumps({"message": "Not Found"}), 0),
            "check_runs не список": (json.dumps({"check_runs": 42}), 0),
            "элемент списка не объект": (json.dumps({"check_runs": ["ok"]}), 0),
        }
        for name, (stdout, returncode) in cases.items():
            with self.subTest(случай=name):
                self.answer(stdout, returncode)

                green, note = ci.branch_status("task/t001-x")

                self.assertFalse(green)
                self.assertIn("неизвестен", note)

    def test_unknown_head_commit_is_not_green(self):
        """Нечего проверять — тоже отказ: sha ветки не определился."""
        with mock.patch.object(ci, "head_sha",
                               lambda branch: ("", "ветки нет")):
            green, note = ci.branch_status("task/t001-x")

        self.assertFalse(green)
        self.assertIn("неизвестен", note)
        self.assertIn("ветки нет", note)


class PaginationTest(unittest.TestCase):
    """Учитываются все проверки коммита, а не первая страница (SPEC T018).

    Подменённый `gh` разбирает `page=` собственного запроса и отдаёт
    заданные страницы — так же, как их отдаёт GitHub. Размер страницы
    подменяется вместе с ними: тесту нужны две страницы, а не 200 проверок.
    """

    def setUp(self):
        patcher = mock.patch.object(ci, "head_sha", lambda branch: (SHA, ""))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.requested: list[int] = []
        self._serve_patches: list = []
        self.addCleanup(self._stop_serve_patches)

    def _stop_serve_patches(self) -> None:
        """Останавливает патчи текущего `serve()` — вызывается и в начале
        следующего `serve()` (конец каждой итерации subTest), и в tearDown
        (требование 4, SPEC T034): без этого патчи предыдущих итераций
        `subTest` копятся до конца всего тестового метода, а не снимаются
        между вызовами `serve()` (ревью T018)."""
        while self._serve_patches:
            self._serve_patches.pop().stop()

    def serve(self, pages: list[list[dict]], total: int | None,
              per_page: int = 30, max_pages: int | None = None) -> None:
        self._stop_serve_patches()
        for name, value in (("CI_CHECKS_PER_PAGE", per_page),
                            ("CI_CHECKS_MAX_PAGES",
                             max_pages or config.CI_CHECKS_MAX_PAGES)):
            patcher = mock.patch.object(config, name, value)
            patcher.start()
            self._serve_patches.append(patcher)

        def fake_gh(*args):
            page = int(args[-1].rsplit("page=", 1)[1])
            self.requested.append(page)
            body = {"check_runs": pages[page - 1] if page <= len(pages) else []}
            if total is not None:
                body["total_count"] = total
            return subprocess.CompletedProcess(list(args), 0,
                                               json.dumps(body), "")

        patcher = mock.patch.object(ci, "gh", fake_gh)
        patcher.start()
        self._serve_patches.append(patcher)

    def status(self) -> tuple[bool, str]:
        return ci.branch_status("task/t001-x")

    def green_page(self, count: int, first: int = 0) -> list[dict]:
        return [run(f"check-{i}") for i in range(first, first + count)]

    def test_a_page_shorter_than_promised_is_unknown_and_not_green(self):
        """Критерий 1: 30 зелёных в теле, 31 обещана — статус неизвестен."""
        self.serve([self.green_page(30)], total=31, per_page=100)

        green, note = self.status()

        self.assertFalse(green, "неполный ответ прошёл за зелёный CI")
        self.assertIn("неизвестен", note)
        self.assertIn("31", note, "в журнале видно, сколько проверок обещано")

    def test_all_pages_are_read_before_the_verdict(self):
        """Критерий 2: 31 проверка двумя страницами, все зелёные — merge."""
        self.serve([self.green_page(30), self.green_page(1, first=30)],
                   total=31)

        green, note = self.status()

        self.assertTrue(green, note)
        self.assertIn("31", note, "учтены все проверки, а не первая страница")
        self.assertEqual(self.requested, [1, 2])

    def test_a_failure_on_the_second_page_is_seen(self):
        """Критерий 2: упавшая 31-я проверка видна и отказывает в merge."""
        self.serve([self.green_page(30),
                    [run("python", conclusion="failure")]], total=31)

        green, note = self.status()

        self.assertFalse(green)
        self.assertIn("python=failure", note)

    def test_an_unfinished_check_on_the_second_page_is_seen(self):
        """Идущая проверка со второй страницы — тоже не зелёный CI."""
        self.serve([self.green_page(30),
                    [run("python", status="in_progress", conclusion=None)]],
                   total=31)

        green, note = self.status()

        self.assertFalse(green)
        self.assertIn("ещё идёт", note)

    def test_an_exhausted_response_does_not_pass_for_a_complete_one(self):
        """Выдача оборвалась пустой страницей, не дойдя до обещанного числа."""
        self.serve([self.green_page(30), []], total=31)

        green, note = self.status()

        self.assertFalse(green)
        self.assertIn("неполон", note)

    def test_a_repeating_page_does_not_pass_for_the_missing_checks(self):
        """Одна и та же страница дважды — не 60 проверок из 31, а отказ."""
        page = self.green_page(30)
        self.serve([page, page], total=31)

        green, note = self.status()

        self.assertFalse(green, "повтор страницы сошёл за полный ответ")
        self.assertIn("неизвестен", note)

    def test_a_response_that_never_adds_up_stops_at_the_page_limit(self):
        """Потолок страниц — предел опроса, а не оценка: недосчитались — отказ."""
        self.serve([self.green_page(2, first=i * 2) for i in range(10)],
                   total=20, per_page=2, max_pages=3)

        green, note = self.status()

        self.assertFalse(green)
        self.assertIn("неизвестен", note)
        self.assertEqual(self.requested, [1, 2, 3], "опрос не бесконечен")

    def test_a_response_without_a_total_count_is_read_to_the_short_page(self):
        """Счётчика нет — полнота меряется длиной страницы (поведение до T018)."""
        self.serve([self.green_page(30), self.green_page(5, first=30)],
                   total=None)

        green, note = self.status()

        self.assertTrue(green, note)
        self.assertIn("35", note)

    def test_an_unreadable_total_count_is_unknown_and_not_green(self):
        for total in ("31", True, -1):
            with self.subTest(счётчик=total):
                self.serve([self.green_page(30)], total=total, per_page=100)

                green, note = self.status()

                self.assertFalse(green, "нечисловой счётчик сошёл за зелёный")
                self.assertIn("неизвестен", note)

    def test_the_page_size_is_asked_for_explicitly(self):
        """Размер страницы задаёт запрос, а не умолчание API (30 проверок)."""
        asked: list[tuple] = []

        def spy_gh(*args):
            asked.append(args)
            return subprocess.CompletedProcess(
                list(args), 0, json.dumps({"check_runs": [],
                                           "total_count": 0}), "")

        with mock.patch.object(ci, "gh", spy_gh):
            ci.check_runs(SHA)

        self.assertIn(f"per_page={config.CI_CHECKS_PER_PAGE}", asked[0][-1])
        self.assertIn("page=1", asked[0][-1])


class HeadShaTest(unittest.TestCase):
    """Sha головного коммита: спрашивается у git, пустой ответ — причина."""

    def test_sha_comes_from_git(self):
        with mock.patch.object(ci.gitcmd, "git", lambda *a:
                               subprocess.CompletedProcess(list(a), 0,
                                                           f"{SHA}\n", "")):
            self.assertEqual(ci.head_sha("task/t001-x"), (SHA, ""))

    def test_missing_branch_is_a_named_reason(self):
        with mock.patch.object(ci.gitcmd, "git", lambda *a:
                               subprocess.CompletedProcess(list(a), 128, "",
                                                           "fatal: no branch")):
            sha, why = ci.head_sha("task/t001-x")

        self.assertEqual(sha, "")
        self.assertIn("fatal: no branch", why)


class GhCallTest(unittest.TestCase):
    """Отсутствие `gh` — ненулевой код, а не исключение (как в gitcmd.git)."""

    def test_missing_cli_is_a_nonzero_result(self):
        with mock.patch.object(ci.subprocess, "run",
                               side_effect=FileNotFoundError("gh")):
            res = ci.gh("api", "repos")

        self.assertNotEqual(res.returncode, 0)
        self.assertIn("gh", res.stderr)

    def test_the_call_is_bounded_in_time(self):
        """Молчащая сеть не вешает гейт: у вызова есть предел ожидания."""
        with mock.patch.object(ci.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "{}", "")
            ci.gh("api", "repos")

        self.assertEqual(run_.call_args.kwargs.get("timeout"),
                         config.GH_TIMEOUT_SEC, "вызов `gh` без предела ожидания")

    def test_silent_gh_is_a_nonzero_result_and_so_not_green(self):
        """Истёкший предел — «статус неизвестен», то есть отказ merge."""
        with mock.patch.object(
                ci.subprocess, "run",
                side_effect=subprocess.TimeoutExpired(["gh"], 60)):
            res = ci.gh("api", "repos")

        self.assertNotEqual(res.returncode, 0)
        self.assertIn("молчал", res.stderr)
        with mock.patch.object(ci, "head_sha", lambda branch: (SHA, "")), \
                mock.patch.object(ci, "gh", lambda *a: res):
            green, note = ci.branch_status("task/t001-x")

        self.assertFalse(green)
        self.assertIn("неизвестен", note)


class FindRunIdTest(unittest.TestCase):
    """`find_run_id` — id workflow-прогона по sha, адрес для `gh run rerun`
    (SPEC T082, требование 7): check-run'ы, которые видит `branch_status`,
    его не несут — нужен отдельный опрос `actions/runs`.
    """

    def answer(self, stdout: str, returncode: int = 0) -> None:
        patcher = mock.patch.object(
            ci, "gh",
            lambda *a, **kw: subprocess.CompletedProcess(list(a), returncode,
                                                          stdout, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_run_id_parsed_from_the_first_workflow_run(self):
        self.answer(json.dumps({"workflow_runs": [{"databaseId": 4242}]}))

        run_id, why = ci.find_run_id(SHA)

        self.assertEqual(run_id, "4242")
        self.assertEqual(why, "")

    def test_no_workflow_runs_for_the_sha_is_not_found(self):
        self.answer(json.dumps({"workflow_runs": []}))

        run_id, why = ci.find_run_id(SHA)

        self.assertEqual(run_id, "")
        self.assertIn("нет", why)

    def test_gh_that_does_not_answer_is_not_found(self):
        self.answer("", returncode=1)

        run_id, why = ci.find_run_id(SHA)

        self.assertEqual(run_id, "")
        self.assertIn("не ответил", why)

    def test_unparseable_response_is_not_found(self):
        self.answer("not json")

        run_id, why = ci.find_run_id(SHA)

        self.assertEqual(run_id, "")
        self.assertIn("не разобран", why)

    def test_missing_numeric_id_is_not_found(self):
        self.answer(json.dumps({"workflow_runs": [{"name": "ci"}]}))

        run_id, why = ci.find_run_id(SHA)

        self.assertEqual(run_id, "")
        self.assertIn("id", why)


class TriggerRerunTest(unittest.TestCase):
    """`trigger_rerun` реально перезапускает CI (не читает тот же статус
    повторно, ревью T082 итерации 1, замечание blocker): триггер —
    `gh run rerun <id> --failed`, ожидание — `gh run watch <id>`.
    """

    def setUp(self):
        patcher = mock.patch.object(ci, "head_sha", lambda branch: (SHA, ""))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(
            ci, "find_run_id", lambda sha: ("4242", ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rerun_and_watch_are_both_called_for_the_found_run(self):
        calls: list[tuple] = []

        def fake_gh(*args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(ci, "gh", fake_gh):
            note = ci.trigger_rerun("task/t001-x")

        self.assertEqual(calls[0], ("run", "rerun", "4242", "--failed"))
        self.assertEqual(calls[1][:3], ("run", "watch", "4242"))
        self.assertIn("4242", note)

    def test_watch_waits_with_a_much_longer_timeout_than_a_rest_poll(self):
        seen_timeouts = []

        def fake_gh(*args, **kwargs):
            seen_timeouts.append(kwargs.get("timeout"))
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(ci, "gh", fake_gh):
            ci.trigger_rerun("task/t001-x")

        # rerun (без явного timeout) + watch (config.CI_RERUN_WAIT_SEC)
        self.assertEqual(seen_timeouts, [None, config.CI_RERUN_WAIT_SEC])

    def test_run_not_found_is_a_best_effort_no_crash(self):
        with mock.patch.object(ci, "find_run_id", lambda sha: ("", "нет прогонов")):
            note = ci.trigger_rerun("task/t001-x")

        self.assertIn("не запущен", note)

    def test_rerun_command_failure_is_a_best_effort_no_crash(self):
        with mock.patch.object(
                ci, "gh",
                lambda *a, **kw: subprocess.CompletedProcess(list(a), 1, "",
                                                              "boom")):
            note = ci.trigger_rerun("task/t001-x")

        self.assertIn("не запущен", note)
        self.assertIn("boom", note)

    def test_unknown_head_sha_is_a_best_effort_no_crash(self):
        with mock.patch.object(ci, "head_sha",
                               lambda branch: ("", "ветки нет")):
            note = ci.trigger_rerun("task/t001-x")

        self.assertIn("не запущен", note)
        self.assertIn("ветки нет", note)


if __name__ == "__main__":
    unittest.main()
