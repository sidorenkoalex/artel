"""Отчёт `mutation-run --wait` печатает строки таблицы «мутация → исход».

Группа: долгоживущий
Красен до реализации: отчёт `--wait` печатает только сводку (поле `report` файла `mutation-result.json`) либо строку «прогон №<n> ещё идёт»/«оборван», а строк файла `<id>-mutation-run-<n>.mutations.tsv` и строки «таблица ещё не начата» в выводе нет; тест AC-8 держит прежнее свойство и зелен с рождения.

Стенд держит связку «команда — фоновый прогон — git — pytest»: настоящий git
(фикстура `real_git`), внешний проект песочницы с клоном и bare-`origin`
(`make_project_repo`), задача в БД пульта с рабочей копией
(`workspace.ensure`). Профиль тестов проекта — раннер пульта с
`report: junit-xml`; модуль проекта `core_<слово>.py` с функциями
`add`/`mul` и тест `tests/test_<слово>.py`; патчи мутаций —
`mutation-<nnn>.diff` каталога документов задачи.

Команда зовётся в процессе теста — `artel.main()` с подменённым
`sys.argv`. Фоновый процесс, который команда запускает
(`subprocess.Popen` интерпретатора с `-c …orchestrator…`), по плану
сценария либо исполняется здесь же тем же кодом в переданном окружении
(режим «run»), либо не исполняется вовсе (режим «hold» — прогон ещё не
начал таблицу); pid, который видит команда, — мёртвый или живой дочерний
процесс песочницы. Узел прогона `acceptance.run_full_suite` обёрнут
наблюдателем, который по номеру вызова зовёт настоящий узел либо
подменяет исход («предел», исключение). `git` на PATH — обёртка: после
`git clean` во временной копии `artel-suite-base-…` она по флагу
сценария оставляет посторонний файл, начиная с заданного числа
применённых патчей. Ожидания по часам нет: «прогон ещё идёт» и
«процесс умер без отчёта» разыгрываются вызовом `--wait 0` при живом или
мёртвом pid и отсутствующем отчёте.

Входы (слова, имена, число и порядок патчей, срез таблицы) — от зерна;
зерно печатается и входит в текст провала.
"""
import contextlib
import difflib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import acceptance, artel, config, store, suite_lock, workspace
from tests.sandbox import _alive_foreign_pid, _dead_pid, make_project_repo

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
COPY_PREFIX = "artel-suite-base-"

KILLED = "убита"
SURVIVED = "не убита"
CUT = "оборвана по пределу"
NOT_RUN = "не прогнана (предел)"
COLUMNS = "номер\tисход\tузлы"
NOT_STARTED = "таблица ещё не начата"
EXCEPTION_REPORT = "прогон оборван исключением пульта"
TIMEOUT_HEAD = "прогон полного набора tests/ превысил "

PROJECT_ENTRY = """  {name}:
    forge: github
    url: file://{origin}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
      full_suite_timeout_sec: {limit}
"""

PYTEST_INI = "[pytest]\npythonpath = .\n"

MODULE = """# модуль песочницы {w}
def add(a, b):
    return a + b


def mul(a, b):
    return a * b
"""

TEST_FILE = """import core_{w}


def test_add_{w}():
    assert core_{w}.add(2, 3) == 5


def test_mul_{w}():
    assert core_{w}.mul(2, 3) == 6
"""

BREAKS = ("return a - b", "return a * b", "return a + b + 1")

# Обёртка git: после `git clean` во временной копии, когда применённых
# патчей (`git apply` без `--check`) уже не меньше числа из файла-флага,
# оставляет в копии посторонний файл.
GIT_WRAPPER = '''#!{python}
import json, os, subprocess, sys
REAL = {real!r}
args = sys.argv[1:]
cwd = os.getcwd()
repo, index = cwd, 0
while index + 1 < len(args) and args[index] == "-C":
    repo = os.path.join(repo, args[index + 1])
    index += 2
sub = args[index] if index < len(args) else ""
if any({prefix!r} in str(a) for a in args) or {prefix!r} in cwd:
    with open({log!r}, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"args": args, "sub": sub}}) + "\\n")
    if sub == "clean" and os.path.exists({flag!r}):
        with open({flag!r}, encoding="utf-8") as fh:
            need = int(fh.read().strip() or "1")
        with open({log!r}, encoding="utf-8") as fh:
            applied = sum(1 for r in map(json.loads, fh.read().splitlines())
                          if r["sub"] == "apply" and not {{"--check", "--stat",
                          "--numstat", "--summary"}} & set(r["args"]))
        if applied >= need:
            code = subprocess.call([REAL, *args])
            with open(os.path.join(repo, {stray!r}), "w", encoding="utf-8") as fh:
                fh.write("посторонний файл песочницы\\n")
            sys.exit(code)
os.execv(REAL, [REAL, *args])
'''


