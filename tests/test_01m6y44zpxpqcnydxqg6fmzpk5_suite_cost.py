"""Цена набора тестов по отчёту junit CI `main`: время тестов из архива (`forge.parse_junit_times`), отчёт CI по sha (`forge.ci_suite_report`), последний исполненный коммит ветки (`forge.last_executed_commit`), сводка (`orchestrator.suite_cost`), её запись и команда `suite-cost`, проверка `doctor` «suite-cost:<target>», предел CI против `.github/workflows/ci.yml`.

Группа: долгоживущий
Красен до реализации: у `forge` нет `parse_junit_times`, `ci_suite_report` и `last_executed_commit`, модуля `orchestrator.suite_cost` нет (импорт в теле теста падает), команды `suite-cost` нет («Неизвестная команда»), строк `doctor` `suite-cost:<target>` нет, константы `config.SUITE_COST_CI_LIMIT_SEC` нет; зелён с рождения `test_ac1_job_test_report_and_test_report_fields_unchanged` — он закрепляет прежние `job_test_report` и состав полей `TestReport`, которые задача менять не должна.

Стенд — `real_git` (`tests.sandbox.RealGitSandbox`): пути `config` во
временном каталоге, `config.ROOT` — настоящий git-репозиторий с веткой
`main` (он же клон артели), БД пульта со схемой. Коммиты `main`, ветки
задач и мержи с темой `<id>: merge task/…` заводятся в нём методом
песочницы `git`. Программа `gh` подменена исполняемым файлом в начале PATH
(тот же приём, что у `tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py`):
он отвечает JSON по правилам `rules.json` (регулярное выражение по строке
аргументов) либо байтами файла архива; сети нет. Признак процесса роли
снят (`runner.in_role_environment`), кроме метода, где он и есть предмет.
Архивы junit собираются в тесте во временном каталоге.

Запись сводки тест находит без знания имени таблицы и колонок: строка любой
таблицы БД (кроме журнала `steps` и `alerts`), одно из значений которой
равно полному sha коммита. Время записи сдвигается в прошлое правкой
значения-метки времени этой строки (тот же вид значения), чтобы порядок
«позже всех» и возраст в строке `doctor` не зависели от часов прогона.

Связки, которые держит файл: «`targets.yaml` песочницы — `forge` —
`ci.gh`/`ci.gh_bytes` — внешний процесс `gh`»; «`artel.main()` по
`sys.argv` — `forge` — `suite_cost` — git песочницы — БД пульта»;
«БД пульта — `doctor.all_checks` — таблица `alerts`». Для `doctor` внешние
процессы, кроме локальных (git без сети, интерпретатор, `ps`), получают
отказ запуска — настоящий CLI роли и `gh` не запускаются.

Отдельно не проверяется строка реестра `docs/triggers.md` для `suite.cost`
(часть AC-11): указание Оператора на гейте SPEC (08.11.2026, п. 1) —
чтение живого файла `docs/` отклонил бы линт детерминизма; строку сверяет
ревью диффа.

Имена узлов, sha, номера check runs и прогонов, id задач — случайные на
каждом запуске; зерно печатается и входит в текст провала.
"""
import dataclasses
import io
import json
import os
import random
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pytest

from orchestrator import (acceptance, alerts, artel, ci, config, doctor, forge,
                          project_profile, runner, schema, store, targets)
from tests.sandbox import artel_target_entry

ARTEL = config.DEFAULT_TARGET
JOB = ci.FULL_SUITE_JOB
ARTIFACT = targets.CI_REPORT_ARTIFACT_DEFAULT
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnopqrstuvwxyz"
LINE = f"suite-cost:{ARTEL}"
BUCKETS = ("до 1 с", "1–10 с", "10–60 с", "60 с и дольше")
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}
NOT_EXECUTED = "задание не исполнялось"
TIME_VALUE = re.compile(r"^(\d{4}-\d{2}-\d{2})([ T])(\d{2}:\d{2}:\d{2})")

FAKE_GH = r'''#!@PYTHON@
import json, os, re, sys
here = os.path.dirname(os.path.abspath(__file__))
joined = " ".join(sys.argv[1:])
with open(os.path.join(here, "calls.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:]) + "\n")
with open(os.path.join(here, "rules.json"), encoding="utf-8") as f:
    rules = json.load(f)
page = re.search(r"[?&]page=([0-9]+)", joined)
page = int(page.group(1)) if page else 1
wanted = re.search(r"[?&]name=([^&\s]+)", joined)
for rule in rules:
    if not re.search(rule["pattern"], joined):
        continue
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
    out.flush()
    sys.exit(rule.get("code", 0))
sys.stderr.write("gh: Not Found (HTTP 404)\n")
sys.exit(1)
'''


# --------------------------------------------------------------- окружение

def stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def junit_zip(cases: list, suite_time: str, tests_attr: int | None = None,
              member: str = "report.xml") -> bytes:
    """Архив артефакта junit: `cases` — [(classname, name, time, исход)];
    `time` — строка атрибута как есть; `tests_attr` — `testsuite@tests`."""
    child = {"failed": '<failure message="boom">трасса</failure>',
             "skipped": '<skipped message="нет"/>', "success": ""}
    rows = "".join(
        f'<testcase classname={quoteattr(c)} name={quoteattr(n)} '
        f'time={quoteattr(t)}>{child[o]}</testcase>\n' for c, n, t, o in cases)
    count = len(cases) if tests_attr is None else tests_attr
    xml = (f'<?xml version="1.0" encoding="utf-8"?>\n<testsuites '
           f'name="pytest tests"><testsuite name="pytest" errors="0" '
           f'failures="0" skipped="0" tests="{count}" '
           f'time={quoteattr(suite_time)}>\n{rows}</testsuite></testsuites>\n')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(zipfile.ZipInfo(member, (2026, 11, 8, 10, 0, 0)),
                    xml.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def timed_cases(times: dict) -> list:
    """`{узел: секунды}` → случаи `junit_zip` (исход — успех)."""
    out = []
    for node, seconds in times.items():
        classname, name = node.split("::")
        out.append((classname, name, repr(float(seconds)), "success"))
    return out


def dataset25() -> dict:
    """25 узлов известного времени: сумма 250 с; два равных (0,5 с) на 20-й
    и 21-й позициях по убыванию, меньший по имени узел — в архиве вторым."""
    values = [70.0, 64.0, 20.0, 15.0, 12.0, 11.0, 9.5, 8.5, 7.0, 6.0, 5.5,
              5.0, 4.0, 3.0, 3.0, 2.5, 0.9, 0.8, 0.7, 0.3, 0.2, 0.1, 0.0]
    times = {f"pkg.m{i:02d}.Case::test_n{i:02d}": v
             for i, v in enumerate(values)}
    times["pkg.tie.Case::test_tie_b"] = 0.5
    times["pkg.tie.Case::test_tie_a"] = 0.5
    return times


def uniform_times(prefix: str, count: int, each: float, last: float) -> dict:
    """`count - 1` узлов по `each` секунд и последний — `last` секунд."""
    times = {f"pkg.{prefix}.Case::test_u{i:03d}": each for i in range(count - 1)}
    times[f"pkg.{prefix}.Case::test_u{count - 1:03d}"] = last
    return times


def reference_summary(times: dict) -> tuple:
    """(tests, total, slowest, buckets) по правилам требования 4."""
    def bucket(t):
        return (BUCKETS[0] if t < 1 else BUCKETS[1] if t < 10
                else BUCKETS[2] if t < 60 else BUCKETS[3])
    total = sum(times.values())
    slowest = [[node, t] for node, t in
               sorted(times.items(), key=lambda kv: (-kv[1], kv[0]))[:20]]
    buckets = {b: {"count": 0, "seconds": 0.0} for b in BUCKETS}
    for t in times.values():
        buckets[bucket(t)]["count"] += 1
        buckets[bucket(t)]["seconds"] += t
    shares = {b: {"count": v["count"],
                  "share": v["seconds"] / total if total else 0.0}
              for b, v in buckets.items()}
    return len(times), total, slowest, shares


def local_command(argv) -> bool:
    """Локальный процесс песочницы: `ps`, интерпретатор Python, git без сети."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name == "ps" or name.startswith("python") or words[0] == sys.executable


def number_re(value: float, decimals=(0, 1, 2, 3)) -> str:
    """Регулярное выражение числа `value`, напечатанного с округлением до
    одного из `decimals` знаков, через точку или запятую."""
    forms = set()
    for d in decimals:
        if d == 0 and abs(value - round(value)) > 1e-9:
            continue
        text = f"{value:.{d}f}"
        forms.add(re.escape(text))
        forms.add(re.escape(text.replace(".", ",")))
    return (r"(?<![0-9A-Za-z.,])(?:" + "|".join(sorted(forms)) +
            r")(?![0-9A-Za-z]|[.,][0-9])")


def has_number(text: str, value: float, decimals=(0, 1, 2, 3)) -> bool:
    return re.search(number_re(value, decimals), text) is not None


def has_share(text: str, share: float) -> bool:
    """Доля напечатана долей (0…1) или процентами."""
    return (re.search(number_re(share, (2, 3, 4)), text) is not None
            or re.search(number_re(share * 100, (0, 1, 2)), text) is not None)


def percent_re(value: float) -> str:
    forms = {f"{value:.1f}", f"{value:.2f}"}
    forms |= {f.replace(".", ",") for f in forms}
    return r"(?:" + "|".join(re.escape(f) for f in sorted(forms)) + r")\s*%"


class Gh:
    """Подменная программа `gh` и её ответы."""

    def __init__(self, root: Path, rng: random.Random):
        self.rng = rng
        self.bin = root / ".artel" / "fake-gh"
        self.bin.mkdir(parents=True, exist_ok=True)
        script = self.bin / "gh"
        script.write_text(FAKE_GH.replace("@PYTHON@", sys.executable),
                          encoding="utf-8")
        script.chmod(0o755)
        self.files = root / ".artel" / "fake-gh-files"
        self.files.mkdir(parents=True, exist_ok=True)
        self.rules: list = []
        self.used: set = set()
        self.flush()

    def new_id(self) -> int:
        while True:
            value = self.rng.randrange(1000, 9_000_000)
            if value not in self.used:
                self.used.add(value)
                return value

    def flush(self) -> None:
        (self.bin / "rules.json").write_text(json.dumps(self.rules),
                                             encoding="utf-8")

    def put(self, pattern: str, **rule) -> None:
        self.rules = [r for r in self.rules if r["pattern"] != pattern]
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

    def check_runs(self, sha: str, runs: list) -> None:
        """Check runs коммита и ответы `actions/jobs/<id>`."""
        public = [{k: v for k, v in r.items() if k != "run_id"} for r in runs]
        self.put(f"commits/{sha}/check-runs",
                 json={"total_count": len(runs), "check_runs": public},
                 list_key="check_runs")
        for r in runs:
            self.put(f"actions/jobs/{r['id']}(?![0-9])",
                     json={**r, "head_sha": sha, "run_attempt": 1})

    def run_jobs(self, run_id: int, jobs: list) -> None:
        self.put(f"actions/runs/{run_id}/jobs",
                 json={"total_count": len(jobs), "jobs": jobs},
                 list_key="jobs")

    def artifacts(self, run_id: int, items: list) -> None:
        self.put(f"actions/runs/{run_id}/artifacts",
                 json={"total_count": len(items), "artifacts": items},
                 list_key="artifacts")

    def artifact(self, run_id: int, data: bytes, created: datetime, *,
                 expired: bool = False, size: int | None = None) -> dict:
        aid = self.new_id()
        path = self.files / f"artifact-{aid}.zip"
        path.write_bytes(data)
        self.put(f"actions/artifacts/{aid}/zip", file=str(path))
        return {"id": aid, "name": ARTIFACT, "expired": expired,
                "size_in_bytes": len(data) if size is None else size,
                "created_at": stamp(created), "workflow_run": {"id": run_id}}

    def attempt(self, sha: str, *, data: bytes | None, job_seconds: int,
                kind: str = "report", start: datetime | None = None) -> int:
        """Попытка задания `JOB` коммита `sha` и артефакт её прогона.

        `kind`: `report` — годный артефакт; `none` — артефакта нет (обрыв);
        `outside` — артефакт создан после `completed_at`; `expired` — срок
        хранения истёк; `big` — объявленный размер больше предела архива;
        `skipped` — у коммита только пропущенные попытки."""
        start = start or datetime(2026, 11, 8, 6, 0, 0)
        end = start + timedelta(seconds=job_seconds)
        run_id = self.new_id()
        if kind == "skipped":
            runs = [{"id": self.new_id(), "name": JOB, "status": "completed",
                     "conclusion": "skipped", "started_at": stamp(start),
                     "completed_at": stamp(start), "run_id": run_id}
                    for _ in range(2)]
            self.check_runs(sha, runs)
            self.artifacts(run_id, [])
            return run_id
        cid = self.new_id()
        run = {"id": cid, "name": JOB, "status": "completed",
               "conclusion": "success", "started_at": stamp(start),
               "completed_at": stamp(end), "run_id": run_id}
        self.check_runs(sha, [run])
        items = []
        if kind != "none":
            created = (end + timedelta(minutes=3) if kind == "outside"
                       else end - timedelta(seconds=5))
            items.append(self.artifact(
                run_id, data, created, expired=kind == "expired",
                size=(config.CI_REPORT_ARCHIVE_MAX_BYTES + 1
                      if kind == "big" else None)))
        self.artifacts(run_id, items)
        return run_id


class Stand:
    """Песочница `real_git`, подменная `gh`, вход `artel.main()`."""

    def __init__(self, sandbox, monkeypatch, capsys):
        self.sb = sandbox
        self.root = Path(sandbox.root)
        self.mp = monkeypatch
        self.capsys = capsys
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.gh = Gh(self.root, self.rng)
        monkeypatch.setenv("PATH", f"{self.gh.bin}{os.pathsep}"
                                   f"{os.environ.get('PATH', '')}")
        for env in ("GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "GH_HOST"):
            monkeypatch.delenv(env, raising=False)
        monkeypatch.setattr(runner, "in_role_environment",
                            lambda env=None: False)
        self.conn = store.db()
        self.counter = 0

    def note(self, extra: str = "") -> str:
        return f"зерно: {self.seed}; {extra}"

    # --- git и задачи

    def word(self, prefix: str, size: int = 6) -> str:
        return prefix + "".join(self.rng.choice(LETTERS) for _ in range(size))

    def task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(CROCKFORD) for _ in range(23))

    def head(self) -> str:
        return self.sb.git("rev-parse", "HEAD").strip()

    def commit(self, message: str | None = None) -> str:
        self.counter += 1
        name = f"file-{self.counter}-{self.word('', 4)}.txt"
        (self.root / name).write_text(f"{self.counter}\n", encoding="utf-8")
        self.sb.git("add", "--", name)
        self.sb.git("commit", "-q", "-m", message or f"коммит {self.counter}")
        return self.head()

    def add_task(self, task_id: str | None = None, target: str = ARTEL) -> str:
        task_id = task_id or self.task_id()
        store.insert_task(self.conn, task_id, "Задача", "done",
                          f"task/{task_id.lower()}-x", target, 10.0)
        return task_id

    def merge(self, task_id: str) -> str:
        """Мерж ветки задачи в `main` с темой `<id>: merge task/…`."""
        branch = f"task/{task_id.lower()}-{self.word('', 5)}"
        self.sb.git("checkout", "-q", "-b", branch)
        self.commit(f"{task_id}: работа")
        self.sb.git("checkout", "-q", config.MAIN_BRANCH)
        self.sb.git("merge", "-q", "--no-ff", "-m",
                    f"{task_id}: merge {branch}", branch)
        return self.head()

    def side_commit(self, base: str) -> str:
        """Коммит на ветке от `base`, не лежащий на линии `main`."""
        branch = self.word("side-", 5)
        self.sb.git("checkout", "-q", "-b", branch, base)
        sha = self.commit("коммит вне линии main")
        self.sb.git("checkout", "-q", config.MAIN_BRANCH)
        return sha

    # --- команда

    def cli(self, *args: str) -> tuple:
        """(код выхода, весь вывод) `artel.py <args>`."""
        self.capsys.readouterr()
        self.mp.setattr(sys, "argv", ["artel.py", *args])
        code = 0
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code
        out = self.capsys.readouterr()
        text = out.out + out.err + (code if isinstance(code, str) else "")
        rc = 0 if code in (None, 0) else (1 if isinstance(code, str) else code)
        return rc, text

    def record(self, sha: str, data: bytes | None, job_seconds: int,
               kind: str = "report") -> tuple:
        self.gh.attempt(sha, data=data, job_seconds=job_seconds, kind=kind)
        return self.cli("suite-cost", "--record", sha)

    # --- БД

    def rows_with(self, value: str) -> list:
        """[(таблица, rowid, {колонка: значение})] — строки таблиц БД
        (кроме `steps`, `alerts`), где одно из значений равно `value`."""
        conn = store.db()
        found = []
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            if table in ("steps", "alerts") or table.startswith("sqlite_"):
                continue
            cur = conn.execute(f'SELECT rowid, * FROM "{table}"')
            cols = [d[0] for d in cur.description][1:]
            for row in cur.fetchall():
                values = dict(zip(cols, row[1:]))
                if value in values.values():
                    found.append((table, row[0], values))
        return found

    def dump(self) -> dict:
        conn = store.db()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: sorted(repr(tuple(row)) for row in
                          conn.execute(f'SELECT * FROM "{t}"'))
                for t in tables}

    def backdate(self, sha: str, ago: timedelta) -> None:
        """Время записи сводки `sha` — `ago` назад (вид значения сохраняется)."""
        rows = self.rows_with(sha)
        assert len(rows) == 1, self.note(f"записей сводки {sha}: {rows}")
        table, rowid, values = rows[0]
        moment = datetime.now(timezone.utc) - ago
        conn = store.db()
        changed = False
        for col, value in values.items():
            new = None
            if isinstance(value, str) and TIME_VALUE.match(value):
                m = TIME_VALUE.match(value)
                new = (moment.strftime(f"%Y-%m-%d{m.group(2)}%H:%M:%S")
                       + value[m.end():])
            elif (isinstance(value, (int, float)) and not isinstance(value, bool)
                  and 1e9 < value < 1e11):
                new = moment.timestamp()
            if new is not None:
                conn.execute(f'UPDATE "{table}" SET "{col}" = ? WHERE rowid = ?',
                             (new, rowid))
                changed = True
        conn.commit()
        assert changed, self.note(f"у записи {values} нет метки времени")

    # --- локальный прогон и doctor

    def journal_local(self, task_id: str, seconds: float,
                      ago: timedelta = timedelta(hours=2)) -> None:
        acceptance.journal_suite_metrics(task_id, {
            "duration_seconds": seconds, "tests": 100,
            "seconds_per_test": seconds / 100, "xdist_workers": 1,
            "load_start_1": 0.4, "load_start_5": 0.5, "load_end_1": 0.6,
            "load_end_5": 0.7, "cpu_cores": 8, "top_processes": []})
        moment = (datetime.now(timezone.utc) - ago).strftime(
            "%Y-%m-%d %H:%M:%SZ")
        conn = store.db()
        conn.execute("UPDATE steps SET ts = ? WHERE id = (SELECT MAX(id) FROM "
                     "steps WHERE task_id = ? AND action = ?)",
                     (moment, task_id, acceptance.SUITE_DURATION_ACTION))
        conn.commit()

    def set_local_limit(self, seconds: int) -> None:
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + f"      full_suite_timeout_sec: {seconds}\n", encoding="utf-8")

    def doctor_lines(self) -> tuple:
        """(строка «CI:», строка «локальный прогон:», все строки
        `suite-cost:<артель>`) — `doctor.all_checks` без внешних процессов."""
        real_run, real_popen = subprocess.run, subprocess.Popen

        def run(argv, *args, **kwargs):
            if local_command(argv):
                return real_run(argv, *args, **kwargs)
            empty = b"" if not (kwargs.get("text") or kwargs.get("encoding")
                                or kwargs.get("universal_newlines")) else ""
            return subprocess.CompletedProcess(argv, 127, empty, empty)

        def popen(argv, *args, **kwargs):
            if local_command(argv):
                return real_popen(argv, *args, **kwargs)
            raise FileNotFoundError(f"песочница: процесс {argv!r} не запускается")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(subprocess, "run", run)
            mp.setattr(subprocess, "Popen", popen)
            checks = doctor.all_checks(store.db())
        mine = [c for c in checks if c.name == LINE]
        ci_line = [c for c in mine if c.detail.startswith("CI:")]
        local = [c for c in mine if c.detail.startswith("локальный прогон:")]
        return (ci_line[0] if len(ci_line) == 1 else None,
                local[0] if len(local) == 1 else None, mine)

    def cost_alerts(self) -> list:
        return [a for a in alerts.open_alerts(store.db(), "trigger")
                if a["source"] == "suite.cost" and a["target"] == ARTEL]


@pytest.fixture
def stand(real_git, monkeypatch, capsys):
    return Stand(real_git, monkeypatch, capsys)


def shown(lines) -> str:
    return "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in lines)


# ------------------------------------------------------------------- AC-1

def three_cases(rng: random.Random) -> list:
    """Три теста разного времени и разных исходов."""
    cls = f"pkg.{''.join(rng.choice(LETTERS) for _ in range(5))}.Case"
    return [(cls, "test_alpha", f"{rng.randrange(1, 900) / 100:.2f}", "success"),
            (cls, "test_beta", f"{rng.randrange(1000, 5000) / 100:.2f}", "failed"),
            (cls, "test_gamma", f"{rng.randrange(6000, 9000) / 100:.3f}", "skipped")]


def test_ac1_parse_junit_times_reads_each_node_and_suite_time(stand):
    """Архив с тремя тестами и подтестом: время каждого узла и `testsuite@time`; пустой `time` — отказ, не ноль.

    Сценарий: архив junit (zip во временном каталоге) с тремя `testcase`
    разного времени и `testsuite@tests` на единицу больше (подтест). Его
    байты — в `forge.parse_junit_times`: `times` — ровно три узла
    `<classname>::<name>` с их временем, `suite_seconds` — `testsuite@time`,
    причина пустая. Тот же архив с пустым `time` у одного `testcase` —
    `(None, None, <непустая причина>)`.

    Ловит мутацию: пустой атрибут `time` читается как 0 — `times` с нулём
    вместо отказа; ключ узла без `classname` или через «.» вместо «::»;
    `suite_seconds` взят суммой `times`, а не `testsuite@time`.
    """
    rng = stand.rng
    cases = three_cases(rng)
    suite_time = f"{rng.randrange(10000, 20000) / 100:.2f}"
    data = junit_zip(cases, suite_time, tests_attr=len(cases) + 1)
    times, suite_seconds, reason = forge.parse_junit_times(data)
    expected = {f"{c}::{n}": float(t) for c, n, t, _o in cases}
    assert times == expected, stand.note(f"{times}")
    assert suite_seconds == float(suite_time), stand.note(f"{suite_seconds}")
    assert reason == "", stand.note(reason)

    broken = list(cases)
    pick = rng.randrange(len(broken))
    c, n, _t, o = broken[pick]
    broken[pick] = (c, n, "", o)
    got = forge.parse_junit_times(junit_zip(broken, suite_time))
    assert got[0] is None and got[1] is None, stand.note(f"{got}")
    assert isinstance(got[2], str) and got[2].strip(), stand.note(f"{got}")


def write_artel_with_component() -> None:
    """Запись артели с одним компонентом `ci_job` = `JOB` (для `job_test_report`)."""
    fields = {"command": "[python3, -m, pytest]", "report": "junit-xml",
              "long_lived_dir": "tests",
              "long_lived_name": "test_<id>_<name>.py",
              "weakening_scope": "[tests/**]",
              "mutation_claim_scope": "[tests/test_*.py]",
              "full_suite": "ci", "ci_job": json.dumps(JOB, ensure_ascii=False)}
    lines = [f"  {ARTEL}:", "    forge: github",
             f"    url: file:///nonexistent/{ARTEL}",
             f"    base: {config.MAIN_BRANCH}", f"    token_slot: {ARTEL}-token",
             "    no_paths: []", "    project_skills: []",
             "    merge_gate: operator", "    components:", "      orch:"]
    lines += [f"        {k}: {v}" for k, v in fields.items()]
    config.TARGETS.write_text("targets:\n" + "\n".join(lines) + "\n",
                              encoding="utf-8")


def test_ac1_job_test_report_and_test_report_fields_unchanged(stand):
    """`job_test_report` на том же архиве отдаёт прежний `TestReport` целиком; поля `TestReport` — ровно `outcomes`, `reason`.

    Сценарий: запись артели с компонентом, чей `ci_job` — задание полного
    набора; подменный `gh` отдаёт check run коммита, прогон и годный
    артефакт с архивом трёх тестов (успех, падение, пропуск). Отчёт равен
    `TestReport(<исходы>)`, `dataclasses.astuple` — `(<исходы>, "")`,
    имена полей — `("outcomes", "reason")`.

    Ловит мутацию: в `TestReport` добавлено поле (в том числе со значением
    по умолчанию, например `times`) — состав полей и `astuple` отличаются;
    `job_test_report` переведён на общий разбор с временем и отдаёт
    исходы с иным видом значения.
    """
    write_artel_with_component()
    cases = three_cases(stand.rng)
    data = junit_zip(cases, "12.5", tests_attr=len(cases) + 1)
    sha = f"{stand.rng.getrandbits(160):040x}"
    stand.gh.attempt(sha, data=data, job_seconds=600)
    report = forge.job_test_report(ARTEL, sha, JOB)
    outcomes = {f"{c}::{n}": o for c, n, _t, o in cases}
    assert report == forge.TestReport(outcomes), stand.note(f"{report}")
    assert dataclasses.astuple(report) == (outcomes, ""), stand.note(f"{report}")
    assert tuple(f.name for f in dataclasses.fields(forge.TestReport)) == (
        "outcomes", "reason")


# ------------------------------------------------------------------- AC-2

@pytest.mark.parametrize("kind", ["report", "none", "outside", "big", "expired",
                                  "skipped"])
def test_ac2_ci_suite_report_outcomes(stand, kind):
    """`ci_suite_report` по подменённым ответам `gh`: отчёт, обрыв, артефакт вне окна, большой архив, истёкший срок, пропущенные попытки.

    Сценарий: у sha — check run задания полного набора длиной
    `job_seconds` (случайная) и артефакт `junit` по варианту. Годный
    артефакт — `times`/`suite_seconds` из архива, `job_seconds` =
    `completed_at − started_at`, причина пустая; артефакта нет (обрыв) —
    `(None, None, job_seconds, причина)`; вне окна попытки, объявленный
    размер больше `config.CI_REPORT_ARCHIVE_MAX_BYTES`, истёкший срок —
    `times` и `suite_seconds` `None`, причина непустая; все попытки
    `skipped` — `job_seconds` `None`, причина называет «задание не
    исполнялось».

    Ловит мутацию: `job_seconds` не считается для попытки без артефакта
    (обрыв неотличим от «не исполнялось»); окно `started_at`–`completed_at`
    не сверяется — поздний артефакт читается; пропущенная попытка отдаёт
    `job_seconds` 0 или причину без «задание не исполнялось».
    """
    rng = stand.rng
    sha = f"{rng.getrandbits(160):040x}"
    job_seconds = rng.randrange(300, 2400)
    times = {f"pkg.m{i}.Case::test_{i}": rng.randrange(1, 5000) / 100
             for i in range(rng.randrange(3, 9))}
    suite = f"{rng.randrange(100, 9000) / 10:.1f}"
    stand.gh.attempt(sha, data=junit_zip(timed_cases(times), suite),
                     job_seconds=job_seconds, kind=kind)
    got = forge.ci_suite_report(ARTEL, sha)
    note = stand.note(f"вариант {kind}; {got}")
    assert isinstance(got, tuple) and len(got) == 4, note
    t, s, j, reason = got
    if kind == "report":
        assert t == times and s == float(suite), note
        assert j == job_seconds and reason == "", note
        return
    assert t is None and s is None, note
    assert isinstance(reason, str) and reason.strip(), note
    if kind == "none":
        assert j == job_seconds, note
    if kind == "skipped":
        assert j is None and NOT_EXECUTED in reason, note


# ------------------------------------------------------------------- AC-3

def branch_runs(stand, present: list) -> dict:
    """Прогоны Actions ветки `main` (новые первыми) с заданием `JOB` по
    видам `present`; {вид: sha}."""
    kinds = {"unfinished": ("in_progress", None, "in_progress", None),
             "skipped": ("completed", "skipped", "completed", "success"),
             "timed_out": ("completed", "timed_out", "completed", "timed_out"),
             "red": ("completed", "failure", "completed", "failure"),
             "green": ("completed", "success", "completed", "success")}
    shas, items = {}, []
    base = datetime(2026, 11, 8, 12, 0, 0)
    for i, kind in enumerate(present):
        jstatus, jconcl, rstatus, rconcl = kinds[kind]
        sha = f"{stand.rng.getrandbits(160):040x}"
        shas[kind] = sha
        run_id = stand.gh.new_id()
        start = base - timedelta(hours=i + 1)
        done = jstatus == "completed"
        job = {"id": stand.gh.new_id(), "run_id": run_id, "name": JOB,
               "status": jstatus, "conclusion": jconcl,
               "started_at": stamp(start),
               "completed_at": stamp(start + timedelta(minutes=20)) if done
               else None, "head_sha": sha}
        other = {"id": stand.gh.new_id(), "run_id": run_id, "name": "changes",
                 "status": "completed", "conclusion": "success",
                 "started_at": stamp(start - timedelta(minutes=1)),
                 "completed_at": stamp(start), "head_sha": sha}
        stand.gh.run_jobs(run_id, [other, job])
        stand.gh.check_runs(sha, [other, job])
        items.append({"id": run_id, "head_sha": sha,
                      "head_branch": config.MAIN_BRANCH, "status": rstatus,
                      "conclusion": rconcl, "event": "push", "name": "CI",
                      "created_at": stamp(start)})
    stand.gh.put(r"actions/runs(\?|\s|$)",
                 json={"total_count": len(items), "workflow_runs": items},
                 list_key="workflow_runs")
    return shas


ALL_RUNS = ["unfinished", "skipped", "timed_out", "red", "green"]


@pytest.mark.parametrize("present,expected", [
    (ALL_RUNS, "timed_out"),
    (["unfinished", "skipped", "red", "green"], "red"),
    (["unfinished", "skipped", "green"], "green"),
    (["unfinished", "skipped"], None),
], ids=["оборванный", "красный", "зелёный", "не найден"])
def test_ac3_last_executed_commit_skips_unfinished_and_skipped(stand, present,
                                                               expected):
    """`last_executed_commit` ветки `main`: первый прогон, где задание завершено с любым заключением, кроме `skipped`.

    Сценарий: подменный `gh` отдаёт прогоны ветки новыми первыми —
    незавершённый, с заданием `skipped`, оборванный (`timed_out`),
    красный, зелёный (в каждом ещё задание `changes` с успехом); у каждого
    прогона — свои задания и check runs коммита. Ответ — sha
    оборванного; без него — красного; без обоих — зелёного; только
    незавершённый и `skipped` — `(None, <непустая причина>)`.

    Ловит мутацию: учитываются только зелёные прогоны (как
    `green_base_commit`) — отдан sha зелёного вместо оборванного или
    красного; незавершённое задание не пропущено — отдан sha
    незавершённого; `skipped` считается исполненным; заключение берётся у
    постороннего задания `changes`.
    """
    shas = branch_runs(stand, present)
    got = forge.last_executed_commit(ARTEL, config.MAIN_BRANCH, JOB)
    note = stand.note(f"прогоны {present}; {got}; sha {shas}")
    assert isinstance(got, tuple) and len(got) == 2, note
    sha, reason = got
    if expected is None:
        assert sha is None and isinstance(reason, str) and reason.strip(), note
    else:
        assert sha == shas[expected], note


# ------------------------------------------------------------------- AC-4

def test_ac4_summarize_counts_testcases_slowest_buckets_and_delta(stand):
    """`summarize` на архиве из 25 тестов с `testsuite@tests` больше числа `testcase`: число, 20 самых медленных, ориентиры, прирост, задачи.

    Сценарий: известный набор 25 узлов (сумма 250 с; два узла по 0,5 с на
    20-й и 21-й позициях, меньший по имени — в архиве вторым) собран в
    архив с `testsuite@tests` = 40 и разобран `parse_junit_times`;
    `summarize` с предыдущей сводкой (10 узлов по 4 с) и списком двух
    задач. `tests` = 25; `slowest` — 20 пар по убыванию, 20-я — меньший по
    имени из равных; четыре ориентира с числом и долей суммы; прирост 15
    тестов и 210 с; `tasks` — переданный список; без `previous` прирост
    `None`. Тот же разбор на случайном наборе (зерно в тексте провала)
    сверяется с эталоном по правилам требования 4.

    Ловит мутацию: число тестов взято из `testsuite@tests` (40 вместо 25);
    при равном времени порядок — по месту в архиве или по убыванию имени
    (20-й — `test_tie_b`); пустой ориентир выпал из `buckets`; доля —
    числом тестов, а не суммой времени; прирост посчитан в обратную
    сторону.
    """
    from orchestrator import suite_cost
    times = dataset25()
    data = junit_zip(timed_cases(times), "61.5", tests_attr=40)
    parsed, suite_seconds, reason = forge.parse_junit_times(data)
    assert reason == "" and parsed is not None, stand.note(reason)
    previous = suite_cost.summarize(uniform_times("prev", 10, 4.0, 4.0),
                                    10.0, 100)
    tasks = [stand.task_id(), stand.task_id()]
    got = suite_cost.summarize(parsed, suite_seconds, 1469, previous, tasks)
    note = stand.note(f"{got}")
    assert got["tests"] == 25, note
    assert got["total_seconds"] == pytest.approx(250.0), note
    slowest = [list(p) for p in got["slowest"]]
    assert len(slowest) == 20, note
    assert slowest[19][0] == "pkg.tie.Case::test_tie_a", note
    _n, _total, ref_slowest, ref_buckets = reference_summary(times)
    assert [p[0] for p in slowest] == [p[0] for p in ref_slowest], note
    assert [p[1] for p in slowest] == pytest.approx([p[1] for p in ref_slowest])
    assert set(got["buckets"]) == set(BUCKETS), note
    for b in BUCKETS:
        assert got["buckets"][b]["count"] == ref_buckets[b]["count"], note
        assert got["buckets"][b]["share"] == pytest.approx(
            ref_buckets[b]["share"]), note
    assert got["delta_tests"] == 15, note
    assert got["delta_seconds"] == pytest.approx(210.0), note
    assert list(got["tasks"]) == tasks, note
    alone = suite_cost.summarize(parsed, suite_seconds, 1469)
    assert alone["delta_tests"] is None and alone["delta_seconds"] is None, \
        stand.note(f"{alone}")

    rng = stand.rng
    rand = {f"pkg.r{i:03d}.Case::test_{rng.choice(LETTERS)}{i:03d}":
            rng.choice([0.25, 0.5, 2.0, 2.0, 15.0, 61.0])
            + rng.randrange(0, 3) * 0.125 for i in range(rng.randrange(21, 60))}
    parsed, suite_seconds, _r = forge.parse_junit_times(
        junit_zip(timed_cases(rand), "9.0", tests_attr=len(rand) * 2))
    got = suite_cost.summarize(parsed, suite_seconds, 10)
    n, total, ref_slowest, ref_buckets = reference_summary(rand)
    note = stand.note(f"случайный набор {rand}; {got}")
    assert got["tests"] == n and got["total_seconds"] == pytest.approx(total), note
    assert [list(p)[0] for p in got["slowest"]] == [p[0] for p in ref_slowest], note
    for b in BUCKETS:
        assert got["buckets"][b]["count"] == ref_buckets[b]["count"], note
        assert got["buckets"][b]["share"] == pytest.approx(
            ref_buckets[b]["share"]), note


# ------------------------------------------------------------------- AC-5

@pytest.mark.parametrize("seconds,bucket", [
    (0.0, "до 1 с"), (0.999, "до 1 с"), (1, "1–10 с"), (9.999, "1–10 с"),
    (10, "10–60 с"), (59.999, "10–60 с"), (60, "60 с и дольше"),
    (3600.5, "60 с и дольше")])
def test_ac5_size_bucket_boundaries(seconds, bucket):
    """`size_bucket` на границах 1, 10 и 60 с: левая граница входит в старший ориентир.

    Ловит мутацию: сравнение `<=` вместо `<` на границе — 1 с, 10 с или
    60 с попадают в младший ориентир.
    """
    from orchestrator import suite_cost
    assert suite_cost.size_bucket(seconds) == bucket


@pytest.mark.parametrize("limit", [2400, 1500, 10000])
@pytest.mark.parametrize("ratio_name,offset,level", [
    ("SUITE_COST_WARN_RATIO", -0.0001, "ok"),
    ("SUITE_COST_WARN_RATIO", 0.0, "warn"),
    ("SUITE_COST_ALERT_RATIO", -0.0001, "warn"),
    ("SUITE_COST_ALERT_RATIO", 0.0, "alert"),
], ids=["74,99 %", "75 %", "84,99 %", "85 %"])
def test_ac5_limit_level_boundaries(limit, ratio_name, offset, level):
    """`limit_level` на долях 74,99 %, 75 %, 84,99 % и 85 % предела: доля, равная порогу, — уже следующий уровень.

    Пороги читаются из `config` (`SUITE_COST_WARN_RATIO`,
    `SUITE_COST_ALERT_RATIO`), а не литералом: значение — крутилка
    Оператора.

    Ловит мутацию: порог `>` вместо `≥` — ровно 75 % даёт `ok`, ровно
    85 % — `warn`; пороги перепутаны местами.
    """
    from orchestrator import suite_cost
    ratio = getattr(config, ratio_name)
    seconds = limit * (ratio + offset)
    assert suite_cost.limit_level(seconds, limit) == level, \
        f"{seconds} из {limit}"


# ------------------------------------------------------------------- AC-6

def merged_tasks_scene(stand) -> tuple:
    """Линия `main`: мерж T3, prev, мержи T1, X (нет в БД), T2, sha.
    (prev, sha, {T1, T2}, T3, X)."""
    t3 = stand.add_task()
    stand.merge(t3)
    prev = stand.commit()
    t1 = stand.add_task()
    stand.merge(t1)
    stray = stand.task_id()
    stand.merge(stray)
    t2 = stand.add_task()
    stand.merge(t2)
    sha = stand.commit()
    return prev, sha, {t1, t2}, t3, stray


def test_ac6_merged_tasks_between_two_shas(stand):
    """`merged_tasks(prev, sha)` — ровно задачи, смерженные в `main` между двумя sha и известные БД.

    Сценарий: в репозитории песочницы на первой родительской линии `main`
    мерж третьей задачи — раньше `prev`; между `prev` и `sha` — мержи двух
    задач проекта и мерж с темой `<x>: merge task/…`, где `<x>` в БД нет.
    Ответ — ровно две задачи.

    Ловит мутацию: интервал без `prev..` (весь лог до `sha`) — в списке
    третья задача; тема не сверяется с БД — в списке `<x>`; лог не по
    первой родительской линии — в списке ещё и коммиты веток с id в теме.
    """
    from orchestrator import suite_cost
    prev, sha, inside, before, stray = merged_tasks_scene(stand)
    got = suite_cost.merged_tasks(prev, sha)
    note = stand.note(f"{got}; ждали {inside}; раньше {before}; нет в БД {stray}")
    assert sorted(got) == sorted(inside), note


# ------------------------------------------------------------------- AC-7

def previous_choice_scene(stand) -> tuple:
    """Записи сводок: предок A с отчётом, ближе — предок B без отчёта,
    коммит C вне линии записан позже всех; затем `--record sha`.
    (код, вывод `suite-cost`, задачи A..sha, задача до A)."""
    root = stand.head()
    t0 = stand.add_task()
    stand.merge(t0)
    a = stand.commit()
    t1 = stand.add_task()
    stand.merge(t1)
    b = stand.commit()
    t2 = stand.add_task()
    stand.merge(t2)
    sha = stand.commit()
    c = stand.side_commit(root)
    for commit, times, job, kind in (
            (a, dataset25(), 1400, "report"),
            (b, None, 2400, "none"),
            (c, uniform_times("side", 31, 10.0, 0.5), 1500, "report")):
        data = junit_zip(timed_cases(times), "50.0") if times else None
        rc, text = stand.record(commit, data, job, kind)
        assert rc == 0, stand.note(f"запись {commit}: {text}")
    stand.backdate(a, timedelta(hours=3))
    stand.backdate(b, timedelta(hours=2))
    stand.backdate(c, timedelta(hours=1))
    rc, text = stand.record(sha, junit_zip(timed_cases(
        uniform_times("now", 44, 8.5, 1.75)), "70.0"), 1450)
    assert rc == 0, stand.note(f"запись {sha}: {text}")
    rc, shown_text = stand.cli("suite-cost")
    return rc, shown_text, {t1, t2}, t0, sha


def test_ac7_record_delta_against_nearest_ancestor_with_report(stand):
    """`suite-cost --record <sha>`: прирост — против ближайшего предка с отчётом, задачи — `merged_tasks` от его sha.

    Сценарий: в песочнице записаны сводки трёх коммитов — предок A с
    отчётом (25 тестов, 250 с), более близкий предок B без отчёта
    (обрыв), коммит C вне линии предков (31 тест, 300,5 с), записанный
    позже всех; между A и `sha` смержены задачи T1 и T2, до A — T0. Запись
    `sha` (44 теста, 367,25 с), затем `suite-cost` без флагов печатает её:
    прирост +19 тестов и 117,25 с, задачи T1 и T2, без T0.

    Ловит мутацию: предыдущая сводка — последняя по времени записи без
    проверки предка (взята C: прирост 13 и 66,75 с, в задачах T0); запись
    без отчёта не пропущена (взята B: прироста нет, задачи — только T2).
    """
    rc, text, tasks, t0, sha = previous_choice_scene(stand)
    note = stand.note(f"код {rc}\n{text}")
    assert rc == 0 and sha[:7] in text, note
    assert has_number(text, 117.25, (2, 3)), note
    assert has_number(text, 19), note
    assert not has_number(text, 66.75, (2, 3)), note
    assert all(t in text for t in tasks) and t0 not in text, note


# ------------------------------------------------------------------- AC-8

def test_ac8_record_once_per_sha_and_keeps_outage(stand):
    """Повторная запись того же sha второй записи не даёт и первую не меняет; обрыв записан с `job_seconds` и причиной.

    Сценарий: `--record sha` с отчётом; затем тот же sha с иными ответами
    `gh` (другая длительность и набор) — строка сводки одна и совпадает с
    первой. Коммит с попыткой без артефакта (обрыв, 2400 с) записан:
    строка несёт 2400 и причину, которую для него отдаёт
    `forge.ci_suite_report`.

    Ловит мутацию: повтор записывает вторую запись (`INSERT` без
    уникальности пары «проект, sha») либо переписывает первую
    (`INSERT OR REPLACE`); попытка без отчёта не записывается или теряет
    причину.
    """
    sha = stand.commit()
    rc, text = stand.record(sha, junit_zip(timed_cases(dataset25()), "61.5"), 1469)
    assert rc == 0, stand.note(text)
    first = stand.rows_with(sha)
    assert len(first) == 1, stand.note(f"{first}")
    stand.record(sha, junit_zip(timed_cases(uniform_times("x", 7, 3.0, 1.0)),
                                "9.0"), 1700)
    again = stand.rows_with(sha)
    assert again == first, stand.note(f"было {first}\nстало {again}")

    outage = stand.commit()
    rc, text = stand.record(outage, None, 2400, kind="none")
    assert rc == 0, stand.note(text)
    rows = stand.rows_with(outage)
    assert len(rows) == 1, stand.note(f"{rows}")
    reason = forge.ci_suite_report(ARTEL, outage)[3]
    stored = " ".join(str(v) for v in rows[0][2].values())
    assert reason and reason in stored, stand.note(f"{reason!r} не в {stored}")
    assert has_number(stored, 2400, (0, 1)), stand.note(stored)


def test_ac8_migrate_creates_summary_table(stand):
    """`migrate()` на БД без таблицы сводок её создаёт, и запись в неё проходит.

    Сценарий: запись сводки находит таблицу (строка с sha); таблица
    удалена — БД «прошлой версии». `orchestrator.schema.migrate(conn)`
    возвращает таблицу, `--record` нового sha её строку записывает.

    Ловит мутацию: таблица объявлена только в `SCHEMA`, без `migrate()` —
    после удаления её нет, и запись отказывает.
    """
    sha = stand.commit()
    rc, text = stand.record(sha, junit_zip(timed_cases(dataset25()), "61.5"), 1469)
    rows = stand.rows_with(sha)
    assert rc == 0 and len(rows) == 1, stand.note(f"{text}\n{rows}")
    table = rows[0][0]
    conn = store.db()
    conn.execute(f'DROP TABLE "{table}"')
    conn.commit()
    schema.migrate(conn)
    conn.commit()
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert table in names, stand.note(f"{table} не в {names}")
    fresh = stand.commit()
    rc, text = stand.record(fresh, junit_zip(timed_cases(dataset25()), "61.5"),
                            1469)
    assert rc == 0 and [r[0] for r in stand.rows_with(fresh)] == [table], \
        stand.note(text)


# ------------------------------------------------------------------- AC-9

def test_ac9_show_latest_summary_without_writing(stand):
    """`suite-cost` без флагов печатает последнюю сводку — значения `summarize` на том же входе — и ничего не пишет.

    Сценарий: записаны сводки A (10 тестов) и B (25 тестов известного
    времени, после мержа задачи T1); запись A сдвинута в прошлое. Вывод
    `suite-cost` несёт sha B, `tests`, `total_seconds`, `suite_seconds`,
    `job_seconds`, все 20 узлов `slowest` (и ни одного из 5 прочих),
    четыре ориентира строкой с числом и долей, прирост и T1 — те же, что
    `summarize(times_B, …, previous=summarize(times_A, …), tasks=[T1])`;
    дамп БД до и после вызова совпадает.

    Ловит мутацию: печать без флагов записывает (журнал, повторная
    запись); печатается первая запись вместо последней; в выводе не все
    20 узлов или лишние; ориентиры без доли.
    """
    from orchestrator import suite_cost
    a = stand.commit()
    times_a = uniform_times("prev", 10, 4.0, 4.0)
    stand.record(a, junit_zip(timed_cases(times_a), "15.0"), 900)
    t1 = stand.add_task()
    stand.merge(t1)
    b = stand.commit()
    times_b = dataset25()
    rc, text = stand.record(b, junit_zip(timed_cases(times_b), "61.5"), 1469)
    assert rc == 0, stand.note(text)
    stand.backdate(a, timedelta(hours=4))
    expected = suite_cost.summarize(
        times_b, 61.5, 1469, suite_cost.summarize(times_a, 15.0, 900), [t1])

    before = stand.dump()
    rc, text = stand.cli("suite-cost")
    assert stand.dump() == before, stand.note("без флагов БД изменилась")
    note = stand.note(f"код {rc}\n{text}\nждали {expected}")
    assert rc == 0 and b[:7] in text, note
    for key in ("tests", "total_seconds", "suite_seconds", "job_seconds",
                "delta_tests", "delta_seconds"):
        assert has_number(text, expected[key]), f"{key}: {note}"
    names = [list(p)[0] for p in expected["slowest"]]
    assert len(names) == 20 and all(n in text for n in names), note
    assert not [n for n in times_b if n not in names and n in text], note
    lines = text.splitlines()
    for bucket, value in expected["buckets"].items():
        assert any(bucket in ln and has_number(ln, value["count"], (0,))
                   and has_share(ln, value["share"]) for ln in lines), \
            f"ориентир {bucket}: {note}"
    assert t1 in text, note


def test_ac9_record_skipped_and_record_latest(stand):
    """`--record` пишет сводку sha, на `skipped` попытке — отказ «задание не исполнялось» без записи; `--record-latest` пишет sha из `forge.last_executed_commit`.

    Сценарий: `--record sha1` с годным отчётом — строка сводки sha1 есть;
    `--record sha2`, у которого все попытки `skipped`, — ненулевой код,
    вывод называет «задание не исполнялось», строки sha2 нет;
    `forge.last_executed_commit` подменён и отдаёт sha3 — `--record-latest`
    записывает сводку sha3.

    Ловит мутацию: `skipped` попытка записана (строка sha2 есть или код 0);
    `--record-latest` берёт голову `main` вместо ответа
    `last_executed_commit`.
    """
    sha1 = stand.commit()
    rc, text = stand.record(sha1, junit_zip(timed_cases(dataset25()), "61.5"),
                            1469)
    assert rc == 0 and len(stand.rows_with(sha1)) == 1, stand.note(text)
    sha2 = stand.commit()
    rc, text = stand.record(sha2, None, 0, kind="skipped")
    note = stand.note(f"код {rc}\n{text}")
    assert rc != 0 and NOT_EXECUTED in text, note
    assert stand.rows_with(sha2) == [], note
    sha3 = stand.commit()
    stand.commit()
    stand.gh.attempt(sha3, data=junit_zip(timed_cases(dataset25()), "61.5"),
                     job_seconds=1300)
    asked = []

    def latest(target, branch, job_name):
        asked.append((target, branch, job_name))
        return sha3, ""

    stand.mp.setattr(forge, "last_executed_commit", latest)
    rc, text = stand.cli("suite-cost", "--record-latest")
    note = stand.note(f"код {rc}\n{text}; вызовы {asked}")
    assert rc == 0 and len(stand.rows_with(sha3)) == 1, note
    assert asked and asked[0] == (ARTEL, config.MAIN_BRANCH, JOB), note


def test_ac9_command_listed_in_help_and_refused_to_role(stand):
    """`suite-cost` есть в блоке «Команды:» справки модуля и недоступна процессу роли.

    Сценарий: в докстринге `orchestrator.artel` после строки «Команды:»
    есть строка с `suite-cost`; с признаком процесса роли `suite-cost`
    отказывает «команда недоступна процессу роли» и сводку не пишет, без
    признака — исполняется (не «Неизвестная команда»).

    Ловит мутацию: команда внесена в белый список ролей — под ролью она
    исполняется; строки справки нет.
    """
    doc = artel.__doc__ or ""
    assert "Команды:" in doc
    assert "suite-cost" in doc.split("Команды:", 1)[1]
    rc, text = stand.cli("suite-cost")
    assert "Неизвестная команда" not in text, stand.note(text)
    sha = stand.commit()
    stand.gh.attempt(sha, data=junit_zip(timed_cases(dataset25()), "61.5"),
                     job_seconds=1469)
    stand.mp.setattr(runner, "in_role_environment", lambda env=None: True)
    rc, text = stand.cli("suite-cost", "--record", sha)
    note = stand.note(f"код {rc}\n{text}")
    assert rc != 0 and "недоступна процессу роли" in text, note
    assert stand.rows_with(sha) == [], note


# ------------------------------------------------------------------ AC-10

AGE_5H = re.compile(r"(?<![0-9])(5\s*ч|5:0\d|5[.,]0\d*\s*ч|30\d\s*мин|"
                    r"18\d\d\d\s*с|5\s*h)")
AGE_2H = re.compile(r"(?<![0-9])(2\s*ч|2:0\d|2[.,]0\d*\s*ч|12\d\s*мин|"
                    r"7\d\d\d\s*с|2\s*h)")


def ci_and_local(stand, ci_seconds: int, local_seconds: float,
                 kind: str = "report", limit: int = 1500) -> tuple:
    """Сводка `main` с `job_seconds` = `ci_seconds` (5 ч назад) и запись
    «прогон: время» задачи артели (2 ч назад) при пределе профиля `limit`.
    (sha, id задачи)."""
    stand.set_local_limit(limit)
    sha = stand.commit()
    data = junit_zip(timed_cases(dataset25()), "61.5") if kind == "report" else None
    rc, text = stand.record(sha, data, ci_seconds, kind)
    assert rc == 0, stand.note(text)
    stand.backdate(sha, timedelta(hours=5))
    task = stand.add_task()
    stand.journal_local(task, local_seconds)
    return sha, task


def test_ac10_doctor_warn_and_alert_levels(stand):
    """CI 1860 из 2400 с — «предупреждение» 77,5 %; локальный прогон 1300 из 1500 с — «тревога» 86,7 % и один алерт `suite.cost`; повтор с иными числами второго алерта не даёт.

    Сценарий: сводка `job_seconds` 1860 записана 5 ч назад, запись
    «прогон: время» задачи артели 1300 с — 2 ч назад, предел профиля
    1500 с. Строка «CI:» `suite-cost:<артель>` — `warn`, «предупреждение»,
    77,5 %, sha и возраст 5 ч; строка «локальный прогон:» — `warn`,
    «тревога», 86,7 %, предел 1500 и возраст 2 ч; открыт ровно один алерт
    kind=trigger, источник `suite.cost`, проекта артели. Новая запись
    1400 с (93,3 %) и повторный `doctor` — алерт по-прежнему один; `fail`
    ни у одной строки.

    Ловит мутацию: время попытки CI сравнивается с пределом локального
    прогона (CI 124 % — «тревога»); сообщение алерта несёт числа — второй
    открытый алерт; уровень `alert` даёт статус `fail`.
    """
    sha, task = ci_and_local(stand, 1860, 1300)
    ci_line, local, mine = stand.doctor_lines()
    note = stand.note(shown(mine))
    assert ci_line is not None and local is not None, note
    assert ci_line.status == "warn" and "предупреждение" in ci_line.detail, note
    assert "тревога" not in ci_line.detail, note
    assert re.search(percent_re(77.5), ci_line.detail), note
    assert sha[:7] in ci_line.detail and AGE_5H.search(ci_line.detail), note
    assert local.status == "warn" and "тревога" in local.detail, note
    assert re.search(percent_re(1300 / 1500 * 100), local.detail), note
    assert "1500" in local.detail and AGE_2H.search(local.detail), note
    assert len(stand.cost_alerts()) == 1, note
    assert all(c.status != "fail" for c in mine), note

    stand.journal_local(task, 1400, ago=timedelta(hours=1))
    _ci, local, mine = stand.doctor_lines()
    note = stand.note(shown(mine))
    assert local is not None and "тревога" in local.detail, note
    assert len(stand.cost_alerts()) == 1, note
    assert all(c.status != "fail" for c in mine), note


def test_ac10_doctor_ok_at_seventy_percent(stand):
    """При 70 % обоих пределов обе строки `suite-cost:<артель>` — `ok`, алерта нет.

    Сценарий: сводка `job_seconds` 1680 (70 % от 2400), запись
    «прогон: время» 1050 с при пределе 1500 (70 %).

    Ловит мутацию: порог предупреждения ниже 75 % или уровень считается
    от суммы двух длительностей — строка `warn`, заведён алерт.
    """
    ci_and_local(stand, 1680, 1050)
    ci_line, local, mine = stand.doctor_lines()
    note = stand.note(shown(mine))
    assert ci_line is not None and ci_line.status == "ok", note
    assert local is not None and local.status == "ok", note
    assert stand.cost_alerts() == [], note


def test_ac10_doctor_outage_summary_is_alert_with_reason(stand):
    """Сводка без отчёта с `job_seconds` 2400 — строка «CI:» «тревога» с причиной отсутствия отчёта.

    Сценарий: запись коммита, у попытки которого нет годного артефакта
    (обрыв, 2400 с); локальный прогон 300 из 1500 с. Строка «CI:» —
    `warn`, «тревога», текст несёт причину, которую для этого sha отдаёт
    `forge.ci_suite_report`; алерт `suite.cost` открыт; `fail` нет.

    Ловит мутацию: сводка без отчёта пропускается проверкой (строка без
    уровня или «пропуск»); причина отсутствия отчёта не печатается.
    """
    sha, _task = ci_and_local(stand, 2400, 300, kind="none")
    reason = forge.ci_suite_report(ARTEL, sha)[3]
    ci_line, _local, mine = stand.doctor_lines()
    note = stand.note(f"причина {reason!r}\n{shown(mine)}")
    assert ci_line is not None and ci_line.status == "warn", note
    assert "тревога" in ci_line.detail and reason and reason in ci_line.detail, note
    assert len(stand.cost_alerts()) == 1, note
    assert all(c.status != "fail" for c in mine), note


def test_ac10_doctor_without_summary_and_with_unread_limit(stand):
    """Без сводки строка «CI:» — пропуск с причиной, строка локального прогона остаётся; `TargetsError` предела — пропуск строки локального прогона с причиной исключения.

    Сценарий: только запись «прогон: время» 1300 с (сводок нет) — строка
    «CI:» `skip` с непустой причиной, строка «локальный прогон:» есть с
    уровнем `warn`. Затем записана сводка, а
    `project_profile.full_suite_limit` бросает `targets.TargetsError` со
    случайным текстом — `all_checks` не падает, строка «локальный прогон:»
    `skip` и несёт текст исключения, строка «CI:» на месте; `fail` нет.

    Ловит мутацию: без сводки проверка не строится вовсе (нет и строки
    локального прогона); `TargetsError` не перехвачен — `all_checks`
    падает; при ошибке предела подставлен предел `config`.
    """
    stand.set_local_limit(1500)
    task = stand.add_task()
    stand.journal_local(task, 1300)
    ci_line, local, mine = stand.doctor_lines()
    note = stand.note(shown(mine))
    assert ci_line is not None and ci_line.status == "skip", note
    assert ci_line.detail[len("CI:"):].strip(), note
    assert local is not None and local.status == "warn", note
    assert all(c.status != "fail" for c in mine), note

    sha = stand.commit()
    rc, text = stand.record(sha, junit_zip(timed_cases(dataset25()), "61.5"), 900)
    assert rc == 0, stand.note(text)
    why = stand.word("предел-не-прочитан-", 8)

    def broken(target):
        raise targets.TargetsError(why)

    stand.mp.setattr(project_profile, "full_suite_limit", broken)
    ci_line, local, mine = stand.doctor_lines()
    note = stand.note(shown(mine))
    assert local is not None and local.status == "skip" and why in local.detail, note
    assert ci_line is not None and ci_line.status in ("ok", "warn"), note
    assert all(c.status != "fail" for c in mine), note


# ------------------------------------------------------------------ AC-11

def job_timeout_minutes(text: str, job_name: str) -> int | None:
    """`timeout-minutes` задания с `name: <job_name>` в тексте workflow."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s+)name:\s*(.+?)\s*$", line)
        if not m or m.group(2).strip("'\"") != job_name:
            continue
        indent = len(m.group(1))
        for later in lines[i + 1:]:
            if not later.strip() or later.lstrip().startswith("#"):
                continue
            if len(later) - len(later.lstrip()) < indent:
                break
            t = re.match(rf"^\s{{{indent}}}timeout-minutes:\s*(\d+)\s*$", later)
            if t:
                return int(t.group(1))
        start = i
        for earlier in reversed(lines[:start]):
            if not earlier.strip() or earlier.lstrip().startswith("#"):
                continue
            if len(earlier) - len(earlier.lstrip()) < indent:
                break
            t = re.match(rf"^\s{{{indent}}}timeout-minutes:\s*(\d+)\s*$", earlier)
            if t:
                return int(t.group(1))
    return None


