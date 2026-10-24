"""Команда `mutation-run <id> --ref <base|head|worktree> --tests <путь>[,…]
[--patches <a>-<b>] [--wait <минуты>] [--wait-lock <минуты>] [--copy-table]
[--workers <n>]`: патчи мутаций `mutation-<nnn>.diff` задачи против
названных тестовых файлов во временной копии и таблица «мутация → исход»
(SPEC 01M5NPKPWFEWTYMBYWVR797AM6, 01M5PWFGJQNV8YSAN5MF0CKHVW).

Доказательство неослабления при консолидации тестов — множество убиваемых
мутаций (ADR-0027 п. 8). Внутри шага роли прогон мутаций не исполним:
сторож роли в корневом `conftest.py` роняет рабочие процессы xdist под
`ARTEL_ROLE`, а около 70 мутаций подряд не укладываются в таймаут шага.
Команда устроена по образцу `suite-run` (`orchestrator/suite_run.py`):

- проверка аргументов, профиля и набора патчей — до замка и копии;
- замок полных прогонов машины `suite_lock` (держатель — `suite-run`
  задачи, номер прогона с префиксом `m`); занятый замок с `--wait-lock N`
  — ожидание его освобождения не дольше N минут с проверкой раз в 10 с,
  без флага — отказ без ожидания; ожидание замок не берёт и файлов
  прогона не создаёт;
- фоновый отвязанный процесс без признака роли в окружении, отчёт —
  `--wait` тем же или повторным вызовом;
- временная копия клона `suite_run._base_copy` на выбранной ревизии
  (для `worktree` — с незакоммиченными файлами рабочей копии задачи) и
  локальный коммит-основа в ней; после каждого патча — сброс к основе;
- контрольный прогон без патча, затем патчи по очереди узлом
  `acceptance.run_full_suite` с отчётом junit-xml вне копии; `--workers n`
  задаёт число рабочих процессов xdist всех этих прогонов;
- таблица `<id>-mutation-run-<n>.mutations.tsv` рядом с логом в
  хозяйстве `suite-run`, строка — сразу после каждой мутации.

Таблица — свидетельство, не гейт: никакой гейт пульта её не читает. С
`--copy-table` команда пишет в каталог документов задачи на диске
справочную копию таблицы `mutation-run-<n>.tsv` (после шапки, после
каждой строки и при каждом отчёте); доказательство исходов — основная
таблица, не копия. Ссылку документов, ветку и рабочую копию задачи
команда не меняет; файлы состояния — свои (`mutation-run.json`,
`mutation-result.json`), `run.json` прогона `suite-run` не трогается.
"""
import contextlib
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

from . import (acceptance, appendix_tree, artifact_branch, config, gitcmd,
               project_profile, repo_context, store, suite_lock, suite_run,
               workspace)
from .reporters import outcome as report_outcome
from .targets import PROFILE_RUNNER_DEFAULT

COMMAND = "mutation-run"
LOG_KIND = "mutation-run"
USAGE = (f"{COMMAND} <id> --ref <base|head|worktree> --tests <путь>[,<путь>…] "
         f"[--patches <a>-<b>] [--wait <минуты>] [--wait-lock <минуты>] "
         f"[--copy-table] [--workers <n>]")

# Шаг опроса замка машины при `--wait-lock` (требование 2 SPEC
# 01M5PWFGJQNV8YSAN5MF0CKHVW); `suite_lock.POLL_SEC` (1 с) для него част.
_LOCK_POLL_SEC = 10

REFS = ("base", "head", "worktree")

KILLED = "убита"
SURVIVED = "не убита"
COLLECTION = "ошибка сбора, импорта или setup"
UNKNOWN = "итог неизвестен"
CUT = "оборвана по пределу"
NOT_RUN = "не прогнана (предел)"
NOT_APPLIED = "патч не применяется"
TOUCHES = "патч трогает тесты"

RED_CONTROL = "тесты красные без мутаций"
NO_PATCHES = "патчей мутаций нет"
PROFILE_REFUSAL = "профиль проекта не поддержан командой mutation-run"

SOURCE_DISK = "каталог на диске"
SOURCE_REF = "ссылка"

# Файлы, от которых зависит сбор и настройка pytest: патч, задевший их,
# менял бы сами тесты, а не код под тестами (требование 6).
_TEST_CONFIG_NAMES = frozenset(("conftest.py", "pyproject.toml", "pytest.ini",
                                ".pytest.ini", "pytest.toml", "setup.cfg",
                                "tox.ini"))

_PATCH_NAME = re.compile(r"^mutation-(\d+)\.diff$")
_RANGE = re.compile(r"^(\d+)-(\d+)$")
_TEST_NAME = re.compile(r"^test_.*\.py$")

# `--continue-on-collection-errors`: ошибка сбора одного файла не обрывает
# прогон остальных, а в отчёте остаётся записью уровня файла (требование 6).
_PYTEST_FLAGS = ("-vv", "--continue-on-collection-errors")

# Компонент в id записей отчёта (`project_profile.test_id`); в таблицу узлы
# идут без него — `<путь>::<имя>`.
_COMPONENT = project_profile.DEFAULT_COMPONENT