def numbered(n: int) -> str:
    return f"mutation-{n:03d}.diff"


def file_diff(path: str, before: str, after: str) -> str:
    lines = difflib.unified_diff(before.splitlines(True),
                                 after.splitlines(True),
                                 f"a/{path}", f"b/{path}")
    return f"diff --git a/{path} b/{path}\n" + "".join(lines)


class RunProbe:
    """Обёртка `acceptance.run_full_suite`: запись вызовов и подмена исхода.

    `plan` — номер вызова (с 1, первый — контрольный прогон) -> "timeout"
    (исход «предел») либо "raise" (исключение посреди прогона); прочие
    вызовы идут в настоящий узел."""

    def __init__(self, real):
        self.real = real
        self.calls = []
        self.plan = {}

    def __call__(self, root, *args, **kwargs):
        number = len(self.calls) + 1
        limit = kwargs.get("limit", args[4] if len(args) > 4 else None)
        self.calls.append({"n": number, "root": str(root), "limit": limit})
        action = self.plan.get(number, "real")
        if action == "raise":
            raise RuntimeError("подмена песочницы: исключение посреди прогона")
        if action == "timeout":
            seconds, source = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")
            return False, (f"{TIMEOUT_HEAD}{seconds}с — завис или ждёт "
                           f"сетевой ответ (источник: {source})\n")
        return self.real(root, *args, **kwargs)


