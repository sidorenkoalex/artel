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


class _HeadShaPatchedTest(unittest.TestCase):
    """`ci.head_sha` подменён фиксированным `SHA` — общий предок трёх
    классов ниже (SPEC 01M2DC6SQVSANMECXPDZJDP75D, R8: их `setUp` были
    байт-в-байт одинаковы; `SHA` — локальная константа этого файла,
    поэтому общий класс живёт здесь, не в tests/sandbox.py)."""

    def setUp(self):
        patcher = mock.patch.object(ci, "head_sha", lambda branch: (SHA, ""))
        patcher.start()
        self.addCleanup(patcher.stop)


class BranchStatusTest(_HeadShaPatchedTest):
    """Решение о зелёности: и по составу проверок, и по способности спросить."""

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


class VerifyingStatusTest(_HeadShaPatchedTest):
    """`ci.verifying_status` — четыре исхода `verifying` (SPEC T079,
    требование 5, AC-5..AC-8): собственная развилка функции, `check_runs`/
    `run_list` подменены — их отдельные правила разбора уже проверены
    выше/в `RunListTest`, здесь проверяется только то, как их результат
    сводится к одному из четырёх исходов."""

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


class CommitNotFoundInOriginTest(unittest.TestCase):
    """`ci._commit_not_found_in_origin` (SPEC
    01M1GS5HZ1JXFGKVR95HEW0AEZ, требование 4): сверка по подстроке "422",
    тем же приёмом, что `status_kind`/`verifying_is_red` уже применяют."""

    def test_detects_the_422_substring(self):
        self.assertTrue(ci._commit_not_found_in_origin(
            "gh не ответил: HTTP 422: No commit found for SHA: abc"))

    def test_other_failures_are_not_detected(self):
        self.assertFalse(ci._commit_not_found_in_origin(
            "gh не ответил: gh молчал дольше 10 с"))


class VerifyingStatus422Test(_HeadShaPatchedTest):
    """`ci.verifying_status` различает HTTP 422 («коммит не найден») от
    прочих сбоев опроса CI (SPEC 01M1GS5HZ1JXFGKVR95HEW0AEZ, требование 4,
    AC-6): вместо нейтрального «статус неизвестен» — именованная причина
    «голова не в origin» с подсказкой push, и без бесполезного фолбэка на
    `gh run list` (коммита на GitHub нет вовсе — прогон с ним не свяжется).
    """

    def set_check_runs(self, runs, why: str = "") -> None:
        patcher = mock.patch.object(ci, "check_runs", lambda sha: (runs, why))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_422_note_names_head_not_in_origin_with_a_push_hint(self):
        self.set_check_runs(
            None, "gh не ответил: HTTP 422: No commit found for SHA: "
            f"{SHA} (https://api.github.com/repos/x/y/commits/{SHA}/check-runs)")

        outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_NONE)
        lowered = note.lower()
        self.assertIn("голова", lowered)
        self.assertIn("origin", lowered)
        self.assertIn("push", lowered)
        self.assertIn("task/t001-x", note)

    def test_422_does_not_fall_back_to_run_list(self):
        self.set_check_runs(None, "gh не ответил: HTTP 422: No commit found")
        called = []
        patcher = mock.patch.object(
            ci, "run_list", lambda branch: called.append(branch) or ([], ""))
        patcher.start()
        self.addCleanup(patcher.stop)

        ci.verifying_status("task/t001-x")

        self.assertEqual(called, [], "gh run list не должен был спрашиваться")

    def test_non_422_failure_keeps_the_neutral_wording(self):
        self.set_check_runs(None, "gh не ответил: gh молчал дольше 10 с")
        patcher = mock.patch.object(ci, "run_list", lambda branch: ([], ""))
        patcher.start()
        self.addCleanup(patcher.stop)

        _outcome, note = ci.verifying_status("task/t001-x")

        self.assertNotIn("push", note.lower())

    def test_empty_check_runs_list_is_not_treated_as_422(self):
        """Пустой список без ошибки — легитимное «проверок нет», не 422:
        различение обязано смотреть на `runs is None`, не только на `why`."""
        self.set_check_runs([])
        patcher = mock.patch.object(ci, "run_list", lambda branch: ([], ""))
        patcher.start()
        self.addCleanup(patcher.stop)

        outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_NONE)
        self.assertNotIn("push", note.lower())


