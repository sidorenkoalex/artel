"""Метрика разведки роли: сколько вызовов инструментов шаг тратит на чтение
и поиск до первой правки и что именно читает (SPEC
01M4RZAYH3SWJW4WFBW4QW15FP).

Только чтение: строки журнала, переданные вызывающим, и файлы логов шагов,
названные записями «agent run started». Ни записи в БД, журнал, логи и
git, ни запуска агентов. Сводку считает одна функция `summarize` — ею
пользуются и команда `explore-stats` (`cmd_explore_stats`), и блок
«Разведка ролей» отчёта `report`, поэтому на одних данных они дают одни
числа.

Модуль не импортирует `report` и `artel`: `report` сам зовёт сводку, а
`artel` — команду; регулярное выражение пути лога объявлено здесь тем же
текстом, что `report._LOG_PATH_RE`.
"""
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import retro, store
from .providers import base as provider_base
from .providers import claude as claude_provider
from .providers import codex as codex_provider

STARTED_ACTION = "agent run started"
COST_ACTIONS = retro.TOKEN_JOURNAL_ACTIONS
JOURNAL_ACTIONS = (STARTED_ACTION,) + tuple(COST_ACTIONS)
_LOG_PATH_RE = re.compile(r"лог: (.+?), промпт: ")
_PROVIDER_RE = re.compile(r"provider=([\w-]+)")
_RUN_NUMBER_RE = re.compile(r"-(\d+)\.log$")
_TS_FORMAT = "%Y-%m-%d %H:%M:%SZ"

# Граница разведки роли: роли, которые пишут код, разведывают до первой
# правки кода; роли, которые пишут только документы, — до первой записи
# любого вида (их «правка кода» не наступает никогда).
CODE_EDIT = "code_edit"
ANY_WRITE = "any_write"
BOUNDARY = {
    "developer": CODE_EDIT,
    "test_author": CODE_EDIT,
    "analyst": ANY_WRITE,
    "reviewer": ANY_WRITE,
    "spec_auditor": ANY_WRITE,
}
DEFAULT_ROLES = ("developer", "test_author", "reviewer", "analyst")
DEFAULT_DAYS = 7
TOP_LIMIT = 10

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", codex_provider.FILE_CHANGE_ITEM)
CODEX_TOOLS = (codex_provider.COMMAND_ITEM, codex_provider.FILE_CHANGE_ITEM)
READ_TOOL = "Read"
GREP_TOOL = "Grep"
BASH_TOOL = "Bash"

# Класс правки.
KIND_CODE = "code"
KIND_DOC = "doc"
KIND_OUTSIDE = "outside"
KIND_UNRECOGNIZED = "unrecognized"

# Форма нормализованного пути.
FORM_WORKTREE = "wt"
FORM_DOCS = "docs"
FORM_OUTSIDE = "outside"

DOCS_DIR = provider_base.DOCS_SEGMENT + "/"
DOCS_LABEL = "<документы задачи>"
# Усечённый остаток пути короче этого числа символов, совпадающий с
# началом `tasks/`, мог быть и кодом, и документом — правка не распознана.
SHORT_REST = len(DOCS_DIR)
_FILE_CHANGE_PATH_RE = re.compile(r'"path":\s*"((?:[^"\\]|\\.)*)"')

NOT_AVAILABLE = "н/д"

# Команды поиска в Bash: начало команды — начало строки или место после
# одного из этих разделителей (вне кавычек).
_COMMAND_STARTS = (";", "&&", "||", "|", "(", "$(")
_SEPARATORS = ("&&", "||", "$(", ";", "|", "(", ")", "&")
_GREP_VALUE_FLAGS = frozenset(("-A", "-B", "-C", "-m", "--include",
                               "--exclude", "-f"))
_RG_VALUE_FLAGS = _GREP_VALUE_FLAGS | {"-t", "--type", "-g", "--glob"}
_REGEXP_FLAGS = ("-e", "--regexp")


# --------------------------------------------------------------- пути

