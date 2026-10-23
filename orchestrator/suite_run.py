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
- на машине одновременно идёт один полный прогон — замок общий с гейтами
  пульта и `notes` (`suite_lock`, SPEC 01M46D5T8SZ9D6S34TZFX8S46V); его
  держит фоновый процесс, а занятый замок — немедленный отказ команды.

Состояния задачи команда не меняет, lease не берёт, журнал шагов не пишет:
всё её хозяйство — в каталоге логов пульта (`_state_dir`), поэтому она в
перечне команд роли (`artel._ROLE_ALLOWED_COMMANDS`).

Роль на Codex идёт в песочнице, открывающей на запись из хозяйства пульта
только `_state_dir` (SPEC 01M4KG7VHHXTVTW5TTX2PGY5RY): логи прогонов лежат
в нём же, а запись журнала задачи, которую прогон без права записи в БД
сделать не смог, откладывается (`suite_lock.defer_journal`) и досылается
процессом пульта (`suite_lock.deliver_journal`).

Шагу разработчика (маркер `ARTEL_ROLE=developer`) новый полный прогон не
положен (SPEC 01M5HDB1GSFDKFM7QB9JZMCCWJ, ADR-0024): `suite-run <id>` без
флагов отказывает до любой записи; `--wait` и `--failed` — прежние.
"""
import contextlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import NamedTuple

from . import (acceptance, appendix_tree, config, gitcmd, liveness,
               project_profile, repo_context, session, store, suite_lock,
               workspace)
from .targets import PROFILE_RUNNER_OWN, TargetsError

# Вид в имени лога прогона: `.artel/logs/suite-run/<id>/<id>-suiterun-<n>.log`
# — имя прежнее, каталог — хозяйство команды (`_new_log`).
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
_FRESH_LOCK_SEC = suite_lock.FRESH_SEC

_CHILD = ("import sys; from orchestrator import suite_run; "
          "suite_run.background(*sys.argv[1:])")

_STATUS = r"PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS"
# Строка хода прогона `-v`: с xdist — «[gw0] [ 50%] PASSED <id>», без него —
# «<id> PASSED [ 50%]».
_PROGRESS = re.compile(
    rf"^(?:\[gw\d+\] \[\s*\d+%\] (?P<s1>{_STATUS}) (?P<n1>.+?)"
    rf"|(?P<n2>\S.*?::.+?) (?P<s2>{_STATUS})(?: +\[\s*\d+%\])?)\s*$",
    re.MULTILINE)
# Строка хода упавшего подтеста (SPEC 01M4PMQ5FQMEV11WPY64G0GNXS): с xdist —
# «[gw0] [ 50%] SUBFAILED<метка> <id>» (id — последнее слово), без него —
# «<id> SUBFAILED<метка> [ 50%]» (id — первое слово). Без xdist провал
# unittest subTest строки хода не оставляет — его знает только короткий
# итог (`acceptance.failed_entries`).
_SUBFAILED_PROGRESS = re.compile(
    r"^(?:\[gw\d+\] \[\s*\d+%\] SUBFAILED(?P<l1>.*?) (?P<n1>\S+)"
    r"|(?P<n2>\S+::\S*) SUBFAILED(?P<l2>.*?)(?: +\[\s*\d+%\])?)\s*$",
    re.MULTILINE)
# Первая секция отчёта pytest после строк хода («==== FAILURES ====» и
# далее): в ней захваченный вывод тестов, и строка вида «<x>::<y> PASSED»
# оттуда — не ход прогона.
_REPORT_SECTION = re.compile(r"^=+ (?!test session starts =).* =+$",
                             re.MULTILINE)
_SUMMARY_COUNT = re.compile(
    r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")


def _extra_flags(command) -> tuple:
    """Флаги pytest пульта к команде прогона; команде компонента с отчётом
    — никаких: она не обязана быть pytest (требование 9)."""
    return () if acceptance._reported(command) is not None else _PYTEST_FLAGS


# ------------------------------------------------------------- состояние

def _state_dir() -> Path:
    """Каталог хозяйства команды — функция: `config.LOGS` подменяют тесты."""
    return suite_lock.directory()


def _task_dir(task_id: str) -> Path:
    return _state_dir() / task_id


def _lock_path() -> Path:
    return suite_lock.path()


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
    """Лог прогона — в каталоге задачи хозяйства команды, не в `config.LOGS`:
    каталог логов пульта роли на Codex на запись не открыт (требование 2)."""
    return _task_dir(task_id) / f"{task_id}-{LOG_KIND}-{run_no}{suffix}.log"


def _new_log(task_id: str) -> Path:
    """Лог следующего прогона задачи, файл создаётся сразу (как у
    `agent_log.new_agent_log`). Номер — следующий за наибольшим из логов
    каталога задачи и номеров `run.json`/`result.json`: прогон, начатый до
    переноса логов из `config.LOGS`, номер не повторит, а `--wait` узнаёт
    свой отчёт именно по номеру."""
    prefix = f"{task_id}-{LOG_KIND}-"
    folder = _task_dir(task_id)
    folder.mkdir(parents=True, exist_ok=True)
    used = [int(p.stem[len(prefix):]) for p in folder.glob(f"{prefix}*.log")
            if p.stem[len(prefix):].isdigit()]
    for state in (_read_json(_run_path(task_id)),
                  _read_json(_result_path(task_id))):
        run = (state or {}).get("run")
        if isinstance(run, int) and not isinstance(run, bool):
            used.append(run)
    path = _log_path(task_id, max(used, default=0) + 1)
    path.touch()
    return path


def _db():
    """БД пульта; не открылась на запись (песочница роли на Codex) —
    только на чтение: команде и прогону из БД нужно лишь прочесть задачу."""
    try:
        return store.db()
    except (sqlite3.Error, OSError):
        return _readonly_db()


def _readonly_db() -> sqlite3.Connection:
    return store.db_readonly()


@contextlib.contextmanager
def _journal_deferred():
    """На время прогона запись журнала, отказанная БД (`sqlite3.Error`),
    откладывается в хозяйство команды (требование 3). Подменяется сам
    `store.journal`: записи журнала делает узел пульта
    (`acceptance.run_full_suite`), который этот модуль не меняет. Сбой
    вызывающий видит, как и прежде, — он же решает, ронять ли прогон.
    Откладываются только действия перечня `suite_lock.deferrable`: автора
    записи досыл ставит сам, из очереди его не берёт."""
    write = store.journal

    def journal(conn, task_id, actor, action, detail="", **kwargs):
        try:
            write(conn, task_id, actor, action, detail, **kwargs)
        except sqlite3.Error:
            with contextlib.suppress(OSError):
                suite_lock.defer_journal({
                    "task_id": task_id, "action": action, "detail": detail,
                    "session_id": (kwargs.get("session_id")
                                   or session.resolve_session_id(None)),
                    "at": store.now()})
            raise

    store.journal = journal
    try:
        yield
    finally:
        store.journal = write


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


# ------------------------------------------------------------ developer
#
# Новый полный прогон шагу разработчика не положен (ADR-0024, поправка
# 22.10.2026): признак — маркер `ARTEL_ROLE`, равный `developer`. Это
# отсечение ошибочного вызова, не граница против намеренного обхода.
# Подсказки под тем же маркером не советуют полный прогон.

def _developer() -> bool:
    return os.environ.get(config.ARTEL_ROLE_ENV) == config.STATE_ROLE["in_dev"]


def _developer_hint(task_id: str) -> str:
    """Что делать developer вместо полного прогона (форма
    `skills/coding-standards.md`)."""
    pult = config.ROOT / "orchestrator" / "artel.py"
    return (f"полный набор прогонят CI и автопроверка приёмки; свои файлы — "
            f"`python3 -m pytest tests/<файлы> -p no:cacheprovider -p timeout "
            f"-o timeout=120` в переднем плане; планка — `python3 {pult} "
            f"plank-run {task_id} [файл]`; повтор упавших прогона Оператора "
            f"или ревьювера — `{_pult_command(task_id)} --failed`")


def _refuse_developer_full_run(task_arg: str) -> None:
    """Ответ developer на `suite-run <id>` без флагов — до любой записи:
    задача разрешается только чтением БД (`mode=ro`), журнал не досылается,
    хозяйство `suite-run` не трогается. Идущий прогон задачи — прежний
    ответ «уже идёт», код 0."""
    conn = _readonly_db()
    try:
        task_id = store.get_task(conn, task_arg)["id"]
    finally:
        conn.close()
    head = f"[{task_id}] suite-run"
    running = _running(task_id)
    if running is not None:
        print(_running_text(head, task_id, running))
        return
    sys.exit(f"{head}: отказ — новый полный прогон `suite-run` недоступен "
             f"роли developer (ARTEL_ROLE=developer), задача {task_id}; "
             f"{_developer_hint(task_id)}")


# ---------------------------------------------------------------- замок
#
# Замок полных прогонов машины — общий с гейтами пульта и `notes`
# (`suite_lock`, SPEC 01M46D5T8SZ9D6S34TZFX8S46V, требование 1): прогон
# гейта при занятом замке ждёт, `suite-run` — отказывает сразу.

def _acquire_lock(task_id: str, run_no: int | None) -> dict | None:
    """Замок прогонов машины за текущим процессом без ожидания: `None` —
    взят, иначе держатель (в том числе прогон гейта)."""
    return suite_lock.acquire(task_id, run_no)


def _hand_lock(task_id: str, run_no: int, pid: int) -> None:
    suite_lock.hand(task_id, run_no, pid)


def _adopt_lock(task_id: str, run_no: int) -> dict | None:
    return suite_lock.adopt(task_id, run_no)


def _release_lock() -> None:
    suite_lock.release()


# ---------------------------------------------------- профиль тестов проекта

def _is_pytest(command: list[str]) -> bool:
    """Команда — запуск pytest: исполняемый файл `pytest`/`py.test` или
    `-m pytest`. Имя интерпретатора само по себе ничего не говорит."""
    return acceptance.is_pytest_command(command)


def _profile_command(target: str) -> tuple:
    """(команда профиля тестов проекта, причина отказа) — требование 2.

    У `runner: pytest-own` и у профиля с итогом из отчёта команда — сам
    профиль (`project_profile.Profile`, с `tools` и полями компонента —
    `project_profile.with_tools`, тот же помощник, что у `decide`; SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требование 15): прогоны и ключ итога идут
    каналом профиля `run_full_suite` и `suite_result_key` (SPEC
    01M52EEHSRD93WMPHWB5VJYRKD); у `pult-pytest` — список, как прежде.
    Признак «не pytest» профилю с отчётом не отказывает (требование 9)."""
    answer = repo_context.profile_of(target)
    if answer.outcome == repo_context.PROFILE_UNREAD:
        return None, (f"профиль тестов проекта «{target}» не прочитан "
                      f"(test_profile в targets.yaml): {answer.reason}")
    if answer.outcome != repo_context.PROFILE_PRESENT:
        return None, (f"у проекта «{target}» нет профиля тестов "
                      f"(test_profile в targets.yaml) — команде прогона "
                      f"неоткуда взять команду")
    profile = None
    if answer.values.get("report") or \
            answer.values.get("runner") == PROFILE_RUNNER_OWN:
        try:
            profile = project_profile.with_tools(
                target, project_profile.Profile.from_values(answer.values))
        except (KeyError, TypeError, ValueError, TargetsError) as exc:
            return None, (f"профиль тестов проекта «{target}» не прочитан "
                          f"(test_profile в targets.yaml): {exc}")
        if acceptance._reported(profile) is not None:
            return profile, ""
    command = [str(part) for part in answer.values.get("command") or ()]
    if not _is_pytest(command):
        return None, (f"команда профиля тестов проекта «{target}» "
                      f"({' '.join(command) or 'пусто'}) — не запуск pytest: "
                      f"флаги параллели pytest (-n) к ней неприменимы")
    if answer.values.get("runner") != PROFILE_RUNNER_OWN:
        return command, ""
    return profile, ""


# -------------------------------------------------------- разбор прогона

class Parsed(NamedTuple):
    """Итог одного прогона: исход (`acceptance.FULL_SUITE_*`), числа,
    упавшие парами (id, первая строка сообщения) и признак «прогон
    завершён» — только такой годится в итог базы (требование 8).
    Упавший подтест — единицей `acceptance.subtest_unit`; `rerun` — id
    тестов для повтора `--failed` (подтест — id родителя); `unknown` —
    строка исхода «неизвестно» (`acceptance.unknown_line`, SPEC
    01M590GJAF0EDV4NBC4C99MFVH, требование 3), иначе пусто."""
    outcome: str
    passed: int
    failed: int
    skipped: int
    failures: list
    finished: bool
    rerun: tuple = ()
    unknown: str = ""


def _progress_part(output: str) -> str:
    """Строки хода — до первой секции отчёта (`_REPORT_SECTION`)."""
    section = _REPORT_SECTION.search(output)
    return output if section is None else output[:section.start()]


def _progress(output: str) -> dict[str, str]:
    """id теста -> исход по строкам хода прогона; упавший хоть раз (в том
    числе на teardown после PASSED) остаётся упавшим. Читаются только
    строки до секций отчёта (`_REPORT_SECTION`). Подтестов здесь нет:
    счёт хода — по тестам (`_subtest_progress`)."""
    statuses = {}
    for match in _PROGRESS.finditer(_progress_part(output)):
        node = (match.group("n1") or match.group("n2")).strip()
        status = match.group("s1") or match.group("s2")
        if statuses.get(node) not in ("FAILED", "ERROR"):
            statuses[node] = status
    return statuses


def _subtest_progress(output: str) -> dict[str, str]:
    """Единица упавшего подтеста -> id родителя по строкам хода. Строка
    `PASSED <id>` родителя после неё провала не снимает: единица — не id
    теста, `_progress` её не перезаписывает."""
    units = {}
    for match in _SUBFAILED_PROGRESS.finditer(_progress_part(output)):
        node = match.group("n1") or match.group("n2")
        label = match.group("l1") if match.group("n1") else match.group("l2")
        units[acceptance.subtest_unit(node, label)] = node
    return units


def parse(green: bool, output: str, *, reported: bool = False) -> Parsed:
    """Разбор вывода прогона. `reported` — вывод профиля с итогом из отчёта
    (SPEC 01M590GJAF0EDV4NBC4C99MFVH, требование 18): упавшие и числа —
    только из сводки отчёта в конце вывода; строки хода сырого вывода
    раннера (id от `workdir`, иной формы) не читаются."""
    outcome = acceptance._full_suite_outcome(green, output)
    summary = acceptance.run_summary_line(output)
    finished = (outcome in (acceptance.FULL_SUITE_GREEN,
                            acceptance.FULL_SUITE_RED) and bool(summary))
    statuses = {} if reported else _progress(output)
    parents = {} if reported else _subtest_progress(output)
    failures = dict.fromkeys(
        (node for node, status in statuses.items()
         if status in ("FAILED", "ERROR")), "")
    failures.update(dict.fromkeys(parents, ""))
    if finished:
        failures.update(acceptance.failed_entries(output))
        parents.update(acceptance.subtest_parents(output))
        counts = {}
        for number, kind in _SUMMARY_COUNT.findall(summary):
            counts[kind.rstrip("s") if kind.startswith("error") else kind] = int(number)
        passed = counts.get("passed", 0)
        failed = counts.get("failed", 0) + counts.get("error", 0)
        skipped = counts.get("skipped", 0)
    else:
        values = list(statuses.values())
        passed = values.count("PASSED")
        failed = (values.count("FAILED") + values.count("ERROR")
                  + len(parents))
        skipped = values.count("SKIPPED")
    rerun = tuple(dict.fromkeys(parents.get(node, node)
                                for node in sorted(failures)))
    unknown = (output.splitlines()[0]
               if output.startswith(acceptance.UNKNOWN_PREFIX) else "")
    return Parsed(outcome, passed, failed, skipped,
                  sorted(failures.items()), finished, rerun, unknown)


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
           base_failed: set | None, base_note: str, log: Path,
           limit: tuple[int, str] | None = None) -> str:
    """Короткий отчёт для шага роли (требования 11-12)."""
    seconds, source = limit or (config.FULL_SUITE_TIMEOUT_SEC, "config")
    title = {
        acceptance.FULL_SUITE_GREEN: "зелёный прогон",
        acceptance.FULL_SUITE_RED: "красный прогон",
        acceptance.FULL_SUITE_TIMEOUT: (
            f"прогон не уложился в предел {seconds} с "
            f"(источник: {source}) и оборван — числа и упавшие по "
            f"успевшей части"),
        acceptance.FULL_SUITE_NO_TESTS: acceptance.FULL_SUITE_NO_TESTS_NOTE,
        acceptance.FULL_SUITE_NOT_STARTED: acceptance.FULL_SUITE_NOT_STARTED,
    }[parsed.outcome]
    if parsed.unknown:
        title = parsed.unknown
    what = "повтор упавших" if mode == MODE_FAILED else "полный набор"
    lines = [f"[{task_id}] suite-run №{run_no} ({what}): {title}",
             f"прошло: {parsed.passed}, упало: {parsed.failed}, "
             f"пропущено: {parsed.skipped}"]
    if parsed.finished and len(parsed.failures) < parsed.failed:
        # Числа — из итоговой строки, перечень — из разбора: расхождение
        # называется прямо, а не прячется за коротким перечнем.
        lines.append(f"итог pytest: {parsed.failed} упавших, разобрано "
                     f"{len(parsed.failures)} — неразобранные ищи в полном "
                     f"логе")
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
    (holder / liveness.SUITE_OWNER_MARKER).write_text(
        str(os.getpid()), encoding="utf-8")
    for parent in (clone, *clone.parents):
        marker = parent / liveness.CANARY_OWNER_MARKER
        if parent.name.startswith("artel-canary-") and marker.is_file():
            shutil.copyfile(marker, holder / marker.name)
            break
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


def _base(task_id: str, target: str, branch: str, command,
          run_no: int, mode: str,
          limit: tuple[int, str] | None = None) -> tuple[set | None, str]:
    """(упавшие на базе, пояснение) — `None` вместо множества: база не
    посчитана, и сравнение не выдумывается (требования 7-8, 10)."""
    clone = workspace.repo(target)
    sha = gitcmd.diff_base(branch, repo=clone)
    if not sha:
        return None, "git не назвал базу ветки задачи"
    try:
        tree = acceptance.suite_tree_hash(clone, ref=sha, base=True,
                                          worktree=False)
        key = acceptance.suite_result_key(tree, command, base=True) if tree else None
        saved = acceptance.saved_suite_result("base", key, tree=tree) if key else None
    except (OSError, ValueError, TypeError, AttributeError):
        tree = key = saved = None
    if saved is not None:
        return set(saved["failed"]), f"база {sha[:12]} — сохранённый итог"
    if mode == MODE_FAILED:
        return None, (f"сохранённого итога базы {sha[:12]} нет, а повтор "
                      f"упавших базу не прогоняет")
    base_log = _log_path(task_id, run_no, "-base")
    with _base_copy(clone, sha) as (copy, refusal):
        if copy is None:
            return None, refusal
        green, output = acceptance.run_full_suite(
            copy, command=command, targets=("tests",),
            extra=_extra_flags(command), log=base_log, limit=limit)
    parsed = parse(green, output,
                   reported=acceptance._reported(command) is not None)
    if not parsed.finished:
        return None, (f"прогон базы {sha[:12]} не завершён "
                      f"({parsed.outcome}); лог базы: {base_log}")
    failed = [node for node, _ in parsed.failures]
    if key and tree:
        acceptance.save_suite_result("base", key, tree, parsed.outcome,
                                     output, base_log)
    return set(failed), f"база {sha[:12]} — прогон базы, лог базы: {base_log}"


def _component_command(conn, task_id: str, target: str) -> tuple:
    """(команда, предел, причина отказа) задачи на записи из нескольких
    компонентов — по профилю компонента задачи (`project_profile.
    for_task`; SPEC 01M5JGSAANR1NZYQD4FCSVE48Y, требование 2): тот же
    выбор канала, что у `_profile_command`, и `component_limit`."""
    decision = project_profile.for_task_target(target, task_id, conn)
    profile = decision.profile
    if profile is None:
        return None, None, decision.refusal
    limit = project_profile.component_limit(profile)
    if acceptance._reported(profile) is not None:
        return profile, limit, ""
    command = [str(part) for part in profile.command]
    if not _is_pytest(command):
        return None, None, (
            f"команда компонента {profile.component} проекта «{target}» "
            f"({' '.join(command) or 'пусто'}) — не запуск pytest: флаги "
            f"параллели pytest (-n) к ней неприменимы")
    if profile.runner != PROFILE_RUNNER_OWN:
        return command, limit, ""
    return profile, limit, ""


# ------------------------------------------------------ фоновый процесс

def _run(task_id: str, run_no: int, mode: str, log: Path) -> tuple[str, bool]:
    conn = _db()
    task = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)
    if project_profile.is_multi(target):
        command, limit, refusal = _component_command(conn, task_id, target)
    else:
        command, refusal = _profile_command(target)
        limit = None if refusal else project_profile.full_suite_limit(target)
    if refusal:
        return f"[{task_id}] suite-run №{run_no}: отказ — {refusal}", False
    targets = ("tests",)
    test_ids: tuple = ()
    if mode == MODE_FAILED:
        targets = tuple(_read_failed(task_id) or ())
        if not targets:
            return (f"[{task_id}] suite-run №{run_no}: отказ — перечня "
                    f"упавших прошлого прогона нет"), False
        if acceptance._own(command) is not None and \
                acceptance._reported(command) is None:
            # id упавших `pytest-own` напечатаны из `workdir` — идут как
            # есть каналом `test_ids`, без перевода путей целей.
            targets, test_ids = (), targets
    wt = workspace.path(task_id, target)
    # Рабочая копия с незакоммиченными правками плюс приложения PLAN (SPEC
    # 01M46C776SZEMYPBQGPNJN1TXY) — тем же узлом, что у автогейта и
    # approve; база ниже идёт без приложений задачи (требование 6).
    with appendix_tree.suite_tree(conn, task_id, wt) as tree:
        if tree.root is None:
            return (f"[{task_id}] suite-run №{run_no}: отказ — "
                    f"{tree.refusal}"), False
        acceptance._last_full_suite_metrics = None
        with acceptance.observed_full_suite():
            green, output = acceptance.run_full_suite(
                tree.root, command=command, targets=targets,
                extra=_extra_flags(command), log=log, limit=limit,
                **({"test_ids": test_ids} if test_ids else {}))
    metrics = acceptance._last_full_suite_metrics
    parsed = parse(green, output,
                   reported=acceptance._reported(command) is not None)
    # Повтор — по id тестов: единицу подтеста `<id> <метка>` pytest не найдёт.
    _write_json(_failed_path(task_id),
                {"run": run_no, "failed": list(parsed.rerun)})
    base_failed, base_note = _base(task_id, target, task["branch"], command,
                                   run_no, mode, limit)
    with contextlib.suppress(OSError), open(log, "a", encoding="utf-8") as fh:
        fh.write(_log_appendix(parsed, base_failed))
    report = render(task_id, run_no, mode, parsed, base_failed, base_note,
                    log, limit)
    if parsed.outcome == acceptance.FULL_SUITE_TIMEOUT and metrics is not None:
        report += "\n" + acceptance.suite_load_line(metrics)
    from . import suite_durations  # suite_durations -> suite_run
    slowest = suite_durations.write_slowest(log)
    if slowest is not None:
        report += f"\nсамые медленные тесты и файлы: {slowest}"
    if tree.note or tree.warning:
        head, _, rest = report.partition("\n")
        report = "\n".join([head, tree.mark("прогон ветки"), rest])
    return report, parsed.outcome == acceptance.FULL_SUITE_GREEN


def background(task_id: str, run_text: str, mode: str) -> None:
    """Тело отвязанного процесса прогона: замок, прогон, отчёт. Отчёт
    пишется на любом исходе — исключение пульта тоже даёт отчёт с путём к
    логу, а не тишину; замок снимается в `finally` (требование 13)."""
    run_no = int(run_text)
    log = _log_path(task_id, run_no)
    log.parent.mkdir(parents=True, exist_ok=True)
    holder = _adopt_lock(task_id, run_no)
    if holder is not None:
        _write_json(_result_path(task_id), {
            "run": run_no, "green": False,
            "report": (f"[{task_id}] suite-run №{run_no}: отказ — на машине "
                       f"уже идёт прогон "
                       f"{suite_lock.describe(holder)}")})
        return
    try:
        try:
            with _journal_deferred():
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
    """Последний прогон задачи, если он ещё идёт: процесс жив, отчёта нет и
    замок машины держит он. Без сверки с замком живой чужой процесс на
    переиспользованном pid сходил за идущий прогон, и команда отвечала
    «уже идёт», не сказав, кто на самом деле держит замок."""
    state = _read_json(_run_path(task_id))
    if state is None or not _alive(state.get("pid")):
        return None
    result = _read_json(_result_path(task_id))
    if result is not None and result.get("run") == state.get("run"):
        return None
    holder = suite_lock.holder()
    if holder is None or holder.get("pid") != state.get("pid"):
        return None
    return state


def _running_text(head: str, task_id: str, running: dict) -> str:
    return (f"{head}: прогон №{running.get('run')} этой задачи уже идёт "
            f"(pid {running.get('pid')}) — второй не запускаю; лог: "
            f"{running.get('log')}; отчёт: {_pult_command(task_id)} "
            f"--wait <минуты>")


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
        hint = (_developer_hint(task_id) if _developer() else
                f"запусти прогон: {_pult_command(task_id)}")
        sys.exit(f"{head}: отказ — у задачи {task_id} нет ни одного прогона "
                 f"suite-run, ждать нечего; {hint}")
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
                hint = (_developer_hint(task_id) if _developer() else
                        f"новый прогон: {_pult_command(task_id)}")
                sys.exit(f"{head}: прогон №{state.get('run')} оборван — "
                         f"фонового процесса (pid {state.get('pid')}) больше "
                         f"нет, отчёта он не оставил; лог: {state.get('log')}; "
                         f"{hint}")
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
    if minutes is None and not failed and _developer():
        _refuse_developer_full_run(task_arg)
        return
    conn = _db()
    task_id = store.resolve_task_id(conn, task_arg)
    # Процесс с правом записи в БД (Оператор, роль на Claude) досылает
    # журнал прогонов роли без такого права; у роли на Codex файлы
    # остаются до процесса пульта (требование 3).
    suite_lock.deliver_journal()
    if minutes is not None:
        _wait(task_id, minutes)
        return
    head = f"[{task_id}] suite-run"
    target = store.task_target(conn, task_id)
    if project_profile.is_multi(target):
        _command, _limit, refusal = _component_command(conn, task_id, target)
    else:
        _command, refusal = _profile_command(target)
    if refusal:
        sys.exit(f"{head}: отказ — {refusal}; прогон не запускался")
    wt = workspace.path(task_id, target)
    if not wt.is_dir():
        sys.exit(f"{head}: отказ — рабочей копии задачи нет ({wt}); "
                 f"прогонять нечего")
    if failed:
        previous = _read_failed(task_id)
        if previous is None:
            hint = (("перечень упавших пишет только полный прогон Оператора "
                     "или ревьювера; упавшие тесты CI или гейта запускай по "
                     "именам — `python3 -m pytest tests/<файл>::<тест> …` в "
                     "переднем плане") if _developer() else
                    f"сначала полный прогон: {_pult_command(task_id)}")
            sys.exit(f"{head}: отказ — прошлого прогона suite-run у задачи "
                     f"нет, повторять нечего; {hint}")
        if not previous:
            hint = (_developer_hint(task_id) if _developer() else
                    f"полный прогон: {_pult_command(task_id)}")
            sys.exit(f"{head}: отказ — в прошлом прогоне упавших нет, "
                     f"повторять нечего; {hint}")
    running = _running(task_id)
    if running is not None:
        print(_running_text(head, task_id, running))
        return
    # Замок берётся здесь, атомарно, до запуска фонового процесса и
    # передаётся ему: два одновременных запуска не могут оба ответить
    # «запущен» — второй отказывает сразу, с держателем (требование 13).
    holder = _acquire_lock(task_id, None)
    if holder is not None:
        sys.exit(f"{head}: отказ — на машине уже идёт прогон "
                 f"{suite_lock.describe(holder)}; одновременно идёт один "
                 f"полный прогон — повтори после его конца")
    mode = MODE_FAILED if failed else MODE_FULL
    try:
        log = _new_log(task_id)
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