_CHILD = ("import sys; from orchestrator import mutation_run; "
          "mutation_run.background(*sys.argv[1:])")

# Коммит-основа во временной копии: своя идентичность и без хуков клона —
# коммит живёт только в копии и убирается вместе с ней.
_BASE_COMMIT = ("-c", "user.name=artel mutation-run",
                "-c", "user.email=mutation-run@artel.invalid",
                "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false")


class Refusal(Exception):
    """Отказ всей команды в фоновом процессе: текст идёт в отчёт."""


# ------------------------------------------------------------- состояние

def _task_dir(task_id: str) -> Path:
    return suite_lock.directory() / task_id


def _run_path(task_id: str) -> Path:
    return _task_dir(task_id) / "mutation-run.json"


def _result_path(task_id: str) -> Path:
    return _task_dir(task_id) / "mutation-result.json"


def _log_path(task_id: str, run_no: int, suffix: str = "") -> Path:
    return _task_dir(task_id) / f"{task_id}-{LOG_KIND}-{run_no}{suffix}.log"


def _table_path(task_id: str, run_no: int) -> Path:
    return _task_dir(task_id) / f"{task_id}-{LOG_KIND}-{run_no}.mutations.tsv"


def _copy_path(task_id: str, target: str, run_no: int) -> Path:
    """Справочная копия таблицы первого уровня каталога документов задачи
    (`--copy-table`); имя guard не считает посторонним."""
    return artifact_branch.docs_dir(task_id, target) / f"{LOG_KIND}-{run_no}.tsv"


def _write_copy(table: Path, copy: Path) -> bool:
    """Перезаписывает копию байтами основной таблицы; False — каталога
    документов или таблицы нет либо запись не удалась. Прямая перезапись,
    без временного файла: каталог документов уходит автокоммитом шага, и
    лишнее имя в нём — посторонний файл (требование 19). Каталог не
    создаётся."""
    try:
        if not copy.parent.is_dir():
            return False
        copy.write_bytes(table.read_bytes())
    except OSError:
        return False
    return True


def _new_log(task_id: str) -> Path:
    """Лог следующего прогона задачи, файл создаётся сразу; номер —
    следующий за наибольшим из логов и файлов состояния команды."""
    prefix = f"{task_id}-{LOG_KIND}-"
    folder = _task_dir(task_id)
    folder.mkdir(parents=True, exist_ok=True)
    used = [int(p.stem[len(prefix):]) for p in folder.glob(f"{prefix}*.log")
            if p.stem[len(prefix):].isdigit()]
    for state in (suite_run._read_json(_run_path(task_id)),
                  suite_run._read_json(_result_path(task_id))):
        run = (state or {}).get("run")
        if isinstance(run, int) and not isinstance(run, bool):
            used.append(run)
    path = _log_path(task_id, max(used, default=0) + 1)
    path.touch()
    return path


def _lock_run(run_no: int) -> str:
    """Номер прогона в замке: префикс `m` отличает его от прогона
    `suite-run` той же задачи в `suite_lock.adopt` (требование 11)."""
    return f"m{run_no}"


def _pult_command(task_id: str) -> str:
    return f"python3 {config.ROOT / 'orchestrator' / 'artel.py'} {COMMAND} {task_id}"


# ---------------------------------------------------------------- патчи

def _disk_patches(folder: Path) -> dict:
    found = {}
    for path in folder.iterdir():
        match = _PATCH_NAME.match(path.name)
        if match and path.is_file():
            found[int(match.group(1))] = (path.name, path.read_bytes())
    return found


def _ref_patches(task_id: str, sha: str) -> tuple[dict, str]:
    """({номер: (имя, байты)}, причина отказа) — патчи коммита `sha`
    ссылки документов задачи."""
    rel_dir = f"tasks/{task_id}"
    paths = artifact_branch.ls_tree(task_id, sha, rel_dir)
    if paths is None:
        return {}, f"ссылка {artifact_branch.branch_name(task_id)} не прочитана"
    found = {}
    for rel in paths:
        name = rel.rsplit("/", 1)[-1]
        match = _PATCH_NAME.match(name)
        if not match or rel != f"{rel_dir}/{name}":
            continue
        text, reason = artifact_branch.show(task_id, sha, rel)
        if text is None:
            return {}, f"патч {rel} ссылки не прочитан: {reason}"
        found[int(match.group(1))] = (name, text.encode("utf-8"))
    return found, ""


def _patches(task_id: str, target: str, ref_sha: str = "") -> tuple:
    """(источник, sha ссылки, {номер: (имя, байты)}, причина отказа).

    Источник — каталог документов задачи на диске; его нет — коммит
    ссылки `refs/artifacts/<id>` (`ref_sha` — уже прочитанная голова:
    фоновый процесс читает тот же коммит, что проверила команда)."""
    folder = artifact_branch.docs_dir(task_id, target)
    if folder.is_dir():
        try:
            return SOURCE_DISK, "", _disk_patches(folder), ""
        except OSError as exc:
            return SOURCE_DISK, "", {}, f"каталог документов не прочитан: {exc}"
    sha = ref_sha or artifact_branch.rev_sha(
        task_id, artifact_branch.branch_name(task_id))
    if not sha:
        return SOURCE_REF, "", {}, ""
    found, reason = _ref_patches(task_id, sha)
    return SOURCE_REF, sha, found, reason


