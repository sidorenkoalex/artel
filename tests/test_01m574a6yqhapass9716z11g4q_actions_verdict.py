"""Статус CI внешнего проекта по запускам GitHub Actions, когда check-runs коммита отказаны токену проекта.

Группа: долгоживущий

Красен до реализации: при HTTP 403 «Resource not accessible …» на check-runs `ci.verifying_status` уходит в «проверки идут/проверок нет» по `gh run list`, `branch_status` и `failed_check_names` — в «статус неизвестен», запусков Actions никто не читает — красны AC-1, AC-2, AC-3, AC-5 (первый вход), AC-7 и AC-8 (зелёного, красного, имён заданий и строки причины нет); AC-4, AC-5 (второй вход), AC-6, AC-9 и AC-10 держат исходы, которые код даёт и сегодня (не зелёный, «неизвестен», прежние тексты), и зелёны.

Сценарий: песочница `SchemaConnTmpRootTest`, в `config.TARGETS` — запись
артели и учебного внешнего проекта, его клон — `make_project_repo`. Голова
ветки задачи — подмена публичного `ci.head_sha`. Вызовы `gh` перехватывает
подмена `subprocess.run` (argv[0] — `gh`), git идёт мимо неё
(`network_guarded_real_run`). Поддельный GitHub (`FakeGitHub`) отвечает так
же, как `gh api` без `--jq`: JSON тела REST-ответа на адреса
`commits/<sha>/check-runs`, `actions/runs?head_sha=<sha>` (с отбором
`event`/`branch`/`status` и страницами `per_page`/`page`) и
`actions/runs/<id>/jobs`, а на `gh run list` — список запусков по ветке.
HTTP-отказ — ненулевой код, тело ошибки в stdout и строка
`gh: <сообщение> (HTTP <код>)` в stderr, как у настоящего `gh`.

Имя проекта, ветка, sha, имена заданий и запусков, состав запусков и выбор
текста 403 — из `random`; зерно печатается и входит в текст провала.
"""
import json
import os
import random
import re
import string
import subprocess
import urllib.parse
from unittest import mock

from orchestrator import ci, config, fsm, store
from tests.sandbox import (SchemaConnTmpRootTest, capture, make_project_repo,
                           network_guarded_real_run, seed_artel_targets)

NOT_ACCESSIBLE = ("Resource not accessible by personal access token",
                  "Resource not accessible by integration")
REASON = "check-runs недоступны токену проекта (403) — итог по Actions runs"
PROJECT_NAMES = ("sled", "sani", "drovni", "rozvalni", "kibitka")
JOB_WORDS = ("тесты", "линтер", "сборка", "типы", "доки", "смоук")
FLOW_WORDS = ("CI", "Проверки", "Сборка", "Конвейер")
HEX = "0123456789abcdef"
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

NETWORK = (1, "", "error connecting to api.github.com\n"
                  "check your internet connection or "
                  "https://localhost/status\n")
TIMEOUT = "timeout"
UNPARSED = (0, "<html><body>502 прокси</body></html>", "")


def ok(payload) -> tuple:
    return 0, json.dumps(payload), ""


def http_error(code: int, message: str) -> tuple:
    body = json.dumps({"message": message, "status": str(code),
                       "documentation_url": "https://localhost/docs/rest"})
    return 1, body, f"gh: {message} (HTTP {code})\n"


def forbidden(text: str) -> tuple:
    return http_error(403, text)


def gh_request(argv: list) -> tuple[str, dict]:
    """(путь REST-адреса, параметры запроса) вызова `gh api`; ("", {}) — не
    `gh api`. Параметры — из строки запроса адреса и из `-f`/`-F`."""
    args = argv[1:]
    if args[:1] != ["api"]:
        return "", {}
    endpoint, params, i = None, {}, 1
    with_value = {"-X", "--method", "-H", "--header", "-q", "--jq", "-t",
                  "--template", "--input", "--cache", "-p", "--preview",
                  "--hostname"}
    while i < len(args):
        arg = args[i]
        if arg in ("-f", "-F", "--field", "--raw-field") and i + 1 < len(args):
            key, _, value = args[i + 1].partition("=")
            params[key] = value
            i += 2
            continue
        if arg in with_value:
            i += 2
            continue
        if not arg.startswith("-") and endpoint is None:
            endpoint = arg
        i += 1
    path, _, query = (endpoint or "").partition("?")
    params.update(urllib.parse.parse_qsl(query))
    return path, params