def normalize(path: str, task_id: str) -> tuple:
    """(форма, путь) значения пути вызова: путь в рабочей копии, документ
    задачи (путь внутри каталога документов) или путь вне рабочей копии
    (как есть). Одна функция на все формы: короткие `wt:`/`docs:` и
    абсолютные пути обеих раскладок пульта."""
    if path.startswith(provider_base.WORKTREE_LOG_PREFIX):
        return FORM_WORKTREE, path[len(provider_base.WORKTREE_LOG_PREFIX):]
    if path.startswith(provider_base.DOCS_LOG_PREFIX):
        return FORM_DOCS, path[len(provider_base.DOCS_LOG_PREFIX):]
    if path.startswith("/"):
        segment = f"/{provider_base.WORKTREES_SEGMENT}/{task_id}/"
        index = path.find(segment)
        if index >= 0:
            return FORM_WORKTREE, path[index + len(segment):]
        docs = re.search(
            rf"/{re.escape(provider_base.ARTEL_DIR_SEGMENT)}/"
            rf"{provider_base.PROJECTS_SEGMENT}/[^/]+/"
            rf"{provider_base.DOCS_SEGMENT}/{re.escape(task_id)}/", path)
        if docs:
            return FORM_DOCS, path[docs.end():]
    return FORM_OUTSIDE, path


def _file_change_path(arg: str) -> str | None:
    """Значение первого видимого поля `path` перечня `file_change`;
    усечённый JSON целиком не разбирается."""
    match = _FILE_CHANGE_PATH_RE.search(arg)
    if match is None:
        return None
    try:
        return json.loads(f'"{match.group(1)}"')
    except ValueError:
        return match.group(1)


def edit_kind(tool: str, arg: str, task_id: str) -> str:
    """Класс правки вызова: код, документ, вне рабочей копии или «не
    распознана». Усечённость меряется по аргументу строки вызова целиком
    (у `file_change` — весь JSON, решение Оператора О-1)."""
    truncated = len(arg) >= claude_provider.TOOL_ARGUMENT_LIMIT
    value = _file_change_path(arg) if tool == codex_provider.FILE_CHANGE_ITEM else arg
    if value is None:
        return KIND_UNRECOGNIZED
    form, rest = normalize(value, task_id)
    if form == FORM_DOCS:
        return KIND_DOC
    if form == FORM_OUTSIDE:
        return KIND_UNRECOGNIZED if truncated else KIND_OUTSIDE
    if rest.startswith(DOCS_DIR):
        return KIND_DOC
    if not rest:
        return KIND_UNRECOGNIZED
    if truncated and len(rest) < SHORT_REST and DOCS_DIR.startswith(rest):
        return KIND_UNRECOGNIZED
    return KIND_CODE


def read_key(arg: str, task_id: str) -> str:
    """Строка топа чтений: путь в рабочей копии как есть, документы задачи
    (и `tasks/<id этой задачи>/X` рабочей копии) — `<документы задачи>/X`,
    путь вне рабочей копии — как есть."""
    form, rest = normalize(arg, task_id)
    if form == FORM_DOCS:
        return f"{DOCS_LABEL}/{rest}"
    if form == FORM_WORKTREE:
        own = f"{DOCS_DIR}{task_id}/"
        if rest.startswith(own):
            return f"{DOCS_LABEL}/{rest[len(own):]}"
        return rest
    return arg


# --------------------------------------------------------------- поиск

def _shell_tokens(text: str) -> list:
    """[(разделитель | None, слово без кавычек, кавычка закрыта, конец)]
    строки оболочки; разделители ищутся вне кавычек."""
    tokens = []
    i, n = 0, len(text)
    while i < n:
        if text[i].isspace():
            i += 1
            continue
        separator = next((s for s in _SEPARATORS if text.startswith(s, i)), None)
        if separator is not None:
            i += len(separator)
            tokens.append((separator, "", True, i))
            continue
        word, closed = [], True
        while i < n and not text[i].isspace() and not any(
                text.startswith(s, i) for s in _SEPARATORS):
            char = text[i]
            if char in "\"'":
                end = text.find(char, i + 1)
                if end < 0:
                    word.append(text[i + 1:])
                    closed, i = False, n
                    break
                word.append(text[i + 1:end])
                i = end + 1
            elif char == "\\" and i + 1 < n:
                word.append(text[i + 1])
                i += 2
            else:
                word.append(char)
                i += 1
        tokens.append((None, "".join(word), closed, i))
    return tokens