class VerifyingIsRedTest(unittest.TestCase):
    """`ci.verifying_is_red` (SPEC T086, требование 2): различает
    завершённый красный CI от прочих трёх исходов `verifying_status` по
    `note`, тем же приёмом, что `status_kind` для `note` `branch_status`
    (`StatusKindTest` выше) — без повторного опроса `gh`."""

    def test_red_note_is_red(self):
        self.assertTrue(ci.verifying_is_red(
            "CI коммита abc12345 не зелёный: python=failure"))

    def test_green_note_is_not_red(self):
        self.assertFalse(ci.verifying_is_red(
            "CI коммита abc12345 зелёный (2 проверок)"))

    def test_running_note_is_not_red(self):
        self.assertFalse(ci.verifying_is_red(
            "CI коммита abc12345 ещё идёт: python"))

    def test_none_notes_are_not_red(self):
        for note in (
                "статус CI неизвестен: ветки нет",
                "у коммита abc12345 нет ни одной проверки CI, и `gh run "
                "list` по ветке task/t001-x не показывает запусков — "
                "проверок нет вовсе"):
            with self.subTest(note=note):
                self.assertFalse(ci.verifying_is_red(note))


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

    def test_the_failed_run_is_picked_over_a_more_recent_green_one(self):
        """Ревью T082 итерации 2, замечание major 2: push- и pull_request-
        триггеры одного sha дают два прогона (открытый PR ветки задачи) —
        «самый свежий» слепо промахивался бы, если упавший прогон не он.
        """
        self.answer(json.dumps({"workflow_runs": [
            {"databaseId": 2, "status": "completed", "conclusion": "success"},
            {"databaseId": 1, "status": "completed", "conclusion": "failure"},
        ]}))

        run_id, why = ci.find_run_id(SHA)

        self.assertEqual(run_id, "1")
        self.assertEqual(why, "")

    def test_the_most_recent_failed_run_is_picked_among_several(self):
        self.answer(json.dumps({"workflow_runs": [
            {"databaseId": 3, "status": "completed", "conclusion": "success"},
            {"databaseId": 2, "status": "completed", "conclusion": "failure"},
            {"databaseId": 1, "status": "completed", "conclusion": "cancelled"},
        ]}))

        run_id, why = ci.find_run_id(SHA)

        self.assertEqual(run_id, "2")
        self.assertEqual(why, "")

    def test_falls_back_to_the_most_recent_run_when_none_is_failed(self):
        """Ни один завершённый прогон не пришёл не-зелёным (гонка API,
        неполный ответ) — деградация на прежнее поведение: ре-ран должен
        хоть на что-то нацелиться, не отказывать совсем."""
        self.answer(json.dumps({"workflow_runs": [
            {"databaseId": 2, "status": "completed", "conclusion": "success"},
            {"databaseId": 1, "status": "completed", "conclusion": "success"},
        ]}))

        run_id, why = ci.find_run_id(SHA)

        self.assertEqual(run_id, "2")
        self.assertEqual(why, "")


class StatusKindTest(unittest.TestCase):
    """Подтип не-зелёного `note` из `branch_status` (SPEC T082, ревью
    итерации 2, замечание major 1): триггерить ре-ран и журналировать
    «подтверждённый красный» имеет смысл только для реально красного
    статуса, не для «ещё идёт»/«неизвестен» — там нечего подтверждать.
    """

    def test_still_running_is_not_red(self):
        self.assertEqual(
            ci.status_kind("CI коммита abc12345 ещё идёт: guard"), "running")

    def test_unknown_status_is_not_red(self):
        for note in ("статус CI неизвестен: ветки нет",
                     "статус CI коммита abc12345 неизвестен: gh не ответил",
                     "у коммита abc12345 нет ни одной проверки CI — "
                     "статус неизвестен"):
            with self.subTest(note=note):
                self.assertEqual(ci.status_kind(note), "unknown")

    def test_failed_conclusion_is_red(self):
        self.assertEqual(
            ci.status_kind("CI коммита abc12345 не зелёный: python=failure"),
            "red")


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


class RerunStartedTest(unittest.TestCase):
    """`ci.rerun_started` (SPEC 01M3F7C2DVYCEANQ8CF1FCSD87, требование 8):
    отличает «повтор не запущен вовсе» от «повтор запущен, дальше ожидание»
    по `note`, которую сама `trigger_rerun` и вернула — тем же приёмом, что
    `verifying_is_red`/`status_kind` (`VerifyingIsRedTest`/`StatusKindTest`
    выше)."""

    def test_started_note_of_trigger_rerun_reads_as_started(self):
        """Успешный `note` `trigger_rerun` — «повтор запущен».

        Ловит мутацию: признак записан как наличие подстроки «запущен»
        вместо отсутствия «не запущен» — тогда `ре-ран … не запущен: …`
        (подстрока «запущен» в нём ЕСТЬ) тоже читался бы как состоявшийся
        повтор, и сбой `gh` уходил бы в журнал успехом.
        """
        self.assertTrue(ci.rerun_started(
            "ре-ран прогона 4242 запущен, ожидание завершения: "
            "gh run watch завершился"))

    def test_both_refusal_notes_of_trigger_rerun_read_as_not_started(self):
        """Оба пути отказа `trigger_rerun` — «повтор не запущен».

        Ловит мутацию: признак сверяется только с одной из двух форм
        отказа (например только с «ре-ран прогона … не запущен») — тогда
        отказ без найденного sha/прогона («ре-ран CI не запущен: …»)
        читался бы как состоявшийся повтор.
        """
        for note in ("ре-ран CI не запущен: ветки нет",
                     "ре-ран прогона 4242 не запущен: boom"):
            with self.subTest(note=note):
                self.assertFalse(ci.rerun_started(note))