def _patch_range(spec: str | None, numbers: list) -> tuple:
    """((a, b), "") либо (None, причина отказа) — требование 1."""
    low, high = min(numbers), max(numbers)
    if spec is None:
        return (low, high), ""
    match = _RANGE.match(spec.strip())
    if not match:
        return None, (f"--patches «{spec}» — не диапазон вида <a>-<b> с "
                      f"целыми a и b")
    a, b = int(match.group(1)), int(match.group(2))
    if a > b:
        return None, f"--patches {spec}: обратный диапазон ({a} больше {b})"
    if a < low or b > high:
        return None, (f"--patches {spec}: диапазон за номерами набора "
                      f"{low}-{high}")
    return (a, b), ""


def _unquote(path: str) -> str:
    path = path.strip()
    if len(path) >= 2 and path[0] == path[-1] == '"':
        path = path[1:-1].encode("latin-1", "backslashreplace").decode(
            "unicode_escape").encode("latin-1", "replace").decode(
            "utf-8", "replace")
    return path


def _strip_side(path: str) -> str | None:
    path = _unquote(path)
    if path == "/dev/null":
        return None
    if path[:2] in ("a/", "b/"):
        path = path[2:]
    return path


def patch_paths(text: str) -> set:
    """Все пути патча: заголовки `diff --git`, `---`/`+++`, оба пути
    переименования и копирования (требование 6)."""
    paths = set()
    for line in text.splitlines():
        if line.startswith("diff --git "):
            rest = line[len("diff --git "):]
            if rest.startswith('"'):
                # Кавыченные пути — порознь: `"a/x" "b/y"`.
                parts = re.findall(r'"(?:[^"\\]|\\.)*"|\S+', rest)
            else:
                left, sep, right = rest.partition(" b/")
                parts = [left, "b/" + right] if sep else rest.split()
            for part in parts:
                stripped = _strip_side(part)
                if stripped:
                    paths.add(stripped)
        elif line.startswith(("--- ", "+++ ")):
            stripped = _strip_side(line[4:].split("\t", 1)[0])
            if stripped:
                paths.add(stripped)
        else:
            for head in ("rename from ", "rename to ", "copy from ",
                         "copy to "):
                if line.startswith(head):
                    paths.add(_unquote(line[len(head):]))
    return {os.path.normpath(p).replace(os.sep, "/") for p in paths if p}


def touches_tests(text: str, tests: list) -> bool:
    for path in patch_paths(text):
        name = path.rsplit("/", 1)[-1]
        if path == "tests" or path.startswith("tests/") or path in tests \
                or name in _TEST_CONFIG_NAMES:
            return True
    return False


# -------------------------------------------------------- --tests и ревизия

def _normalize(raw: str, wt: Path) -> str:
    path = raw.strip()
    if os.path.isabs(path):
        with contextlib.suppress(ValueError):
            path = os.path.relpath(path, wt)
    return os.path.normpath(path).replace(os.sep, "/") if path else ""


def _revision(ref: str, branch: str, clone: Path, wt: Path) -> tuple:
    """(sha ревизии прогона, причина отказа)."""
    if ref == "base":
        sha = gitcmd.diff_base(branch, repo=clone) or ""
        what = "база ветки задачи"
    elif ref == "head":
        sha = gitcmd.branch_head_sha(branch, repo=clone)
        what = f"голова ветки {branch}"
    else:
        sha = gitcmd.head_sha(wt) if wt.is_dir() else ""
        what = f"HEAD рабочей копии {wt}"
    return sha, ("" if sha else f"{what} не прочитана")


def _tree_files(ref: str, sha: str, clone: Path, wt: Path) -> tuple:
    """(множество файлов дерева выбранной ревизии под `tests/`, причина).
    Для `worktree` — файлы рабочей копии на диске, отслеживаемые и
    неотслеживаемые не игнорируемые (то, что перенесёт копия)."""
    if ref != "worktree":
        files = gitcmd.ls_tree_files(sha, "tests", repo=clone)
        if files is None:
            return None, f"git ls-tree {sha[:12]} не ответил"
        return set(files), ""
    res = gitcmd.in_repo(wt, "ls-files", "--cached", "--others",
                         "--exclude-standard", "-z", "--", "tests")
    if res is None or res.returncode != 0:
        return None, "файлы рабочей копии задачи не прочитаны"
    return {p for p in res.stdout.split("\0") if p and (wt / p).is_file()}, ""


def _check_tests(raw: str, files: set, wt: Path) -> tuple:
    """(нормализованные пути, причина отказа) — требование 1."""
    entries = raw.split(",")
    if not raw.strip() or any(not e.strip() for e in entries):
        return None, "--tests: пустой список или пустая запись в нём"
    paths = []
    for entry in entries:
        path = _normalize(entry, wt)
        if path in ("tests", ".") or path.startswith("../") or path == ".." \
                or not path.startswith("tests/"):
            if path == "tests":
                return None, (f"--tests «{entry}» — каталог tests/: полный "
                              f"набор этой командой не гоняется")
            return None, f"--tests «{entry}» — путь вне tests/"
        if path not in files:
            if any(f.startswith(path + "/") for f in files):
                return None, (f"--tests «{entry}» — каталог, а не файл "
                              f"test_*.py")
            return None, (f"--tests «{entry}» — файла {path} нет в дереве "
                          f"ревизии прогона")
        if not _TEST_NAME.match(path.rsplit("/", 1)[-1]):
            return None, f"--tests «{entry}» — имя файла не вида test_*.py"
        if path not in paths:
            paths.append(path)
    return paths, ""