class Bench:
    """Проект песочницы, задачи, команда `mutation-run` в процессе теста."""

    def __init__(self, sandbox):
        self.sandbox = sandbox
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.probe_dir = Path(tempfile.mkdtemp(
            prefix="artel-mutation-table-")).resolve()
        sandbox.addCleanup(shutil.rmtree, self.probe_dir, ignore_errors=True)
        self.git_log = self.probe_dir / "git.jsonl"
        self.stray_flag = self.probe_dir / "stray-after"
        self.stray = f"stray-{self.word()}.txt"
        bin_dir = self.probe_dir / "bin"
        bin_dir.mkdir()
        real_git = shutil.which("git")
        if not real_git:
            raise RuntimeError("git не найден на PATH")
        wrapper = bin_dir / "git"
        wrapper.write_text(GIT_WRAPPER.format(
            python=sys.executable, real=real_git, prefix=COPY_PREFIX,
            log=str(self.git_log), flag=str(self.stray_flag),
            stray=self.stray), encoding="utf-8")
        wrapper.chmod(0o755)
        self.start_patch(mock.patch.dict(os.environ, {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "PYTHONDONTWRITEBYTECODE": "1"}))
        self.start_patch(mock.patch.object(config, "FULL_SUITE_WORKERS", 2))
        self.conn = store.db()
        self.entries = []
        self.child_errors = []
        # Режим фонового процесса: "run" — исполнить здесь же, "hold" —
        # не исполнять; pid, который получает команда.
        self.background = "run"
        self.pid = _dead_pid()

    def start_patch(self, patcher):
        value = patcher.start()
        self.sandbox.addCleanup(patcher.stop)
        return value

    # --- фикстуры сценария ----------------------------------------------------

    def word(self, size: int = 7) -> str:
        return "".join(self.rng.choice(LETTERS) for _ in range(size))

    def new_task_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ALPHABET) for _ in range(23))

    def add_project(self) -> dict:
        w = self.word()
        target = "p" + self.word()
        limit = self.rng.randint(1000, 3000)
        origin = config.PROJECTS / target / "origin.git"
        self.entries.append(PROJECT_ENTRY.format(
            name=target, origin=origin, base=config.MAIN_BRANCH, limit=limit))
        text = "targets:\n" + "".join(self.entries)
        for path in {Path(config.TARGETS), self.sandbox.root / "targets.yaml"}:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        clone = make_project_repo(target)
        files = {"pytest.ini": PYTEST_INI,
                 f"core_{w}.py": MODULE.format(w=w),
                 f"tests/test_{w}.py": TEST_FILE.format(w=w)}
        for rel, body in files.items():
            path = clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        self.sandbox.git("-C", str(clone), "add", "-A")
        self.sandbox.git("-C", str(clone), "commit", "-q", "-m",
                         "проект песочницы")
        self.sandbox.git("-C", str(clone), "push", "-q", "origin",
                         config.MAIN_BRANCH)
        return {"target": target, "w": w, "clone": clone,
                "module": f"core_{w}.py", "test": f"tests/test_{w}.py",
                "files": files}

    def add_task(self, project: dict) -> str:
        task_id = self.new_task_id()
        branch = f"task/{task_id.lower()}-mutation-table"
        store.insert_task(self.conn, task_id, "Фикстура mutation-run",
                          "in_dev", branch, project["target"], 25.0)
        _wt, error = workspace.ensure(task_id, branch)
        if error:
            raise RuntimeError(f"рабочая копия не заведена: {error}")
        return task_id

    def docs_dir(self, project: dict, task_id: str) -> Path:
        return config.PROJECTS / project["target"] / "tasks" / task_id

    def write_patches(self, project: dict, task_id: str, patches: list) -> None:
        folder = self.docs_dir(project, task_id)
        folder.mkdir(parents=True, exist_ok=True)
        for number, text in enumerate(patches, start=1):
            (folder / numbered(number)).write_text(text, encoding="utf-8")

    def commit_ref(self, project: dict, task_id: str, patches: list) -> str:
        """Коммит ссылки `refs/artifacts/<id>` клона с патчами задачи."""
        clone = project["clone"]
        holder = Path(tempfile.mkdtemp(prefix="artel-mutation-ref-"))
        self.sandbox.addCleanup(shutil.rmtree, holder, ignore_errors=True)
        work = holder / "w"
        self.sandbox.git("-C", str(clone), "worktree", "add", "-q",
                         "--detach", str(work), "HEAD")
        folder = work / "tasks" / task_id
        folder.mkdir(parents=True)
        for number, text in enumerate(patches, start=1):
            (folder / numbered(number)).write_text(text, encoding="utf-8")
        self.sandbox.git("-C", str(work), "add", "-A")
        self.sandbox.git("-C", str(work), "commit", "-q", "-m",
                         "документы задачи")
        sha = self.sandbox.git("-C", str(work), "rev-parse", "HEAD").strip()
        self.sandbox.git("-C", str(clone), "update-ref",
                         f"refs/artifacts/{task_id}", sha)
        self.sandbox.git("-C", str(clone), "worktree", "remove", "--force",
                         str(work))
        return sha

    def breaking(self, project: dict) -> str:
        before = project["files"][project["module"]]
        return file_diff(project["module"], before,
                         before.replace("return a + b",
                                        self.rng.choice(BREAKS)))

    def comment(self, project: dict) -> str:
        before = project["files"][project["module"]]
        old = f"# модуль песочницы {project['w']}"
        return file_diff(project["module"], before,
                         before.replace(old, f"{old}: {self.word()}"))

    def probe(self) -> RunProbe:
        probe = RunProbe(acceptance.run_full_suite)
        self.start_patch(mock.patch.object(acceptance, "run_full_suite", probe))
        return probe

    # --- команда --------------------------------------------------------------

    def run_child(self, tokens: list, kwargs: dict) -> None:
        """Фоновый процесс команды — в процессе теста, тем же кодом."""
        env = kwargs.get("env")
        environ = (mock.patch.dict(os.environ, env, clear=True)
                   if env is not None else contextlib.nullcontext())
        saved_argv, saved_cwd = sys.argv, os.getcwd()
        try:
            with environ:
                if kwargs.get("cwd"):
                    os.chdir(kwargs["cwd"])
                sys.argv = ["-c", *tokens[3:]]
                exec(compile(tokens[2], "<mutation-run child>", "exec"),
                     {"__name__": "__main__"})
        except SystemExit as exc:
            if exc.code not in (None, 0):
                self.child_errors.append(f"фоновый процесс: выход {exc.code}")
        except Exception:  # noqa: BLE001 — исход фонового процесса виден тесту
            self.child_errors.append(traceback.format_exc())
        finally:
            sys.argv = saved_argv
            os.chdir(saved_cwd)

    def popen(self):
        real_popen = subprocess.Popen

        def popen(argv, *args, **kwargs):
            tokens = ([str(t) for t in argv]
                      if isinstance(argv, (list, tuple)) else [])
            child = (len(tokens) > 2 and tokens[0] == sys.executable
                     and tokens[1] == "-c" and "orchestrator" in tokens[2])
            if not child:
                return real_popen(argv, *args, **kwargs)
            if self.background == "run":
                self.run_child(tokens, kwargs)
            proc = mock.Mock(pid=self.pid, returncode=None)
            proc.poll.return_value = None
            return proc

        return mock.patch.object(subprocess, "Popen", popen)

    def command(self, *args: str) -> tuple:
        """(код выхода, вывод stdout и stderr) `artel.py mutation-run <args>`."""
        buf, code = io.StringIO(), 0
        with mock.patch.object(sys, "argv", ["artel.py", "mutation-run", *args]), \
                self.popen(), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                artel.main()
            except SystemExit as exc:
                code = exc.code
                if isinstance(code, str):
                    buf.write(code + "\n")
        return (0 if code is None else code), buf.getvalue()

    def start(self, task_id: str, project: dict) -> int:
        """Запуск прогона без `--wait`; номер прогона из вывода команды."""
        _code, out = self.command(task_id, "--ref", "head", "--tests",
                                  project["test"])
        match = re.search(r"прогон №(\d+)", out)
        if match is None:
            raise RuntimeError(f"прогон не запущен: {self.explain(out)}")
        return int(match.group(1))

    def state_dir(self, task_id: str) -> Path:
        return suite_lock.directory() / task_id

    def table_path(self, task_id: str, run_no: int) -> Path:
        return self.state_dir(task_id) / \
            f"{task_id}-mutation-run-{run_no}.mutations.tsv"

    def last_table(self, task_id: str) -> Path | None:
        pattern = re.compile(rf"^{task_id}-mutation-run-(\d+)\.mutations\.tsv$")
        folder = self.state_dir(task_id)
        found = sorted((int(m.group(1)), p) for p in folder.glob("*.tsv")
                       if (m := pattern.match(p.name))) \
            if folder.is_dir() else []
        return found[-1][1] if found else None

    def table_lines(self, task_id: str) -> list:
        path = self.last_table(task_id)
        if path is None:
            return []
        return path.read_bytes().decode("utf-8").split("\n")[:-1]

    def result_path(self, task_id: str) -> Path:
        return self.state_dir(task_id) / "mutation-result.json"

    def report(self, task_id: str) -> str:
        path = self.result_path(task_id)
        if not path.exists():
            return ""
        return json.loads(path.read_text(encoding="utf-8")).get("report", "")

    def explain(self, text: str = "") -> str:
        errors = "\n".join(self.child_errors)[-3000:]
        return (f"зерно: {self.seed}\nвывод команды:\n{text[-4000:]}\n"
                f"сбои фонового процесса:\n{errors}")