class RedStatusShaTest(unittest.TestCase):
    """`ci.red_status_sha` (SPEC 01M3F7C2DVYCEANQ8CF1FCSD87, требование 4):
    достаёт короткий sha коммита из `note` красного исхода
    `verifying_status` — парная к `verifying_is_red`."""

    def test_sha_comes_from_the_note_verifying_status_itself_writes(self):
        """Sha берётся из настоящей `note` `verifying_status`, не из
        рукописного образца.

        Ловит мутацию: регулярка разошлась с текстом, который
        `verifying_status` реально кладёт в `note` (другой падеж, другое
        слово, sha не в первой позиции) — сверка головы ветки требования 4
        перестала бы находить sha и отказывала бы всегда.
        """
        with mock.patch.object(ci, "head_sha", lambda branch: (SHA, "")), \
             mock.patch.object(
                 ci, "gh",
                 lambda *a, **kw: subprocess.CompletedProcess(
                     list(a), 0,
                     json.dumps({"total_count": 1, "check_runs": [
                         run("python", conclusion="failure")]}), "")):
            outcome, note = ci.verifying_status("task/t001-x")

        self.assertEqual(outcome, ci.VERIFYING_RED)
        self.assertEqual(ci.red_status_sha(note), SHA[:8])

    def test_non_red_notes_have_no_sha(self):
        """Не-красный `note` sha не отдаёт вовсе.

        Ловит мутацию: sha ищется любой шестнадцатеричной подстрокой, без
        привязки к «не зелёный» — тогда зелёный/идущий `note` тоже отдавал
        бы sha, и сверка требования 4 «проходила» бы на записи журнала,
        которая красноту не подтверждает.
        """
        for note in (f"CI коммита {SHA[:8]} зелёный (2 проверок)",
                     f"CI коммита {SHA[:8]} ещё идёт: python",
                     "статус CI неизвестен: ветки нет"):
            with self.subTest(note=note):
                self.assertEqual(ci.red_status_sha(note), "")


class FailedCheckNamesTest(_HeadShaPatchedTest):
    """`ci.failed_check_names` (SPEC 01M3F7C2DVYCEANQ8CF1FCSD87,
    требование 5): имена завершённых не-зелёных check-run'ов коммита —
    единственный общий язык двух РАЗНЫХ коммитов (головы ветки задачи и
    вершины главной ветки)."""

    def answer(self, stdout: str, returncode: int = 0) -> None:
        patcher = mock.patch.object(
            ci, "gh",
            lambda *a, **kw: subprocess.CompletedProcess(list(a), returncode,
                                                         stdout, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def names(self, runs: list, returncode: int = 0) -> tuple:
        self.answer(json.dumps({"total_count": len(runs), "check_runs": runs}),
                    returncode)
        return ci.failed_check_names(SHA)

    def test_only_completed_non_green_names_are_collected(self):
        """Собираются имена только завершённых и только не-зелёных.

        Ловит мутацию: фильтр `status == "completed"` убран — тогда
        незавершённое задание вершины главной ветки попадало бы в
        «упавшие», и совпадение имён отказывало бы повтору при живом,
        ещё идущем CI главной ветки.
        """
        names, why = self.names([
            run("guard"),                                   # зелёное
            run("skipped-job", conclusion="skipped"),        # зелёное
            run("python", conclusion="failure"),             # упало
            run("map", conclusion="timed_out"),              # упало
            run("idet", status="in_progress", conclusion=None),  # не завершено
        ])

        self.assertEqual(names, {"python", "map"})
        self.assertEqual(why, "")

    def test_all_green_gives_an_empty_set_not_none(self):
        """Все проверки зелёные — пустое множество, а не «неизвестно».

        Ловит мутацию: пустой результат сворачивается в `None` («статус
        неизвестен») — тогда зелёная вершина главной ветки отказывала бы
        повтору, и команда не сработала бы ни разу.
        """
        names, why = self.names([run("guard"), run("python")])

        self.assertEqual(names, set())
        self.assertEqual(why, "")

    def test_no_checks_at_all_is_unknown_with_a_named_reason(self):
        """Ни одной проверки — «статус неизвестен», не пустое множество.

        Ловит мутацию: коммит без check-run'ов отдаёт пустое множество —
        тогда пересечение с ним пусто ВСЕГДА, и повтор шёл бы поверх
        главной ветки, чей статус никто не подтвердил (инвариант 19).
        """
        names, why = self.names([])

        self.assertIsNone(names)
        self.assertIn(SHA[:8], why)
        self.assertIn("неизвестен", why)

    def test_unanswered_gh_is_unknown_with_the_reason_inside(self):
        """`gh` не ответил — «неизвестно» и причина внутри.

        Ловит мутацию: сбой `gh` проглатывается в пустое множество —
        первый же сетевой сбой превращал бы команду в слепой перезапуск,
        маскирующий дефект главной ветки.
        """
        names, why = self.names([], returncode=1)

        self.assertIsNone(names)
        self.assertIn(SHA[:8], why)


if __name__ == "__main__":
    unittest.main()