def search_string(command: str) -> str | None:
    """Искомая строка первой команды `grep`/`rg`/`git grep` строки Bash
    либо `None`: команды поиска нет или шаблон оборван обрезкой строки."""
    tokens = _shell_tokens(command)
    for index, (separator, word, _closed, _end) in enumerate(tokens):
        if separator is not None:
            continue
        if index > 0 and tokens[index - 1][0] not in _COMMAND_STARTS:
            continue
        if word in ("grep", "rg"):
            args_from, value_flags = index + 1, (
                _RG_VALUE_FLAGS if word == "rg" else _GREP_VALUE_FLAGS)
        elif (word == "git" and index + 1 < len(tokens)
              and tokens[index + 1][0] is None and tokens[index + 1][1] == "grep"):
            args_from, value_flags = index + 2, _GREP_VALUE_FLAGS
        else:
            continue
        args = []
        for token in tokens[args_from:]:
            if token[0] is not None:
                break
            args.append(token)
        return _pattern(args, value_flags, len(command))
    return None


def _pattern(args: list, value_flags: frozenset, length: int) -> str | None:
    pattern = None
    position = 0
    while position < len(args):
        word = args[position][1]
        if word in _REGEXP_FLAGS:
            pattern = args[position + 1] if position + 1 < len(args) else None
            break
        if word.startswith("--regexp="):
            _sep, _word, closed, end = args[position]
            pattern = (None, word[len("--regexp="):], closed, end)
            break
        if word in value_flags:
            position += 2
            continue
        if word.startswith("-"):
            position += 1
            continue
        pattern = args[position]
        break
    if pattern is None:
        return None
    _sep, text, closed, end = pattern
    if not closed or not text:
        return None
    if length >= claude_provider.TOOL_ARGUMENT_LIMIT and end >= length:
        return None
    return text


# --------------------------------------------------------------- сводка

def _moment(ts) -> datetime | None:
    try:
        return datetime.strptime(ts or "", _TS_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _tool_calls(log) -> list | None:
    """[(инструмент, видимый аргумент)] строк вызова лога шага; `None` —
    лога нет или он не читается."""
    try:
        text = Path(log).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    prefix = claude_provider.TOOL_CALL_LINE_PREFIX
    calls = []
    for line in text.splitlines():
        if line.startswith(prefix):
            name, _, arg = line[len(prefix):].partition(" ")
            if name:
                calls.append((name, arg))
    return calls


def _journal_steps(steps) -> list:
    """Шаги из записей «agent run started» в хронологии `id`; провайдер —
    из ближайшей следующей записи стоимости той же задачи и роли, не
    стоящей за следующим «agent run started» той же задачи и роли."""
    rows = []
    for row in steps:
        action = row["action"]
        if action not in JOURNAL_ACTIONS:
            continue
        rows.append((row["id"], row["task_id"], row["ts"], row["actor"],
                     action, row["detail"] or ""))
    rows.sort(key=lambda r: r[0])
    found, pending = [], {}
    for _id, task_id, ts, actor, action, detail in rows:
        key = (task_id, actor)
        if action == STARTED_ACTION:
            match = _LOG_PATH_RE.search(detail)
            step = {"task": task_id, "role": actor, "ts": ts,
                    "log": match.group(1) if match else None, "provider": None}
            found.append(step)
            pending[key] = step
            continue
        step = pending.pop(key, None)
        if step is not None:
            provider = _PROVIDER_RE.search(detail)
            step["provider"] = provider.group(1) if provider else None
    return found


def _empty_counts() -> dict:
    return {"steps": 0, "first_runs": 0, "codex_steps": 0, "calls": [],
            "to_code": [], "to_write": [], "no_code_edit": 0, "no_write": 0,
            "bounded": 0, "bounded_calls": 0, "no_boundary": 0,
            "unrecognized_edits": 0, "outside_writes": 0, "logs_missing": 0,
            "reads": Counter(), "truncated_reads": 0, "reads_total": 0,
            "searches": Counter()}


def _count_step(counts: dict, step: dict, calls: list) -> None:
    task, boundary_kind = step["task"], BOUNDARY[step["role"]]
    if step["provider"]:
        codex = step["provider"] == codex_provider.CLI_NAME
    else:
        codex = any(name in CODEX_TOOLS for name, _arg in calls)
    run = _RUN_NUMBER_RE.search(Path(step["log"]).name)
    counts["steps"] += 1
    counts["first_runs"] += bool(run and int(run.group(1)) == 1)
    counts["codex_steps"] += codex
    counts["calls"].append(len(calls))

    first_code = first_write = None
    for index, (name, arg) in enumerate(calls):
        if name not in EDIT_TOOLS:
            continue
        kind = edit_kind(name, arg, task)
        counts["unrecognized_edits"] += kind == KIND_UNRECOGNIZED
        counts["outside_writes"] += kind == KIND_OUTSIDE
        if first_write is None:
            first_write = index
        if kind == KIND_CODE and first_code is None:
            first_code = index
    for event, key, missing in ((first_code, "to_code", "no_code_edit"),
                                (first_write, "to_write", "no_write")):
        if event is None:
            counts[missing] += 1
        else:
            counts[key].append(event)
    boundary = first_code if boundary_kind == CODE_EDIT else first_write
    if boundary is None:
        counts["no_boundary"] += 1
    else:
        counts["bounded"] += boundary
        counts["bounded_calls"] += len(calls)

    # Шаг без границы весь считается разведкой (решение Оператора О-A).
    for name, arg in calls[:len(calls) if boundary is None else boundary]:
        if name == READ_TOOL and not codex:
            counts["reads_total"] += 1
            if len(arg) >= claude_provider.TOOL_ARGUMENT_LIMIT:
                counts["truncated_reads"] += 1
            else:
                counts["reads"][read_key(arg, task)] += 1
        elif name == GREP_TOOL and arg:
            counts["searches"][arg] += 1
        elif name == BASH_TOOL:
            needle = search_string(arg)
            if needle:
                counts["searches"][needle] += 1


def _top(counter: Counter) -> list:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:TOP_LIMIT]