@pytest.fixture
def bench(real_git):
    """Стенд команды поверх песочницы `real_git`."""
    return Bench(real_git)


def missing_lines(lines: list, out: str) -> list:
    """Строки таблицы, которых нет среди строк вывода дословно."""
    printed = set(out.split("\n"))
    return [line for line in lines if line not in printed]


def row_numbers(lines: list) -> list:
    return [int(line.split("\t", 1)[0]) for line in lines
            if line.split("\t", 1)[0].isdigit()]


def test_ac1_finished_wait_prints_every_table_line_and_summary(bench):
    """Законченный прогон: отчёт `--wait` несёт каждую строку таблицы дословно и сводку.

    Сценарий: два–четыре патча (ломающий `add` и правки комментария, состав
    и порядок — от зерна), `mutation-run --ref head --tests <тест> --wait 1`.
    Таблица прогона на диске несёт строки `#` шапки, строку колонок и строку
    на каждый патч; каждая её строка встречается среди строк вывода
    побайтно, а поле `report` файла `mutation-result.json` — в выводе.

    Ловит мутацию: отчёт печатает только сводку, как до задачи, — строк
    шапки, колонок и исходов в выводе нет; печатаются только строки
    исходов без строк `#` шапки или без строки колонок; колонки строки
    исхода печатаются через пробелы вместо табуляции либо с обрезанным
    полем узлов — строка не равна строке файла; таблица печатается вместо
    сводки — поля `report` в выводе нет.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    count = bench.rng.randint(2, 4)
    patches = [bench.breaking(project)] + [bench.comment(project)
                                           for _ in range(count - 1)]
    bench.rng.shuffle(patches)
    bench.write_patches(project, task_id, patches)
    _code, out = bench.command(task_id, "--ref", "head", "--tests",
                               project["test"], "--wait", "1")
    lines = bench.table_lines(task_id)
    assert COLUMNS in lines, bench.explain(out)
    assert any(line.startswith("#") for line in lines), bench.explain(out)
    assert sorted(row_numbers(lines)) == list(range(1, count + 1)), \
        bench.explain(out)
    assert any(f"\t{KILLED}\t" in line for line in lines), bench.explain(out)
    assert missing_lines(lines, out) == [], bench.explain(out)
    report = bench.report(task_id)
    assert report, bench.explain(out)
    assert report in out, bench.explain(out)


def test_ac2_repeated_wait_after_end_prints_same_table_lines(bench):
    """Повторный `--wait` после конца прогона печатает те же строки таблицы.

    Сценарий: прогон двух–трёх патчей с `--wait 1` закончен; затем команда
    дважды зовётся только с `--wait <0 или 1>` (значение — от зерна). Вывод
    каждого повторного вызова несёт дословно каждую строку файла таблицы
    этого прогона — тех же строк, что печатает отчёт запустившего вызова.

    Ловит мутацию: таблица печатается только вызовом, запустившим прогон
    (из памяти фонового прогона или из флага «только что запущен»), — в
    повторном отчёте строк таблицы нет; повторный вызов печатает только
    шапку или только строки исходов.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    patches = [bench.breaking(project)] + [
        bench.comment(project) for _ in range(bench.rng.randint(1, 2))]
    bench.write_patches(project, task_id, patches)
    _code, first = bench.command(task_id, "--ref", "head", "--tests",
                                 project["test"], "--wait", "1")
    lines = bench.table_lines(task_id)
    assert len(row_numbers(lines)) == len(patches), bench.explain(first)
    for attempt in (1, 2):
        _code, out = bench.command(task_id, "--wait",
                                   str(bench.rng.randint(0, 1)))
        assert bench.table_lines(task_id) == lines, bench.explain(out)
        assert missing_lines(lines, out) == [], \
            f"повторный вызов {attempt}: {bench.explain(out)}"


