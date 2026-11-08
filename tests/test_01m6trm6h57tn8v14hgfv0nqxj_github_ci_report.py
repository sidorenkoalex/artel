"""Итог и отчёт junit задания CI у хостинга GitHub: `forge.job_result`, `forge.job_test_report`, `Job.id` check runs, поле `ci_report_artifact`, строка `doctor` об отчёте зелёного коммита базы; прежние итоги GitLab и записей без `report`.

Группа: долгоживущий
Красен до реализации: у реализации GitHub реестра `forge` нет `job_result` и `job_test_report` — обе отвечают «не реализовано для github», `gh` не вызывается; `Job.id` у check runs не заполнен; поле `ci_report_artifact` загрузчику неизвестно, а запись GitHub с `full_suite: ci` отказывает при загрузке; строки `doctor` об отчёте нет; зелены с рождения тесты прежнего поведения — AC-6 (строки записи GitLab, литералы хостинга в `doctor`), AC-8 и отказ значения неверного типа AC-5 (неизвестное поле отказывает с его именем и сейчас).

Стенд — песочница путей `config` (`tmp_root`, для приёмки —
`light_transition`): `config.TARGETS` — файл во временном каталоге теста с
вымышленной записью проекта (или вымышленной записью артели), клон проекта
— `tests.sandbox.make_project_repo`. Программа `gh` подменена исполняемым
файлом в начале PATH: он отвечает по правилам `rules.json` (регулярное
выражение по строке аргументов → JSON, двоичный файл, поток байтов, сон,
запись своего pid) и пишет в `calls.jsonl` аргументы и переменные
`GH_REPO`/`GH_TOKEN` каждого вызова. Ответы — пути `gh api` раздела
критериев SPEC: check runs коммита, задание прогона (`run_id`), артефакты
прогона (с фильтром `name=`, если он задан в запросе), скачивание архива,
прогоны ветки базы; дополнительно — задания прогона. Транспорт GitLab —
шпион, который отказывает и записывает вызов. Архивы и отчёты junit
собираются в тесте во временном каталоге. Сети нет: адреса — на
`localhost`, `gh` подменён.

Связки, которые держит файл: «запись `targets.yaml` песочницы — `forge` —
`ci.gh`/двоичный вызов `gh` — внешний процесс»; приёмка — узел
`acceptance.acceptance_suite` с источниками трёх условий принятия итога CI,
подменёнными публичными именами (как у
`tests/test_01m5xzskk8gzteca2kwafhe029_ci_full_suite.py`); строки `doctor` —
`doctor.project_entry_checks` + `doctor.project_checks.component_checks`.

Имена проектов, заданий, номера check runs и прогонов, тесты отчёта —
случайные на каждом запуске; зерно печатается и входит в текст провала.
"""
import ast
import dataclasses
import inspect
import json
import os
import random
import re
import signal
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from xml.sax.saxutils import quoteattr

import pytest

from orchestrator import (acceptance, ci, config, doctor, forge, gitlab_adapter,
                          runner, store, targets, workspace)
from tests.sandbox import fake_keychain_token, make_project_repo

LETTERS = "abcdefghijkmnopqrstuvwxyz"
ARTEL = config.DEFAULT_TARGET
OUTCOMES = ("success", "failed", "error", "skipped")
T0 = datetime(2026, 11, 7, 10, 0, 0, tzinfo=timezone.utc)
# Слова причины отказа по пределу времени и по размеру (AC-3): причина
# называет случай.
TIME_WORDS = re.compile(r"(?i)врем|timeout|тайм-?аут")
SIZE_WORDS = re.compile(r"(?i)размер|байт|size|объ[её]м|[КМ]Б\b")

FAKE_GH = r'''#!@PYTHON@
import json, os, re, sys, time
here = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
joined = " ".join(argv)
with open(os.path.join(here, "calls.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": argv, "gh_repo": os.environ.get("GH_REPO"),
                        "gh_token": os.environ.get("GH_TOKEN"),
                        "pid": os.getpid()}) + "\n")
with open(os.path.join(here, "rules.json"), encoding="utf-8") as f:
    rules = json.load(f)
page = re.search(r"[?&]page=([0-9]+)", joined)
page = int(page.group(1)) if page else 1
wanted = re.search(r"[?&]name=([^&\s]+)", joined)
for rule in rules:
    if not re.search(rule["pattern"], joined):
        continue
    if rule.get("pidfile"):
        with open(rule["pidfile"], "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    out = sys.stdout.buffer
    if "json" in rule:
        payload = dict(rule["json"])
        key = rule.get("list_key")
        if key:
            items = payload[key] if page == 1 else []
            if wanted and key == "artifacts":
                items = [i for i in items if i.get("name") == wanted.group(1)]
                payload["total_count"] = len(items)
            payload[key] = items
        out.write(json.dumps(payload).encode("utf-8"))
    if "file" in rule:
        with open(rule["file"], "rb") as f:
            out.write(f.read())
    left = rule.get("stream", 0)
    chunk = b"\0" * 65536
    while left > 0:
        n = min(left, len(chunk))
        out.write(chunk[:n])
        left -= n
    out.flush()
    if "sleep" in rule:
        time.sleep(rule["sleep"])
    sys.exit(rule.get("code", 0))
sys.stderr.write("gh: Not Found (HTTP 404)\n")
sys.exit(1)
'''


# --- окружение сценария ---

def word(rng: random.Random, prefix: str, size: int = 6) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def junit_xml(cases: list) -> bytes:
    """Отчёт junit: `cases` — [(classname, name, исход)], исход из
    `OUTCOMES`; `success` — `testcase` без вложенных элементов."""
    child = {"failed": '<failure message="boom">трасса</failure>',
             "error": '<error message="oops">трасса</error>',
             "skipped": '<skipped message="нет"/>', "success": ""}
    rows = "".join(f'<testcase classname={quoteattr(c)} name={quoteattr(n)} '
                   f'time="0.01">{child[o]}</testcase>\n' for c, n, o in cases)
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<testsuites>'
            f'<testsuite name="pytest" tests="{len(cases)}">\n{rows}'
            f'</testsuite></testsuites>\n').encode("utf-8")