class FakeGitHub:
    """Поддельный GitHub за подменой `subprocess.run`: отвечает на вызовы
    `gh`, прочее (git) передаёт настоящему `subprocess.run`.

    Ответ — кортеж (код, stdout, stderr) либо `TIMEOUT` (вызов поднимает
    `subprocess.TimeoutExpired`, как молчащая сеть)."""

    def __init__(self, default_check_runs):
        self.calls: list[list[str]] = []
        self.default_check_runs = default_check_runs
        self.check_runs: dict = {}
        self.runs: dict = {}
        self.runs_answer: dict = {}
        self.runs_extra: dict = {}
        self.jobs: dict = {}
        self.jobs_answer: dict = {}
        self.jobs_extra: dict = {}
        self.run_list: list = []

    def __call__(self, cmd, *args, **kwargs):
        if not cmd or os.path.basename(str(cmd[0])) != "gh":
            return network_guarded_real_run(cmd, *args, **kwargs)
        argv = [str(a) for a in cmd]
        self.calls.append(argv)
        answer = self.answer(argv)
        if answer == TIMEOUT:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout") or 1)
        code, out, err = answer
        return subprocess.CompletedProcess(cmd, code, out, err)

    def actions_head_sha_calls(self) -> list:
        return [c for c in self.calls
                if "actions/runs" in " ".join(c) and "head_sha" in " ".join(c)]

    @staticmethod
    def page(items: list, params: dict, extra: int, key: str) -> tuple:
        per_page = int(params.get("per_page") or 30)
        page = int(params.get("page") or 1)
        chunk = items[(page - 1) * per_page: page * per_page]
        return ok({"total_count": len(items) + extra, key: chunk})

    def answer(self, argv: list) -> tuple:
        if argv[1:3] == ["run", "list"]:
            return ok(self.run_list)
        path, params = gh_request(argv)
        match = re.search(r"commits/([^/]+)/check-runs$", path)
        if match:
            return self.check_runs.get(match.group(1), self.default_check_runs)
        match = re.search(r"actions/runs/(\d+)(?:/attempts/\d+)?/jobs$", path)
        if match:
            run_id = int(match.group(1))
            if run_id in self.jobs_answer:
                return self.jobs_answer[run_id]
            return self.page(self.jobs.get(run_id, []), params,
                             self.jobs_extra.get(run_id, 0), "jobs")
        if re.search(r"actions/runs$", path):
            sha = params.get("head_sha", "")
            if sha in self.runs_answer:
                return self.runs_answer[sha]
            runs = [r for r in self.runs.get(sha, [])
                    if params.get("event") in (None, r["event"])
                    and params.get("branch") in (None, r["head_branch"])
                    and params.get("status") in (None, r["status"],
                                                 r["conclusion"])]
            return self.page(runs, params, self.runs_extra.get(sha, 0),
                             "workflow_runs")
        return http_error(404, "Not Found")