@pytest.mark.parametrize("table", ["начата", "не начата"])
def test_ac3_running_wait_prints_written_lines_and_running_mark(bench, table):
    """Прогон ещё идёт: строки таблицы на момент вызова и «прогон №<n> ещё идёт».

    Сценарий «начата»: фоновый прогон исполнен, затем его отчёт
    `mutation-result.json` убран, pid фонового процесса — живой процесс
    песочницы, а файл таблицы урезан до среза строк, длина которого — от
    зерна (не короче шапки со строкой колонок). `--wait 0` печатает каждую
    строку урезанного файла дословно и строку «прогон №<n> ещё идёт» с
    номером этого прогона. Сценарий «не начата»: фоновый процесс не
    исполнялся (живой pid, файла таблицы нет) — `--wait 0` печатает
    «прогон №<n> ещё идёт» и строку «таблица ещё не начата».

    Ловит мутацию: таблица печатается только у законченного прогона — при
    живом процессе строк файла в выводе нет; вместо файла на момент вызова
    печатается таблица из сохранённого отчёта или ожидаемый полный набор
    строк; при отсутствии файла печать падает исключением чтения или
    молчит без «таблица ещё не начата»; пометка «ещё идёт» заменена новым
    текстом без номера прогона.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    bench.write_patches(project, task_id, [
        bench.breaking(project), bench.comment(project), bench.comment(project)])
    bench.pid = _alive_foreign_pid(bench.sandbox)
    bench.background = "run" if table == "начата" else "hold"
    run_no = bench.start(task_id, project)
    lines = []
    if table == "начата":
        bench.result_path(task_id).unlink(missing_ok=True)
        full = bench.table_lines(task_id)
        header = full.index(COLUMNS) + 1
        lines = full[:bench.rng.randint(header, len(full))]
        bench.table_path(task_id, run_no).write_bytes(
            "".join(line + "\n" for line in lines).encode("utf-8"))
    else:
        assert not bench.table_path(task_id, run_no).exists()
    _code, out = bench.command(task_id, "--wait", "0")
    assert f"прогон №{run_no} ещё идёт" in out, bench.explain(out)
    if table == "начата":
        assert missing_lines(lines, out) == [], bench.explain(out)
    else:
        assert NOT_STARTED in out.split("\n"), bench.explain(out)


def test_ac4_limit_cut_wait_prints_cut_and_not_run_rows(bench):
    """Обрыв по пределу: строки до обрыва, «оборвана по пределу» и «не прогнана (предел)».

    Сценарий: три–пять патчей, первый ломает `add`, остальные правят
    комментарий; прогон второго патча подменён исходом «предел». В файле
    таблицы строка 1 — «убита», 2 — «оборвана по пределу», остальные — «не
    прогнана (предел)»; отчёт `--wait 1` печатает дословно шапку, строку
    колонок и все эти строки.

    Ловит мутацию: таблица печатается только при зелёном исходе — у
    оборванного прогона строк нет; печатаются строки до обрыва без строки
    оборванной мутации или без строк «не прогнана (предел)»; строки
    обрыва печатаются своим текстом, а не строкой файла.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    count = bench.rng.randint(3, 5)
    bench.write_patches(project, task_id, [bench.breaking(project)] + [
        bench.comment(project) for _ in range(count - 1)])
    probe = bench.probe()
    probe.plan[3] = "timeout"
    _code, out = bench.command(task_id, "--ref", "head", "--tests",
                               project["test"], "--wait", "1")
    lines = bench.table_lines(task_id)
    rows = {int(line.split("\t")[0]): line.split("\t")[1]
            for line in lines if line.split("\t")[0].isdigit()}
    expected = {1: KILLED, 2: CUT, **{n: NOT_RUN for n in range(3, count + 1)}}
    assert rows == expected, bench.explain(out)
    assert missing_lines(lines, out) == [], bench.explain(out)


