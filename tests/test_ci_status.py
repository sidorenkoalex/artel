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


class RunListTest(unittest.TestCase):
    """`ci.run_list` — второй источник статуса CI в `verifying` (SPEC T079,
    требование 5): запуски `gh run list` по ветке, второй сигнал против
    check-runs коммита при задержке события GitHub (роадмап P3, T040)."""

    def answer(self, stdout: str, returncode: int = 0) -> None:
        patcher = mock.patch.object(
            ci, "gh",
            lambda *a: subprocess.CompletedProcess(list(a), returncode,
                                                   stdout, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_runs_come_back_as_a_list(self):
        self.answer(json.dumps([{"headBranch": "task/t001-x",
                                 "status": "in_progress"}]))

        runs, why = ci.run_list("task/t001-x")

        self.assertEqual(runs, [{"headBranch": "task/t001-x",
                                 "status": "in_progress"}])
        self.assertEqual(why, "")

    def test_no_runs_is_an_empty_list_not_none(self):
        self.answer(json.dumps([]))

        runs, why = ci.run_list("task/t001-x")

        self.assertEqual(runs, [])
        self.assertEqual(why, "")

    def test_gh_that_does_not_answer_is_none(self):
        self.answer("", 1)

        runs, why = ci.run_list("task/t001-x")

        self.assertIsNone(runs)
        self.assertIn("не ответил", why)

    def test_unparsable_json_is_none(self):
        self.answer("not json")

        runs, why = ci.run_list("task/t001-x")

        self.assertIsNone(runs)
        self.assertIn("не разобран", why)

    def test_non_list_payload_is_none(self):
        self.answer(json.dumps({"message": "not found"}))

        runs, why = ci.run_list("task/t001-x")

        self.assertIsNone(runs)
        self.assertIn("нет списка", why)

    def test_asks_for_the_branch_and_a_bounded_limit(self):
        asked: list[tuple] = []

        def spy_gh(*args):
            asked.append(args)
            return subprocess.CompletedProcess(list(args), 0, "[]", "")

        with mock.patch.object(ci, "gh", spy_gh):
            ci.run_list("task/t001-x")

        self.assertIn("run", asked[0])
        self.assertIn("list", asked[0])
        self.assertIn("task/t001-x", asked[0])
        self.assertIn(str(config.CI_RUN_LIST_LIMIT), asked[0])


class VerifyingStatusTest(unittest.TestCase):
    """`ci.verifying_status` — четыре исхода `verifying` (SPEC T079,
    требование 5, AC-5..AC-8): собственная развилка функции, `check_runs`/
    `run_list` подменены — их отдельные правила разбора уже проверены
    выше/в `RunListTest`, здесь проверяется только то, как их результат
    сводится к одному из четырёх исходов."""

    def setUp(self):
        patcher = mock.patch.object(ci, "head_sha", lambda branch: (SHA, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_check_runs(self, runs, why: str = "") -> None:
        patcher = mock.patch.object(ci, "check_runs", lambda sha: (runs, why))
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_run_list(self, runs, why: str = "") -> None:
        patcher = mock.patch.object(ci, "run_list", lambda branch: (runs, why))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_all_green_and_completed_is_green(self):
        self.set_check_runs([run("guard"), run("python")])

        outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_GREEN)
        self.assertIn(SHA[:8], note)

    def test_a_red_conclusion_is_red_not_running_or_none(self):
        self.set_check_runs([run("guard"),
                             run("python", conclusion="failure")])

        outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_RED)
        self.assertIn("python=failure", note)

    def test_an_unfinished_check_run_is_running(self):
        self.set_check_runs([run("python", status="in_progress",
                                 conclusion=None)])

        outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_RUNNING)
        self.assertIn("python", note)

    def test_no_check_runs_and_no_run_list_is_none_at_all(self):
        """AC-6: check-runs пусты И `gh run list` тоже ничего не видит."""
        self.set_check_runs([])
        self.set_run_list([])

        outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_NONE)
        self.assertIn("проверок нет вовсе", note)

    def test_no_check_runs_but_gh_run_list_sees_a_run_is_running(self):
        """AC-7: check-runs пусты, но `gh run list` видит запуск по ветке —
        трактуется как «проверки идут», источник назван в журнале."""
        self.set_check_runs([])
        self.set_run_list([{"headBranch": "task/t001-x",
                            "status": "in_progress"}])

        outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_RUNNING)
        self.assertIn("gh run list", note)

    def test_unknown_check_runs_status_falls_back_to_run_list_too(self):
        """`check_runs` вернул (None, why) — тоже «пусто» для этой развилки
        (неизвестный статус не отличим от отсутствия проверок здесь)."""
        self.set_check_runs(None, "gh не ответил")
        self.set_run_list([{"headBranch": "task/t001-x"}])

        outcome, _ = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_RUNNING)

    def test_run_list_that_does_not_answer_still_reports_none(self):
        self.set_check_runs([])
        self.set_run_list(None, "gh run list не ответил")

        outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_NONE)
        self.assertIn("проверок нет вовсе", note)

    def test_unknown_head_commit_is_none(self):
        with mock.patch.object(ci, "head_sha",
                               lambda branch: ("", "ветки нет")):
            outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_NONE)
        self.assertIn("ветки нет", note)

    def test_never_calls_run_list_when_check_runs_already_answered(self):
        """Требование 5, AC-12: не должно быть лишних вызовов, если ответ
        по check-runs коммита уже есть (зелёный/красный/идёт)."""
        self.set_check_runs([run("guard")])
        called = []
        patcher = mock.patch.object(
            ci, "run_list", lambda branch: called.append(branch) or ([], ""))
        patcher.start()
        self.addCleanup(patcher.stop)

        ci.verifying_status("task/t001-x")

        self.assertEqual(called, [], "run_list вызван, хотя check_runs уже ответил")


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


if __name__ == "__main__":
    unittest.main()