def test_ac11_ci_limit_matches_workflow_timeout():
    """`config.SUITE_COST_CI_LIMIT_SEC` равен `timeout-minutes` × 60 задания `ci.FULL_SUITE_JOB` в `.github/workflows/ci.yml`.

    Сценарий: текст workflow репозитория читается от `__file__` теста;
    у задания с `name:` — `ci.FULL_SUITE_JOB` берётся `timeout-minutes`
    того же уровня отступа. Строку реестра `docs/triggers.md` для
    `suite.cost` сверяет ревью диффа (указание Оператора на гейте SPEC):
    чтение живого файла `docs/` отклонил бы линт детерминизма.

    Ловит мутацию: константа предела CI задана литералом, разошедшимся с
    `timeout-minutes` (2400 при 45 мин), или в минутах (40 вместо 2400).
    """
    workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
    minutes = job_timeout_minutes(workflow.read_text(encoding="utf-8"), JOB)
    assert minutes is not None, f"у задания «{JOB}» нет timeout-minutes"
    assert config.SUITE_COST_CI_LIMIT_SEC == minutes * 60


# ------------------------------------------------------------------ AC-12

MUTATIONS = ["testsuite_tests", "strict_threshold", "outside_interval",
             "test_report_field", "second_record", "ci_vs_local_limit",
             "latest_without_ancestor", "skipped_recorded", "only_green",
             "schema_only"]