def test_ac5_reset_refusal_wait_prints_header_and_written_rows(bench):
    """Отказ сброса копии после второго патча: шапка и строки патчей 1 и 2 дословно, сводка отказа.

    Сценарий: три патча (состав — от зерна: ломающий и правки
    комментария); обёртка git после `git clean` во временной копии, когда
    применено уже два патча, оставляет посторонний файл — сброс к основе
    после второго патча отказывает всей команде. В файле таблицы — шапка,
    строка колонок и строки патчей 1 и 2; отчёт `--wait 1` печатает каждую
    строку файла дословно и поле `report` отказа.

    Ловит мутацию: таблица печатается только у законченного прогона — при
    отказе (`green: false`) вывод несёт одну сводку; печать таблицы
    добавлена только в ветку исключения, а не отказа пульта; печатается
    только последняя строка исхода — строки патча 1 нет; таблица
    печатается вместо сводки — поля `report` нет.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    patches = [bench.breaking(project), bench.comment(project),
               bench.comment(project)]
    bench.rng.shuffle(patches)
    bench.write_patches(project, task_id, patches)
    bench.stray_flag.write_text("2", encoding="utf-8")
    _code, out = bench.command(task_id, "--ref", "head", "--tests",
                               project["test"], "--wait", "1")
    lines = bench.table_lines(task_id)
    assert row_numbers(lines) == [1, 2], bench.explain(out)
    assert COLUMNS in lines, bench.explain(out)
    report = bench.report(task_id)
    assert bench.stray in report, bench.explain(out)
    assert missing_lines(lines, out) == [], bench.explain(out)
    assert report in out, bench.explain(out)


def test_ac6_exception_wait_prints_header_and_first_row(bench):
    """Исключение пульта на втором патче: шапка и строка первого патча дословно, сводка исключения.

    Сценарий: два–три патча; прогон второго патча подменён исключением
    (третий вызов узла прогона). В файле таблицы — шапка, строка колонок и
    одна строка исхода — патча 1; отчёт `--wait 1` печатает каждую строку
    файла дословно и поле `report` со словами «прогон оборван исключением
    пульта».

    Ловит мутацию: печать таблицы добавлена только в путь законченного
    прогона и отказа `Refusal` — при исключении вывод несёт одну сводку;
    печатается только шапка без строки патча 1; таблица печатается вместо
    сводки исключения.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    bench.write_patches(project, task_id, [bench.breaking(project)] + [
        bench.comment(project) for _ in range(bench.rng.randint(1, 2))])
    probe = bench.probe()
    probe.plan[3] = "raise"
    _code, out = bench.command(task_id, "--ref", "head", "--tests",
                               project["test"], "--wait", "1")
    lines = bench.table_lines(task_id)
    assert row_numbers(lines) == [1], bench.explain(out)
    assert COLUMNS in lines, bench.explain(out)
    report = bench.report(task_id)
    assert EXCEPTION_REPORT in report, bench.explain(out)
    assert missing_lines(lines, out) == [], bench.explain(out)
    assert report in out, bench.explain(out)


