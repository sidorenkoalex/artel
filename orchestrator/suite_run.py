"""Команда `suite-run <id> [--wait <минуты> | --failed]`: полный прогон
тестов проекта задачи из шага роли (SPEC 01M462QACEH29RPRD2RZHGHQFM).

Роли полный набор запрещён сторожем `conftest.py`, а пульт гонял его только
на своих гейтах. 05.10 роль сама делила набор на пачки, обходила сторож
перечислением файлов `tests/` и отдельной копией базы выясняла, что
падения есть и на main, — три шага, два таймаута по 45 минут. Здесь то же
самое — штатно:

- прогон рабочей копии задачи (с незакоммиченными правками) узлом пульта
  `acceptance.run_full_suite` с параллелью и командой профиля тестов
  проекта, без признака роли в окружении;
- отдельным отвязанным процессом: полный набор не укладывается в 10 минут
  вызова инструмента роли, поэтому команда сразу возвращается, а отчёт
  роль забирает `--wait` (не дольше `config.SUITE_RUN_MAX_WAIT_MIN`);
- упавшие делятся на «новые на ветке» и «падают и на базе» по итогу базы
  ветки (sha `gitcmd.diff_base`): сохранённому гейтом или прошлым прогоном
  (`acceptance.saved_failures`), иначе — прогоном базы во временной
  рабочей копии клона тем же фоновым процессом;
- `--failed` повторяет только упавшие прошлого прогона задачи;
- на машине одновременно идёт один прогон (замок держит фоновый процесс).

Состояния задачи команда не меняет, lease не берёт, журнал шагов не пишет:
всё её хозяйство — в каталоге логов пульта (`_state_dir`), поэтому она в
перечне команд роли (`artel._ROLE_ALLOWED_COMMANDS`).
"""
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import NamedTuple

from . import (acceptance, agent_log, config, gitcmd, liveness, repo_context,
               store, workspace)

# «Роль» в имени лога прогона: `.artel/logs/<id>-suiterun-<n>.log`, номер
# прогона — номер `agent_log.new_agent_log`, второй нумерации нет.
LOG_KIND = "suiterun"

STILL_RUNNING = "ещё идёт"
NO_BASE = "база не посчитана"
NEW_ON_BRANCH = "новые на ветке"
ALSO_ON_BASE = "падают и на базе"

MODE_FULL = "full"
MODE_FAILED = "failed"

# `-vv`: строка на каждый выполненный тест (ход прогона и числа успевшей
# части при обрыве по пределу) и сообщение упавшего в «short test summary
# info» без обрезки по ширине терминала (признак группы ошибки).
_PYTEST_FLAGS = ("-vv",)

_POLL_SEC = 1.0
# Замок, только что созданный соседом, ещё может быть пуст: столько секунд
# пустой файл считается занятым, а не брошенным.
_FRESH_LOCK_SEC = 5

_CHILD = ("import sys; from orchestrator import suite_run; "
          "suite_run.background(*sys.argv[1:])")

_STATUS = r"PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS"
# Строка хода прогона `-v`: с xdist — «[gw0] [ 50%] PASSED <id>», без него —
# «<id> PASSED [ 50%]».
_PROGRESS = re.compile(
    rf"^(?:\[gw\d+\] \[\s*\d+%\] (?P<s1>{_STATUS}) (?P<n1>.+?)"
    rf"|(?P<n2>\S.*?::.+?) (?P<s2>{_STATUS})(?: +\[\s*\d+%\])?)\s*$",
    re.MULTILINE)
# Первая секция отчёта pytest после строк хода («==== FAILURES ====» и
# далее): в ней захваченный вывод тестов, и строка вида «<x>::<y> PASSED»
# оттуда — не ход прогона.
_REPORT_SECTION = re.compile(r"^=+ (?!test session starts =).* =+$",
                             re.MULTILINE)