def pid_alive(pid: int) -> bool:
    """Процесс `pid` есть; завершённый потомок этого процесса пожинается."""
    try:
        done, _status = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class GhWorld:
    """Подменная программа `gh` и её ответы."""

    def __init__(self, root: Path, rng: random.Random, seed: int):
        self.rng = rng
        self.seed = seed
        self.bin = root / ".artel" / "fake-gh"
        self.bin.mkdir(parents=True, exist_ok=True)
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH.replace("@PYTHON@", sys.executable),
                      encoding="utf-8")
        gh.chmod(0o755)
        self.files = root / "fixture-files"
        self.files.mkdir(parents=True, exist_ok=True)
        self.rules: list = []
        self.pidfiles: list = []
        self.used_ids: set = set()
        self.owner = word(rng, "own", 4)
        self.repo = word(rng, "rep", 4)
        self.flush()

    def new_id(self, low: int = 1000, high: int = 9_000_000) -> int:
        while True:
            value = self.rng.randrange(low, high)
            if value not in self.used_ids:
                self.used_ids.add(value)
                return value

    def flush(self) -> None:
        (self.bin / "rules.json").write_text(json.dumps(self.rules),
                                             encoding="utf-8")

    def add(self, pattern: str, **rule) -> None:
        self.rules.append(dict(rule, pattern=pattern))
        self.flush()

    def drop(self, pattern: str) -> None:
        self.rules = [r for r in self.rules if r["pattern"] != pattern]
        self.flush()

    def calls(self) -> list:
        path = self.bin / "calls.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def clear_calls(self) -> None:
        (self.bin / "calls.jsonl").unlink(missing_ok=True)

    def pidfile(self) -> Path:
        path = self.bin / f"pid-{len(self.pidfiles)}"
        self.pidfiles.append(path)
        return path

    def kill_leftovers(self) -> None:
        for path in self.pidfiles:
            try:
                pid = int(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            pid_alive(pid)

    # --- ответы ---

    def check_run(self, name: str, run_id: int, *, cid: int | None = None,
                  status: str = "completed", conclusion: str | None = "success",
                  start: datetime | None = None) -> dict:
        cid = self.new_id() if cid is None else cid
        start = start or T0 + timedelta(minutes=self.rng.randrange(0, 600))
        done = status == "completed"
        url = (f"https://localhost/{self.owner}/{self.repo}/actions/runs/"
               f"{run_id}/job/{cid}")
        return {"id": cid, "name": name, "status": status,
                "conclusion": conclusion if done else None,
                "started_at": stamp(start),
                "completed_at": stamp(start + timedelta(minutes=5)) if done else None,
                "details_url": url, "html_url": url, "run_id": run_id}

    def commit(self, sha: str, runs: list) -> None:
        """Check runs коммита и задания прогонов (`actions/jobs/<id>`,
        `actions/runs/<run_id>/jobs`)."""
        pattern = f"commits/{sha}/check-runs"
        self.drop(pattern)
        self.add(pattern, json={"total_count": len(runs),
                                "check_runs": [self.public(r) for r in runs]},
                 list_key="check_runs")
        for run in runs:
            job = {"id": run["id"], "run_id": run["run_id"], "name": run["name"],
                   "status": run["status"], "conclusion": run["conclusion"],
                   "started_at": run["started_at"],
                   "completed_at": run["completed_at"], "head_sha": sha,
                   "run_attempt": 1}
            jpattern = f"actions/jobs/{run['id']}(?![0-9])"
            self.drop(jpattern)
            self.add(jpattern, json=job)
        by_run: dict = {}
        for run in runs:
            by_run.setdefault(run["run_id"], []).append(run)
        for run_id, mine in by_run.items():
            rpattern = f"actions/runs/{run_id}/jobs"
            self.drop(rpattern)
            jobs = [{"id": r["id"], "run_id": run_id, "name": r["name"],
                     "status": r["status"], "conclusion": r["conclusion"],
                     "started_at": r["started_at"],
                     "completed_at": r["completed_at"], "head_sha": sha}
                    for r in mine]
            self.add(rpattern, json={"total_count": len(jobs), "jobs": jobs},
                     list_key="jobs")

    @staticmethod
    def public(run: dict) -> dict:
        return {k: v for k, v in run.items() if k != "run_id"}

    def artifacts(self, run_id: int, items: list) -> None:
        pattern = f"actions/runs/{run_id}/artifacts"
        self.drop(pattern)
        self.add(pattern, json={"total_count": len(items), "artifacts": items},
                 list_key="artifacts")

    def artifact(self, run_id: int, name: str, created: datetime, *,
                 members: dict | None = None, raw: bytes | None = None,
                 expired: bool = False, size: int | None = None,
                 zip_rule: dict | None = None) -> dict:
        """Артефакт прогона и ответ на его скачивание: архив из `members`
        (имя → байты) либо байты `raw`; `zip_rule` — особый ответ
        скачивания (поток, сон)."""
        aid = self.new_id()
        path = self.files / f"artifact-{aid}.zip"
        if raw is not None:
            path.write_bytes(raw)
        else:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                for member, data in (members or {}).items():
                    zf.writestr(zipfile.ZipInfo(member, (2026, 11, 7, 10, 0, 0)),
                                data, compress_type=zipfile.ZIP_DEFLATED)
        real = path.stat().st_size
        pattern = f"actions/artifacts/{aid}/zip"
        self.drop(pattern)
        self.add(pattern, **(zip_rule or {"file": str(path)}))
        return {"id": aid, "name": name, "expired": expired,
                "size_in_bytes": real if size is None else size,
                "created_at": stamp(created),
                "archive_download_url": (f"https://localhost/api/v3/repos/"
                                         f"{self.owner}/{self.repo}/actions/"
                                         f"artifacts/{aid}/zip"),
                "workflow_run": {"id": run_id}}

    def green_runs(self, base: str, runs: list) -> None:
        """Прогоны workflow ветки `base` со статусом success: [(run_id, sha)]."""
        pattern = r"actions/runs(\?|\s|$)"
        self.drop(pattern)
        items = [{"id": run_id, "head_sha": sha, "head_branch": base,
                  "status": "completed", "conclusion": "success",
                  "event": "push", "name": "CI",
                  "created_at": stamp(T0 + timedelta(hours=10 - i))}
                 for i, (run_id, sha) in enumerate(runs)]
        self.add(pattern, json={"total_count": len(items),
                                "workflow_runs": items},
                 list_key="workflow_runs")


def component_lines(job: str, artifact: str | None = None,
                    mode: str | None = "ci", extra: dict | None = None) -> list:
    fields = {
        "command": "[python3, -m, pytest]",
        "report": "junit-xml",
        "long_lived_dir": "tests",
        "long_lived_name": "test_<id>_<name>.py",
        "weakening_scope": "[tests/**]",
        "mutation_claim_scope": "[tests/test_*.py]",
    }
    if mode is not None:
        fields["full_suite"] = mode
        fields["ci_job"] = job
    if artifact is not None:
        fields["ci_report_artifact"] = artifact
    fields.update(extra or {})
    return [f"        {k}: {v}" for k, v in fields.items()]


def without_report(sc) -> list:
    """Поля компонента без `report`, `full_suite` и `ci_job`."""
    return [line for line in component_lines(sc.job, mode=None)
            if not line.strip().startswith("report:")]


class Scene:
    """Запись проекта GitHub (или артели) в `targets.yaml` песочницы,
    подменная `gh`, шпион транспорта GitLab."""

    def __init__(self, sandbox, monkeypatch, *, artel: bool = False):
        self.sandbox = sandbox
        self.root = Path(sandbox.root)
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.gh = GhWorld(self.root, self.rng, self.seed)
        self.artel = artel
        self.name = ARTEL if artel else word(self.rng, "ghp")
        self.comp = word(self.rng, "c", 4)
        self.base = word(self.rng, "base-", 4)
        self.job = f"{self.rng.choice(('full-suite', 'pytest', 'tests'))}-{self.rng.randrange(1, 99)}"
        self.slot = f"{self.name}-slot-{self.rng.randrange(100, 999)}"
        self.url = f"https://localhost/{self.gh.owner}/{self.gh.repo}"
        self.sha = f"{self.rng.getrandbits(160):040x}"
        self.gitlab_calls: list = []
        monkeypatch.setenv("PATH", f"{self.gh.bin}{os.pathsep}{os.environ.get('PATH', '')}")
        for env in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST"):
            monkeypatch.delenv(env, raising=False)

        def transport(*args, **kwargs):
            self.gitlab_calls.append(args)
            raise OSError("песочница: транспорт GitLab не вызывается")

        monkeypatch.setattr(gitlab_adapter, "transport", transport)
        monkeypatch.setattr(runner, "in_role_environment", lambda env=None: False)
        self.write()
        if not artel:
            make_project_repo(self.name, origin=False)

    def note(self, extra: str = "") -> str:
        return f"зерно: {self.seed}; проект {self.name}; задание {self.job}; {extra}"

    def write(self, *, artifact: str | None = None, mode: str | None = "ci",
              comps: list | None = None, forge_name: str = "github",
              gate: str = "operator") -> None:
        """Запись в `config.TARGETS`; `comps` — [(имя, строки полей)]."""
        comps = comps or [(self.comp, component_lines(self.job, artifact, mode))]
        if self.artel:
            head = [f"  {ARTEL}:", "    forge: github",
                    f"    url: file:///nonexistent/{ARTEL}",
                    f"    base: {config.MAIN_BRANCH}",
                    f"    token_slot: {ARTEL}-token"]
        else:
            head = [f"  {self.name}:", f"    forge: {forge_name}",
                    f"    url: {self.url}", f"    base: {self.base}",
                    f"    token_slot: {self.slot}"]
        lines = head + ["    no_paths: []", "    project_skills: []",
                        f"    merge_gate: {gate}", "    components:"]
        for comp, fields in comps:
            lines += [f"      {comp}:", *fields]
        text = "targets:\n"
        if not self.artel:
            text += (f"  {ARTEL}:\n    forge: github\n"
                     f"    url: file:///nonexistent/{ARTEL}\n"
                     f"    base: {config.MAIN_BRANCH}\n"
                     f"    token_slot: {ARTEL}-token\n    no_paths: []\n"
                     f"    project_skills: []\n    merge_gate: operator\n"
                     f"    test_profile:\n      command: [python3, -m, pytest]\n"
                     f"      long_lived_dir: tests\n"
                     f"      long_lived_name: test_<id>_<name>.py\n"
                     f"      weakening_scope: [tests/**/*.py]\n"
                     f"      mutation_claim_scope: [tests/test_*.py]\n"
                     f"      report: junit-xml\n      install: []\n")
        config.TARGETS.write_text(text + "\n".join(lines) + "\n", encoding="utf-8")

    def cases(self, n: int | None = None, kinds=OUTCOMES) -> list:
        n = n if n is not None else self.rng.randrange(4, 12)
        out = [(f"pkg.{word(self.rng, 'mod_', 4)}.Case{i}",
                word(self.rng, "test_", 5), kinds[i % len(kinds)])
               for i in range(n)]
        self.rng.shuffle(out)
        return out

    @staticmethod
    def outcomes(cases: list) -> dict:
        return {f"{c}::{n}": o for c, n, o in cases}

    def attempt(self, *, conclusion: str = "success", status: str = "completed",
                cases: list | None = None, artifact: str = "junit",
                run_id: int | None = None, cid: int | None = None) -> dict:
        """Исполненная попытка задания: check run и годный артефакт отчёта
        в его прогоне."""
        run_id = self.gh.new_id() if run_id is None else run_id
        run = self.gh.check_run(self.job, run_id, cid=cid, status=status,
                                conclusion=conclusion)
        cases = self.cases() if cases is None else cases
        start = datetime.strptime(run["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        art = self.gh.artifact(run_id, artifact, start + timedelta(minutes=4),
                               members={"report.xml": junit_xml(cases)})
        return {"run": run, "run_id": run_id, "cases": cases, "artifacts": [art],
                "start": start}

    def noise(self) -> dict:
        return self.gh.check_run(word(self.rng, "lint-", 3), self.gh.new_id())

    def report(self, sha: str | None = None, job: str | None = None):
        return forge.job_test_report(self.name, sha or self.sha, job or self.job)

    def result(self, sha: str | None = None, job: str | None = None):
        return forge.job_result(self.name, sha or self.sha, job or self.job)


@pytest.fixture
def scene(tmp_root, monkeypatch):
    sc = Scene(tmp_root, monkeypatch)
    yield sc
    sc.gh.kill_leftovers()


@pytest.fixture
def artel_scene(tmp_root, monkeypatch):
    sc = Scene(tmp_root, monkeypatch, artel=True)
    yield sc
    sc.gh.kill_leftovers()


def assert_entry_calls(sc: Scene) -> None:
    """Каждый вызов `gh` — `gh api` с `GH_REPO` записи и токеном её слота
    (внешняя запись) либо без `GH_REPO` (артель)."""
    calls = sc.gh.calls()
    assert calls, sc.note("gh не вызван")
    for call in calls:
        if sc.artel:
            assert call["gh_repo"] is None, sc.note(f"GH_REPO у вызова артели: {call}")
        else:
            assert call["gh_repo"] == f"{sc.gh.owner}/{sc.gh.repo}", \
                sc.note(f"вызов без GH_REPO записи: {call}")
            assert call["gh_token"] == fake_keychain_token(sc.slot), \
                sc.note(f"вызов без токена слота записи: {call}")


def zip_calls(sc: Scene) -> list:
    return [c for c in sc.gh.calls()
            if any(re.search(r"actions/artifacts/[0-9]+/zip", a) for a in c["argv"])]


# --- AC-1 ---

def skipped_twin_scene(sc: Scene) -> dict:
    """Два check run задания: исполненный (артефакт с отчётом в своём
    прогоне) и пропущенный условием (в другом прогоне, со своим отчётом);
    номер пропущенного больше номера исполненного."""
    conclusion = sc.rng.choice(("success", "failure"))
    ids = sorted(sc.gh.new_id() for _ in range(2))
    done = sc.attempt(conclusion=conclusion, cid=ids[0])
    skip_run = sc.gh.new_id()
    skipped = sc.gh.check_run(sc.job, skip_run, cid=ids[1], conclusion="skipped")
    decoy = sc.gh.artifact(skip_run, "junit", T0, members={
        "report.xml": junit_xml(sc.cases(3, ("failed",)))})
    sc.gh.artifacts(done["run_id"], done["artifacts"])
    sc.gh.artifacts(skip_run, [decoy])
    runs = [done["run"], skipped, sc.noise()]
    sc.rng.shuffle(runs)
    sc.gh.commit(sc.sha, runs)
    done["expected"] = "success" if conclusion == "success" else "failed"
    return done


def check_skipped_twin(sc: Scene) -> None:
    done = skipped_twin_scene(sc)
    result = sc.result()
    report = sc.report()
    note = sc.note(f"результат {result}; отчёт {report}")
    assert result.status == done["expected"], note
    assert report.outcomes == Scene.outcomes(done["cases"]), note
    assert set(report.outcomes.values()) <= set(ci.JOB_REPORT_OUTCOMES), note
    assert all("::" in key for key in report.outcomes), note
    assert zip_calls(sc), sc.note("архив артефакта не скачивался")
    assert sc.gitlab_calls == [], sc.note(f"транспорт GitLab вызван: {sc.gitlab_calls}")
    assert_entry_calls(sc)


def test_ac1_executed_attempt_over_skipped_twin(scene):
    """Исполненный check run задания берётся вместо пропущенного условием — и статус, и отчёт; каждый вызов `gh` несёт `GH_REPO` и токен записи.

    Сценарий: у коммита два check run с именем задания — исполненный
    (`success` или `failure` по зерну) с артефактом `junit` в своём прогоне
    и пропущенный (`skipped`) в другом прогоне, у которого свой артефакт
    `junit` с иным отчётом; номер пропущенного больше номера исполненного.
    `forge.job_result` даёт статус исполненного, `forge.job_test_report` —
    его отчёт: ключи `<classname>::<name>`, исходы из
    `ci.JOB_REPORT_OUTCOMES`. Подменная `gh` записала каждый вызов: у
    всех, включая двоичное скачивание архива, `GH_REPO=<владелец>/<имя>`
    из `url` записи и `GH_TOKEN` слота записи. Транспорт GitLab не вызван.

    Ловит мутацию: попытка — наибольший номер без учёта `skipped` (статус
    `skipped`, отчёт пропущенного прогона); двоичный вызов скачивания без
    `GH_REPO` (`subprocess` с `gh api …/zip` без окружения записи) — у
    вызова в журнале `gh_repo` пуст; вызов через `forge.github_call` или
    транспорт GitLab.
    """
    check_skipped_twin(scene)


def test_ac1_artel_entry_reads_without_gh_repo(artel_scene):
    """Тот же сценарий у вымышленной записи артели: статус и отчёт прочитаны, отказа «артель» нет, ни у одного вызова `gh` нет `GH_REPO`.

    Сценарий: `config.TARGETS` — файл во временном каталоге теста с
    вымышленной записью артели (компонент с `report`, `full_suite: ci`,
    `ci_job`), программа `gh` подменена.

    Ловит мутацию: чтение через `forge.github_call` — отказ «артель: адреса
    её форджа у пульта нет», статус `None`; либо вход `gh` с `repo` клона и
    для артели — у вызова в журнале `GH_REPO`.
    """
    check_skipped_twin(artel_scene)


def test_ac1_running_latest_attempt_is_running(scene):
    """Две исполненные попытки задания, у большего номера состояние `in_progress` — `job_result` даёт `running`, а не итог меньшего номера.

    Ловит мутацию: попытка выбирается среди завершённых check runs (или по
    порядку в ответе) — статус `success`/`failed` прежней попытки вместо
    `running`.
    """
    sc = scene
    low, high = sorted(sc.gh.new_id() for _ in range(2))
    old = sc.attempt(conclusion=sc.rng.choice(("success", "failure")), cid=low)
    new = sc.gh.check_run(sc.job, old["run_id"], cid=high, status="in_progress")
    sc.gh.artifacts(old["run_id"], old["artifacts"])
    runs = [new, old["run"], sc.noise()]
    sc.rng.shuffle(runs)
    sc.gh.commit(sc.sha, runs)
    result = sc.result()
    assert result.status == "running", sc.note(f"результат {result}")
    assert sc.gitlab_calls == [], sc.note(f"транспорт GitLab вызван: {sc.gitlab_calls}")
    assert_entry_calls(sc)


# --- AC-2 ---

@pytest.mark.parametrize("others", [0, 2])
def test_ac2_missing_job_names_job(scene, others):
    """У коммита нет check run с именем задания — `JobResult(None, причина)`, причина называет задание.

    Сценарий: у коммита ни одного check run (`others` = 0) либо два check
    run других имён.

    Ловит мутацию: отсутствие задания читается как пустой статус `""` или
    `skipped`; причина без имени задания.
    """
    sc = scene
    sc.gh.commit(sc.sha, [sc.noise() for _ in range(others)])
    result = sc.result()
    note = sc.note(f"результат {result}")
    assert result.status is None, note
    assert sc.job in result.reason, note


# --- AC-3 ---

def make_report_scene(sc: Scene, *, artifacts=None, members=None, raw=None,
                      zip_rule=None, size=None, expired=False) -> dict:
    """Одна исполненная попытка задания; артефакты прогона — `artifacts`
    (функция от попытки) или один годный `junit` из `members`/`raw`."""
    run_id = sc.gh.new_id()
    run = sc.gh.check_run(sc.job, run_id)
    start = datetime.strptime(run["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    att = {"run": run, "run_id": run_id, "start": start}
    if artifacts is not None:
        items = artifacts(att)
    else:
        if members is None and raw is None:
            members = {"report.xml": junit_xml(sc.cases())}
        items = [sc.gh.artifact(run_id, "junit", start + timedelta(minutes=4),
                                members=members, raw=raw, zip_rule=zip_rule,
                                size=size, expired=expired)]
    sc.gh.artifacts(run_id, items)
    sc.gh.commit(sc.sha, [run, sc.noise()])
    return att


def big_noise(rng: random.Random, n: int) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(n))


def setup_case(sc: Scene, case: str, monkeypatch) -> tuple:
    """Готовит случай AC-3; (шаблон слов причины, строка для причины)."""
    rng = sc.rng
    good = {"report.xml": junit_xml(sc.cases())}
    if case == "no_artifact":
        make_report_scene(sc, artifacts=lambda a: [])
        return re.compile(r"(?i)артефакт"), None
    if case == "expired":
        make_report_scene(sc, expired=True)
        return re.compile(r"(?i)срок|expired|ист[её]к|хранени"), None
    if case == "created_before_start":
        make_report_scene(sc, artifacts=lambda a: [sc.gh.artifact(
            a["run_id"], "junit", a["start"] - timedelta(seconds=1),
            members=good)])
        return re.compile(r"(?i)артефакт"), None
    if case == "corrupt_archive":
        make_report_scene(sc, raw=b"PK\x03\x04" + big_noise(rng, 300))
        return re.compile(r"(?i)архив|zip"), None
    if case == "two_fit_artifacts":
        make_report_scene(sc, artifacts=lambda a: [
            sc.gh.artifact(a["run_id"], "junit", a["start"] + timedelta(minutes=m),
                           members=good) for m in (1, 3)])
        return re.compile(r"(?i)больше одного|несколько|два|двух|\b2\b|неоднознач"), None
    if case == "zero_xml":
        make_report_scene(sc, members={"readme.txt": b"no report"})
        return re.compile(r"(?i)xml"), None
    if case == "two_xml":
        make_report_scene(sc, members={"a/report.xml": junit_xml(sc.cases()),
                                       "b/other.xml": junit_xml(sc.cases())})
        return re.compile(r"(?i)xml"), None
    if case == "path_outside":
        evil = rng.choice(("../report.xml", "/report.xml", "x/../../report.xml"))
        make_report_scene(sc, members={evil: junit_xml(sc.cases())})
        return re.compile(r"(?i)пут[ьиюём]|path|вне каталог|за предел"), None
    if case in ("archive_too_big", "size_understated"):
        monkeypatch.setattr(config, "CI_REPORT_ARCHIVE_MAX_BYTES", 10_000,
                            raising=False)
        monkeypatch.setattr(config, "CI_REPORT_UNPACKED_MAX_BYTES", 50_000_000,
                            raising=False)
        members = dict(good)
        members["blob.bin"] = big_noise(rng, 60_000)
        run_id = sc.gh.new_id()
        run = sc.gh.check_run(sc.job, run_id)
        start = datetime.strptime(run["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        path = sc.gh.files / f"stored-{run_id}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
            for member, data in members.items():
                zf.writestr(member, data)
        size = 100 if case == "size_understated" else None
        art = sc.gh.artifact(run_id, "junit", start + timedelta(minutes=4),
                             raw=path.read_bytes(), size=size)
        sc.gh.artifacts(run_id, [art])
        sc.gh.commit(sc.sha, [run, sc.noise()])
        return SIZE_WORDS, None
    if case == "unpacked_too_big":
        monkeypatch.setattr(config, "CI_REPORT_ARCHIVE_MAX_BYTES", 50_000,
                            raising=False)
        monkeypatch.setattr(config, "CI_REPORT_UNPACKED_MAX_BYTES", 100_000,
                            raising=False)
        cases = [(f"pkg.mod.Case{i}", f"test_{i:06d}", "success") for i in range(4000)]
        make_report_scene(sc, members={"report.xml": junit_xml(cases)})
        return SIZE_WORDS, None
    if case == "download_timeout":
        monkeypatch.setattr(config, "CI_REPORT_DOWNLOAD_TIMEOUT_SEC", 1,
                            raising=False)
        make_report_scene(sc, zip_rule={"sleep": 5, "pidfile": str(sc.gh.pidfile())})
        return TIME_WORDS, None
    if case == "duplicate_key":
        cls, name = f"pkg.{word(rng, 'm', 4)}.Case", word(rng, "test_", 5)
        cases = sc.cases(3, ("success",))
        dup = [(cls, name, "failed"), *cases, (cls, name, "success")]
        make_report_scene(sc, members={"report.xml": junit_xml(dup)})
        return None, f"{cls}::{name}"
    if case in ("zero_components", "two_components"):
        if case == "zero_components":
            sc.write(comps=[(sc.comp, component_lines(word(rng, "other-", 4)))])
        else:
            comps = []
            for i in range(2):
                comp = f"{sc.comp}{i}"
                comps.append((comp, component_lines(sc.job, extra={
                    "paths": f"[^{comp}/]",
                    "long_lived_dir": f"{comp}/tests",
                })))
            sc.write(comps=comps)
        make_report_scene(sc)
        return re.compile(r"(?i)компонент.*" + re.escape(sc.job) + "|"
                          + re.escape(sc.job) + r".*компонент"), None
    raise AssertionError(case)


REFUSAL_CASES = [
    "no_artifact", "expired", "created_before_start", "corrupt_archive",
    "two_fit_artifacts", "zero_xml", "two_xml", "path_outside",
    "archive_too_big", "size_understated", "unpacked_too_big",
    "download_timeout", "duplicate_key", "zero_components", "two_components"]


def tree_snapshot(root: Path, skip: tuple) -> set:
    return {str(p.relative_to(root)) for p in root.rglob("*")
            if not any(p == s or s in p.parents for s in skip)}


@pytest.mark.parametrize("case", REFUSAL_CASES)
def test_ac3_unfit_report_refused_without_leftovers(scene, case, monkeypatch):
    """Каждый негодный случай отчёта — `TestReport(None, причина)` с названным случаем; вне временного каталога файлов не появилось, временный каталог удалён.

    Случаи: артефакта нет; срок хранения истёк; единственный артефакт
    создан до `started_at` попытки; архив повреждён; два годных артефакта;
    ноль и два файла `*.xml`; путь в архиве вне каталога (`../`, `/`,
    `x/../../`); архив больше `CI_REPORT_ARCHIVE_MAX_BYTES` — по
    фактическим байтам и при заниженном `size_in_bytes`; содержимое после
    распаковки больше `CI_REPORT_UNPACKED_MAX_BYTES` (обе константы
    подменены); `gh` при скачивании спит дольше подменённого
    `CI_REPORT_DOWNLOAD_TIMEOUT_SEC` (1 с) — процесс `gh` после вызова снят;
    ключ `<classname>::<name>` дважды — сначала с `failure`, затем без
    вложенных элементов; ноль и два компонента записи с `ci_job` задания.
    Причина сверяется по словам случая (артефакт; срок; архив/zip; xml;
    путь; размер; время; компонент вместе с именем задания) либо по самому
    ключу-повтору. Каталог
    временных файлов (`tempfile.tempdir`) подменён пустым каталогом
    песочницы, текущий каталог — другим пустым: после вызова оба пусты, а
    дерево песочницы (кроме каталога подменной `gh`) не изменилось.

    Ловит мутацию: нет проверки путей до распаковки (`zipfile` молча снимает
    `..` — отчёт разобран, `outcomes` не `None`); окно `created_at` не
    сверяется (артефакт до `started_at` разобран); размер сверяется по
    `size_in_bytes`, а не по полученным байтам; повтор ключа перезаписывает
    исход; по пределу времени процесс `gh` не снят (pid жив); каталог
    распаковки не удалён (в подменённом `tempfile.tempdir` остались файлы).
    """
    sc = scene
    words, needle = setup_case(sc, case, monkeypatch)
    watch = sc.root / "tempdir-watch"
    watch.mkdir()
    cwd = sc.root / "cwd-watch"
    cwd.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(watch))
    monkeypatch.chdir(cwd)
    before = tree_snapshot(sc.root, (sc.gh.bin, watch, cwd))
    report = sc.report()
    after = tree_snapshot(sc.root, (sc.gh.bin, watch, cwd))
    note = sc.note(f"случай {case}; отчёт {report}")
    assert report.outcomes is None, note
    assert report.reason, note
    if needle is not None:
        assert needle in report.reason, note
    else:
        assert words.search(report.reason), note
    assert list(watch.iterdir()) == [], sc.note(f"{case}: {list(watch.rglob('*'))}")
    assert list(cwd.iterdir()) == [], sc.note(f"{case}: {list(cwd.rglob('*'))}")
    assert after == before, sc.note(f"{case}: новые файлы {sorted(after - before)}")
    for path in sc.gh.pidfiles:
        if path.exists():
            pid = int(path.read_text(encoding="utf-8"))
            assert not pid_alive(pid), sc.note(f"{case}: процесс gh {pid} жив")


def test_ac3_size_limit_trips_while_reading_stream(scene, monkeypatch):
    """Поток скачивания больше предела размера при живом процессе `gh` — отказ по размеру раньше предела времени, процесс `gh` снят.

    Сценарий: `CI_REPORT_ARCHIVE_MAX_BYTES` — 1 КБ,
    `CI_REPORT_DOWNLOAD_TIMEOUT_SEC` — 3 с; подменная `gh` при скачивании
    пишет свой pid, выдаёт поток 1 МБ и, не закрывая вывод, спит 5 с.
    `forge.job_test_report` возвращается раньше 3 с, причина называет
    размер и не называет время, процесса с записанным pid после вызова нет.

    Ловит мутацию: `subprocess.run(capture_output=True, timeout=…)` и сверка
    длины по `TimeoutExpired` — вызов ждёт весь предел времени (возврат
    позже 3 с) и называет время; поток читается целиком без снятия
    процесса — pid жив.
    """
    sc = scene
    monkeypatch.setattr(config, "CI_REPORT_ARCHIVE_MAX_BYTES", 1024, raising=False)
    monkeypatch.setattr(config, "CI_REPORT_DOWNLOAD_TIMEOUT_SEC", 3, raising=False)
    pidfile = sc.gh.pidfile()
    make_report_scene(sc, zip_rule={"stream": 1 << 20, "sleep": 5,
                                    "pidfile": str(pidfile)})
    started = time.monotonic()
    report = sc.report()
    elapsed = time.monotonic() - started
    note = sc.note(f"отчёт {report}; {elapsed:.2f} с")
    assert report.outcomes is None, note
    assert elapsed < 3, note
    assert SIZE_WORDS.search(report.reason), note
    assert not TIME_WORDS.search(report.reason), note
    assert pidfile.exists(), sc.note("gh скачивания не запускался")
    pid = int(pidfile.read_text(encoding="utf-8"))
    assert not pid_alive(pid), sc.note(f"процесс gh {pid} жив")


# --- AC-4 ---

STATUS_TABLE = [
    ("completed", "success", "success"),
    ("completed", "failure", "failed"),
    ("completed", "timed_out", "failed"),
    ("completed", "cancelled", "canceled"),
    ("completed", "skipped", "skipped"),
    ("completed", "neutral", None),
    ("completed", "action_required", None),
    ("completed", "stale", None),
    ("queued", None, "running"),
    ("in_progress", None, "running"),
    ("waiting", None, "running"),
    ("pending", None, "running"),
    ("requested", None, "running"),
    ("completed", "invented", None),
    ("invented", None, None),
]


def odd_value(sc: Scene, value: str) -> str:
    return word(sc.rng, "vymysel-", 5) if value == "invented" else value


@pytest.mark.parametrize("status,conclusion,expected", STATUS_TABLE)
def test_ac4_check_run_values_map_to_job_status(scene, status, conclusion, expected):
    """Заключение и состояние check run переводятся в статус `JobResult` по таблице требования 2; негодное значение — статус вне `ci.JOB_FINISHED` и не `running`, причина называет значение.

    Сценарий: у коммита единственный check run задания с состоянием и
    заключением из строки таблицы; «invented» — вымышленное значение,
    порождённое зерном (заключение или состояние). Для `neutral`,
    `action_required`, `stale` и вымышленного — статус не `None`, не
    входит в `ci.JOB_FINISHED`, не `running`, а причина содержит значение.

    Ловит мутацию: `timed_out` читается как `canceled`; `requested` или
    `waiting` не входит в незавершённые; `neutral` переводится в `success`
    (как в `ci.GREEN`) — статус в `ci.JOB_FINISHED`; незнакомое значение
    без причины.
    """
    sc = scene
    if status == "invented":
        status = odd_value(sc, status)
    if conclusion == "invented":
        conclusion = odd_value(sc, conclusion)
    run_id = sc.gh.new_id()
    run = sc.gh.check_run(sc.job, run_id, status=status, conclusion=conclusion)
    if status != "completed":
        run["conclusion"] = None
        run["completed_at"] = None
    sc.gh.commit(sc.sha, [run, sc.noise()])
    result = sc.result()
    note = sc.note(f"{status}/{conclusion}: {result}")
    if expected is not None:
        assert result.status == expected, note
        return
    shown = conclusion if status == "completed" else status
    assert result.status is not None, note
    assert result.status not in ci.JOB_FINISHED, note
    assert result.status != "running", note
    assert shown in result.reason, note


class AcceptanceStand:
    """Задача внешнего проекта GitHub в `acceptance` поверх
    `light_transition`; условия принятия итога CI выполнены."""

    def __init__(self, s, monkeypatch):
        self.s = s
        self.scene = Scene(s, monkeypatch)
        sc = self.scene
        self.spy = mock.Mock(side_effect=lambda *a, **kw: acceptance.FullSuiteRun(
            True, acceptance.FULL_SUITE_GREEN, "12 passed", None,
            "локальный полный набор компонента зелёный"))
        tree = f"{sc.rng.getrandbits(160):040x}"
        real_is_ancestor = acceptance.gitcmd.is_ancestor

        def is_ancestor(ancestor, descendant, repo=None):
            if "origin/" in ancestor:
                return descendant == sc.sha
            return real_is_ancestor(ancestor, descendant, repo=repo)

        s.wt_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(workspace, "on_task_branch", lambda *a, **k: True)
        monkeypatch.setattr(workspace, "path", lambda *a, **k: s.wt_path)
        monkeypatch.setattr(ci, "head_sha", lambda branch, repo=None: (sc.sha, ""))
        monkeypatch.setattr(acceptance.gitcmd, "is_ancestor", is_ancestor)
        monkeypatch.setattr(acceptance, "full_suite", self.spy)
        monkeypatch.setattr(acceptance, "suite_tree_hash", lambda *a, **k: tree)
        store.update_task(store.db(), s.TASK, target=sc.name)
        s.set_state("acceptance")

    def suite(self):
        s = self.s
        conn = store.db()
        before = len(store.task_steps(conn, s.TASK))
        run = acceptance.acceptance_suite(
            conn, s.wt_path, s.TASK, s.branch, workspace.task_repo(s.TASK),
            actor="operator", fresh=False)
        added = store.task_steps(store.db(), s.TASK)[before:]
        return run, added


@pytest.fixture
def accept_stand(light_transition, monkeypatch):
    stand = AcceptanceStand(light_transition, monkeypatch)
    yield stand
    stand.scene.gh.kill_leftovers()


@pytest.mark.parametrize("verdict", ["green", "red"])
def test_ac4_acceptance_takes_github_ci_job(accept_stand, verdict):
    """Приёмка компонента GitHub с `report` и `full_suite: ci` берёт итог задания CI: зелёный отчёт — «принят из задания CI» с числом тестов, `failure` с упавшим тестом — красный итог с именем теста.

    Сценарий: у головы ветки задачи check run задания — `success` с
    отчётом без падений либо `failure` с одним `failed` в отчёте; отчёт —
    артефакт `junit` прогона. Локальный полный прогон — шпион.

    Ловит мутацию: отчёт не читается (итог «неизвестно» — приёмка без
    записи «принят из задания CI»); число тестов в записи — не число
    тестов отчёта; упавший тест отчёта не попадает в красный итог.
    """
    st = accept_stand
    sc = st.scene
    if verdict == "green":
        cases = sc.cases(kinds=("success", "skipped"))
        att = sc.attempt(conclusion="success", cases=cases)
    else:
        cases = sc.cases(kinds=("success",))
        cls, name = f"pkg.{word(sc.rng, 'm', 4)}.Case", word(sc.rng, "test_", 6)
        cases.append((cls, name, "failed"))
        att = sc.attempt(conclusion="failure", cases=cases)
    sc.gh.artifacts(att["run_id"], att["artifacts"])
    sc.gh.commit(sc.sha, [att["run"], sc.noise()])
    run, added = st.suite()
    journal = "\n".join(f"{r['action']}: {r['detail'] or ''}" for r in added)
    note = sc.note(f"{run.outcome} {run.detail!r}\n{journal}")
    st.spy.assert_not_called()
    if verdict == "green":
        assert run.green, note
        accepted = [r for r in added
                    if r["action"] == acceptance.CI_JOB_ACCEPTED_ACTION]
        assert accepted, note
        assert f"тестов {len(cases)}" in (accepted[-1]["detail"] or ""), note
    else:
        assert not run.green, note
        assert run.outcome == acceptance.FULL_SUITE_RED, note
        assert name in run.detail, note


# --- AC-5 ---

def test_ac5_default_artifact_is_junit(scene):
    """Компонент без `ci_report_artifact` — отчёт из артефакта `junit`, а не из соседнего артефакта другого имени.

    Сценарий: у прогона попытки два годных артефакта — `junit` и
    случайного имени с иным отчётом.

    Ловит мутацию: умолчание поля — не `junit` (или берётся первый
    артефакт прогона) — отчёт другого артефакта либо отказ.
    """
    sc = scene
    att = sc.attempt()
    other = sc.gh.artifact(att["run_id"], word(sc.rng, "rep-", 5),
                           att["start"] + timedelta(minutes=2),
                           members={"report.xml": junit_xml(sc.cases())})
    items = [other, *att["artifacts"]]
    sc.rng.shuffle(items)
    sc.gh.artifacts(att["run_id"], items)
    sc.gh.commit(sc.sha, [att["run"]])
    report = sc.report()
    assert report.outcomes == Scene.outcomes(att["cases"]), sc.note(f"{report}")


def test_ac5_named_artifact_is_taken(scene):
    """Компонент с `ci_report_artifact: <имя>` — отчёт из артефакта этого имени, а не из `junit`.

    Ловит мутацию: поле не читается — отчёт артефакта `junit`.
    """
    sc = scene
    name = word(sc.rng, "rep-", 5)
    sc.write(artifact=name)
    att = sc.attempt(artifact=name)
    junit = sc.gh.artifact(att["run_id"], "junit",
                           att["start"] + timedelta(minutes=2),
                           members={"report.xml": junit_xml(sc.cases())})
    items = [junit, *att["artifacts"]]
    sc.rng.shuffle(items)
    sc.gh.artifacts(att["run_id"], items)
    sc.gh.commit(sc.sha, [att["run"]])
    report = sc.report()
    assert report.outcomes == Scene.outcomes(att["cases"]), sc.note(f"{report}")


@pytest.mark.parametrize("value", ["5", "[junit, other]", "true"])
def test_ac5_wrong_type_refused_with_field_name(scene, value):
    """Значение `ci_report_artifact` неверного типа — отказ загрузки записи с именем поля.

    Сценарий: значение — число, список, логическое.

    Ловит мутацию: тип значения не сверяется — запись загружается без
    отказа.
    """
    sc = scene
    sc.write(artifact=value)
    with pytest.raises(targets.TargetsError, match="ci_report_artifact"):
        targets.load()


# --- AC-6 ---

def doctor_names(sc: Scene) -> dict:
    entry = targets.target(sc.name)
    found = (list(doctor.project_entry_checks(sc.name, entry))
             + list(doctor.project_checks.component_checks(sc.name, entry)))
    return {c.name: c for c in found}


def new_doctor_line(sc: Scene):
    """Строки `doctor` записи с `full_suite: ci`, которых нет у той же
    записи без `full_suite`/`ci_job`; запись возвращается к `ci`."""
    sc.write(mode=None)
    base = set(doctor_names(sc))
    sc.write()
    lines = doctor_names(sc)
    return [c for n, c in lines.items() if n not in base], lines


def base_commit(sc: Scene, *, executed: bool, artifact: bool) -> tuple:
    sha = f"{sc.rng.getrandbits(160):040x}"
    run_id = sc.gh.new_id()
    if executed:
        att = sc.attempt(run_id=run_id)
        sc.gh.artifacts(run_id, att["artifacts"] if artifact else [])
        runs = [att["run"], sc.noise()]
    else:
        runs = [sc.gh.check_run(sc.job, run_id, conclusion="skipped"), sc.noise()]
        sc.gh.artifacts(run_id, [])
    sc.gh.commit(sha, runs)
    return run_id, sha


DOCTOR_CASES = [
    ("ok", "ok"), ("ok_after_skipped", "ok"), ("no_green_run", "warn"),
    ("not_executed", "warn"), ("no_artifact", "warn")]


@pytest.mark.parametrize("case,status", DOCTOR_CASES)
@pytest.mark.parametrize("artel", [False, True])
def test_ac6_doctor_line_reads_report_of_green_base(tmp_root, monkeypatch, case,
                                                    status, artel):
    """Строка `doctor` записи GitHub с `report` и `full_suite: ci` (без мержа людьми и у артели): `ok` — отчёт зелёного коммита базы читается, `warn` с причиной — зелёного прогона с исполненным заданием нет или артефакта нет.

    Сценарий: прогоны ветки базы со статусом success
    (`actions/runs?branch=<base>&status=success`) — у первого задание
    исполнено с артефактом (`ok`); у первого задание пропущено условием, у
    второго исполнено с артефактом (`ok`); прогонов нет (`warn`); у всех
    задание только пропущено (`warn`); задание исполнено, артефакта нет
    (`warn`). Строка — та, которой нет у той же записи без
    `full_suite`/`ci_job`; она одна.

    Ловит мутацию: строка только у записей с мержем людьми (условие
    `human`) или не у артели — строки нет; зелёный коммит — первый прогон
    без сверки исполнения задания — `warn` вместо `ok`; отсутствие
    артефакта не проверяется — `ok` вместо `warn`.
    """
    sc = Scene(tmp_root, monkeypatch, artel=artel)
    try:
        base = config.MAIN_BRANCH if artel else sc.base
        if case == "ok":
            runs = [base_commit(sc, executed=True, artifact=True)]
        elif case == "ok_after_skipped":
            runs = [base_commit(sc, executed=False, artifact=False),
                    base_commit(sc, executed=True, artifact=True)]
        elif case == "no_green_run":
            runs = []
        elif case == "not_executed":
            runs = [base_commit(sc, executed=False, artifact=False)
                    for _ in range(2)]
        else:
            runs = [base_commit(sc, executed=True, artifact=False)]
        sc.gh.green_runs(base, runs)
        new, lines = new_doctor_line(sc)
        shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in lines.values())
        note = sc.note(f"случай {case}; артель {artel}\n{shown}")
        assert len(new) == 1, note
        assert new[0].status == status, note
        if status == "warn":
            assert new[0].detail, note
    finally:
        sc.gh.kill_leftovers()


def gitlab_scene(sc: Scene, monkeypatch, gate: str) -> list:
    """Вымышленная запись GitLab с компонентом с `report` и `full_suite:
    ci`; функции `forge` строк GitLab подменены."""
    monkeypatch.setattr(forge, "project_info",
                        lambda target: forge.ProjectInfo(config.MAIN_BRANCH, 40))
    monkeypatch.setattr(forge, "protections",
                        lambda target: forge.Protections(["main"], ["v1"]))
    monkeypatch.setattr(forge, "branch_pipeline",
                        lambda target, branch: forge.BranchPipeline("a" * 40, forge.GREEN))
    sc.write(forge_name="gitlab", gate=gate)
    names = [f"project-{kind}-{sc.name}" for kind in
             ("clone", "artifacts-push", "ci-pull-request", "base-protection",
              "token", "ci-token", "no-paths", "skills")]
    if gate == "target-human":
        names += [f"project-ci-file-no-paths-{sc.name}",
                  f"project-submodules-{sc.name}",
                  f"project-ci-reruns-{sc.name}-{sc.comp}"]
    return names


@pytest.mark.parametrize("gate", ["operator", "target-human"])
def test_ac6_gitlab_entry_lines_unchanged(scene, monkeypatch, gate):
    """У записи GitLab с компонентом с `report` и `full_suite: ci` список имён строк `project_entry_checks` + `component_checks` — прежний.

    Сценарий: вымышленная запись `forge: gitlab` (`merge_gate` `operator`
    или `target-human`), функции `forge` строк GitLab подменены; список
    имён сверяется целиком и по порядку с прежним (8 строк записи, у
    `target-human` — ещё `ci-file-no-paths`, `submodules` и `ci-reruns`
    компонента).

    Ловит мутацию: строка требования 8 добавлена любой записи с `report` и
    `full_suite: ci` — у записи GitLab лишнее имя.
    """
    sc = scene
    expected = gitlab_scene(sc, monkeypatch, gate)
    entry = targets.target(sc.name)
    found = (list(doctor.project_entry_checks(sc.name, entry))
             + list(doctor.project_checks.component_checks(sc.name, entry)))
    assert [c.name for c in found] == expected, sc.note(
        "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in found))


def test_ac6_doctor_module_has_no_hosting_literals():
    """В исходном тексте `orchestrator/doctor/project_checks.py` нет строковых литералов `"github"`/`"gitlab"` — хостинг выбирается через реестр.

    Сценарий: разбор синтаксического дерева модуля
    (`inspect.getsource(doctor.project_checks)`): ни одного узла-константы
    со значением `github` или `gitlab`, в том числе в частях f-строк.

    Ловит мутацию: строка `doctor` выбрана по `forge == "github"` или
    `entry.get("forge") != "gitlab"` — литерал найден в разборе.
    """
    tree = ast.parse(inspect.getsource(doctor.project_checks))
    found = [f"строка {node.lineno}: {node.value!r}" for node in ast.walk(tree)
             if isinstance(node, ast.Constant) and node.value in ("github", "gitlab")]
    assert found == [], found


# --- AC-7 ---

def restart_scene(sc: Scene, monkeypatch) -> dict:
    """Попытка N у коммита; при вызове `forge.job_test_report` у коммита
    появляется попытка с большим номером того же прогона — `success` с
    зелёным отчётом — и только затем идёт настоящее чтение отчёта."""
    low, high = sorted(sc.gh.new_id() for _ in range(2))
    first = sc.attempt(conclusion="success",
                       cases=sc.cases(kinds=("success",)), cid=low)
    skipped = sc.gh.check_run(sc.job, sc.gh.new_id(), conclusion="skipped",
                              cid=sc.gh.new_id(1, 999))
    sc.gh.artifacts(first["run_id"], first["artifacts"])
    sc.gh.commit(sc.sha, [first["run"], skipped, sc.noise()])
    real = forge.job_test_report
    state = {"switched": False}

    def report(target, sha, job_name):
        if not state["switched"]:
            state["switched"] = True
            later = first["start"] + timedelta(minutes=20)
            run = sc.gh.check_run(sc.job, first["run_id"], cid=high, start=later)
            art = sc.gh.artifact(first["run_id"], "junit",
                                 later + timedelta(minutes=4),
                                 members={"report.xml": junit_xml(
                                     sc.cases(kinds=("success",)))})
            sc.gh.artifacts(first["run_id"], [*first["artifacts"], art])
            sc.gh.commit(sc.sha, [first["run"], run, skipped, sc.noise()])
        return real(target, sha, job_name)

    monkeypatch.setattr(forge, "job_test_report", report)
    return {"first": first, "skipped": skipped, "state": state, "high": high}


def test_ac7_restart_during_read_is_unknown(scene, monkeypatch):
    """Новая попытка задания между чтением статуса и чтением отчёта — `ci.job_full_suite` у записи GitHub даёт `JOB_UNKNOWN` «перезапущено во время чтения».

    Сценарий: при первом чтении попытка — check run N (`success`, зелёный
    отчёт); в момент вызова `forge.job_test_report` у коммита появляется
    check run того же имени с номером больше N, `success`, с зелёным
    отчётом своего окна.

    Ловит мутацию: `_GitHub.pipeline_status` не заполняет `Job.id` — номера
    до и после чтения оба `None`, сверка «одна попытка» не срабатывает, итог
    зелёный.
    """
    sc = scene
    plan = restart_scene(sc, monkeypatch)
    suite = ci.job_full_suite(sc.name, sc.sha, sc.job)
    note = sc.note(f"{suite}")
    assert plan["state"]["switched"], note
    assert suite.state == ci.JOB_UNKNOWN, note
    assert "перезапущено во время чтения" in suite.reason, note


def test_ac7_pipeline_jobs_carry_check_run_ids(scene):
    """`PipelineStatus.jobs` у GitHub несёт `Job.id`, равный номеру check run, у каждого check run, в том числе пропущенного.

    Сценарий: запись без `report`; check runs задания (исполненный и
    пропущенный), идущий check run и посторонний.

    Ловит мутацию: `Job.id` заполняется только у исполненных check runs
    (или не заполняется вовсе) — у пропущенного `None`.
    """
    sc = scene
    sc.write(comps=[(sc.comp, without_report(sc))])
    runs =[sc.gh.check_run(sc.job, sc.gh.new_id()),
            sc.gh.check_run(sc.job, sc.gh.new_id(), conclusion="skipped"),
            sc.gh.check_run(word(sc.rng, "x-", 3), sc.gh.new_id(),
                            status="in_progress"),
            sc.noise()]
    sc.rng.shuffle(runs)
    sc.gh.commit(sc.sha, runs)
    res = forge.pipeline_status(sc.name, sc.sha)
    got = sorted((j.name, j.id) for j in res.jobs)
    assert got == sorted((r["name"], r["id"]) for r in runs), sc.note(f"{res}")


# --- AC-8 ---

PIPELINE_CASES = [
    # (check runs: [(status, conclusion)], verdict, причина, упавшие)
    ([("completed", "success"), ("completed", "skipped")], forge.GREEN, "", []),
    ([("completed", "success"), ("completed", "failure")], forge.RED,
     "упали проверки: {1}", ["{1}"]),
    ([("completed", "success"), ("in_progress", None)], forge.RUNNING,
     "проверки не завершены", []),
    ([("completed", "neutral"), ("completed", "action_required")], forge.UNKNOWN,
     "исход проверок не установлен: {1}", []),
    ([], forge.NONE, "у коммита {sha8} нет check runs", []),
]


@pytest.mark.parametrize("runs,verdict,reason,failed", PIPELINE_CASES)
def test_ac8_github_pipeline_status_unchanged_but_id(scene, runs, verdict,
                                                     reason, failed):
    """`pipeline_status` записи GitHub без `report`: `verdict`, `reason`, `failed` прежние, `jobs` отличаются от прежних только полем `id`.

    Сценарий: запись без компонентов с `report`; check runs коммита из
    строки параметров с случайными именами; прежний вид `jobs` —
    `Job(<имя>, <заключение или состояние>)`.

    Ловит мутацию: перевод статусов требования 2 применён и к
    `pipeline_status` (`failure` → `failed` в `Job.status`) или пропущенный
    check run выпал из `jobs`; причина или итог изменились.
    """
    sc = scene
    sc.write(comps=[(sc.comp, without_report(sc))])
    names =[word(sc.rng, "chk-", 4) + str(i) for i in range(len(runs))]
    items = []
    for name, (status, conclusion) in zip(names, runs):
        run = sc.gh.check_run(name, sc.gh.new_id(), status=status,
                              conclusion=conclusion)
        items.append(run)
    sc.gh.commit(sc.sha, items)
    res = forge.pipeline_status(sc.name, sc.sha)
    fill = {str(i): n for i, n in enumerate(names)}
    want_reason = reason.replace("{sha8}", sc.sha[:8])
    for key, value in fill.items():
        want_reason = want_reason.replace("{" + key + "}", value)
    want_failed = [fill[f.strip("{}")] for f in failed]
    note = sc.note(f"{res}")
    assert res.verdict == verdict, note
    assert res.reason == want_reason, note
    assert res.failed == want_failed, note
    expected_jobs = ([] if verdict == forge.NONE else
                     [forge.Job(r["name"], str(r["conclusion"] or r["status"] or ""))
                      for r in items])
    assert [dataclasses.replace(j, id=None) for j in res.jobs] == expected_jobs, note


class GitlabTransport:
    """Транспорт GitLab: конвейер коммита, его задания и отчёт тестов."""

    def __init__(self, project: str, sha: str, job: str, cases: list):
        self.project = project
        self.sha = sha
        self.job = job
        self.cases = cases
        self.calls: list = []

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url))
        quoted = self.project.replace("/", "%2F")
        path = url.split("/api/v4", 1)[1]
        if path.startswith(f"/projects/{quoted}/pipelines?"):
            data = [{"id": 11, "sha": self.sha, "status": "failed"}]
        elif path.startswith(f"/projects/{quoted}/pipelines/11/jobs?"):
            data = [{"id": 5, "name": self.job, "status": "success",
                     "stage": "test", "allow_failure": False},
                    {"id": 6, "name": "lint", "status": "failed",
                     "stage": "lint", "allow_failure": False}]
        elif path == f"/projects/{quoted}/pipelines/11/test_report":
            return 200, {}, json.dumps({"test_suites": [{
                "name": self.job, "test_cases": [
                    {"classname": c, "name": n, "status": o}
                    for c, n, o in self.cases]}]}).encode("utf-8")
        else:
            return 404, {}, b"{}"
        return 200, {"X-Total": str(len(data))}, json.dumps(data).encode("utf-8")


def test_ac8_gitlab_results_unchanged(scene, monkeypatch):
    """`job_result`, `job_test_report`, `pipeline_status` записи GitLab на тех же ответах транспорта — прежние значения; `gh` не вызывается.

    Сценарий: вымышленная запись `forge: gitlab` с компонентом `report` и
    `full_suite: ci`; транспорт GitLab отдаёт один конвейер коммита
    (`failed`) с заданием `success` и упавшим `lint`, отчёт тестов задания.

    Ловит мутацию: функции GitHub подставлены для любого хостинга — вызван
    `gh`, итоги другие; ключи отчёта GitLab переведены в иной вид.
    """
    sc = scene
    sc.write(forge_name="gitlab")
    cases = [("pkg.mod.Case", "test_ok", "success"),
             ("pkg.mod.Case", "test_bad", "failed")]
    transport = GitlabTransport(f"{sc.gh.owner}/{sc.gh.repo}", sc.sha, sc.job, cases)
    monkeypatch.setattr(gitlab_adapter, "transport", transport)
    result = forge.job_result(sc.name, sc.sha, sc.job)
    report = forge.job_test_report(sc.name, sc.sha, sc.job)
    status = forge.pipeline_status(sc.name, sc.sha)
    note = sc.note(f"{result}; {report}; {status}; {transport.calls}")
    assert result == forge.JobResult("success", ""), note
    assert report == forge.TestReport({"pkg.mod.Case::test_ok": "success",
                                       "pkg.mod.Case::test_bad": "failed"}, ""), note
    assert status.verdict == forge.RED, note
    assert status.failed == ["lint"], note
    assert status.reason == ("задание lint упало (failed); конвейер 11 "
                             "завершился статусом failed"), note
    assert [(j.name, j.status, j.stage, j.id) for j in status.jobs] == [
        (sc.job, "success", "test", 5), ("lint", "failed", "lint", 6)], note
    assert sc.gh.calls() == [], note


def test_ac8_entry_without_report_runs_local_suite(accept_stand):
    """Приёмка записи GitHub без `report` (компонент без `full_suite`) — прежний локальный прогон полного набора, `gh` не вызывается.

    Ловит мутацию: итог задания CI читается у любой записи GitHub — вызван
    `gh`, шпион локального прогона не вызван.
    """
    st = accept_stand
    sc = st.scene
    sc.write(comps=[(sc.comp, without_report(sc))])
    run, _added = st.suite()
    note = sc.note(f"{run.outcome} {run.detail!r}")
    assert st.spy.called, note
    assert sc.gh.calls() == [], note