def test_ac7_dead_process_without_report_prints_table(bench):
    """Фоновый процесс умер без отчёта: строка «оборван … отчёта он не оставил» и строки таблицы.

    Сценарий: фоновый прогон трёх патчей исполнен, его pid — мёртвый
    процесс, отчёт `mutation-result.json` убран, файл таблицы урезан до
    среза строк (длина — от зерна, не короче шапки со строкой колонок).
    `--wait 0` печатает строку «прогон №<n> оборван — фонового процесса
    (pid …) больше нет, отчёта он не оставил» и каждую строку урезанного
    файла дословно.

    Ловит мутацию: таблица печатается только при наличии отчёта — у
    умершего без отчёта процесса вывод несёт одну строку «оборван»;
    печать таблицы стоит после `sys.exit` с текстом обрыва и не
    исполняется; вместо файла печатается полная таблица из памяти.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    bench.write_patches(project, task_id, [
        bench.breaking(project), bench.comment(project), bench.comment(project)])
    run_no = bench.start(task_id, project)
    bench.result_path(task_id).unlink(missing_ok=True)
    full = bench.table_lines(task_id)
    assert COLUMNS in full, bench.explain()
    lines = full[:bench.rng.randint(full.index(COLUMNS) + 1, len(full))]
    bench.table_path(task_id, run_no).write_bytes(
        "".join(line + "\n" for line in lines).encode("utf-8"))
    _code, out = bench.command(task_id, "--wait", "0")
    dead = re.compile(rf"прогон №{run_no} оборван — фонового процесса .* "
                      rf"больше нет, отчёта он не оставил")
    assert dead.search(out), bench.explain(out)
    assert missing_lines(lines, out) == [], bench.explain(out)


@pytest.mark.parametrize("outcome", ["законченный", "исключение"])
def test_ac8_docs_dir_and_artifacts_ref_untouched(bench, outcome):
    """Каталог документов задачи и `refs/artifacts/<id>` после прогона с `--wait` те же.

    Сценарий: патчи лежат и в каталоге документов задачи, и в коммите
    ссылки `refs/artifacts/<id>` клона проекта; прогон законченный или
    оборванный исключением на втором патче, отчёт забран `--wait 1` и
    повторным `--wait 0`. Содержимое каталога документов (имена и байты
    файлов) и sha ссылки — те же, что до прогона; `refs/artifacts/*`
    репозитория пульта песочницы не изменились.

    Ловит мутацию: отчёт `--wait` кладёт копию таблицы
    `mutation-run-<n>.tsv` в каталог документов задачи — в каталоге
    появляется файл; копия коммитится в ссылку документов — sha
    `refs/artifacts/<id>` сдвигается.
    """
    project = bench.add_project()
    task_id = bench.add_task(project)
    patches = [bench.breaking(project), bench.comment(project)]
    bench.write_patches(project, task_id, patches)
    bench.commit_ref(project, task_id, patches)
    if outcome == "исключение":
        bench.probe().plan[3] = "raise"
    docs = bench.docs_dir(project, task_id)
    clone = str(project["clone"])
    ref = f"refs/artifacts/{task_id}"

    def snapshot() -> dict:
        return {
            "docs": {str(p.relative_to(docs)): p.read_bytes()
                     for p in sorted(docs.rglob("*")) if p.is_file()},
            "ref": bench.sandbox.git("-C", clone, "rev-parse", ref),
            "pult refs": bench.sandbox.git("for-each-ref", "refs/artifacts"),
        }

    before = snapshot()
    _code, out = bench.command(task_id, "--ref", "head", "--tests",
                               project["test"], "--wait", "1")
    _code, again = bench.command(task_id, "--wait", "0")
    assert bench.table_lines(task_id), bench.explain(out)
    assert snapshot() == before, bench.explain(out + again)
