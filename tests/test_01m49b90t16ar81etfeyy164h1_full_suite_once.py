"""Полный набор CI ветки задачи — один раз на sha: пульт не засчитывает
зелёным коммит, у которого задание полного набора только пропущено
(`skipped`) и нигде не исполнилось, и ре-ран целится в прогон, где оно шло.

Группа: долгоживущий

Красен до реализации: `verifying_status`/`branch_status` засчитывают `skipped` любой проверки зелёным (`ci.GREEN`), а `find_run_id` берёт первый прогон с плохим заключением — коммит с пропущенным в push полным набором без завершённого pull_request читается зелёным (AC-4, AC-5, AC-7, AC-8, AC-9, AC-14), а при двух упавших прогонах ре-ран уходит в push (AC-10).

Методы AC-6, AC-12 и AC-13 зелены и до реализации: они держат зелёный
исход, который реализация обязана сохранить (полный набор исполнен в
pull_request; пропущенные проверки вне перечня; внешний проект).

Планка провалидирована временным стабом реализации (перечень — имена
проверок `python`/`python-min`; для артели проверка перечня без
исполненного близнеца или с неизвестным событием прогона — не зелёная;
`find_run_id` — прогон упавшей проверки перечня по её `check_suite`):
все методы зелёные, стаб удалён.

Перечень полного набора — задания `python` и `python-min` файла
`.github/workflows/ci.yml`; check-run задания GitHub Actions называется
`name:` задания (без него — его ключом), поэтому имена проверок сценариев
берутся из самого `ci.yml` — тест не знает, в какой форме реализация
объявила перечень. Прочие задания `ci.yml` дают проверки вне перечня.

GitHub изображает подставной `ci.gh` (публичная точка выхода модуля в
`gh`, её же подменяют `tests/test_ci_status.py` и соседи), голову ветки —
подставной `ci.head_sha`. Подставной `gh` отвечает на формы запросов, по
которым прогон проверки и его событие реально узнаются у GitHub
(check-run'ы коммита, прогоны коммита, прогон, его задания, задание,
check-run и check-suite по id, `run list`/`run view`), и на `run rerun`/
`run watch`; в режиме «прогоны недоступны» отвечает только на check-run'ы
коммита.

Клон артели подаётся обеими формами, которыми его передают вызыватели:
`repo=None` (умолчание) и путь клона `repo_context.clone_path(
config.DEFAULT_TARGET)` (`workspace.task_repo` задачи артели); внешний
проект — путь клона вне области артели.

Какая из проверок перечня пропущена, какие проверки вне перечня
пропущены, sha, id прогонов и проверок, порядок прогонов и проверок в
ответе и вид сбоя запроса прогонов выбираются случайно; зерно печатается
и входит в текст провала.
"""
import json
import random
import re
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from orchestrator import ci, config, repo_context

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
FULL_JOBS = ("python", "python-min")
OWNER_REPO = "artel-owner/artel"
BAD_CONCLUSIONS = ("failure", "timed_out", "cancelled")


def workflow_check_names(text: str) -> dict:
    """{ключ задания: имя его check-run'а} из текста workflow: `name:`
    задания (отступ 4 под ключом с отступом 2 в `jobs:`), без него — ключ."""
    jobs: dict = {}
    in_jobs, current = False, None
    for line in text.splitlines():
        if line and not line[0].isspace():
            in_jobs = line.split(":")[0].strip() == "jobs"
            current = None
            continue
        if not in_jobs:
            continue
        key = re.match(r"^  ([A-Za-z0-9_-]+):\s*(#.*)?$", line)
        if key:
            current = key.group(1)
            jobs[current] = current
            continue
        name = re.match(r"^    name:\s*(.+?)\s*$", line)
        if name and current:
            value = name.group(1)
            if value[:1] in "'\"" and value[-1:] == value[:1]:
                value = value[1:-1]
            if "${{" not in value:
                jobs[current] = value
    return jobs