_SUMMARY_COUNT = re.compile(
    r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")


# ------------------------------------------------------------- состояние

def _state_dir() -> Path:
    """Каталог хозяйства команды — функция: `config.LOGS` подменяют тесты."""
    return config.LOGS / "suite-run"


def _task_dir(task_id: str) -> Path:
    return _state_dir() / task_id


def _lock_path() -> Path:
    return _state_dir() / "lock.json"


def _run_path(task_id: str) -> Path:
    """Последний запущенный прогон задачи: номер, pid, лог, начало."""
    return _task_dir(task_id) / "run.json"


def _result_path(task_id: str) -> Path:
    """Отчёт последнего завершённого прогона задачи."""
    return _task_dir(task_id) / "result.json"


def _failed_path(task_id: str) -> Path:
    """Перечень упавших последнего прогона задачи (требование 9)."""
    return _task_dir(task_id) / "failed.json"


def _log_path(task_id: str, run_no: int, suffix: str = "") -> Path:
    return config.LOGS / f"{task_id}-{LOG_KIND}-{run_no}{suffix}.log"


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict) -> None:
    """Запись через временный файл и `replace`: ожидающий `--wait` не
    прочтёт половину файла."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _read_failed(task_id: str) -> list[str] | None:
    data = _read_json(_failed_path(task_id))
    if data is None or not isinstance(data.get("failed"), list):
        return None
    return [str(node) for node in data["failed"]]


def _alive(pid) -> bool:
    try:
        return liveness._pid_alive(int(pid))
    except (TypeError, ValueError):
        return False


def _pult_command(task_id: str) -> str:
    return f"python3 {config.ROOT / 'orchestrator' / 'artel.py'} suite-run {task_id}"


# ---------------------------------------------------------------- замок

def _acquire_lock(task_id: str, run_no: int | None) -> dict | None:
    """Замок прогонов машины за текущим процессом: `None` — взят, иначе
    держатель. Создание файла `O_EXCL` — атомарно; брошенный замок (pid
    мёртв) снимается и берётся заново."""
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"task_id": task_id, "pid": os.getpid(),
                          "run": run_no}, ensure_ascii=False)
    for _ in range(3):
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            holder = _read_json(path)
            if holder is not None and _alive(holder.get("pid")):
                return holder
            if holder is None and _fresh(path):
                return {"task_id": "?", "pid": "?"}
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        return None
    return _read_json(path) or {"task_id": "?", "pid": "?"}


def _fresh(path: Path) -> bool:
    try:
        return time.time() - path.stat().st_mtime < _FRESH_LOCK_SEC
    except OSError:
        return False


def _hand_lock(task_id: str, run_no: int, pid: int) -> None:
    """Замок, взятый процессом команды, — за фоновым процессом прогона:
    держателем становится `pid`, задача и номер прогона те же."""
    _write_json(_lock_path(), {"task_id": task_id, "pid": pid, "run": run_no})


def _adopt_lock(task_id: str, run_no: int) -> dict | None:
    """Фоновый процесс принимает замок, переданный ему командой (тот же
    id задачи и номер прогона), — `None`; замка для него нет — берёт сам
    (`_acquire_lock`): вызов `background` в обход команды."""
    holder = _read_json(_lock_path())
    if (holder is not None and holder.get("task_id") == task_id
            and holder.get("run") == run_no):
        _hand_lock(task_id, run_no, os.getpid())
        return None
    return _acquire_lock(task_id, run_no)


def _release_lock() -> None:
    holder = _read_json(_lock_path())
    if holder is not None and holder.get("pid") == os.getpid():
        with contextlib.suppress(FileNotFoundError):
            _lock_path().unlink()


# ---------------------------------------------------- профиль тестов проекта

def _is_pytest(command: list[str]) -> bool:
    """Команда — запуск pytest: исполняемый файл `pytest`/`py.test` или
    `-m pytest`. Имя интерпретатора само по себе ничего не говорит."""
    if any(Path(part).name in ("pytest", "py.test") for part in command):
        return True
    return any(flag == "-m" and module == "pytest"
               for flag, module in zip(command, command[1:]))


def _profile_command(target: str) -> tuple[list[str] | None, str]:
    """(команда профиля тестов проекта, причина отказа) — требование 2."""
    answer = repo_context.profile_of(target)
    if answer.outcome == repo_context.PROFILE_UNREAD:
        return None, (f"профиль тестов проекта «{target}» не прочитан "
                      f"(test_profile в targets.yaml): {answer.reason}")
    if answer.outcome != repo_context.PROFILE_PRESENT:
        return None, (f"у проекта «{target}» нет профиля тестов "
                      f"(test_profile в targets.yaml) — команде прогона "
                      f"неоткуда взять команду")
    command = [str(part) for part in answer.values.get("command") or ()]
    if not _is_pytest(command):
        return None, (f"команда профиля тестов проекта «{target}» "
                      f"({' '.join(command) or 'пусто'}) — не запуск pytest: "
                      f"флаги параллели pytest (-n) к ней неприменимы")
    return command, ""


# -------------------------------------------------------- разбор прогона

class Parsed(NamedTuple):
    """Итог одного прогона: исход (`acceptance.FULL_SUITE_*`), числа,
    упавшие парами (id, первая строка сообщения) и признак «прогон
    завершён» — только такой годится в итог базы (требование 8)."""
    outcome: str
    passed: int
    failed: int
    skipped: int
    failures: list
    finished: bool


def _progress(output: str) -> dict[str, str]:
    """id теста -> исход по строкам хода прогона; упавший хоть раз (в том
    числе на teardown после PASSED) остаётся упавшим. Читаются только
    строки до секций отчёта (`_REPORT_SECTION`)."""
    section = _REPORT_SECTION.search(output)
    if section is not None:
        output = output[:section.start()]
    statuses = {}
    for match in _PROGRESS.finditer(output):
        node = (match.group("n1") or match.group("n2")).strip()
        status = match.group("s1") or match.group("s2")
        if statuses.get(node) not in ("FAILED", "ERROR"):
            statuses[node] = status
    return statuses


def parse(green: bool, output: str) -> Parsed:
    outcome = acceptance._full_suite_outcome(green, output)
    summary = acceptance.run_summary_line(output)
    finished = (outcome in (acceptance.FULL_SUITE_GREEN,
                            acceptance.FULL_SUITE_RED) and bool(summary))
    statuses = _progress(output)
    failures = dict.fromkeys(
        (node for node, status in statuses.items()
         if status in ("FAILED", "ERROR")), "")
    if finished:
        failures.update(acceptance.failed_entries(output))
        counts = {}
        for number, kind in _SUMMARY_COUNT.findall(summary):
            counts[kind.rstrip("s") if kind.startswith("error") else kind] = int(number)
        passed = counts.get("passed", 0)
        failed = counts.get("failed", 0) + counts.get("error", 0)
        skipped = counts.get("skipped", 0)
    else:
        values = list(statuses.values())
        passed = values.count("PASSED")
        failed = values.count("FAILED") + values.count("ERROR")
        skipped = values.count("SKIPPED")
    return Parsed(outcome, passed, failed, skipped,
                  sorted(failures.items()), finished)


# ------------------------------------------------------------------ отчёт

def _plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def _clip(text: str) -> str:
    limit = config.SUITE_RUN_MAX_LINE_CHARS
    return text if len(text) <= limit else text[:limit] + "…"


def _groups(failures: list) -> list[tuple[str, list[str]]]:
    """Группы по признаку ошибки (тип исключения и первая строка
    сообщения — так их печатает pytest), крупные первыми."""
    groups = {}
    for node, message in failures:
        key = message or "(признак неизвестен: сводки pytest по тесту нет)"
        groups.setdefault(key, []).append(node)
    return sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))


def _group_lines(failures: list) -> list[str]:
    groups = _groups(failures)
    shown = groups[:config.SUITE_RUN_MAX_GROUPS]
    lines = []
    for signature, nodes in shown:
        lines.append(f"  {_clip(signature)} — {len(nodes)} "
                     f"{_plural(len(nodes), 'тест', 'теста', 'тестов')}")
        lines.extend(f"    {node}" for node in sorted(nodes)[:3])
    rest = groups[len(shown):]
    if rest:
        tests = sum(len(nodes) for _, nodes in rest)
        lines.append(f"  и ещё {len(rest)} "
                     f"{_plural(len(rest), 'группа', 'группы', 'групп')}, "
                     f"{tests} {_plural(tests, 'тест', 'теста', 'тестов')}")
    return lines


def render(task_id: str, run_no: int, mode: str, parsed: Parsed,
           base_failed: set | None, base_note: str, log: Path) -> str:
    """Короткий отчёт для шага роли (требования 11-12)."""
    title = {
        acceptance.FULL_SUITE_GREEN: "зелёный прогон",
        acceptance.FULL_SUITE_RED: "красный прогон",
        acceptance.FULL_SUITE_TIMEOUT: (
            f"прогон не уложился в предел {config.FULL_SUITE_TIMEOUT_SEC} с "
            f"и оборван — числа и упавшие по успевшей части"),
        acceptance.FULL_SUITE_NO_TESTS: acceptance.FULL_SUITE_NO_TESTS_NOTE,
    }[parsed.outcome]
    what = "повтор упавших" if mode == MODE_FAILED else "полный набор"
    lines = [f"[{task_id}] suite-run №{run_no} ({what}): {title}",
             f"прошло: {parsed.passed}, упало: {parsed.failed}, "
             f"пропущено: {parsed.skipped}"]
    if parsed.failures:
        if base_failed is None:
            lines.append(f"{NO_BASE} ({base_note}) — упавшие по базе не "
                         f"делятся")
            lines.append("упавшие по признаку ошибки:")
            lines.extend(_group_lines(parsed.failures))
        else:
            new = [f for f in parsed.failures if f[0] not in base_failed]
            old = len(parsed.failures) - len(new)
            lines.append(f"упавшие: {NEW_ON_BRANCH}: {len(new)}, "
                         f"{ALSO_ON_BASE}: {old} ({base_note}; их перечень — "
                         f"в конце лога)")
            if new:
                lines.append(f"{NEW_ON_BRANCH} по признаку ошибки:")
                lines.extend(_group_lines(new))
    lines.append(f"полный лог: {log}")
    return "\n".join(lines)


def _log_appendix(parsed: Parsed, base_failed: set | None) -> str:
    """Полные перечни упавших — в конец лога: в отчёте «падают и на базе»
    только числом (требование 12)."""
    lines = ["", "===== suite-run: упавшие ====="]
    for node, message in parsed.failures:
        mark = ("" if base_failed is None
                else f" [{ALSO_ON_BASE}]" if node in base_failed
                else f" [{NEW_ON_BRANCH}]")
        lines.append(f"{node}{mark} — {message or '(сообщения нет)'}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------- прогон базы

@contextlib.contextmanager
def _base_copy(clone: Path, sha: str):
    """(каталог, причина отказа) — временная рабочая копия клона на `sha`
    в системном временном каталоге; убирается и снимается с учёта клона на
    любом исходе (требование 15)."""
    holder = Path(tempfile.mkdtemp(prefix="artel-suite-base-"))
    copy = holder / "base"
    try:
        gitcmd.in_repo(clone, "worktree", "prune")
        res = gitcmd.in_repo(clone, "worktree", "add", "--detach",
                             str(copy), sha)
        if res is None or res.returncode != 0:
            reason = ((res.stderr or "").strip()[:200] if res is not None
                      else "") or "git не ответил"
            yield None, f"временная рабочая копия базы не заведена: {reason}"
        else:
            yield copy, ""
    finally:
        gitcmd.in_repo(clone, "worktree", "remove", "--force", str(copy))
        shutil.rmtree(holder, ignore_errors=True)
        gitcmd.in_repo(clone, "worktree", "prune")


def _base(task_id: str, target: str, branch: str, command: list[str],
          run_no: int, mode: str) -> tuple[set | None, str]:
    """(упавшие на базе, пояснение) — `None` вместо множества: база не
    посчитана, и сравнение не выдумывается (требования 7-8, 10)."""
    clone = workspace.repo(target)
    sha = gitcmd.diff_base(branch, repo=clone)
    if not sha:
        return None, "git не назвал базу ветки задачи"
    saved = acceptance.saved_failures(sha)
    if saved is not None:
        return set(saved), f"база {sha[:12]} — сохранённый итог"
    if mode == MODE_FAILED:
        return None, (f"сохранённого итога базы {sha[:12]} нет, а повтор "
                      f"упавших базу не прогоняет")
    base_log = _log_path(task_id, run_no, "-base")
    with _base_copy(clone, sha) as (copy, refusal):
        if copy is None:
            return None, refusal
        green, output = acceptance.run_full_suite(
            copy, command=command, targets=("tests",), extra=_PYTEST_FLAGS,
            log=base_log)
    parsed = parse(green, output)
    if not parsed.finished:
        return None, (f"прогон базы {sha[:12]} не завершён "
                      f"({parsed.outcome}); лог базы: {base_log}")
    failed = [node for node, _ in parsed.failures]
    acceptance.save_failures(sha, failed, "suite-run")
    return set(failed), f"база {sha[:12]} — прогон базы, лог базы: {base_log}"


# ------------------------------------------------------ фоновый процесс

def _run(task_id: str, run_no: int, mode: str, log: Path) -> tuple[str, bool]:
    conn = store.db()
    task = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)
    command, refusal = _profile_command(target)
    if refusal:
        return f"[{task_id}] suite-run №{run_no}: отказ — {refusal}", False
    targets = ("tests",)
    if mode == MODE_FAILED:
        targets = tuple(_read_failed(task_id) or ())
        if not targets:
            return (f"[{task_id}] suite-run №{run_no}: отказ — перечня "
                    f"упавших прошлого прогона нет"), False
    wt = workspace.path(task_id, target)
    green, output = acceptance.run_full_suite(
        wt, command=command, targets=targets, extra=_PYTEST_FLAGS, log=log)
    parsed = parse(green, output)
    _write_json(_failed_path(task_id),
                {"run": run_no, "failed": [n for n, _ in parsed.failures]})
    base_failed, base_note = _base(task_id, target, task["branch"], command,
                                   run_no, mode)
    with contextlib.suppress(OSError), open(log, "a", encoding="utf-8") as fh:
        fh.write(_log_appendix(parsed, base_failed))
    return (render(task_id, run_no, mode, parsed, base_failed, base_note, log),
            parsed.outcome == acceptance.FULL_SUITE_GREEN)


def background(task_id: str, run_text: str, mode: str) -> None:
    """Тело отвязанного процесса прогона: замок, прогон, отчёт. Отчёт
    пишется на любом исходе — исключение пульта тоже даёт отчёт с путём к
    логу, а не тишину; замок снимается в `finally` (требование 13)."""
    run_no = int(run_text)
    log = _log_path(task_id, run_no)
    holder = _adopt_lock(task_id, run_no)
    if holder is not None:
        _write_json(_result_path(task_id), {
            "run": run_no, "green": False,
            "report": (f"[{task_id}] suite-run №{run_no}: отказ — на машине "
                       f"уже идёт прогон suite-run задачи "
                       f"{holder.get('task_id')} (pid {holder.get('pid')})")})
        return
    try:
        try:
            report, green = _run(task_id, run_no, mode, log)
        except Exception as exc:  # отчёт обязан быть на любом исходе
            traceback.print_exc()
            report, green = (f"[{task_id}] suite-run №{run_no}: прогон оборван "
                             f"исключением пульта {type(exc).__name__}: {exc}; "
                             f"лог: {log}; трассировка: "
                             f"{_task_dir(task_id) / 'background.log'}"), False
        _write_json(_result_path(task_id),
                    {"run": run_no, "green": green, "report": report})
    finally:
        _release_lock()


# --------------------------------------------------------------- команда

def _parse_args(rest: list) -> tuple[str, str | None, bool]:
    usage = "suite-run <id> [--wait <минуты> | --failed]"
    positional, wait, failed = [], None, False
    index = 0
    while index < len(rest):
        arg = rest[index]
        if arg == "--wait":
            if wait is not None or index + 1 >= len(rest):
                sys.exit(f"{usage}: --wait требует одно число минут")
            wait = rest[index + 1]
            index += 2
            continue
        if arg == "--failed":
            failed = True
        elif arg.startswith("--"):
            sys.exit(f"неизвестный флаг {arg!r}; использование: {usage}")
        else:
            positional.append(arg)
        index += 1
    if len(positional) != 1:
        sys.exit(usage)
    if wait is not None and failed:
        sys.exit(f"{usage}: --wait и --failed не сочетаются — повтор "
                 f"запускается без --wait, отчёт забирается --wait")
    return positional[0], wait, failed


def _wait_minutes(text: str) -> int:
    limit = config.SUITE_RUN_MAX_WAIT_MIN
    try:
        minutes = int(text)
    except ValueError:
        minutes = -1
    if not 0 <= minutes <= limit:
        sys.exit(f"suite-run --wait: отказ — «{text}» не число минут от 0 до "
                 f"{limit} (config.SUITE_RUN_MAX_WAIT_MIN = {limit}: одно "
                 f"ожидание укладывается в вызов инструмента роли); прогон не "
                 f"тронут, жди повторным --wait")
    return minutes


def _running(task_id: str) -> dict | None:
    """Последний прогон задачи, если он ещё идёт: процесс жив, отчёта нет."""
    state = _read_json(_run_path(task_id))
    if state is None or not _alive(state.get("pid")):
        return None
    result = _read_json(_result_path(task_id))
    if result is not None and result.get("run") == state.get("run"):
        return None
    return state


def _progress_text(state: dict) -> str:
    done = []
    for suffix, label in (("", "ветки"), ("-base", "базы")):
        path = Path(str(state["log"]).removesuffix(".log") + f"{suffix}.log")
        if suffix and not path.exists():
            continue
        try:
            text = path.read_bytes().decode("utf-8", errors="replace")
        except OSError:
            text = ""
        done.append(f"прогон {label}: выполнено тестов по логу "
                    f"{len(_progress(text))}")
    elapsed = int(time.time() - float(state.get("started") or time.time()))
    return f"идёт {elapsed} с; " + "; ".join(done)


def _wait(task_id: str, minutes: int) -> None:
    head = f"[{task_id}] suite-run"
    state = _read_json(_run_path(task_id))
    if state is None:
        sys.exit(f"{head}: отказ — у задачи {task_id} нет ни одного прогона "
                 f"suite-run, ждать нечего; запусти прогон: "
                 f"{_pult_command(task_id)}")
    deadline = time.monotonic() + minutes * 60
    while True:
        result = _read_json(_result_path(task_id))
        if result is not None and result.get("run") == state.get("run"):
            print(result.get("report", ""))
            if not result.get("green"):
                sys.exit(1)
            return
        if not _alive(state.get("pid")):
            # Процесс мог дописать отчёт и выйти между двумя чтениями.
            result = _read_json(_result_path(task_id))
            if result is None or result.get("run") != state.get("run"):
                sys.exit(f"{head}: прогон №{state.get('run')} оборван — "
                         f"фонового процесса (pid {state.get('pid')}) больше "
                         f"нет, отчёта он не оставил; лог: {state.get('log')}; "
                         f"новый прогон: {_pult_command(task_id)}")
            continue
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print(f"{head}: прогон №{state.get('run')} {STILL_RUNNING} — "
                  f"{_progress_text(state)}; лог: {state.get('log')}")
            sys.exit(f"{head}: прогон не прерван; отчёт — повторным "
                     f"{_pult_command(task_id)} --wait <минуты>")
        time.sleep(min(_POLL_SEC, remaining))


def cmd_suite_run(rest: list) -> None:
    task_arg, wait, failed = _parse_args(rest)
    minutes = _wait_minutes(wait) if wait is not None else None
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_arg)
    if minutes is not None:
        _wait(task_id, minutes)
        return
    head = f"[{task_id}] suite-run"
    target = store.task_target(conn, task_id)
    command, refusal = _profile_command(target)
    if refusal:
        sys.exit(f"{head}: отказ — {refusal}; прогон не запускался")
    wt = workspace.path(task_id, target)
    if not wt.is_dir():
        sys.exit(f"{head}: отказ — рабочей копии задачи нет ({wt}); "
                 f"прогонять нечего")
    if failed:
        previous = _read_failed(task_id)
        if previous is None:
            sys.exit(f"{head}: отказ — прошлого прогона suite-run у задачи "
                     f"нет, повторять нечего; сначала полный прогон: "
                     f"{_pult_command(task_id)}")
        if not previous:
            sys.exit(f"{head}: отказ — в прошлом прогоне упавших нет, "
                     f"повторять нечего; полный прогон: "
                     f"{_pult_command(task_id)}")
    running = _running(task_id)
    if running is not None:
        print(f"{head}: прогон №{running.get('run')} этой задачи уже идёт "
              f"(pid {running.get('pid')}) — второй не запускаю; лог: "
              f"{running.get('log')}; отчёт: {_pult_command(task_id)} "
              f"--wait <минуты>")
        return
    # Замок берётся здесь, атомарно, до запуска фонового процесса и
    # передаётся ему: два одновременных запуска не могут оба ответить
    # «запущен» — второй отказывает сразу, с держателем (требование 13).
    holder = _acquire_lock(task_id, None)
    if holder is not None:
        sys.exit(f"{head}: отказ — на машине уже идёт прогон suite-run "
                 f"задачи {holder.get('task_id')} (pid {holder.get('pid')}); "
                 f"одновременно идёт один прогон — повтори после его конца")
    mode = MODE_FAILED if failed else MODE_FULL
    try:
        log = agent_log.new_agent_log(task_id, LOG_KIND)
        run_no = int(log.stem.rsplit("-", 1)[1])
        _hand_lock(task_id, run_no, os.getpid())
        _task_dir(task_id).mkdir(parents=True, exist_ok=True)
        # Признак роли снимается: это прогон пульта, сторож `conftest.py`
        # его не отклоняет, даже когда команду позвал процесс роли
        # (требование 3).
        env = {k: v for k, v in os.environ.items()
               if k != config.ARTEL_ROLE_ENV}
        with open(_task_dir(task_id) / "background.log", "ab") as errors:
            proc = subprocess.Popen(
                [sys.executable, "-c", _CHILD, task_id, str(run_no), mode],
                cwd=str(config.ROOT), env=env, stdin=subprocess.DEVNULL,
                stdout=errors, stderr=subprocess.STDOUT,
                start_new_session=True)
    except BaseException:
        _release_lock()
        raise
    _hand_lock(task_id, run_no, proc.pid)
    _write_json(_run_path(task_id), {"run": run_no, "pid": proc.pid,
                                     "log": str(log), "mode": mode,
                                     "started": time.time()})
    what = "повтор упавших" if failed else "полный набор"
    print(f"{head}: прогон №{run_no} ({what}) запущен фоном, pid {proc.pid}; "
          f"лог: {log}")
    print(f"  отчёт: {_pult_command(task_id)} --wait <минуты, не больше "
          f"{config.SUITE_RUN_MAX_WAIT_MIN}>")