def _median(values: list):
    return statistics.median(values) if values else None


def _result(counts: dict) -> dict:
    return {
        "steps": counts["steps"],
        "first_runs": counts["first_runs"],
        "codex_steps": counts["codex_steps"],
        "median_calls": _median(counts["calls"]),
        "median_to_code_edit": _median(counts["to_code"]),
        "no_code_edit": counts["no_code_edit"],
        "median_to_write": _median(counts["to_write"]),
        "no_write": counts["no_write"],
        "share": (counts["bounded"] / counts["bounded_calls"]
                  if counts["bounded_calls"] else None),
        "no_boundary": counts["no_boundary"],
        "unrecognized_edits": counts["unrecognized_edits"],
        "outside_writes": counts["outside_writes"],
        "logs_missing": counts["logs_missing"],
        "top_reads": _top(counts["reads"]),
        "truncated_reads": counts["truncated_reads"],
        "reads_total": counts["reads_total"],
        "top_searches": _top(counts["searches"]),
    }


def summarize(steps, now: datetime, days: int, roles) -> dict:
    """Сводка разведки по ролям за `days` суток до `now` включительно.

    `steps` — строки журнала (доступ по ключу; читаются только `id,
    task_id, ts, actor, action, detail`), отбор действий и порядок `id` —
    здесь. Отбор «только задачи из `tasks`» — за вызывающим. Результат —
    «роль → показатели»; роль вне `BOUNDARY` — `{"refusal": текст}`."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = now - timedelta(days=days)
    roles = list(roles)
    counts = {role: _empty_counts() for role in roles if role in BOUNDARY}
    seen_logs = set()
    for step in _journal_steps(steps):
        role_counts = counts.get(step["role"])
        if role_counts is None:
            continue
        moment = _moment(step["ts"])
        if moment is None or moment < cutoff:
            continue
        log = step["log"]
        if log is not None:
            if log in seen_logs:
                continue
            seen_logs.add(log)
        calls = _tool_calls(log) if log else None
        if calls is None:
            role_counts["logs_missing"] += 1
            continue
        _count_step(role_counts, step, calls)
    result = {}
    for role in roles:
        if role in counts:
            result[role] = _result(counts[role])
        else:
            result[role] = {"refusal": (
                f"роль {role!r} вне границ разведки; известны: "
                f"{', '.join(BOUNDARY)}")}
    return result


# --------------------------------------------------------------- вывод

def _number(value) -> str:
    if value is None:
        return NOT_AVAILABLE
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _share(value) -> str:
    return NOT_AVAILABLE if value is None else f"{value * 100:.1f}%"


def render_lines(summary: dict, roles, days: int) -> list:
    """Строки текста сводки по ролям — общий вывод команды и блока
    `report`; пустой период — одна строка «шагов за N суток нет»."""
    roles = list(roles)
    known = [role for role in roles if "refusal" not in summary[role]]
    if len(known) == len(roles) and not any(
            summary[role]["steps"] or summary[role]["logs_missing"]
            for role in roles):
        return [f"шагов за {days} суток нет"]
    lines = []
    for role in roles:
        data = summary[role]
        if "refusal" in data:
            lines.append(f"{role}: {data['refusal']}")
            continue
        lines += [
            f"{role}:",
            f"  шагов: {data['steps']} (первых прогонов: {data['first_runs']}, "
            f"Codex: {data['codex_steps']})",
            f"  медиана вызовов: {_number(data['median_calls'])}",
            f"  медиана до первой правки кода: "
            f"{_number(data['median_to_code_edit'])}",
            f"  правка кода не наступила: {data['no_code_edit']}",
            f"  медиана до первой записи: {_number(data['median_to_write'])}",
            f"  запись не наступила: {data['no_write']}",
            f"  доля разведки: {_share(data['share'])}",
            f"  шагов без правки: {data['no_boundary']}",
            f"  правок не распознано: {data['unrecognized_edits']}",
            f"  записей вне рабочей копии: {data['outside_writes']}",
            f"  логов не найдено: {data['logs_missing']}",
            "  топ-10 файлов:",
        ]
        lines += [f"    {count} {path}" for path, count in data["top_reads"]] \
            or ["    нет"]
        lines.append(f"  путь обрезан: {data['truncated_reads']} из "
                     f"{data['reads_total']} чтений")
        lines.append("  топ-10 искомых строк:")
        lines += [f"    {count} {needle}" for needle, count in data["top_searches"]] \
            or ["    нет"]
    return lines


# --------------------------------------------------------------- команда

_USAGE = "explore-stats [--days N] [--role <роль>]"


def _parse_args(rest: list) -> tuple:
    days, roles = DEFAULT_DAYS, list(DEFAULT_ROLES)
    index = 0
    while index < len(rest):
        flag = rest[index]
        if flag not in ("--days", "--role"):
            sys.exit(f"explore-stats: неизвестный аргумент {flag!r}; "
                     f"использование: {_USAGE}")
        if index + 1 >= len(rest):
            sys.exit(f"explore-stats: {flag} без значения; использование: {_USAGE}")
        value = rest[index + 1]
        if flag == "--days":
            try:
                days = int(value)
            except ValueError:
                days = 0
            if days <= 0:
                sys.exit(f"explore-stats: --days ждёт целое число суток больше "
                         f"нуля, получено {value!r}")
        else:
            if value not in BOUNDARY:
                sys.exit(f"explore-stats: неизвестная роль {value!r}; известны: "
                         f"{', '.join(BOUNDARY)}")
            roles = [value]
        index += 2
    return days, roles


def cmd_explore_stats(rest: list) -> None:
    """Команда `explore-stats [--days N] [--role <роль>]`: сводка разведки
    по ролям текстом. Журнал — тремя выборками `store.steps_of_action`
    («agent run started» и действия стоимости), только задачи из `tasks`
    (как у блока `report`); ничего не пишет."""
    days, roles = _parse_args(rest)
    conn = store.db()
    known = {row["id"] for row in store.all_tasks(conn)}
    rows = []
    for action in JOURNAL_ACTIONS:
        rows += [row for row in store.steps_of_action(conn, action)
                 if row["task_id"] in known]
    rows.sort(key=lambda row: row["id"])
    summary = summarize(rows, datetime.now(timezone.utc), days, roles)
    print("\n".join(render_lines(summary, roles, days)))