def stamp(minutes_ago: float) -> str:
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def completed(args, stdout: str = "", returncode: int = 0,
              stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


class FakeGitHub:
    """Подставной `ci.gh`: check-run'ы и workflow-прогоны коммитов."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.runs: list = []
        self.checks: dict = {}
        # "" — исправен; "runs" — сбой всего, кроме check-run'ов коммита.
        self.broken = ""
        self.broken_kind = rng.choice(("code", "garbage"))
        self.used: set = set()
        self.calls: list = []

    def new_id(self, low: int, high: int) -> int:
        while True:
            value = self.rng.randint(low, high)
            if value not in self.used:
                self.used.add(value)
                return value

    def add_run(self, sha: str, event: str, checks: list,
                run_status: str | None = None) -> dict:
        """Прогон `event` на `sha` с проверками [(имя, состояние)]:
        состояние — заключение завершённой проверки либо "running".
        `run_status` — статус самого прогона вопреки его проверкам
        (прогон в очереди, проверок перечня ещё нет)."""
        run_id = self.new_id(10 ** 10, 10 ** 11 - 1)
        suite = self.new_id(10 ** 9, 10 ** 10 - 1)
        created = []
        for name, state in checks:
            check_id = self.new_id(10 ** 8, 10 ** 9 - 1)
            if state == "running":
                status, conclusion = "in_progress", None
            else:
                status, conclusion = "completed", state
            url = (f"http://127.0.0.1/{OWNER_REPO}/actions/runs/{run_id}"
                   f"/job/{check_id}")
            created.append({
                "id": check_id, "name": name, "status": status,
                "conclusion": conclusion, "head_sha": sha,
                "started_at": stamp(3),
                "completed_at": stamp(1) if status == "completed" else None,
                "check_suite": {"id": suite},
                "details_url": url, "html_url": url,
                "app": {"slug": "github-actions"},
                # Поля сценария, не GitHub: ответы их не отдают.
                "_run": run_id, "_event": event,
            })
        if run_status is not None:
            status, conclusion = run_status, None
        elif any(c["status"] != "completed" for c in created):
            status, conclusion = "in_progress", None
        elif any(c["conclusion"] not in ci.GREEN for c in created):
            status, conclusion = "completed", "failure"
        else:
            status, conclusion = "completed", "success"
        run = {
            "id": run_id, "name": "ci", "event": event, "head_sha": sha,
            "head_branch": "task/x", "run_number": self.rng.randint(1, 9999),
            "run_attempt": 1, "check_suite_id": suite,
            "status": status, "conclusion": conclusion,
            "html_url": f"http://127.0.0.1/{OWNER_REPO}/actions/runs/{run_id}",
            "_checks": created,
        }
        self.runs.append(run)
        commit_checks = self.checks.setdefault(sha, [])
        commit_checks.extend(created)
        self.rng.shuffle(commit_checks)
        return run

    # Формы ответа -----------------------------------------------------

    @staticmethod
    def public(record: dict) -> dict:
        return {k: v for k, v in record.items() if not k.startswith("_")}

    def job(self, check: dict) -> dict:
        return {"id": check["id"], "run_id": check["_run"],
                "name": check["name"], "status": check["status"],
                "conclusion": check["conclusion"],
                "head_sha": check["head_sha"],
                "started_at": check["started_at"],
                "completed_at": check["completed_at"],
                "html_url": check["html_url"]}

    def cli_run(self, run: dict) -> dict:
        return {"databaseId": run["id"], "number": run["run_number"],
                "event": run["event"], "headSha": run["head_sha"],
                "headBranch": run["head_branch"], "status": run["status"],
                "conclusion": run["conclusion"] or "", "name": "ci",
                "workflowName": "ci", "url": run["html_url"],
                "jobs": [{"databaseId": c["id"], "name": c["name"],
                          "status": c["status"],
                          "conclusion": c["conclusion"] or "",
                          "url": c["html_url"]} for c in run["_checks"]]}

    def suite(self, run: dict) -> dict:
        return {"id": run["check_suite_id"], "head_sha": run["head_sha"],
                "status": run["status"], "conclusion": run["conclusion"],
                "app": {"slug": "github-actions"}}

    def find_check(self, check_id: int) -> dict | None:
        for run in self.runs:
            for check in run["_checks"]:
                if check["id"] == check_id:
                    return check
        return None

    def runs_of(self, sha: str | None) -> list:
        return [r for r in self.runs
                if sha is None or r["head_sha"].startswith(sha)
                or sha.startswith(r["head_sha"])]

    def __call__(self, *args, **_kwargs) -> subprocess.CompletedProcess:
        args = [str(a) for a in args]
        self.calls.append(args)
        joined = " ".join(args)
        page = re.search(r"[?&]page=(\d+)", joined)
        first_page = page is None or page.group(1) == "1"

        found = re.search(r"commits/([0-9a-fA-F]{7,40})/check-runs", joined)
        if args[:1] == ["api"] and found:
            runs = [self.public(c) for c in self.checks.get(found.group(1), [])]
            return completed(args, json.dumps(
                {"total_count": len(runs),
                 "check_runs": runs if first_page else []}))
        if self.broken == "runs":
            if self.broken_kind == "code":
                return completed(args, returncode=1,
                                 stderr="gh: HTTP 502 Bad Gateway (песочница)")
            return completed(args, "<html>502 — не JSON</html>")

        if args[:1] == ["api"]:
            return self.api(args, joined, first_page)
        if args[:2] in (["run", "rerun"], ["run", "watch"]):
            return completed(args, "ok")
        if args[:2] == ["run", "list"]:
            sha = None
            for flag in ("--commit", "-c"):
                if flag in args and args.index(flag) + 1 < len(args):
                    sha = args[args.index(flag) + 1]
            runs = self.runs_of(sha)
            if "--event" in args and args.index("--event") + 1 < len(args):
                event = args[args.index("--event") + 1]
                runs = [r for r in runs if r["event"] == event]
            return completed(args, json.dumps([self.cli_run(r) for r in runs]))
        if args[:2] == ["run", "view"] and len(args) > 2:
            for run in self.runs:
                if str(run["id"]) == args[2]:
                    return completed(args, json.dumps(self.cli_run(run)))
            return completed(args, returncode=1, stderr="gh: прогон не найден")
        return completed(args, returncode=1,
                         stderr=f"gh песочницы: вызов не поддержан: {joined}")

    def api(self, args, joined: str, first_page: bool):
        not_found = completed(args, returncode=1,
                              stderr="gh: HTTP 404: Not Found (песочница)")
        match = re.search(r"actions/runs/(\d+)/jobs", joined)
        if match:
            run = next((r for r in self.runs
                        if str(r["id"]) == match.group(1)), None)
            if run is None:
                return not_found
            jobs = [self.job(c) for c in run["_checks"]]
            return completed(args, json.dumps(
                {"total_count": len(jobs), "jobs": jobs if first_page else []}))
        match = re.search(r"actions/runs/(\d+)(?![\d/])", joined)
        if match:
            run = next((r for r in self.runs
                        if str(r["id"]) == match.group(1)), None)
            if run is None:
                return not_found
            return completed(args, json.dumps(self.public(run)))
        if re.search(r"actions/runs(?![\w/])", joined):
            sha = re.search(r"head_sha=([0-9a-fA-F]+)", joined)
            runs = self.runs_of(sha.group(1) if sha else None)
            event = re.search(r"[?&]event=([\w-]+)", joined)
            if event:
                runs = [r for r in runs if r["event"] == event.group(1)]
            return completed(args, json.dumps(
                {"total_count": len(runs),
                 "workflow_runs": ([self.public(r) for r in runs]
                                   if first_page else [])}))
        match = (re.search(r"actions/jobs/(\d+)", joined)
                 or re.search(r"check-runs/(\d+)", joined))
        if match:
            check = self.find_check(int(match.group(1)))
            if check is None:
                return not_found
            body = (self.job(check) if "actions/jobs" in joined
                    else self.public(check))
            return completed(args, json.dumps(body))
        match = re.search(r"commits/([0-9a-fA-F]{7,40})/check-suites", joined)
        if match:
            suites = [self.suite(r) for r in self.runs_of(match.group(1))]
            return completed(args, json.dumps(
                {"total_count": len(suites),
                 "check_suites": suites if first_page else []}))
        match = re.search(r"check-suites/(\d+)", joined)
        if match:
            run = next((r for r in self.runs
                        if str(r["check_suite_id"]) == match.group(1)), None)
            if run is None:
                return not_found
            return completed(args, json.dumps(self.suite(run)))
        return completed(args, returncode=1,
                         stderr=f"gh песочницы: вызов не поддержан: {joined}")


class FullSuiteOncePerShaTest(unittest.TestCase):
    """Пропущенный полный набор без исполненного близнеца — не зелёный."""

    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.jobs = workflow_check_names(WORKFLOW.read_text(encoding="utf-8"))
        missing = [j for j in FULL_JOBS if j not in self.jobs]
        self.assertFalse(missing, f"в {WORKFLOW} нет заданий {missing}")
        self.full = [self.jobs[j] for j in FULL_JOBS]
        self.others = [name for job, name in self.jobs.items()
                       if job not in FULL_JOBS]
        self.sha = "".join(self.rng.choice("0123456789abcdef")
                           for _ in range(40))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.external = Path(tmp.name) / "projects" / "external" / "repo"
        self.reset()
        for target, value in (
                ("gh", lambda *a, **k: self.fake(*a, **k)),
                ("head_sha", lambda branch, **_k: (self.sha, ""))):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    # Помощники сценария ----------------------------------------------

    def reset(self) -> None:
        self.fake = FakeGitHub(random.Random(self.rng.randrange(2 ** 32)))

    def artel_repos(self) -> tuple:
        return (None, repo_context.clone_path(config.DEFAULT_TARGET))

    def skipped_full(self) -> list:
        """Проверки перечня, пропущенные в push: одна случайная или обе."""
        count = self.rng.randint(1, len(self.full))
        return self.rng.sample(self.full, count)

    def add(self, event: str, full: dict, skip_others=(), fail_others=(),
            run_status: str | None = None, with_others: bool = True) -> dict:
        """Прогон `event` с проверками перечня `full` {имя: состояние} и
        проверками вне перечня: `skip_others` — пропущены, `fail_others` —
        упали, прочие — зелёные либо (случайно) пропущены."""
        checks = list(full.items())
        if with_others:
            for name in self.others:
                if name in fail_others:
                    state = "failure"
                elif name in skip_others or self.rng.random() < 0.3:
                    state = "skipped"
                else:
                    state = "success"
                checks.append((name, state))
        self.rng.shuffle(checks)
        return self.fake.add_run(self.sha, event, checks, run_status)

    def push_with_full(self, state_of) -> dict:
        """Push-прогон: каждая проверка перечня — `state_of(имя)`."""
        return self.add("push", {n: state_of(n) for n in self.full})

    def msg(self, note: str, extra: str = "") -> str:
        return f"зерно: {self.seed}\n{extra}\nтекст статуса:\n{note}"

    def assert_not_green(self, label: str, repos=None) -> None:
        for repo in repos or self.artel_repos():
            with self.subTest(case=label, repo=str(repo), reader="verifying"):
                outcome, note = ci.verifying_status("task/x", repo=repo)
                self.assertNotEqual(outcome, ci.VERIFYING_GREEN,
                                    self.msg(note, label))
            with self.subTest(case=label, repo=str(repo), reader="branch"):
                green, note = ci.branch_status("task/x", repo=repo)
                self.assertIs(green, False, self.msg(note, label))

    def assert_green(self, label: str, repos=None) -> None:
        for repo in repos or self.artel_repos():
            with self.subTest(case=label, repo=str(repo), reader="verifying"):
                outcome, note = ci.verifying_status("task/x", repo=repo)
                self.assertEqual(outcome, ci.VERIFYING_GREEN,
                                 self.msg(note, label))
            with self.subTest(case=label, repo=str(repo), reader="branch"):
                green, note = ci.branch_status("task/x", repo=repo)
                self.assertIs(green, True, self.msg(note, label))

    def verifying_not_green(self, label: str) -> None:
        for repo in self.artel_repos():
            with self.subTest(case=label, repo=str(repo)):
                outcome, note = ci.verifying_status("task/x", repo=repo)
                self.assertNotEqual(outcome, ci.VERIFYING_GREEN,
                                    self.msg(note, label))

    # Сценарии AC-4…AC-6 ----------------------------------------------

    def build_ac4(self) -> None:
        """Перечень пропущен в push (одна проверка или обе), прогона
        pull_request нет; непропущенная проверка перечня — зелёная."""
        self.reset()
        skipped = self.skipped_full()
        self.push_with_full(
            lambda n: "skipped" if n in skipped else "success")

    def build_ac5(self, variant: str) -> None:
        """Перечень пропущен в push; прогон pull_request есть, но
        задание перечня в нём не завершено."""
        self.reset()
        self.push_with_full(lambda _n: "skipped")
        if variant == "проверка перечня идёт":
            running = self.skipped_full()
            self.add("pull_request",
                     {n: "running" if n in running else "success"
                      for n in self.full})
        elif variant == "прогон в очереди, проверок нет":
            self.fake.add_run(self.sha, "pull_request", [],
                              run_status=self.rng.choice(("queued",
                                                          "in_progress")))
        else:  # прогон идёт, проверок перечня в нём ещё нет
            self.add("pull_request", {}, run_status="in_progress")
        self.rng.shuffle(self.fake.runs)

    def build_ac6(self) -> None:
        """Перечень пропущен в push и исполнен `success` в pull_request,
        прочие проверки зелёные."""
        self.reset()
        self.push_with_full(lambda _n: "skipped")
        self.add("pull_request", {n: "success" for n in self.full})
        self.rng.shuffle(self.fake.runs)

    AC5_VARIANTS = ("проверка перечня идёт", "прогон в очереди, проверок нет",
                    "прогон идёт, проверок перечня ещё нет")

    # Критерии ---------------------------------------------------------

    def test_ac4_skipped_full_suite_without_pull_request_is_not_green(self):
        """Пропуск полного набора в push без прогона pull_request — не
        зелёный `verifying`.

        У коммита один прогон — push: проверки перечня (одна случайная
        или обе) `skipped`, остальные проверки зелёные или пропущены.
        `ci.verifying_status` для клона артели (обеими формами `repo`) не
        возвращает `ci.VERIFYING_GREEN`.

        Ловит мутацию: `skipped` проверки перечня по-прежнему входит в
        зелёные заключения (`ci.GREEN`) — исход `VERIFYING_GREEN` с текстом
        «CI коммита … зелёный».
        """
        self.build_ac4()
        self.verifying_not_green("перечень skipped в push, pull_request нет")

    def test_ac5_pull_request_run_not_finished_is_not_green(self):
        """Прогон pull_request есть, но задание перечня в нём не завершено.

        Перечень `skipped` в push; прогон pull_request: (1) проверка
        перечня в нём идёт; (2) прогон в очереди без единой проверки;
        (3) прогон идёт, проверки вне перечня в нём завершены, проверок
        перечня ещё нет. Во всех трёх `ci.verifying_status` не возвращает
        `ci.VERIFYING_GREEN`.

        Ловит мутацию: пропуск засчитывается, как только у коммита виден
        прогон pull_request (по самому прогону, не по исполненной в нём
        проверке перечня), — варианты (2) и (3) читаются зелёными.
        """
        for variant in self.AC5_VARIANTS:
            self.build_ac5(variant)
            self.verifying_not_green(variant)

    def test_ac6_full_suite_success_in_pull_request_is_green(self):
        """Перечень пропущен в push и исполнен `success` в pull_request —
        зелёный `verifying`.

        Прочие проверки обоих прогонов зелёные или пропущены; порядок
        прогонов в ответе случайный. `ci.verifying_status` для клона
        артели (обеими формами `repo`) возвращает `ci.VERIFYING_GREEN`.

        Ловит мутацию: правило требует исполнения проверки перечня в
        прогоне того же события, где она пропущена (или в прогоне push),
        — коммит с полным набором, прошедшим в pull_request, навсегда
        остаётся «ещё идёт».
        """
        self.build_ac6()
        for repo in self.artel_repos():
            with self.subTest(repo=str(repo)):
                outcome, note = ci.verifying_status("task/x", repo=repo)
                self.assertEqual(outcome, ci.VERIFYING_GREEN, self.msg(note))

    def test_ac7_branch_status_follows_the_same_rule(self):
        """`branch_status` (гейт мержа, `approve`) решает так же, как
        `verifying_status`.

        На раскладах AC-4 и трёх раскладах AC-5 `ci.branch_status`
        возвращает `False`, на раскладе AC-6 — `True` (клон артели обеими
        формами `repo`).

        Ловит мутацию: правило о пропущенном полном наборе доведено только
        до `verifying_status`, а `branch_status` по-прежнему считает
        `skipped` зелёным — гейт мержа пропускает коммит до завершения
        прогона pull_request.
        """
        cases = [("AC-4", self.build_ac4, False)]
        cases += [(f"AC-5: {v}", lambda v=v: self.build_ac5(v), False)
                  for v in self.AC5_VARIANTS]
        cases += [("AC-6", self.build_ac6, True)]
        for label, build, expected in cases:
            build()
            for repo in self.artel_repos():
                with self.subTest(case=label, repo=str(repo)):
                    green, note = ci.branch_status("task/x", repo=repo)
                    self.assertIs(green, expected, self.msg(note, label))

    def test_ac8_undefined_event_of_skipped_full_suite_is_not_green(self):
        """Событие прогона пропущенной проверки перечня не определилось —
        коммит не зелёный.

        Запрос прогонов коммита отвечает ненулевым кодом либо неразборным
        текстом (вид сбоя случайный), check-run'ы коммита читаются.
        Расклады: (1) перечень `skipped` в одном прогоне, второго прогона
        нет; (2) перечень `skipped` в одном прогоне и `success` в другом —
        событие пропуска узнать не у кого. Ни `ci.verifying_status`, ни
        `ci.branch_status` не засчитывают коммит зелёным.

        Ловит мутацию: сбой запроса прогонов читается как «прогонов
        pull_request нет, проверять нечего» либо пропуск засчитывается без
        события прогона по одному имени исполненного близнеца — расклад (2)
        зелёный при недоступном индексе прогонов.
        """
        for label, with_twin in (("skipped, близнеца нет", False),
                                 ("skipped и success в другом прогоне", True)):
            self.reset()
            self.fake.broken = "runs"
            self.push_with_full(lambda _n: "skipped")
            if with_twin:
                self.add("pull_request", {n: "success" for n in self.full})
            self.rng.shuffle(self.fake.runs)
            self.assert_not_green(label)

    def test_ac9_push_without_pull_request_needs_the_full_suite(self):
        """Push без PR: исполненный полный набор — зелёный, пропущенный —
        нет.

        Единственный прогон коммита — push. (1) Проверки перечня `success`,
        проверки вне перечня зелёные или пропущены (в том числе такие, что
        идут только на pull_request) — `ci.verifying_status` даёт
        `VERIFYING_GREEN`, `ci.branch_status` — `True`. (2) Проверка
        перечня (одна случайная или обе) `skipped` — ни тот, ни другой не
        зелёный.

        Ловит мутацию: правило о пропуске применено ко всем проверкам
        коммита, а не к перечню, — пропущенная на push проверка вне
        перечня делает расклад (1) не зелёным; либо `skipped` перечня
        по-прежнему зелёный — расклад (2) зелёный.
        """
        self.reset()
        self.push_with_full(lambda _n: "success")
        self.assert_green("push без PR, перечень исполнен")

        self.reset()
        skipped = self.skipped_full()
        self.push_with_full(
            lambda n: "skipped" if n in skipped else "success")
        self.assert_not_green("push без PR, перечень skipped")

    def test_ac10_rerun_targets_the_run_where_full_suite_ran(self):
        """Ре-ран целится в прогон pull_request, где упало задание перечня.

        Проверка перечня (случайная) упала в прогоне pull_request и
        пропущена в прогоне push. (1) Push-прогон в остальном зелёный,
        порядок прогонов в ответе случайный. (2) Проверка вне перечня
        упала в обоих прогонах, push-прогон в ответе первым. В обоих
        `ci.find_run_id(sha)` возвращает id прогона pull_request, а
        `ci.trigger_rerun("task/x")` зовёт `gh run rerun` с этим id и не
        зовёт его с id push-прогона.

        Ловит мутацию: прогон выбирается как первый в ответе с плохим
        заключением прогона — в раскладе (2) ре-ран уходит в push-прогон,
        где задание перечня пропущено, и упавшие тесты не перезапускаются.
        """
        for label in ("push зелёный", "проверка вне перечня упала в обоих"):
            self.reset()
            failing = self.rng.choice(self.full)
            other_fail = (self.rng.choice(self.others),) \
                if label.startswith("проверка") else ()
            push = self.add("push", {n: "skipped" for n in self.full},
                            fail_others=other_fail)
            pr = self.add("pull_request",
                          {n: "failure" if n == failing else "success"
                           for n in self.full}, fail_others=other_fail)
            if not other_fail:
                self.rng.shuffle(self.fake.runs)
            note = (f"{label}; упала {failing}; push {push['id']}, "
                    f"pull_request {pr['id']}")
            with self.subTest(case=label, reader="find_run_id"):
                run_id, why = ci.find_run_id(self.sha)
                self.assertEqual(run_id, str(pr["id"]), self.msg(why, note))
            with self.subTest(case=label, reader="trigger_rerun"):
                self.fake.calls.clear()
                result = ci.trigger_rerun("task/x")
                reruns = [c for c in self.fake.calls if c[:2] == ["run", "rerun"]]
                self.assertTrue(
                    any(str(pr["id"]) in c for c in reruns),
                    self.msg(result, f"{note}; вызовы rerun: {reruns}"))
                self.assertFalse(
                    any(str(push["id"]) in c for c in reruns),
                    self.msg(result, f"{note}; вызовы rerun: {reruns}"))

    def test_ac12_skipped_check_outside_the_list_stays_green(self):
        """Проверка вне перечня, пропущенная в обоих прогонах, не мешает
        зелёному.

        Проверка вне перечня (случайная из прочих заданий `ci.yml`)
        `skipped` и в push, и в pull_request; перечень пропущен в push и
        `success` в pull_request, прочие проверки зелёные.
        `ci.verifying_status` возвращает `VERIFYING_GREEN`,
        `ci.branch_status` — `True`.

        Ловит мутацию: правило «пропуск без исполненного близнеца — не
        зелёный» применено к любой проверке, а не только к перечню, —
        пропущенная везде проверка вне перечня держит коммит «ещё идёт».
        """
        self.assertTrue(self.others, f"в {WORKFLOW} нет заданий вне перечня")
        outside = self.rng.choice(self.others)
        self.reset()
        self.add("push", {n: "skipped" for n in self.full},
                 skip_others=(outside,))
        self.add("pull_request", {n: "success" for n in self.full},
                 skip_others=(outside,))
        self.rng.shuffle(self.fake.runs)
        self.assert_green(f"{outside} skipped в обоих прогонах")

    def test_ac13_external_project_is_judged_as_before(self):
        """Коммит внешнего проекта оценивается как до изменения.

        `repo` — клон внешнего проекта (путь вне области артели). Проверки
        с теми же именами, что перечень артели, только `skipped` в
        единственном прогоне push, остальные зелёные или пропущены —
        набор, зелёный до изменения: (1) при исправном запросе прогонов;
        (2) при сбое запроса прогонов. `ci.verifying_status` даёт
        `VERIFYING_GREEN`, `ci.branch_status` — `True`.

        Ловит мутацию: перечень артели применён к любому проекту — коммит
        внешнего проекта с пропущенными проверками того же имени держится
        «ещё идёт».
        """
        for label, broken in (("индекс прогонов есть", ""),
                              ("индекс прогонов недоступен", "runs")):
            self.reset()
            self.fake.broken = broken
            self.push_with_full(lambda _n: "skipped")
            self.assert_green(f"внешний проект: {label}",
                              repos=(self.external,))

    def test_ac14_list_matches_full_suite_jobs_of_workflow(self):
        """Перечень полного набора совпадает с заданиями `python` и
        `python-min` файла `ci.yml`.

        Задания `python` и `python-min` в `ci.yml` есть. Для каждого
        задания `ci.yml` разыгрывается push без PR, где проверка этого
        задания (её имя — `name:` задания) единственная `skipped`, прочие
        `success`: для `python`/`python-min` `ci.verifying_status` не
        зелёный (задание в перечне), для прочих — `VERIFYING_GREEN`
        (не в перечне).

        Ловит мутацию: перечень объявлен ключами заданий («python») либо
        с опечаткой в имени проверки, а сравнивается с именем check-run'а
        (`name:` задания), — пропущенная проверка полного набора не
        узнаётся и коммит зелёный; либо `name:` задания в `ci.yml`
        переименован без правки перечня.
        """
        for job, name in self.jobs.items():
            self.reset()
            checks = [(n, "skipped" if n == name else "success")
                      for n in self.jobs.values()]
            self.rng.shuffle(checks)
            self.fake.add_run(self.sha, "push", checks)
            in_list = job in FULL_JOBS
            for repo in self.artel_repos():
                with self.subTest(job=job, repo=str(repo)):
                    outcome, note = ci.verifying_status("task/x", repo=repo)
                    if in_list:
                        self.assertNotEqual(
                            outcome, ci.VERIFYING_GREEN,
                            self.msg(note, f"{job} ({name}) не в перечне"))
                    else:
                        self.assertEqual(
                            outcome, ci.VERIFYING_GREEN,
                            self.msg(note, f"{job} ({name}) в перечне"))


if __name__ == "__main__":
    unittest.main()