class ActionsSandbox(SchemaConnTmpRootTest):
    """Учебный внешний проект; check-runs коммитов отвечают 403 «Resource
    not accessible …» (текст — из `random`), запуски Actions задаёт тест."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        seed_artel_targets()
        self.project = (self.rng.choice(PROJECT_NAMES)
                        + str(self.rng.randrange(10, 100)))
        self.clone = make_project_repo(self.project, origin=False)
        self.base = config.MAIN_BRANCH
        self.branch = (f"task/{self.ulid().lower()}-"
                       f"{self.rng.choice(PROJECT_NAMES)}")
        self.sha = self.hex40()
        self.main_sha = self.hex40()
        self.forbidden_text = self.rng.choice(NOT_ACCESSIBLE)
        self.next_id = self.rng.randrange(10 ** 6, 10 ** 7)
        self.used_names: set = set()
        self.reset_github()
        patcher = mock.patch.object(subprocess, "run", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(ci, "head_sha",
                                    lambda branch, repo=None: (self.sha, ""))
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake(self, cmd, *args, **kwargs):
        return self.gh(cmd, *args, **kwargs)

    def reset_github(self, text: str | None = None) -> FakeGitHub:
        self.gh = FakeGitHub(forbidden(text or self.forbidden_text))
        return self.gh

    # --- случайные входы -------------------------------------------------

    def hex40(self) -> str:
        return "".join(self.rng.choice(HEX) for _ in range(40))

    def ulid(self) -> str:
        return "01" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(24))

    def fresh_name(self, words) -> str:
        while True:
            name = f"{self.rng.choice(words)}-{self.rng.randrange(100, 1000)}"
            if name not in self.used_names:
                self.used_names.add(name)
                return name

    def why(self, text: str) -> str:
        return (f"{text} (зерно {self.seed}, проект {self.project}, ветка "
                f"{self.branch}, sha {self.sha[:8]}, вызовы gh: "
                f"{self.gh.calls})")

    # --- запуски Actions -------------------------------------------------

    def add_run(self, event: str, *, sha: str | None = None,
                status: str = "completed", conclusion: str | None = "success",
                head_branch: str | None = None, jobs=None,
                job_conclusion: str | None = None) -> dict:
        """Запуск коммита `sha` (по умолчанию — головы ветки задачи) с
        заданиями: `jobs` — список (имя, статус, заключение); по умолчанию
        одно–три задания со статусом и заключением запуска
        (`job_conclusion`, если задан)."""
        sha = sha or self.sha
        run_id = self.next_id
        self.next_id += self.rng.randrange(1, 50)
        name = self.fresh_name(FLOW_WORDS)
        if head_branch is None:
            head_branch = self.branch if sha == self.sha else self.base
        run = {
            "id": run_id, "name": name, "display_title": name,
            "event": event, "status": status, "conclusion": conclusion,
            "head_branch": head_branch, "head_sha": sha, "run_attempt": 1,
            "check_suite_id": run_id + 7,
            "html_url": f"https://localhost/artel-tests/{self.project}"
                        f"/actions/runs/{run_id}",
            "jobs_url": f"https://localhost/api/v3/repos/artel-tests/"
                        f"{self.project}/actions/runs/{run_id}/jobs",
            "created_at": "2026-10-18T09:00:00Z",
            "updated_at": "2026-10-18T09:05:00Z",
        }
        if jobs is None:
            jc = job_conclusion if job_conclusion is not None else conclusion
            jobs = [(self.fresh_name(JOB_WORDS), status, jc)
                    for _ in range(self.rng.randint(1, 3))]
        self.gh.jobs[run_id] = [
            {"id": run_id * 10 + i, "run_id": run_id, "name": jname,
             "status": jstatus, "conclusion": jconclusion,
             "started_at": "2026-10-18T09:00:10Z",
             "completed_at": ("2026-10-18T09:04:00Z"
                              if jstatus == "completed" else None),
             "html_url": f"https://localhost/artel-tests/{self.project}"
                         f"/actions/runs/{run_id}/job/{run_id * 10 + i}"}
            for i, (jname, jstatus, jconclusion) in enumerate(jobs)]
        self.gh.runs.setdefault(sha, []).append(run)
        return run

    def job_names(self, run: dict) -> list:
        return [j["name"] for j in self.gh.jobs[run["id"]]]

    def green_branch_runs(self) -> list:
        """Завершённые зелёные запуски ветки задачи: хотя бы один
        `pull_request` и ноль–два прочих событий."""
        runs = [self.add_run("pull_request",
                             conclusion=self.rng.choice(sorted(ci.GREEN - {"skipped"})))]
        for _ in range(self.rng.randint(0, 2)):
            runs.append(self.add_run(
                self.rng.choice(("push", "workflow_dispatch", "pull_request")),
                conclusion=self.rng.choice(sorted(ci.GREEN))))
        self.rng.shuffle(self.gh.runs[self.sha])
        return runs

    def red_run(self, event: str, sha: str | None = None) -> tuple[dict, str]:
        """Завершённый красный запуск: одно задание `failure`, остальные
        зелёные. Возвращает (запуск, имя красного задания)."""
        red_name = self.fresh_name(JOB_WORDS)
        jobs = [(self.fresh_name(JOB_WORDS), "completed", "success")
                for _ in range(self.rng.randint(0, 2))]
        jobs.insert(self.rng.randint(0, len(jobs)),
                    (red_name, "completed", "failure"))
        run = self.add_run(event, sha=sha, conclusion="failure", jobs=jobs)
        return run, red_name

    def running_run(self, event: str = "pull_request") -> dict:
        status = self.rng.choice(("in_progress", "queued"))
        return self.add_run(event, status=status, conclusion=None,
                            jobs=[(self.fresh_name(JOB_WORDS), status, None)])

    def refusals(self) -> list:
        """Отказы чтения check-runs, не подпадающие под переход на Actions
        (требование 4): сеть, таймаут, 401, 404, 5xx, 403 лимита запросов,
        неразобранный ответ."""
        five = self.rng.choice((500, 502, 503, 504))
        return [("сеть", NETWORK), ("таймаут", TIMEOUT),
                ("401", http_error(401, "Bad credentials")),
                ("404", http_error(404, "Not Found")),
                (str(five), http_error(five, "Server Error")),
                ("403 rate limit", http_error(
                    403, f"API rate limit exceeded for user ID "
                         f"{self.rng.randrange(10 ** 5, 10 ** 7)}.")),
                ("неразобранный", UNPARSED)]

    def run_list_entry(self) -> dict:
        return {"headBranch": self.branch, "status": "in_progress",
                "conclusion": ""}

    # --- чтение статуса --------------------------------------------------

    def verifying(self) -> tuple[str, str]:
        return ci.verifying_status(self.branch, repo=self.clone)

    def branch_verdict(self) -> tuple[bool, str]:
        return ci.branch_status(self.branch, repo=self.clone)

    def failed(self, sha: str | None = None):
        return ci.failed_check_names(sha or self.sha, repo=self.clone)

    def assert_reason_line(self, note: str, where: str) -> None:
        lines = note.splitlines()
        self.assertTrue(lines, self.why(f"{where}: note пуст"))
        self.assertNotIn(REASON, lines[0], self.why(
            f"{where}: строка причины перехода на Actions — первая строка "
            f"note:\n{note}"))
        self.assertTrue(any(REASON in line for line in lines[1:]), self.why(
            f"{where}: в note нет строки «{REASON}» (не первой):\n{note}"))

    def assert_red(self, name: str, where: str) -> None:
        """Красный исход на всех трёх входах, `name` — среди упавших."""
        outcome, note = self.verifying()
        self.assertEqual(outcome, ci.VERIFYING_RED, self.why(
            f"{where}: verifying_status не красный:\n{note}"))
        self.assertIn(name, note, self.why(
            f"{where}: note verifying_status не называет {name}:\n{note}"))
        self.assertTrue(ci.verifying_is_red(note), self.why(
            f"{where}: verifying_is_red ложно:\n{note}"))
        self.assertEqual(ci.red_status_sha(note), self.sha[:8], self.why(
            f"{where}: red_status_sha не даёт sha головы:\n{note}"))
        green, bnote = self.branch_verdict()
        self.assertFalse(green, self.why(f"{where}: branch_status зелёный"))
        self.assertEqual(ci.status_kind(bnote), "red", self.why(
            f"{where}: status_kind не red:\n{bnote}"))
        names, why = self.failed()
        self.assertIsNotNone(names, self.why(
            f"{where}: failed_check_names вернул None: {why}"))
        self.assertIn(name, names, self.why(
            f"{where}: failed_check_names без {name}: {names}"))

    # --- FSM -------------------------------------------------------------

    def external_task_in_verifying(self) -> str:
        task_id = self.ulid()
        store.insert_task(self.conn, task_id, "Задача проекта", "verifying",
                          self.branch, self.project, 25.0)
        return task_id

    def advance(self, task_id: str) -> str:
        def body():
            try:
                fsm.cmd_advance(task_id)
            except SystemExit as exc:
                print(f"\nSystemExit: {exc}")
        return capture(body)

    def last_verifying_note(self, task_id: str) -> str | None:
        notes = [r["detail"] for r in store.task_steps(store.db(), task_id)
                 if r["action"] == fsm.VERIFYING_STATUS_ACTION]
        return notes[-1] if notes else None


class GreenTest(ActionsSandbox):

    def test_ac1_green_actions_runs_give_green_and_leave_verifying(self):
        """Все запуски ветки задачи (среди них `pull_request`) зелёные: оба читателя статуса — зелёный, задача уходит из `verifying`.

        check-runs головы — 403 «Resource not accessible …»; запуски
        Actions коммита — один–три завершённых зелёных, хотя бы один
        события `pull_request`. `verifying_status` даёт `VERIFYING_GREEN`,
        `branch_status` — `True`; задача внешнего проекта в `verifying`
        после одного `fsm.cmd_advance` — в `review`.

        Ловит мутацию: переход на Actions встроен только в
        `verifying_status` (или только в `branch_status`) — второй
        читатель отдаёт «статус неизвестен», не `True`; либо 403 по-прежнему
        уходит в `_no_checks_by_branch` — задача остаётся в `verifying`.
        """
        self.green_branch_runs()
        outcome, note = self.verifying()
        self.assertEqual(outcome, ci.VERIFYING_GREEN, self.why(
            f"verifying_status не зелёный:\n{note}"))
        green, bnote = self.branch_verdict()
        self.assertTrue(green, self.why(f"branch_status не зелёный:\n{bnote}"))
        task_id = self.external_task_in_verifying()
        out = self.advance(task_id)
        state = store.get_task(store.db(), task_id)["state"]
        self.assertEqual(state, "review", self.why(
            f"задача не вышла из verifying (состояние {state}):\n{out}"))


class RedTest(ActionsSandbox):

    def test_ac2_red_run_names_failed_job_on_all_readers(self):
        """Красный запуск ветки задачи — красный исход с именем упавшего задания у всех трёх читателей.

        Три варианта (`subTest`): красный `pull_request` среди зелёных;
        красный `push` при зелёном `pull_request`; красный запуск рядом с
        идущим. В каждом: `VERIFYING_RED`, имя красного задания в `note`,
        `verifying_is_red` истинно, `red_status_sha` — 8 знаков sha головы;
        `branch_status` — `False`, `status_kind` — "red";
        `failed_check_names` содержит имя задания.

        Ловит мутацию: учитываются только запуски `pull_request` (красный
        `push` даёт зелёный), идущий запуск выигрывает у красного (исход
        «проверки идут», `status_kind` — running), в `note` попадает имя
        запуска вместо имени задания, либо красный текст без «CI коммита
        <sha> не зелёный:» — `verifying_is_red`/`red_status_sha` его не
        узнают.
        """
        def pr_red_among_green():
            self.add_run("pull_request")
            for _ in range(self.rng.randint(0, 2)):
                self.add_run(self.rng.choice(("push", "pull_request")))
            return self.red_run("pull_request")[1]

        def push_red_pr_green():
            self.add_run("pull_request")
            return self.red_run("push")[1]

        def red_beside_running():
            self.running_run(self.rng.choice(("pull_request", "push")))
            return self.red_run(self.rng.choice(("pull_request", "push")))[1]

        for label, build in (("красный pull_request", pr_red_among_green),
                             ("красный push, зелёный pull_request",
                              push_red_pr_green),
                             ("красный рядом с идущим", red_beside_running)):
            with self.subTest(вариант=label):
                self.reset_github()
                name = build()
                self.rng.shuffle(self.gh.runs[self.sha])
                self.assert_red(name, label)


class RunningAndRedWithoutJobsTest(ActionsSandbox):

    def test_ac3_running_run_and_red_run_without_red_jobs(self):
        """Идущий запуск без красных — «проверки идут»; красный запуск без красных заданий — красный с именем запуска.

        Идущий: запуск `pull_request` в `in_progress`/`queued` и,
        возможно, зелёные завершённые рядом — `VERIFYING_RUNNING`,
        `verifying_is_red` ложно, `branch_status` — `False` со
        `status_kind` "running". Красный без красных заданий (`subTest`):
        заданий нет и заключение `failure`; заключение `startup_failure` —
        `VERIFYING_RED` с именем запуска в `note`, `failed_check_names`
        содержит имя запуска (не пустое множество).

        Ловит мутацию: идущий запуск читается зелёным или красным (в `note`
        нет «ещё идёт» — `status_kind` даёт red), либо имена упавших
        собираются только из заданий — красный запуск без заданий даёт
        `set()` или зелёный исход.
        """
        with self.subTest(вариант="идущий"):
            self.reset_github()
            self.running_run("pull_request")
            for _ in range(self.rng.randint(0, 2)):
                self.add_run(self.rng.choice(("push", "pull_request")))
            outcome, note = self.verifying()
            self.assertEqual(outcome, ci.VERIFYING_RUNNING, self.why(
                f"идущий: verifying_status не «проверки идут»:\n{note}"))
            self.assertFalse(ci.verifying_is_red(note), self.why(
                f"идущий: verifying_is_red истинно:\n{note}"))
            green, bnote = self.branch_verdict()
            self.assertFalse(green, self.why("идущий: branch_status зелёный"))
            self.assertEqual(ci.status_kind(bnote), "running", self.why(
                f"идущий: status_kind не running:\n{bnote}"))
        for conclusion in ("failure", "startup_failure"):
            label = f"красный без заданий ({conclusion})"
            with self.subTest(вариант=label):
                self.reset_github()
                if self.rng.random() < 0.5:
                    self.add_run("pull_request")
                run = self.add_run(self.rng.choice(("pull_request", "push")),
                                   conclusion=conclusion, jobs=[])
                outcome, note = self.verifying()
                self.assertEqual(outcome, ci.VERIFYING_RED, self.why(
                    f"{label}: verifying_status не красный:\n{note}"))
                self.assertIn(run["name"], note, self.why(
                    f"{label}: note не называет запуск {run['name']}:\n{note}"))
                names, why = self.failed()
                self.assertTrue(names, self.why(
                    f"{label}: failed_check_names пуст или None: "
                    f"{names!r} ({why})"))
                self.assertIn(run["name"], names, self.why(
                    f"{label}: failed_check_names без имени запуска: {names}"))


class NoBranchTriggerTest(ActionsSandbox):

    def assert_like_no_checks(self, label: str) -> None:
        """Исход коммита без проверок: по `gh run list` — «проверки идут»
        либо «проверок нет вовсе»; `branch_status` — «неизвестен»."""
        for listed in (False, True):
            with self.subTest(вариант=label, gh_run_list=listed):
                self.gh.run_list = [self.run_list_entry()] if listed else []
                outcome, note = self.verifying()
                if listed:
                    self.assertEqual(outcome, ci.VERIFYING_RUNNING, self.why(
                        f"{label}: при запуске в gh run list не «идут»:\n{note}"))
                    self.assertIn("проверки идут", note, self.why(note))
                else:
                    self.assertEqual(outcome, ci.VERIFYING_NONE, self.why(
                        f"{label}: при пустом gh run list не «нет»:\n{note}"))
                    self.assertIn("проверок нет вовсе", note, self.why(note))
                green, bnote = self.branch_verdict()
                self.assertFalse(green, self.why(
                    f"{label}: branch_status зелёный:\n{bnote}"))
                self.assertEqual(ci.status_kind(bnote), "unknown", self.why(
                    f"{label}: status_kind не unknown:\n{bnote}"))

    def test_ac4_no_runs_or_only_push_runs_behave_as_no_checks(self):
        """Нет ни одного запуска либо только зелёные `push` без `pull_request` — исход коммита без проверок по `gh run list`.

        Два входа: у коммита запусков нет вовсе; у коммита одни–два
        завершённых зелёных запуска события `push`. На каждом —
        `gh run list` по ветке пуст (`VERIFYING_NONE`, «проверок нет
        вовсе») и показывает запуск (`VERIFYING_RUNNING`, «проверки
        идут»); `branch_status` — `False` со `status_kind` "unknown".

        Ловит мутацию: пустой список запусков или одни зелёные `push`
        читаются зелёным (нет условия «есть запуск триггера ветки»), либо
        исход не смотрит в `gh run list` (оба ответа дают одно и то же),
        либо `branch_status` пишет не «неизвестен».
        """
        self.reset_github()
        self.assert_like_no_checks("запусков нет")
        self.reset_github()
        for _ in range(self.rng.randint(1, 2)):
            self.add_run("push", conclusion=self.rng.choice(sorted(ci.GREEN)))
        self.assert_like_no_checks("только зелёные push")

    def test_ac5_other_branch_runs_stay_out_of_verdict(self):
        """Красный запуск другой ветки не красит зелёный `pull_request` задачи; единственный чужой запуск — исход без проверок.

        Первый вход: зелёный завершённый `pull_request` ветки задачи и
        красный запуск с `head_branch` базовой ветки — `VERIFYING_GREEN`,
        `branch_status` — `True`. Второй: единственный запуск коммита —
        другой ветки (зелёный или красный, из `random`) — исход AC-4 на
        обоих ответах `gh run list`.

        Ловит мутацию: отбора по `head_branch` на пути Actions нет —
        красный запуск базовой ветки красит задачу, а единственный чужой
        зелёный запуск даёт зелёный исход.
        """
        with self.subTest(вариант="свой зелёный + чужой красный"):
            self.reset_github()
            self.add_run("pull_request")
            other = self.rng.choice((self.base, f"feature/{self.ulid().lower()}"))
            self.add_run(self.rng.choice(("push", "pull_request")),
                         conclusion="failure", head_branch=other)
            self.rng.shuffle(self.gh.runs[self.sha])
            outcome, note = self.verifying()
            self.assertEqual(outcome, ci.VERIFYING_GREEN, self.why(
                f"чужой красный покрасил verifying_status:\n{note}"))
            green, bnote = self.branch_verdict()
            self.assertTrue(green, self.why(
                f"чужой красный покрасил branch_status:\n{bnote}"))
        self.reset_github()
        self.add_run(self.rng.choice(("pull_request", "push")),
                     conclusion=self.rng.choice(("success", "failure")),
                     head_branch=self.base)
        self.assert_like_no_checks("единственный чужой запуск")


# Неполученный, неразобранный и неполный ответ Actions — по уровню: запуски
# коммита или задания одного запуска.
BROKEN_KINDS = ("неполный", "неразобранный", "не получен")


class UnknownActionsAnswerTest(ActionsSandbox):

    def not_received(self) -> tuple | str:
        return self.rng.choice((http_error(self.rng.choice((500, 502, 503)),
                                           "Server Error"),
                                NETWORK, TIMEOUT))

    def break_answer(self, kind: str, level: str, sha: str, run: dict) -> None:
        if level == "запуски":
            if kind == "неполный":
                self.gh.runs_extra[sha] = self.rng.randint(1, 5)
            elif kind == "неразобранный":
                self.gh.runs_answer[sha] = UNPARSED
            else:
                self.gh.runs_answer[sha] = self.not_received()
        else:
            if kind == "неполный":
                self.gh.jobs_extra[run["id"]] = self.rng.randint(1, 5)
            elif kind == "неразобранный":
                self.gh.jobs_answer[run["id"]] = UNPARSED
            else:
                self.gh.jobs_answer[run["id"]] = self.not_received()

    def test_ac6_unknown_actions_answer_never_green_never_empty_set(self):
        """Пустой, неполный, неразобранный или не полученный ответ Actions — не зелёный, «неизвестен», `failed_check_names` — `None`; `auto` не останавливается красным.

        Головы ветки и вершины main: check-runs — 403; запуски — зелёные
        (у головы — с `pull_request`, у main — `push`), но ответ ломается
        на уровне запусков или заданий одного запуска (`total_count`
        больше выданного, не JSON, HTTP 5xx/обрыв сети/таймаут). На каждом
        входе: `verifying_status` — `VERIFYING_NONE` или
        `VERIFYING_RUNNING`, `verifying_is_red` ложно; `branch_status` —
        `False` со `status_kind` "unknown"; `failed_check_names` головы и
        вершины main — `(None, непустая причина)`. Пустой ответ (запусков
        нет) — не зелёный и `failed_check_names` — `None`. Задача в
        `verifying` после `fsm.cmd_advance` остаётся в `verifying`, а
        запись журнала опроса (её читает `auto`, `auto.py:485`) не красная
        для `ci.verifying_is_red` — цикл не останавливается алертом.

        Ловит мутацию: сверки с `total_count` на пути Actions нет (неполный
        список зелёных запусков или заданий даёт зелёный и `set()`), сбой
        ответа Actions оформлен красным текстом («не зелёный:») — `auto`
        остановился бы алертом, либо пустой ответ даёт `set()`.
        """
        task_id = self.external_task_in_verifying()
        with self.subTest(вариант="пустой"):
            self.reset_github()
            self.gh.run_list = (
                [self.run_list_entry()] if self.rng.random() < 0.5 else [])
            outcome, note = self.verifying()
            self.assertNotEqual(outcome, ci.VERIFYING_GREEN, self.why(note))
            self.assertFalse(ci.verifying_is_red(note), self.why(note))
            green, bnote = self.branch_verdict()
            self.assertFalse(green, self.why(bnote))
            for sha in (self.sha, self.main_sha):
                names, why = self.failed(sha)
                self.assertIsNone(names, self.why(
                    f"пустой: failed_check_names({sha[:8]}) = {names!r}"))
                self.assertTrue(why, self.why("пустой: причина пуста"))
        for kind in BROKEN_KINDS:
            for level in ("запуски", "задания"):
                label = f"{kind}: {level}"
                with self.subTest(вариант=label):
                    self.reset_github()
                    self.gh.run_list = (
                        [self.run_list_entry()] if self.rng.random() < 0.5
                        else [])
                    head_runs = self.green_branch_runs()
                    main_runs = [self.add_run("push", sha=self.main_sha)
                                 for _ in range(self.rng.randint(1, 2))]
                    self.break_answer(kind, level, self.sha,
                                      self.rng.choice(head_runs))
                    self.break_answer(kind, level, self.main_sha,
                                      self.rng.choice(main_runs))
                    outcome, note = self.verifying()
                    self.assertIn(outcome, (ci.VERIFYING_NONE,
                                            ci.VERIFYING_RUNNING), self.why(
                        f"{label}: verifying_status = {outcome}:\n{note}"))
                    self.assertFalse(ci.verifying_is_red(note), self.why(
                        f"{label}: verifying_is_red истинно:\n{note}"))
                    green, bnote = self.branch_verdict()
                    self.assertFalse(green, self.why(
                        f"{label}: branch_status зелёный:\n{bnote}"))
                    self.assertEqual(ci.status_kind(bnote), "unknown",
                                     self.why(f"{label}: status_kind не "
                                              f"unknown:\n{bnote}"))
                    for sha in (self.sha, self.main_sha):
                        names, why = self.failed(sha)
                        self.assertIsNone(names, self.why(
                            f"{label}: failed_check_names({sha[:8]}) = "
                            f"{names!r}"))
                        self.assertTrue(why, self.why(
                            f"{label}: причина пуста"))
                    out = self.advance(task_id)
                    state = store.get_task(store.db(), task_id)["state"]
                    self.assertEqual(state, "verifying", self.why(
                        f"{label}: задача ушла из verifying ({state}):\n{out}"))
                    polled = self.last_verifying_note(task_id)
                    self.assertIsNotNone(polled, self.why(
                        f"{label}: опрос verifying не записан в журнал:\n{out}"))
                    self.assertFalse(ci.verifying_is_red(polled), self.why(
                        f"{label}: запись опроса красная — auto остановился "
                        f"бы алертом:\n{polled}"))


class MainTipTest(ActionsSandbox):

    def test_ac7_main_tip_failed_job_names_from_push_runs(self):
        """Вершина main проекта: красное задание завершённого запуска `push` — в `failed_check_names`, все зелёные — пустое множество.

        check-runs вершины main — 403; её запуски — одно–три завершённых
        события `push` базовой ветки. С одним красным заданием (рядом —
        зелёные) `failed_check_names(<sha main>)` содержит его имя и не
        содержит имён зелёных заданий; все задания зелёные — `set()`.

        Ловит мутацию: в `failed_check_names` перенесён отбор вердикта
        ветки (только `pull_request` или только ветка задачи) — красное
        задание `push` базовой ветки не попадает в множество, либо
        зелёное задание считается упавшим.
        """
        with self.subTest(вариант="одно красное задание"):
            self.reset_github()
            greens = [self.add_run("push", sha=self.main_sha)
                      for _ in range(self.rng.randint(0, 2))]
            run, red_name = self.red_run("push", sha=self.main_sha)
            self.rng.shuffle(self.gh.runs[self.main_sha])
            names, why = self.failed(self.main_sha)
            self.assertIsNotNone(names, self.why(f"None: {why}"))
            self.assertIn(red_name, names, self.why(f"нет {red_name}: {names}"))
            green_jobs = {n for r in greens for n in self.job_names(r)}
            green_jobs |= {j["name"] for j in self.gh.jobs[run["id"]]
                           if j["conclusion"] == "success"}
            self.assertFalse(green_jobs & names, self.why(
                f"зелёные задания среди упавших: {green_jobs & names}"))
        with self.subTest(вариант="все зелёные"):
            self.reset_github()
            for _ in range(self.rng.randint(1, 3)):
                self.add_run("push", sha=self.main_sha)
            names, why = self.failed(self.main_sha)
            self.assertEqual(names, set(), self.why(
                f"все зелёные: {names!r} ({why})"))


class ReasonLineTest(ActionsSandbox):

    def scenarios(self):
        def green():
            self.green_branch_runs()

        def red():
            self.add_run("pull_request")
            self.red_run(self.rng.choice(("pull_request", "push")))

        def running():
            self.running_run()

        def red_without_jobs():
            self.add_run("pull_request", conclusion="startup_failure", jobs=[])

        def none():
            self.gh.run_list = (
                [self.run_list_entry()] if self.rng.random() < 0.5 else [])

        def other_branch_only():
            self.add_run("pull_request", head_branch=self.base)

        def incomplete():
            self.green_branch_runs()
            self.gh.runs_extra[self.sha] = self.rng.randint(1, 5)

        def not_received():
            self.gh.runs_answer[self.sha] = NETWORK

        return (("зелёный", green), ("красный", red), ("идущий", running),
                ("красный без заданий", red_without_jobs),
                ("запусков нет", none), ("только чужая ветка", other_branch_only),
                ("неполный", incomplete), ("не получен", not_received))

    def test_ac8_reason_line_on_every_actions_outcome_both_403_texts(self):
        """На каждом исходе по Actions `note` обоих читателей несёт строку причины не первой строкой; оба текста 403 дают один и тот же переход.

        Исходы AC-1..AC-6 (зелёный, красный, идущий, красный без
        заданий, запусков нет, только чужая ветка, неполный и не
        полученный ответ) разыгрываются для 403 «… by personal access
        token» и «… by integration». У `verifying_status` и
        `branch_status` строка «check-runs недоступны токену проекта (403)
        — итог по Actions runs» есть в `note` и не первая; исход и первая
        строка `note` на двух текстах 403 совпадают.

        Ловит мутацию: строка причины не пишется (или пишется первой, и
        разборщики первой строки читают её), либо переход на Actions
        распознаёт только «personal access token» — для «integration»
        исход другой.
        """
        for label, build in self.scenarios():
            seen = {}
            first_id = self.next_id
            for text in NOT_ACCESSIBLE:
                with self.subTest(исход=label, текст_403=text):
                    # Один и тот же сценарий на обоих текстах 403: те же
                    # случайные запуски, имена и номера.
                    self.reset_github(text)
                    self.next_id, self.used_names = first_id, set()
                    saved = self.rng
                    self.rng = random.Random(f"{self.seed}-{label}")
                    try:
                        build()
                    finally:
                        self.rng = saved
                    outcome, note = self.verifying()
                    green, bnote = self.branch_verdict()
                    self.assert_reason_line(note, f"{label}: verifying_status")
                    self.assert_reason_line(bnote, f"{label}: branch_status")
                    seen[text] = (outcome, note.splitlines()[0],
                                  green, bnote.splitlines()[0])
            if len(seen) == 2:
                a, b = (seen[t] for t in NOT_ACCESSIBLE)
                self.assertEqual(a, b, self.why(
                    f"{label}: исход на «integration» отличается от «personal "
                    f"access token»: {a} / {b}"))


def gh_why(answer) -> str:
    """Причина `check_runs` на ответ `answer` — формулы `ci.py` до правки
    (`check_runs_page`: код `gh`, неразобранный JSON; `gh`: таймаут)."""
    if answer == TIMEOUT:
        return f"gh не ответил: gh молчал дольше {config.GH_TIMEOUT_SEC} с"
    code, out, err = answer
    if code != 0:
        detail = (err or out).strip()[:200]
        return f"gh не ответил: {detail or f'код {code}'}"
    try:
        json.loads(out)
    except json.JSONDecodeError as exc:
        return f"ответ gh не разобран: {exc}"
    raise AssertionError(f"ответ {answer!r} разбирается — не отказ")


class OtherRefusalsTest(ActionsSandbox):

    def read_all(self, repo) -> tuple:
        kwargs = {"repo": repo} if repo is not None else {}
        return (ci.verifying_status(self.branch, **kwargs),
                ci.branch_status(self.branch, **kwargs),
                ci.failed_check_names(self.sha, **kwargs))

    def test_ac9_other_check_runs_refusals_unchanged_without_actions(self):
        """Сеть, таймаут, 401, 404, 5xx, 403 «API rate limit exceeded», неразобранный ответ check-runs внешнего проекта — исход и текст как до правки, запросов Actions по `head_sha` нет.

        У коммита есть зелёный запуск `pull_request` (переход на Actions
        дал бы зелёный). Для каждого отказа исходы и тексты
        `verifying_status`, `branch_status` и `failed_check_names`
        внешнего проекта совпадают с исходами артели на тех же ответах
        (путь артели — прежний, AC-10 фиксирует его формулами), а среди
        вызовов `gh` внешнего проекта нет `actions/runs?head_sha=`.

        Ловит мутацию: на Actions уходит любой 403 (в том числе rate
        limit) или любой отказ check-runs — исход внешнего проекта
        зелёный или его текст расходится с прежним, а журнал вызовов `gh`
        несёт запрос `actions/runs?head_sha=`.
        """
        for label, answer in self.refusals():
            with self.subTest(отказ=label):
                results = {}
                for who, repo in (("артель", None), ("проект", self.clone)):
                    self.reset_github()
                    self.gh.default_check_runs = answer
                    self.add_run("pull_request")
                    self.gh.run_list = [self.run_list_entry()] if (
                        self.seed % 2) else []
                    results[who] = self.read_all(repo)
                    if who == "проект":
                        self.assertEqual(self.gh.actions_head_sha_calls(), [],
                                         self.why(f"{label}: запрос Actions "
                                                  f"по head_sha"))
                self.assertEqual(results["проект"], results["артель"],
                                 self.why(f"{label}: внешний проект "
                                          f"расходится с прежним путём"))


class ArtelUnchangedTest(ActionsSandbox):

    def test_ac10_artel_check_runs_refusals_keep_previous_texts(self):
        """Артель на 403 «Resource not accessible …» и прочих отказах check-runs — прежние исходы и тексты, Actions по `head_sha` не спрашиваются.

        У коммита есть зелёный запуск `pull_request` (переход на Actions
        дал бы зелёный). Для обоих текстов 403 и отказов AC-9 исход
        `verifying_status` — по `gh run list` (`VERIFYING_RUNNING` «…
        показывает запуск — проверки идут» либо `VERIFYING_NONE` «… не
        показывает запусков — проверок нет вовсе»), `branch_status` и
        `failed_check_names` — «статус CI коммита <sha> неизвестен:
        <причина>»; тексты — формулы `ci.py` до правки, ни одного запроса
        `actions/runs?head_sha=`.

        Ловит мутацию: переход на Actions без охраны «не артель» —
        артель на 403 даёт зелёный исход по запускам Actions и делает
        запрос `actions/runs?head_sha=`.
        """
        cases = [(f"403 {t}", forbidden(t)) for t in NOT_ACCESSIBLE]
        cases += self.refusals()
        short = self.sha[:8]
        for label, answer in cases:
            for listed in (False, True):
                with self.subTest(отказ=label, gh_run_list=listed):
                    self.reset_github()
                    self.gh.default_check_runs = answer
                    self.add_run("pull_request")
                    self.gh.run_list = [self.run_list_entry()] if listed else []
                    why = gh_why(answer)
                    first = f"статус check-runs коммита {short} неизвестен ({why})"
                    if listed:
                        expected = (ci.VERIFYING_RUNNING,
                                    f"{first}, но `gh run list` по ветке "
                                    f"{self.branch} показывает запуск — "
                                    f"проверки идут")
                    else:
                        expected = (ci.VERIFYING_NONE,
                                    f"{first}, и `gh run list` по ветке "
                                    f"{self.branch} не показывает запусков "
                                    f"— проверок нет вовсе")
                    unknown = f"статус CI коммита {short} неизвестен: {why}"
                    self.assertEqual(ci.verifying_status(self.branch),
                                     expected, self.why(label))
                    self.assertEqual(ci.branch_status(self.branch),
                                     (False, unknown), self.why(label))
                    self.assertEqual(ci.failed_check_names(self.sha),
                                     (None, unknown), self.why(label))
                    self.assertEqual(self.gh.actions_head_sha_calls(), [],
                                     self.why(f"{label}: запрос Actions"))