@pytest.mark.parametrize("mutation", MUTATIONS)
def test_ac12_each_named_mutation_turns_its_criterion_red(stand, mutation):
    """Каждая мутация AC-12 меняет исход своего различающего сценария из AC-1…AC-10.

    Пары «мутация — сценарий»: число тестов из `testsuite@tests` (AC-4:
    25 `testcase` при `tests` = 40); `>` вместо `≥` (AC-5: ровно порог и
    ровно 1/10/60 с); задача вне интервала (AC-6: мерж до `prev`); поле
    `TestReport` (AC-1: состав полей); повтор — вторая запись (AC-8);
    время попытки против локального предела (AC-10: CI 1860 при локальном
    1500 — «предупреждение»); последняя по времени без проверки предка
    (AC-7); `skipped` записана (AC-9); только зелёные (AC-3: оборванный
    новее зелёного); таблица только в `SCHEMA` (AC-8: удаление и
    `migrate()`).

    Ловит мутацию: каждая из названных в AC-12 — утверждение её пары
    краснеет (25 ≠ 40; порог даёт младший уровень; в списке задача до
    `prev`; лишнее поле; две строки; «тревога» в строке «CI:»; прирост
    против C; строка `skipped` sha; sha зелёного; таблицы нет).
    """
    from orchestrator import suite_cost
    if mutation == "testsuite_tests":
        parsed, suite, _r = forge.parse_junit_times(
            junit_zip(timed_cases(dataset25()), "61.5", tests_attr=40))
        assert suite_cost.summarize(parsed, suite, 100)["tests"] == 25
    elif mutation == "strict_threshold":
        assert suite_cost.limit_level(
            2400 * config.SUITE_COST_WARN_RATIO, 2400) == "warn"
        assert suite_cost.limit_level(
            2400 * config.SUITE_COST_ALERT_RATIO, 2400) == "alert"
        assert [suite_cost.size_bucket(s) for s in (1, 10, 60)] == list(BUCKETS[1:])
    elif mutation == "outside_interval":
        prev, sha, inside, before, stray = merged_tasks_scene(stand)
        got = suite_cost.merged_tasks(prev, sha)
        assert before not in got and stray not in got and set(got) == inside, \
            stand.note(f"{got}")
    elif mutation == "test_report_field":
        assert [f.name for f in dataclasses.fields(forge.TestReport)] == [
            "outcomes", "reason"]
    elif mutation == "second_record":
        sha = stand.commit()
        stand.record(sha, junit_zip(timed_cases(dataset25()), "61.5"), 1469)
        stand.record(sha, junit_zip(timed_cases(dataset25()), "61.5"), 1500)
        assert len(stand.rows_with(sha)) == 1, stand.note()
    elif mutation == "ci_vs_local_limit":
        ci_and_local(stand, 1860, 300)
        ci_line, _local, mine = stand.doctor_lines()
        assert ci_line is not None and "предупреждение" in ci_line.detail \
            and "тревога" not in ci_line.detail, stand.note(shown(mine))
    elif mutation == "latest_without_ancestor":
        rc, text, tasks, t0, _sha = previous_choice_scene(stand)
        assert has_number(text, 117.25, (2, 3)) and t0 not in text, \
            stand.note(text)
    elif mutation == "skipped_recorded":
        sha = stand.commit()
        rc, text = stand.record(sha, None, 0, kind="skipped")
        assert rc != 0 and stand.rows_with(sha) == [], stand.note(text)
    elif mutation == "only_green":
        shas = branch_runs(stand, ALL_RUNS)
        assert forge.last_executed_commit(ARTEL, config.MAIN_BRANCH, JOB)[0] \
            == shas["timed_out"], stand.note(f"{shas}")
    else:
        sha = stand.commit()
        stand.record(sha, junit_zip(timed_cases(dataset25()), "61.5"), 1469)
        rows = stand.rows_with(sha)
        assert len(rows) == 1, stand.note()
        conn = store.db()
        conn.execute(f'DROP TABLE "{rows[0][0]}"')
        conn.commit()
        schema.migrate(conn)
        assert rows[0][0] in {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