def _profile_refusal(target: str) -> str:
    """Причина отказа по профилю тестов проекта; пусто — раннер пульта
    (требование 2)."""
    answer = repo_context.profile_of(target)
    if answer.multi:
        return PROFILE_REFUSAL
    if answer.outcome == repo_context.PROFILE_PRESENT and \
            (answer.values.get("runner") or PROFILE_RUNNER_DEFAULT) \
            != PROFILE_RUNNER_DEFAULT:
        return PROFILE_REFUSAL
    command, refusal = suite_run._profile_command(target)
    if refusal:
        return refusal
    if not isinstance(command, list):
        return PROFILE_REFUSAL
    return ""


def _command(target: str) -> list:
    command, _refusal = suite_run._profile_command(target)
    return command


# ---------------------------------------------------------- исход мутации

def _node(case) -> str:
    try:
        _comp, path, name, _n = project_profile.parse_test_id(case.id)
    except ValueError:
        return case.id
    return f"{path}::{name}"


def classify(green: bool, report: Path, cwd: Path) -> tuple[str, list]:
    """(исход, узлы) прогнанной мутации по коду возврата и отчёту
    junit-xml (требование 8). «Итог неизвестен» никогда не «не убита»
    (инвариант 41): отчёта нет, не разобран, пуст; ненулевой код без
    записей `failed`/`error`."""
    records, _reason = report_outcome.parse_junit(report, _COMPONENT, "", cwd)
    if records is None:
        return UNKNOWN, []
    killed = [_node(r) for r in records
              if r.outcome == report_outcome.FAILED and not r.file_level]
    if killed:
        return KILLED, killed
    broken = [_node(r) for r in records
              if r.outcome == report_outcome.ERROR or r.file_level]
    if broken:
        return COLLECTION, broken
    if not records or not green:
        return UNKNOWN, []
    return SURVIVED, []


# ------------------------------------------------------------ фоновый прогон

class _Budget:
    """Предел профиля на всю команду (требование 7): каждый прогон
    получает остаток от старта команды."""

    def __init__(self, limit: tuple):
        self.seconds, self.source = int(limit[0]), limit[1]
        self.start = time.monotonic()

    def remaining(self) -> float:
        return self.seconds - (time.monotonic() - self.start)

    def for_run(self) -> tuple | None:
        left = self.remaining()
        if left <= 0:
            return None
        return min(self.seconds, max(1, math.ceil(left))), self.source


def _git_ok(copy: Path, *args: str) -> str:
    res = gitcmd.in_repo(copy, *args)
    if res is None or res.returncode != 0:
        reason = ((res.stderr or res.stdout or "").strip()[:300]
                  if res is not None else "") or "git не ответил"
        raise Refusal(f"git {' '.join(args)} во временной копии: {reason}")
    return res.stdout


def _reset(copy: Path, base: str) -> None:
    """Копия — к коммиту-основе; посторонний файл после сброса — отказ
    всей команды (требование 6)."""
    _git_ok(copy, "reset", "-q", "--hard", base)
    _git_ok(copy, "clean", "-ffdx")
    status = _git_ok(copy, "status", "--porcelain")
    if status.strip():
        raise Refusal(f"после сброса к основе {base[:12]} копия не чиста — "
                      f"git status --porcelain не пуст:\n{status.rstrip()}")


class _Run:
    """Один прогон команды в фоновом процессе."""

    def __init__(self, task_id: str, run_no: int, log: Path, scratch: Path,
                 workers: str = "", copy_table: bool = False):
        self.task_id, self.run_no, self.log = task_id, run_no, log
        self.scratch = scratch
        self.table = _table_path(task_id, run_no)
        self.workers = workers
        self.copy_table = copy_table
        self.copy: Path | None = None

    def note(self, text: str) -> None:
        with contextlib.suppress(OSError), \
                open(self.log, "a", encoding="utf-8") as fh:
            fh.write(text.rstrip("\n") + "\n")

    def sync_copy(self) -> None:
        if self.copy is not None:
            _write_copy(self.table, self.copy)

    def header(self, text: str) -> None:
        self.table.write_text(text, encoding="utf-8")
        self.sync_copy()

    def row(self, number: int, result: str, nodes: list = ()) -> None:
        with open(self.table, "a", encoding="utf-8") as fh:
            fh.write(f"{number}\t{result}\t{','.join(nodes)}\n")
            fh.flush()
        self.sync_copy()
        self.note(f"мутация {number}: {result}"
                  + (f" — {', '.join(nodes)}" if nodes else ""))

    def suite(self, copy: Path, command, tests: list, label: str,
              limit: tuple) -> tuple:
        """(зелено, вывод, путь отчёта) прогона названных тестов в копии."""
        report = self.scratch / f"{label}.xml"
        report.unlink(missing_ok=True)
        run_log = _log_path(self.task_id, self.run_no, f"-{label}")
        # `-n` в конце `extra`: последнее значение в команде pytest берёт
        # верх над `-n config.FULL_SUITE_WORKERS` узла прогона.
        workers = ("-n", self.workers) if self.workers else ()
        green, output = acceptance.run_full_suite(
            copy, command=command, targets=tuple(tests),
            extra=(*_PYTEST_FLAGS, f"--junitxml={report}", *workers),
            log=run_log, limit=limit)
        self.note(f"прогон {label}: предел {limit[0]} с; лог: {run_log}")
        if not run_log.exists() or not run_log.stat().st_size:
            with contextlib.suppress(OSError):
                run_log.write_text(output, encoding="utf-8")
        return green, output, report


