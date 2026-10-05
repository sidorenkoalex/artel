"""Статус CI коммита называет событие и номер workflow-прогона у каждой
упавшей, идущей и зависшей проверки: на один sha бывают два прогона одного
workflow (push и pull_request) с одноимёнными проверками, и текст без
события не говорит, какой из двух логов читать.

Группа: долгоживущий

Красен до реализации: `verifying_status`, `branch_status` и `main_line_status` собирают текст только из имени и заключения check-run'а и прогоны коммита не спрашивают — в тексте нет ни события, ни номера прогона, ни пометки «событие не определено», ни фразы о расхождении исхода по событиям (методы AC-1…AC-7 и разборщики AC-8 на этих текстах падают на отсутствии этих частей).

Метод AC-8 зелен и до реализации: разборщики на нынешнем тексте уже дают
нужные исходы, он держит их на новом тексте после реализации.

Планка провалидирована временным стабом реализации (событие и номер
прогона — сопоставлением check-run'а с прогоном коммита по `check_suite`;
все методы зелёные, стаб удалён).

GitHub изображает подставной `ci.gh` (публичная точка выхода модуля в
`gh`, её же подменяют `tests/test_ci_status.py` и соседи). Он отвечает на
те формы запросов, которыми прогон и его событие реально узнаются у
GitHub, не навязывая реализации одну из них:
- `api …/commits/<sha>/check-runs` — check-run'ы коммита; у каждого
  `check_suite.id` его прогона и `details_url`/`html_url` вида
  `…/actions/runs/<id прогона>/job/<id check-run'а>`;
- `api …/actions/runs?head_sha=<sha>` (с `event=` — отбор по событию) —
  прогоны коммита: `id`, `event`, `check_suite_id`, `run_number`,
  `status`, `conclusion`, `head_sha`;
- `api …/actions/runs/<id>`, `…/actions/runs/<id>/jobs`,
  `…/actions/jobs/<id>`, `…/check-runs/<id>`, `…/commits/<sha>/
  check-suites`, `…/check-suites/<id>` — прогон, его задания (id задания =
  id check-run'а, у задания `run_id`), check-run и check-suite по id;
- `run list --commit <sha>` и `run view <id>` — формы CLI (`databaseId`,
  `event`, `headSha`, `number`, `jobs`).
Флаги `--json`/`--jq` не разбираются: ответ — всегда полный JSON. В
режиме «прогоны недоступны» (AC-7) каждый вызов, кроме check-run'ов
коммита, отвечает ненулевым кодом либо неразборным текстом.

«Номер прогона» — id workflow-прогона (в критерии — 37320196602), не его
порядковый `run_number`: у прогонов песочницы оба поля есть и различны.

Принадлежность события и номера проверке в тексте, форму которого
критерий не фиксирует (идущие, зависшие, проверки main, «событие не
определено»), проверяется по отрезку текста: от вхождения имени проверки
до следующего вхождения любого имени проверки сценария или конца строки.
Имена проверок выбираются так, что ни одно не входит в другое.

Имена проверок, id прогонов и check-run'ов, sha, заключения провала,
порядок прогонов в ответе, событие вне push/pull_request и вид сбоя
запроса прогонов выбираются случайно; зерно печатается и входит в текст
провала.
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

from orchestrator import ci, config

CHECK_NAMES = (
    "Синтаксис и тесты оркестратора",
    "Инварианты на минимальной версии Python",
    "protected-paths",
    "id-format-greplint",
    "Свежесть карты кода",
    "Линтер шаблонов",
    "Сборка документации",
)
EXAMPLE_NAME = "Синтаксис и тесты оркестратора"
EXAMPLE_RUN_ID = 37320196602
BAD_CONCLUSIONS = ("failure", "timed_out", "cancelled")
OTHER_EVENTS = ("workflow_dispatch", "schedule", "repository_dispatch",
                "merge_group")
UNDEFINED = "событие не определено"
OWNER_REPO = "artel-owner/artel"
# Аннотация проверки в форме AC-1 — для поиска фразы AC-6 вне аннотаций.
ANNOTATION = re.compile(r"\((?:push|pull_request), прогон \d+\)")


def stamp(minutes_ago: float) -> str:
    moment = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def completed(args, stdout: str = "", returncode: int = 0,
              stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


def mentions(text: str, word: str) -> bool:
    return re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", text) is not None


def segments(text: str, names) -> list[str]:
    """Отрезки `text` от каждого вхождения имени проверки до следующего
    вхождения любого имени либо конца строки."""
    starts = sorted({m.start() for name in names
                     for m in re.finditer(re.escape(name), text)})
    out = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        newline = text.find("\n", start)
        if newline != -1:
            end = min(end, newline)
        out.append(text[start:end])
    return out


class FakeGitHub:
    """Подставной `ci.gh`: check-run'ы и workflow-прогоны коммитов."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.runs: list[dict] = []
        self.checks: dict[str, list[dict]] = {}
        # "" — исправен; "runs" — сбой всего, кроме check-run'ов коммита;
        # "all" — сбой любого вызова.
        self.broken = ""
        self.broken_kind = rng.choice(("code", "garbage"))
        self.used: set[int] = set()

    def new_id(self, low: int, high: int) -> int:
        while True:
            value = self.rng.randint(low, high)
            if value not in self.used:
                self.used.add(value)
                return value

    def add_run(self, sha: str, event: str, checks: list[tuple[str, str]],
                run_id: int | None = None) -> tuple[dict, list[dict]]:
        """Прогон `event` на `sha` с проверками [(имя, состояние)]:
        состояние — заключение завершённой проверки, "running" (идёт
        минуту) или "stuck" (без исхода дольше порога зависания)."""
        if run_id is None:
            run_id = self.new_id(10 ** 10, 10 ** 11 - 1)
        else:
            self.used.add(run_id)
        suite = self.new_id(10 ** 9, 10 ** 10 - 1)
        created = []
        for name, state in checks:
            check_id = self.new_id(10 ** 8, 10 ** 9 - 1)
            if state == "running":
                status, conclusion, age = "in_progress", None, 1
            elif state == "stuck":
                status = self.rng.choice(("in_progress", "queued"))
                conclusion, age = None, config.CI_STUCK_CHECK_MINUTES + 30
            else:
                status, conclusion, age = "completed", state, 3
            url = (f"http://127.0.0.1/{OWNER_REPO}/actions/runs/{run_id}"
                   f"/job/{check_id}")
            created.append({
                "id": check_id, "name": name, "status": status,
                "conclusion": conclusion, "head_sha": sha,
                "started_at": stamp(age),
                "completed_at": stamp(1) if status == "completed" else None,
                "check_suite": {"id": suite},
                "details_url": url, "html_url": url,
                "app": {"slug": "github-actions"},
                # Поля сценария, не GitHub: ответы их не отдают.
                "_run": run_id, "_event": event,
            })
        if any(c["status"] != "completed" for c in created):
            run_status, run_conclusion = "in_progress", None
        elif any(c["conclusion"] not in ci.GREEN for c in created):
            run_status, run_conclusion = "completed", "failure"
        else:
            run_status, run_conclusion = "completed", "success"
        run = {
            "id": run_id, "name": "CI", "event": event, "head_sha": sha,
            "head_branch": "main", "run_number": self.rng.randint(1, 9999),
            "run_attempt": 1, "check_suite_id": suite,
            "status": run_status, "conclusion": run_conclusion,
            "html_url": f"http://127.0.0.1/{OWNER_REPO}/actions/runs/{run_id}",
            "_checks": created,
        }
        self.runs.append(run)
        self.checks.setdefault(sha, []).extend(created)
        return run, created

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
                "html_url": check["html_url"],
                "check_run_url": (f"http://127.0.0.1/repos/{OWNER_REPO}"
                                  f"/check-runs/{check['id']}")}

    def cli_run(self, run: dict) -> dict:
        return {"databaseId": run["id"], "number": run["run_number"],
                "event": run["event"], "headSha": run["head_sha"],
                "headBranch": run["head_branch"], "status": run["status"],
                "conclusion": run["conclusion"] or "", "name": "CI",
                "workflowName": "CI", "url": run["html_url"],
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

    def runs_of(self, sha: str | None) -> list[dict]:
        return [r for r in self.runs
                if sha is None or r["head_sha"].startswith(sha)
                or sha.startswith(r["head_sha"])]

    def __call__(self, *args, **_kwargs) -> subprocess.CompletedProcess:
        args = [str(a) for a in args]
        joined = " ".join(args)
        page_match = re.search(r"[?&]page=(\d+)", joined)
        first_page = page_match is None or page_match.group(1) == "1"

        if self.broken == "all":
            return completed(args, returncode=1,
                             stderr="gh: сеть недоступна (песочница)")
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


class CiStatusNamesRunEventTest(unittest.TestCase):
    """Текст статусов CI называет событие и номер прогона проверки."""

    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # Каталог без git: дифф головы push'а на main не читается, и обход
        # линии идёт глубже пропущенной на голове проверки (документировано
        # у `main_line_status`) — без настоящего git в сценарии.
        self.no_git = Path(tmp.name)
        self.sha = self.new_sha()
        self.line = [self.sha]
        self.fake = FakeGitHub(random.Random(self.rng.randrange(2 ** 32)))
        for target, value in (
                ("gh", lambda *a, **k: self.fake(*a, **k)),
                ("head_sha", lambda branch, **_k: (self.sha, "")),
                ("first_parent_line",
                 lambda sha, limit, **_k: list(self.line)[:limit])):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    # Помощники сценария ----------------------------------------------

    def new_sha(self) -> str:
        return "".join(self.rng.choice("0123456789abcdef") for _ in range(40))

    def names(self, count: int, include: str | None = None) -> list[str]:
        pool = [n for n in CHECK_NAMES if n != include]
        picked = self.rng.sample(pool, count - (1 if include else 0))
        if include:
            picked.insert(self.rng.randrange(len(picked) + 1), include)
        return picked

    def bad(self) -> str:
        return self.rng.choice(BAD_CONCLUSIONS)

    def reset(self, seed: int | None = None) -> None:
        self.fake = FakeGitHub(random.Random(
            self.rng.randrange(2 ** 32) if seed is None else seed))

    def shuffle_runs(self) -> None:
        self.rng.shuffle(self.fake.runs)

    def msg(self, note: str, extra: str = "") -> str:
        return f"зерно: {self.seed}\n{extra}\nтекст статуса:\n{note}"

    def assert_names_run(self, note: str, check: dict, names,
                         undefined: bool = False) -> None:
        """У вхождения имени `check` в `note` — событие и номер его прогона
        (либо «событие не определено»)."""
        for seg in segments(note, names):
            if not seg.startswith(check["name"]):
                continue
            if undefined and UNDEFINED in seg:
                return
            if (not undefined and mentions(seg, check["_event"])
                    and re.search(rf"прогон {check['_run']}(?!\d)", seg)):
                return
        want = (UNDEFINED if undefined
                else f"событие {check['_event']} и «прогон {check['_run']}»")
        self.fail(self.msg(note, f"у проверки «{check['name']}» "
                                 f"(check-run {check['id']}) нет: {want}"))

    def red_form(self, check: dict) -> str:
        return (f"{check['name']}={check['conclusion']} "
                f"({check['_event']}, прогон {check['_run']})")

    def residual(self, note: str) -> str:
        return ANNOTATION.sub("", note)

    # Критерии ---------------------------------------------------------

    def test_ac1_verifying_red_names_event_and_run_of_each_failed_check(self):
        """Красный `verifying` называет у каждой упавшей проверки её прогон.

        Коммит несёт два прогона одного workflow: pull_request с id
        37320196602, где «Синтаксис и тесты оркестратора» упала, и push, где
        та же проверка зелёная, а упала другая. Текст содержит дословно
        «Синтаксис и тесты оркестратора=failure (pull_request, прогон
        37320196602)» и ту же форму для упавшей проверки push-прогона.

        Ловит мутацию: событие и номер берутся у первого (или самого
        свежего) прогона коммита, а не у прогона самой проверки — упавшая
        проверка push-прогона подписана «(pull_request, прогон 37320196602)»,
        либо вместо id прогона в текст попадает его `run_number`.
        """
        names = self.names(4, include=EXAMPLE_NAME)
        others = [n for n in names if n != EXAMPLE_NAME]
        push_red = self.rng.choice(others)
        _pr, pr_checks = self.fake.add_run(
            self.sha, "pull_request",
            [(n, "failure" if n == EXAMPLE_NAME else "success") for n in names],
            run_id=EXAMPLE_RUN_ID)
        _push, push_checks = self.fake.add_run(
            self.sha, "push",
            [(n, self.bad() if n == push_red else "success") for n in names])
        self.shuffle_runs()

        outcome, note = ci.verifying_status("task/x")

        self.assertEqual(outcome, ci.VERIFYING_RED, self.msg(note))
        self.assertIn("Синтаксис и тесты оркестратора=failure (pull_request, "
                      "прогон 37320196602)", note, self.msg(note))
        for check in pr_checks + push_checks:
            if check["conclusion"] not in ci.GREEN:
                self.assertIn(self.red_form(check), note, self.msg(note))

    def test_ac2_verifying_running_and_stuck_name_event_and_run(self):
        """«Ещё идёт» и «проверка зависла» называют прогон каждой проверки.

        Первый сценарий: одноимённая проверка идёт и в push-, и в
        pull_request-прогоне, плюс ещё одна идущая — исход
        `VERIFYING_RUNNING`, у каждой идущей проверки в тексте её событие и
        номер её прогона. Второй: в двух прогонах по зависшей проверке
        (без исхода дольше `config.CI_STUCK_CHECK_MINUTES`) — исход
        `VERIFYING_STUCK`, у каждой зависшей проверки событие и номер.

        Ловит мутацию: событие и номер прогона добавлены только в ветку
        красного исхода `verifying_status` — тексты «ещё идёт» и «проверка
        зависла» остаются прежними, без события и номера.
        """
        names = self.names(3)
        twin, other, green = names
        _a, pr_checks = self.fake.add_run(
            self.sha, "pull_request", [(twin, "running"), (green, "success")])
        _b, push_checks = self.fake.add_run(
            self.sha, "push", [(twin, "running"), (other, "running"),
                               (green, "success")])
        self.shuffle_runs()
        outcome, note = ci.verifying_status("task/x")
        self.assertEqual(outcome, ci.VERIFYING_RUNNING, self.msg(note))
        for check in pr_checks + push_checks:
            if check["status"] != "completed":
                self.assert_names_run(note, check, names)

        self.reset()
        stuck_a, stuck_b, green = self.names(3)
        _a, pr_checks = self.fake.add_run(
            self.sha, "pull_request", [(stuck_a, "stuck"), (green, "success")])
        _b, push_checks = self.fake.add_run(
            self.sha, "push", [(stuck_b, "stuck"), (green, "success")])
        self.shuffle_runs()
        outcome, note = ci.verifying_status("task/x")
        self.assertEqual(outcome, ci.VERIFYING_STUCK, self.msg(note))
        for check in pr_checks + push_checks:
            if check["status"] != "completed":
                self.assert_names_run(note, check, [stuck_a, stuck_b, green])

    def test_ac3_branch_status_red_and_running_name_event_and_run(self):
        """`branch_status` называет прогон упавшей и идущей проверки.

        Красный сценарий — тот же расклад, что у AC-1 (упавшие проверки в
        pull_request- и push-прогонах): каждая упавшая — в форме
        «<имя>=<заключение> (<событие>, прогон <номер>)», исход `False`.
        Сценарий «ещё идёт» — идущие проверки в двух прогонах: у каждой в
        тексте её событие и номер прогона, исход `False`.

        Ловит мутацию: событие и номер прогона доведены только до
        `verifying_status`, а `branch_status` собирает прежний текст «имя=
        заключение» и «ещё идёт: имя».
        """
        names = self.names(4)
        pr_red, push_red = self.rng.sample(names, 2)
        _a, pr_checks = self.fake.add_run(
            self.sha, "pull_request",
            [(n, self.bad() if n == pr_red else "success") for n in names])
        _b, push_checks = self.fake.add_run(
            self.sha, "push",
            [(n, self.bad() if n == push_red else "success") for n in names])
        self.shuffle_runs()
        green, note = ci.branch_status("task/x")
        self.assertIs(green, False, self.msg(note))
        failed = [c for c in pr_checks + push_checks
                  if c["conclusion"] not in ci.GREEN]
        self.assertEqual(len(failed), 2)
        for check in failed:
            self.assertIn(self.red_form(check), note, self.msg(note))

        self.reset()
        names = self.names(3)
        twin, other, green_name = names
        _a, pr_checks = self.fake.add_run(
            self.sha, "pull_request", [(twin, "running"),
                                       (green_name, "success")])
        _b, push_checks = self.fake.add_run(
            self.sha, "push", [(twin, "success"), (other, "running")])
        self.shuffle_runs()
        green, note = ci.branch_status("task/x")
        self.assertIs(green, False, self.msg(note))
        self.assertEqual(ci.status_kind(note), "running", self.msg(note))
        for check in pr_checks + push_checks:
            if check["status"] != "completed":
                self.assert_names_run(note, check, names)

    def test_ac4_main_line_names_run_on_the_commit_where_check_failed(self):
        """`main_line_status` называет прогон на том коммите линии, где
        проверка упала или идёт.

        Красный сценарий: на голове main проверка A пропущена (а C упала в
        прогоне головы), под головой — промежуточный коммит без проверок,
        ещё глубже — коммит, где A упала в своём прогоне. `note` исхода
        `MAIN_RED` у A называет событие и номер прогона глубокого коммита,
        а не прогона головы; у C — прогона головы. Сценарий «проверки ещё
        идут»: на голове A идёт в pull_request-прогоне, D — в push-прогоне;
        у каждой в `note` исхода `MAIN_RUNNING` её событие и номер прогона.

        Ловит мутацию: прогоны запрашиваются только у опорного коммита
        линии (`sha` головы) — упавшая глубже проверка A подписана прогоном
        головы либо остаётся без события и номера.
        """
        mid, deep = self.new_sha(), self.new_sha()
        self.line = [self.sha, mid, deep]
        a, b, c = self.names(3)
        deep_event = self.rng.choice(("push", "pull_request"))
        head_run, head_checks = self.fake.add_run(
            self.sha, "push", [(a, "skipped"), (b, "success"),
                               (c, self.bad())])
        _d, deep_checks = self.fake.add_run(
            deep, deep_event, [(a, self.bad()), (b, "success")])
        self.shuffle_runs()

        status = ci.main_line_status(self.sha, repo=self.no_git)

        self.assertEqual(status.kind, ci.MAIN_RED, self.msg(status.note))
        failed_deep = next(ch for ch in deep_checks if ch["name"] == a)
        failed_head = next(ch for ch in head_checks if ch["name"] == c)
        self.assert_names_run(status.note, failed_deep, [a, b, c])
        self.assert_names_run(status.note, failed_head, [a, b, c])
        for seg in segments(status.note, [a, b, c]):
            if seg.startswith(a):
                self.assertNotRegex(seg, rf"прогон {head_run['id']}(?!\d)",
                                    self.msg(status.note,
                                             "A подписана прогоном головы"))

        self.reset()
        self.line = [self.sha]
        a, d, green = self.names(3)
        _a, pr_checks = self.fake.add_run(
            self.sha, "pull_request", [(a, "running"), (green, "success")])
        _b, push_checks = self.fake.add_run(
            self.sha, "push", [(d, "running"), (green, "success")])
        self.shuffle_runs()
        status = ci.main_line_status(self.sha, repo=self.no_git)
        self.assertEqual(status.kind, ci.MAIN_RUNNING, self.msg(status.note))
        for check in pr_checks + push_checks:
            if check["status"] != "completed":
                self.assert_names_run(status.note, check, [a, d, green])

    def test_ac5_other_event_is_named_by_its_own_name(self):
        """Прогон события вне push/pull_request назван именем события.

        Единственный прогон коммита — случайное событие из
        `workflow_dispatch`/`schedule`/`repository_dispatch`/`merge_group`
        с упавшей проверкой. Красные тексты `verifying_status` и
        `branch_status` несут «<имя>=<заключение> (<событие>, прогон
        <номер>)» с этим именем события, `note` `main_line_status` —
        событие и номер у упавшей проверки.

        Ловит мутацию: событие сводится к двум известным — всё, что не
        push, подписано «pull_request» (или не подписано вовсе).
        """
        event = self.rng.choice(OTHER_EVENTS)
        names = self.names(3)
        red = self.rng.choice(names)
        _run, checks = self.fake.add_run(
            self.sha, event,
            [(n, self.bad() if n == red else "success") for n in names])
        failed = next(ch for ch in checks if ch["name"] == red)

        outcome, note = ci.verifying_status("task/x")
        self.assertEqual(outcome, ci.VERIFYING_RED, self.msg(note))
        self.assertIn(self.red_form(failed), note, self.msg(note))

        green, note = ci.branch_status("task/x")
        self.assertIs(green, False, self.msg(note))
        self.assertIn(self.red_form(failed), note, self.msg(note))

        status = ci.main_line_status(self.sha, repo=self.no_git)
        self.assertEqual(status.kind, ci.MAIN_RED, self.msg(status.note))
        self.assert_names_run(status.note, failed, names)

    def test_ac6_divergent_outcome_by_event_gets_a_separate_phrase(self):
        """Расхождение исхода одноимённой проверки по событиям — отдельная
        фраза; без расхождения фразы нет.

        Для `verifying_status`, `branch_status` и `main_line_status` на
        одном и том же коммите (те же id прогонов и проверок) разыгрываются
        расклады проверки X: (1) push зелёный, pull_request красный;
        (2) наоборот; (3) красная в обоих; (4) прогон только pull_request,
        красный. Фраза ищется в тексте за вычетом аннотаций проверок
        «(<событие>, прогон <номер>)»: в (1) и (2) остаток называет и push,
        и pull_request, и остатки (1) и (2) различны — фраза говорит, какое
        событие зелёное, а какое красное; в (3) и (4) остаток не называет
        ни одного из событий.

        Ловит мутацию: фраза выводится при любом наличии двух прогонов на
        коммите (появляется и в раскладе «красная в обоих»), либо её текст
        не зависит от того, какое событие зелёное, — остатки (1) и (2)
        совпадают.
        """
        names = self.names(3)
        x = self.rng.choice(names)
        seed = self.rng.randrange(2 ** 32)
        conclusion = self.bad()

        def build(push_x: str | None, pr_x: str) -> None:
            self.reset(seed)
            self.fake.add_run(self.sha, "pull_request",
                              [(n, pr_x if n == x else "success")
                               for n in names])
            if push_x is not None:
                self.fake.add_run(self.sha, "push",
                                  [(n, push_x if n == x else "success")
                                   for n in names])

        readers = {
            "verifying_status": lambda: ci.verifying_status("task/x")[1],
            "branch_status": lambda: ci.branch_status("task/x")[1],
            "main_line_status":
                lambda: ci.main_line_status(self.sha, repo=self.no_git).note,
        }
        layouts = {
            "push зелёный, pull_request красный": ("success", conclusion),
            "push красный, pull_request зелёный": (conclusion, "success"),
            "красная в обоих": (conclusion, conclusion),
            "только pull_request": (None, conclusion),
        }
        for reader, read in readers.items():
            residuals = {}
            for layout, (push_x, pr_x) in layouts.items():
                if reader == "main_line_status" and layout == "красная в обоих":
                    # Main сводит одноимённые проверки коммита в одну
                    # строку; как подписать её двумя прогонами, AC-4 не
                    # фиксирует — расклад проверяется на двух других.
                    continue
                build(push_x, pr_x)
                note = read()
                residuals[layout] = rest = self.residual(note)
                with self.subTest(reader=reader, layout=layout):
                    divergent = layout.startswith("push")
                    for event in ("push", "pull_request"):
                        if divergent:
                            self.assertTrue(
                                mentions(rest, event), self.msg(
                                    note, f"{reader}: фраза о расхождении не "
                                          f"называет {event}"))
                        else:
                            self.assertFalse(
                                mentions(rest, event), self.msg(
                                    note, f"{reader}: фраза о расхождении "
                                          f"при одинаковом исходе ({event})"))
            with self.subTest(reader=reader, layout="(1) против (2)"):
                self.assertNotEqual(
                    residuals["push зелёный, pull_request красный"],
                    residuals["push красный, pull_request зелёный"],
                    f"зерно: {self.seed}\n{reader}: фраза не различает, "
                    f"какое событие зелёное")

    def test_ac7_runs_query_failure_marks_event_undefined_keeps_outcome(self):
        """Сбой запроса прогонов не отменяет статус и не меняет исход.

        Все запросы к GitHub, кроме check-run'ов коммита, отвечают
        ненулевым кодом либо неразборным текстом (вид сбоя — случайный).
        Для красного, идущего и зависшего раскладов `verifying_status`,
        красного и идущего `branch_status` и `main_line_status` исход тот
        же, что при исправном запросе (`VERIFYING_RED`/`False`/`MAIN_RED`,
        `VERIFYING_RUNNING`/`False`/`MAIN_RUNNING`, `VERIFYING_STUCK`), а у
        каждой упавшей, идущей и зависшей проверки — «событие не
        определено».

        Ловит мутацию: сбой запроса прогонов возвращается как «статус CI
        неизвестен» (`VERIFYING_NONE`/«неизвестен»/`MAIN_UNKNOWN`) либо
        проверки печатаются вовсе без пометки — Оператор снова не знает,
        что событие не названо.
        """
        names = self.names(3)
        a, b, green_name = names

        def scenario(states: dict) -> list[dict]:
            self.reset()
            self.fake.broken = "runs"
            _pr, pr_checks = self.fake.add_run(
                self.sha, "pull_request",
                [(a, states["a"]), (green_name, "success")])
            _push, push_checks = self.fake.add_run(
                self.sha, "push", [(b, states["b"]), (green_name, "success")])
            return [c for c in pr_checks + push_checks
                    if c["status"] != "completed"
                    or c["conclusion"] not in ci.GREEN]

        cases = (
            ("verifying красный", {"a": self.bad(), "b": "failure"},
             lambda: ci.verifying_status("task/x"), ci.VERIFYING_RED),
            ("verifying идёт", {"a": "running", "b": "running"},
             lambda: ci.verifying_status("task/x"), ci.VERIFYING_RUNNING),
            ("verifying зависла", {"a": "stuck", "b": "stuck"},
             lambda: ci.verifying_status("task/x"), ci.VERIFYING_STUCK),
            ("branch красный", {"a": self.bad(), "b": "success"},
             lambda: ci.branch_status("task/x"), False),
            ("branch идёт", {"a": "running", "b": "success"},
             lambda: ci.branch_status("task/x"), False),
            ("main красный", {"a": self.bad(), "b": "failure"},
             lambda: tuple(ci.main_line_status(self.sha, repo=self.no_git)
                           [i] for i in (0, 5)), ci.MAIN_RED),
            ("main идёт", {"a": "running", "b": "running"},
             lambda: tuple(ci.main_line_status(self.sha, repo=self.no_git)
                           [i] for i in (0, 5)), ci.MAIN_RUNNING),
        )
        for label, states, read, expected in cases:
            with self.subTest(case=label):
                bad_checks = scenario(states)
                outcome, note = read()
                self.assertEqual(outcome, expected, self.msg(note, label))
                if label.startswith("branch"):
                    self.assertEqual(
                        ci.status_kind(note),
                        "running" if "идёт" in label else "red",
                        self.msg(note, label))
                for check in bad_checks:
                    self.assert_names_run(note, check, names, undefined=True)

    def test_ac8_parsers_keep_outcomes_on_the_new_text(self):
        """Разборщики текста статуса дают прежние исходы на новом тексте.

        Тексты берутся из самих `verifying_status`/`branch_status` в
        раскладах: красный с событиями и фразой о расхождении (push
        зелёный, pull_request красный), красный с «событие не определено»,
        «ещё идёт», «проверка зависла» (с событиями и без), зелёный, а для
        `status_kind` — ещё «статус неизвестен» при сбое check-run'ов.
        `verifying_is_red` истинен только на красных; `red_status_sha` —
        короткий sha коммита на красных и "" на прочих; `status_kind` —
        "red"/"running"/"unknown"; `stuck_check_ids` — ровно id зависших
        check-run'ов, без номеров прогонов; `verifying_head_not_in_origin`
        ложен на красных и идущих.

        Ловит мутацию: номер прогона записан в той же форме, что id
        зависшей проверки («check-run id …»), и попадает в `stuck_check_ids`
        (ci-rerun перезапускает несуществующее задание); фраза о
        расхождении или пометка содержит «не зелёный:»/«ещё идёт»/
        «неизвестен» (например «событие неизвестно») — `verifying_is_red`
        или `status_kind` меняют исход; аннотация вставлена между sha и
        «не зелёный» — `red_status_sha` теряет sha.
        """
        names = self.names(3)
        x, y, green_name = names
        short = self.sha[:8]

        def build(pr: dict, push: dict, broken: str = "") -> list[dict]:
            self.reset()
            self.fake.broken = broken
            _a, pr_checks = self.fake.add_run(self.sha, "pull_request",
                                              list(pr.items()))
            _b, push_checks = self.fake.add_run(self.sha, "push",
                                                list(push.items()))
            self.shuffle_runs()
            return pr_checks + push_checks

        bad = self.bad()
        red_layouts = {
            "красный, расхождение": ({x: bad, green_name: "success"},
                                     {x: "success", green_name: "success"}, ""),
            "красный, событие не определено": (
                {x: bad, green_name: "success"},
                {y: "failure", green_name: "success"}, "runs"),
        }
        for label, (pr, push, broken) in red_layouts.items():
            with self.subTest(case=label):
                build(pr, push, broken)
                outcome, note = ci.verifying_status("task/x")
                self.assertEqual(outcome, ci.VERIFYING_RED, self.msg(note))
                self.assertTrue(ci.verifying_is_red(note), self.msg(note))
                self.assertEqual(ci.red_status_sha(note), short, self.msg(note))
                self.assertFalse(ci.verifying_head_not_in_origin(note),
                                 self.msg(note))
                self.assertEqual(ci.stuck_check_ids(note), [], self.msg(note))
                build(pr, push, broken)
                _green, note = ci.branch_status("task/x")
                self.assertEqual(ci.status_kind(note), "red", self.msg(note))
                self.assertEqual(ci.red_status_sha(note), short, self.msg(note))

        for broken in ("", "runs"):
            with self.subTest(case=f"ещё идёт, сбой={broken or 'нет'}"):
                build({x: "running", green_name: "success"},
                      {x: "success", y: "running"}, broken)
                outcome, note = ci.verifying_status("task/x")
                self.assertEqual(outcome, ci.VERIFYING_RUNNING, self.msg(note))
                self.assertFalse(ci.verifying_is_red(note), self.msg(note))
                self.assertEqual(ci.red_status_sha(note), "", self.msg(note))
                self.assertFalse(ci.verifying_head_not_in_origin(note),
                                 self.msg(note))
                build({x: "running", green_name: "success"},
                      {x: "success", y: "running"}, broken)
                _green, note = ci.branch_status("task/x")
                self.assertEqual(ci.status_kind(note), "running", self.msg(note))

            with self.subTest(case=f"зависла, сбой={broken or 'нет'}"):
                checks = build({x: "stuck", green_name: "success"},
                               {y: "stuck", green_name: "success"}, broken)
                stuck = sorted(str(c["id"]) for c in checks
                               if c["status"] != "completed")
                outcome, note = ci.verifying_status("task/x")
                self.assertEqual(outcome, ci.VERIFYING_STUCK, self.msg(note))
                self.assertEqual(sorted(ci.stuck_check_ids(note)), stuck,
                                 self.msg(note))
                self.assertFalse(ci.verifying_is_red(note), self.msg(note))
                self.assertEqual(ci.red_status_sha(note), "", self.msg(note))

        with self.subTest(case="зелёный"):
            build({x: "success"}, {x: "success", y: "skipped"})
            outcome, note = ci.verifying_status("task/x")
            self.assertEqual(outcome, ci.VERIFYING_GREEN, self.msg(note))
            self.assertFalse(ci.verifying_is_red(note), self.msg(note))
            self.assertEqual(ci.red_status_sha(note), "", self.msg(note))

        with self.subTest(case="статус check-run'ов неизвестен"):
            build({x: bad}, {x: "success"}, "all")
            green, note = ci.branch_status("task/x")
            self.assertIs(green, False, self.msg(note))
            self.assertEqual(ci.status_kind(note), "unknown", self.msg(note))


if __name__ == "__main__":
    unittest.main()