def _prepare(copy: Path, ref: str, wt: Path) -> str:
    """Копия с незакоммиченными файлами (`worktree`) и коммит-основа."""
    if ref == "worktree":
        error = appendix_tree._carry_uncommitted(wt, copy)
        if error:
            raise Refusal(error)
    _git_ok(copy, "add", "-A")
    _git_ok(copy, *_BASE_COMMIT, "commit", "-q", "--no-verify",
            "--allow-empty", "-m", "mutation-run: основа")
    return _git_ok(copy, "rev-parse", "HEAD").strip()


def _header(run: _Run, ref: str, sha: str, tests: list, source: str,
            ref_sha: str, chosen: list, patches: dict) -> str:
    where = (f"{SOURCE_REF} {artifact_branch.branch_name(run.task_id)} "
             f"{ref_sha}" if source == SOURCE_REF else
             f"{SOURCE_DISK}")
    lines = [f"# {COMMAND} №{run.run_no} задачи {run.task_id}",
             f"# источник патчей: {where}",
             f"# ревизия прогона: {ref} {sha}",
             f"# тесты: {', '.join(tests)}",
             f"# рабочих процессов: "
             f"{run.workers or config.FULL_SUITE_WORKERS}"]
    for number in chosen:
        name, body = patches[number]
        lines.append(f"# патч {number} {name} sha256 "
                     f"{hashlib.sha256(body).hexdigest()}")
    lines.append("номер\tисход\tузлы")
    return "\n".join(lines) + "\n"


def _mutate(run: _Run, task_id: str, ref: str, tests: list, low: int,
            high: int, ref_sha: str) -> str:
    conn = suite_run._db()
    task = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)
    command = _command(target)
    budget = _Budget(project_profile.full_suite_limit(target))
    clone = workspace.repo(target)
    wt = workspace.path(task_id, target)
    source, ref_sha, patches, reason = _patches(task_id, target, ref_sha)
    if reason:
        raise Refusal(reason)
    chosen = sorted(n for n in patches if low <= n <= high)
    if not chosen:
        raise Refusal(NO_PATCHES)
    sha, reason = _revision(ref, task["branch"], clone, wt)
    if reason:
        raise Refusal(reason)
    if run.copy_table:
        run.copy = _copy_path(task_id, target, run.run_no)
    run.header(_header(run, ref, sha, tests, source, ref_sha, chosen,
                       patches))
    counts: dict = {}
    with suite_run._base_copy(clone, sha) as (copy, refusal):
        if copy is None:
            raise Refusal(refusal)
        base = _prepare(copy, ref, wt)
        limit = budget.for_run()
        if limit is None:
            raise Refusal(f"контрольный прогон оборван по пределу "
                          f"{budget.seconds} с")
        green, output, report = run.suite(copy, command, tests, "control",
                                          limit)
        if acceptance.full_suite_outcome(green, output) == \
                acceptance.FULL_SUITE_TIMEOUT:
            raise Refusal(f"контрольный прогон оборван по пределу "
                          f"{limit[0]} с")
        verdict, nodes = classify(green, report, copy)
        if verdict != SURVIVED:
            raise Refusal(f"{RED_CONTROL}: контрольный прогон — {verdict}"
                          + (f" ({', '.join(nodes)})" if nodes else "")
                          + f"; лог: {_log_path(task_id, run.run_no, '-control')}")
        expired = False
        for number in chosen:
            name, body = patches[number]
            text = body.decode("utf-8", "replace")
            applied = False
            if expired:
                result, nodes = NOT_RUN, []
            elif touches_tests(text, tests):
                result, nodes = TOUCHES, []
            else:
                applied = True
                result, nodes = _one(run, copy, command, tests, number, body,
                                     budget)
                expired = result in (CUT, NOT_RUN)
            run.row(number, result, nodes)
            counts[result] = counts.get(result, 0) + 1
            if applied:
                # Строка мутации уже в таблице: отказ сброса её не теряет.
                _reset(copy, base)
    summary = ", ".join(f"{k}: {v}" for k, v in counts.items())
    return (f"[{task_id}] {COMMAND} №{run.run_no}: прогнано патчей "
            f"{len(chosen)} ({summary}); таблица: {run.table}; лог: {run.log}")


def _one(run: _Run, copy: Path, command, tests: list, number: int,
         body: bytes, budget: _Budget) -> tuple:
    """(исход, узлы) одного патча; копию к основе возвращает вызывающий."""
    patch = run.scratch / f"mutation-{number:03d}.diff"
    patch.write_bytes(body)
    res = gitcmd.in_repo(copy, "apply", str(patch))
    if res is None or res.returncode != 0:
        reason = (res.stderr or "").strip()[:300] if res is not None else ""
        run.note(f"мутация {number}: git apply — {reason or 'git не ответил'}")
        return NOT_APPLIED, []
    limit = budget.for_run()
    if limit is None:
        return NOT_RUN, []
    green, output, report = run.suite(copy, command, tests, f"p{number:03d}",
                                      limit)
    if acceptance.full_suite_outcome(green, output) == \
            acceptance.FULL_SUITE_TIMEOUT:
        return CUT, []
    return classify(green, report, copy)


def background(task_id: str, run_text: str, ref: str, tests_text: str,
               range_text: str, ref_sha: str = "", workers: str = "",
               copy_table: str = "") -> None:
    """Тело отвязанного процесса: замок, копия, контроль, патчи, отчёт.
    Отчёт пишется на любом исходе; замок снимается в `finally`.
    `workers` — значение `--workers` (пусто — умолчание узла прогона),
    `copy_table` — непустое при `--copy-table`."""
    run_no = int(run_text)
    lock_run = _lock_run(run_no)
    log = _log_path(task_id, run_no)
    log.parent.mkdir(parents=True, exist_ok=True)
    holder = suite_lock.adopt(task_id, lock_run)
    if holder is not None:
        suite_run._write_json(_result_path(task_id), {
            "run": run_no, "green": False,
            "report": (f"[{task_id}] {COMMAND} №{run_no}: отказ — на машине "
                       f"уже идёт прогон {suite_lock.describe(holder)}")})
        return
    low, high = (int(x) for x in range_text.split("-"))
    tests = [t for t in tests_text.split(",") if t]
    scratch = Path(tempfile.mkdtemp(prefix="artel-mutation-run-"))
    try:
        run = _Run(task_id, run_no, log, scratch, workers, bool(copy_table))
        try:
            report, green = _mutate(run, task_id, ref, tests, low, high,
                                    ref_sha), True
        except Refusal as exc:
            report, green = (f"[{task_id}] {COMMAND} №{run_no}: отказ — "
                             f"{exc}; лог: {log}"), False
        except Exception as exc:  # отчёт обязан быть на любом исходе
            traceback.print_exc()
            report, green = (f"[{task_id}] {COMMAND} №{run_no}: прогон оборван "
                             f"исключением пульта {type(exc).__name__}: {exc}; "
                             f"лог: {log}; трассировка: "
                             f"{_task_dir(task_id) / 'mutation-background.log'}"
                             ), False
        run.note(report)
        suite_run._write_json(_result_path(task_id),
                              {"run": run_no, "green": green, "report": report})
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        suite_lock.release()


# --------------------------------------------------------------- команда

_SWITCHES = ("--copy-table",)

# Флаги прогона: в режиме только отчёта им нечего задавать (требование 13).
_RUN_FLAGS = ("--wait-lock", "--copy-table", "--workers")


def _parse_args(rest: list) -> dict:
    options = {"--ref": None, "--tests": None, "--patches": None,
               "--wait": None, "--wait-lock": None, "--workers": None,
               "--copy-table": None}
    positional = []
    index = 0
    while index < len(rest):
        arg = rest[index]
        if arg in _SWITCHES:
            if options[arg] is not None:
                sys.exit(f"{USAGE}: {arg} повторён")
            options[arg] = True
            index += 1
            continue
        if arg in options:
            if options[arg] is not None or index + 1 >= len(rest):
                sys.exit(f"{USAGE}: {arg} требует одно значение")
            options[arg] = rest[index + 1]
            index += 2
            continue
        if arg.startswith("--"):
            sys.exit(f"неизвестный флаг {arg!r}; использование: {USAGE}")
        positional.append(arg)
        index += 1
    if len(positional) != 1:
        sys.exit(USAGE)
    options["id"] = positional[0]
    return options


def _wait_minutes(text: str) -> int:
    limit = config.SUITE_RUN_MAX_WAIT_MIN
    try:
        minutes = int(text)
    except ValueError:
        minutes = -1
    if not 0 <= minutes <= limit:
        sys.exit(f"{COMMAND} --wait: отказ — «{text}» не число минут от 0 до "
                 f"{limit}; прогон не тронут, жди повторным --wait")
    return minutes


def _lock_minutes(text: str, wait: int | None) -> int:
    """Значение `--wait-lock` (требования 1, 5, 6): целое `int(строка)`
    от 0 до предела, в сумме с `--wait` не больше предела."""
    limit = config.SUITE_RUN_MAX_WAIT_MIN
    try:
        minutes = int(text)
    except ValueError:
        minutes = -1
    if not 0 <= minutes <= limit:
        sys.exit(f"{COMMAND} --wait-lock: отказ — «{text}» не целое число "
                 f"минут от 0 до {limit}; формат: --wait-lock <минуты>; "
                 f"прогон не запускался")
    if wait is not None and minutes + wait > limit:
        sys.exit(f"{COMMAND}: отказ — --wait-lock {minutes} и --wait {wait} "
                 f"в сумме больше предела {limit} мин одного вызова; прогон "
                 f"не запускался")
    return minutes


def _workers(text: str) -> str:
    """Значение `--workers` (требование 20; ANSWER-2 пп. 2–3): целое
    `int(строка)` от 1 до числа процессоров машины."""
    limit = os.cpu_count() or 1
    try:
        workers = int(text)
    except ValueError:
        workers = 0
    if not 1 <= workers <= limit:
        sys.exit(f"{COMMAND} --workers: отказ — «{text}» не целое число "
                 f"рабочих процессов от 1 до {limit} (процессоров машины); "
                 f"формат: --workers <n>; прогон не запускался")
    return str(workers)


def _running(task_id: str) -> dict | None:
    """Последний прогон задачи, если он ещё идёт (как `suite_run._running`)."""
    state = suite_run._read_json(_run_path(task_id))
    if state is None or not suite_run._alive(state.get("pid")):
        return None
    result = suite_run._read_json(_result_path(task_id))
    if result is not None and result.get("run") == state.get("run"):
        return None
    holder = suite_lock.holder()
    if holder is None or holder.get("pid") != state.get("pid"):
        return None
    return state


def _print_table(task_id: str, run_no) -> bool:
    """Печатает основную таблицу прогона дословно (SPEC
    01M5P2BHX6M16XXM0TSVWW9HEM): хозяйство `suite-run` роли на Claude
    закрыто, и перенести таблицу в PLAN она может только из вывода.
    False — файла таблицы этого прогона нет."""
    if not isinstance(run_no, int) or isinstance(run_no, bool):
        return False
    path = _table_path(task_id, run_no)
    try:
        text = path.read_bytes().decode("utf-8", "replace")
    except OSError:
        return False
    print(f"--- таблица {path} ---")
    # Недописанная фоном последняя строка выводится как есть, но отделяется
    # от следующего текста отчёта переводом строки.
    if text and not text.endswith("\n"):
        text += "\n"
    print(text, end="")
    return True


def _show_table(task_id: str, state: dict) -> bool:
    """Таблица прогона в отчёте; у прогона с `--copy-table` копия сначала
    перезаписывается из основной таблицы (требование 12), после таблицы —
    её путь либо одна строка «копии нет» (требования 9, 11)."""
    run_no = state.get("run")
    copied = None
    if state.get("copy_table") and isinstance(run_no, int) \
            and not isinstance(run_no, bool):
        target = store.task_target(suite_run._db(), task_id)
        copy = _copy_path(task_id, target, run_no)
        table = _table_path(task_id, run_no)
        copied = copy if table.is_file() and _write_copy(table, copy) else ""
    shown = _print_table(task_id, run_no)
    if copied:
        print(f"копия таблицы: {copied}")
    elif copied is not None:
        print("копии нет — каталога документов задачи на диске или таблицы "
              "прогона нет")
    return shown


def _wait(task_id: str, minutes: int) -> None:
    head = f"[{task_id}] {COMMAND}"
    state = suite_run._read_json(_run_path(task_id))
    if state is None:
        sys.exit(f"{head}: отказ — у задачи {task_id} нет ни одного прогона "
                 f"{COMMAND}, ждать нечего")
    deadline = time.monotonic() + minutes * 60
    while True:
        result = suite_run._read_json(_result_path(task_id))
        if result is not None and result.get("run") == state.get("run"):
            _show_table(task_id, state)
            print(result.get("report", ""))
            if not result.get("green"):
                sys.exit(1)
            return
        if not suite_run._alive(state.get("pid")):
            result = suite_run._read_json(_result_path(task_id))
            if result is None or result.get("run") != state.get("run"):
                _show_table(task_id, state)
                sys.stdout.flush()
                sys.exit(f"{head}: прогон №{state.get('run')} оборван — "
                         f"фонового процесса (pid {state.get('pid')}) больше "
                         f"нет, отчёта он не оставил; лог: {state.get('log')}")
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if not _show_table(task_id, state):
                print("таблица ещё не начата")
            print(f"{head}: прогон №{state.get('run')} ещё идёт; лог: "
                  f"{state.get('log')}")
            sys.exit(f"{head}: прогон не прерван; отчёт — повторным "
                     f"{_pult_command(task_id)} --wait <минуты>")
        time.sleep(min(suite_run._POLL_SEC, remaining))


def _take_lock(task_id: str, minutes: int, head: str) -> None:
    """Берёт замок машины за командой либо выходит отказом (требования
    1–4). Занятый замок ждётся не дольше `minutes` минут, проверка — раз в
    `_LOCK_POLL_SEC` с; ожидание замок не держит и файлов прогона не
    заводит, `KeyboardInterrupt` из сна уходит наружу без прогона.
    Освободившийся замок, перехваченный другим прогоном, — та же
    занятость: ожидание идёт до срока."""
    holder = suite_lock.acquire(task_id, None)
    if holder is None:
        return
    if minutes <= 0:
        sys.exit(f"{head}: отказ — на машине уже идёт прогон "
                 f"{suite_lock.describe(holder)}; одновременно идёт один "
                 f"полный прогон — повтори после его конца")
    print(f"{head}: замок машины держит прогон {suite_lock.describe(holder)} "
          f"— жду его освобождения не дольше {minutes} мин, проверка раз в "
          f"{_LOCK_POLL_SEC} с", flush=True)
    # Срок кратен шагу опроса: последняя проверка приходится ровно на срок.
    deadline = time.monotonic() + minutes * 60
    while time.monotonic() < deadline:
        time.sleep(_LOCK_POLL_SEC)
        holder = suite_lock.acquire(task_id, None)
        if holder is None:
            return
    sys.exit(f"{head}: отказ — на машине уже идёт прогон "
             f"{suite_lock.describe(holder)}; ожидание {minutes} мин истекло "
             f"— повтори после его конца")


def cmd_mutation_run(rest: list) -> None:
    options = _parse_args(rest)
    minutes = (_wait_minutes(options["--wait"])
               if options["--wait"] is not None else None)
    conn = suite_run._db()
    task_id = store.resolve_task_id(conn, options["id"])
    head = f"[{task_id}] {COMMAND}"
    ref, tests_raw = options["--ref"], options["--tests"]
    if ref is None and tests_raw is None and options["--patches"] is None:
        flags = [f for f in _RUN_FLAGS if options[f] is not None]
        if flags:
            sys.exit(f"{head}: отказ — {', '.join(flags)} задаёт прогон, а "
                     f"вызов без --ref, --tests и --patches — только отчёт; "
                     f"формат отчёта: {COMMAND} <id> --wait <минуты>; "
                     f"использование: {USAGE}")
        if minutes is None:
            sys.exit(USAGE)
        _wait(task_id, minutes)
        return
    if ref not in REFS or tests_raw is None:
        sys.exit(f"{head}: отказ — нужны --ref <base|head|worktree> и "
                 f"--tests; использование: {USAGE}")
    lock_minutes = (_lock_minutes(options["--wait-lock"], minutes)
                    if options["--wait-lock"] is not None else 0)
    workers = (_workers(options["--workers"])
               if options["--workers"] is not None else "")
    copy_table = bool(options["--copy-table"])
    task = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)

    def refuse(reason: str) -> None:
        sys.exit(f"{head}: отказ — {reason}; прогон не запускался")

    refusal = _profile_refusal(target)
    if refusal:
        refuse(refusal)
    clone = workspace.repo(target)
    wt = workspace.path(task_id, target)
    if ref == "worktree" and not wt.is_dir():
        refuse(f"рабочей копии задачи нет ({wt})")
    source, ref_sha, patches, reason = _patches(task_id, target)
    if reason:
        refuse(reason)
    if not patches:
        refuse(f"{NO_PATCHES} ({source})")
    span, reason = _patch_range(options["--patches"], sorted(patches))
    if reason:
        refuse(reason)
    sha, reason = _revision(ref, task["branch"], clone, wt)
    if reason:
        refuse(reason)
    files, reason = _tree_files(ref, sha, clone, wt)
    if reason:
        refuse(reason)
    tests, reason = _check_tests(tests_raw, files, wt)
    if reason:
        refuse(reason)
    running = _running(task_id)
    if running is not None:
        print(f"{head}: прогон №{running.get('run')} этой задачи уже идёт "
              f"(pid {running.get('pid')}) — второй не запускаю; отчёт: "
              f"{_pult_command(task_id)} --wait <минуты>")
        return
    _take_lock(task_id, lock_minutes, head)
    try:
        log = _new_log(task_id)
        run_no = int(log.stem.rsplit("-", 1)[1])
        suite_lock.hand(task_id, _lock_run(run_no), os.getpid())
        # Признак роли снимается только у фонового процесса: это прогон
        # пульта, сторож `conftest.py` его не отклоняет (требование 3).
        env = {k: v for k, v in os.environ.items()
               if k != config.ARTEL_ROLE_ENV}
        with open(_task_dir(task_id) / "mutation-background.log", "ab") as errors:
            proc = subprocess.Popen(
                [sys.executable, "-c", _CHILD, task_id, str(run_no), ref,
                 ",".join(tests), f"{span[0]}-{span[1]}", ref_sha, workers,
                 "1" if copy_table else ""],
                cwd=str(config.ROOT), env=env, stdin=subprocess.DEVNULL,
                stdout=errors, stderr=subprocess.STDOUT,
                start_new_session=True)
    except BaseException:
        suite_lock.release()
        raise
    suite_lock.hand(task_id, _lock_run(run_no), proc.pid)
    suite_run._write_json(_run_path(task_id), {
        "run": run_no, "pid": proc.pid, "log": str(log), "ref": ref,
        "tests": tests, "patches": f"{span[0]}-{span[1]}",
        "started": time.time(), "copy_table": copy_table})
    print(f"{head}: прогон №{run_no} (патчи {span[0]}-{span[1]}, ref {ref}) "
          f"запущен фоном, pid {proc.pid}; лог: {log}; таблица: "
          f"{_table_path(task_id, run_no)}")
    if minutes is None:
        print(f"  отчёт: {_pult_command(task_id)} --wait <минуты, не больше "
              f"{config.SUITE_RUN_MAX_WAIT_MIN}>")
        return
    _wait(task_id, minutes)
