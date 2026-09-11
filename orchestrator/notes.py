"""Команда `note`: строка в копилку/бэклог/очередь изолированным коммитом
от `origin/<config.MAIN_BRANCH>`, минуя пин HEAD главной копии (ADR-0013;
tasks/01M1VBEHTDYPK3E4RRFHWYYYW3).

Правка `docs/backlog.md` идёт не в рабочей копии `config.ROOT`, а в
отдельном постоянном git-репозитории (`_work_dir()`, лениво заводится
`git init` при первом обращении) — HEAD/ветка/рабочее дерево главной
копии не трогаются ни при одном исходе (AC-5). Каждая попытка коммита —
свежий `fetch origin/<MAIN_BRANCH>` + пересчёт правки от актуального
содержимого: non-fast-forward отклонённый push повторяется с новым
fetch до `MAX_PUSH_ATTEMPTS` раз (требование 4). Сетевой отказ fetch или
исчерпание повторов push не теряют коммит — параметры операции (не
сырой git-объект: они детерминированно воспроизводимы от текущего
содержимого раздела) удерживаются JSON-файлом в `_pending_dir()`
(требование 5) до следующего вызова `note`/`note --flush` (требование 7).

Пути `_work_dir()`/`_pending_dir()` читают `config.ROOT` заново при
каждом вызове, не кэшируются модульной константой при импорте:
`tests/sandbox.ALL_CONFIG_ATTRS` патчит только перечисленный список
атрибутов `config` по имени, а функция, читающая `config.ROOT` в момент
вызова, корректно видит патч песочницы без правки общего тестового
файла (тот же приём, что применяют модули пакета к `config.TASKS` и
остальным путям).
"""
import argparse
import json
import sys
import time
import uuid
from pathlib import Path

from . import config, gitcmd, store

BACKLOG_REL = "docs/backlog.md"

# Имена разделов — как заголовки docs/backlog.md (требование 1).
SECTION_HEADINGS = {
    "копилка": "## Копилка",
    "бэклог": "## Бэклог",
    "очередь": "## Очередь Оператора",
}

MAX_PUSH_ATTEMPTS = 3

# Идентичность коммитов note — служебное действие оркестратора, не роли и
# не Оператора лично (тот же приём, что fixation.FIXATION_AUTHOR_*):
# коммитит и там, где `git config user.email` не настроен вовсе.
NOTE_AUTHOR_NAME = "Artel Operator Note"
NOTE_AUTHOR_EMAIL = "operator-note@artel.invalid"


class NoteError(Exception):
    """Не используется наружу — валидация отказывает через sys.exit сразу,
    здесь только для внутренней читаемости кода (не поймана нигде)."""


def _work_dir() -> Path:
    return config.ROOT / ".artel" / "notes-work"


def _pending_dir() -> Path:
    return config.ROOT / ".artel" / "notes-pending"


def _pending_paths() -> list[Path]:
    d = _pending_dir()
    if not d.exists():
        return []
    return sorted(d.glob("*.json"))


def pending_notes() -> list[dict]:
    """Удержанные, ещё не отправленные заметки — требование 5/6, AC-7.

    Единственная точка, которую опрашивают приёмочные тесты и
    `doctor.check_pending_notes()`: хранилище (файлы JSON) — деталь
    реализации, наружу отдаётся только список параметров операций.
    """
    result = []
    for path in _pending_paths():
        try:
            result.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return result


def _hold_pending(request: dict) -> None:
    d = _pending_dir()
    d.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time() * 1000):013d}-{uuid.uuid4().hex[:8]}.json"
    (d / name).write_text(json.dumps(request, ensure_ascii=False),
                          encoding="utf-8")


def _row_cells(line: str) -> list[str]:
    s = line.strip()
    inner = s[1:-1] if s.startswith("|") and s.endswith("|") else s
    return [c.strip() for c in inner.split("|")]


def _find_table_header(lines: list[str], heading_idx: int, heading: str) -> int:
    j = heading_idx + 1
    while j < len(lines):
        line = lines[j]
        if line.startswith("## ") and line != heading:
            break
        if line.strip().startswith("|"):
            return j
        j += 1
    sys.exit(f"таблица раздела «{heading}» не найдена в {BACKLOG_REL}")


def _apply_insert(original: str, section_key: str, text: str) -> tuple[str, str]:
    heading = SECTION_HEADINGS[section_key]
    lines = original.split("\n")
    try:
        heading_idx = lines.index(heading)
    except ValueError:
        sys.exit(f"раздел «{heading}» не найден в {BACKLOG_REL}")
    header_idx = _find_table_header(lines, heading_idx, heading)
    header_cells = _row_cells(lines[header_idx])
    given_cells = [c.strip() for c in text.split("|")]
    if len(given_cells) != len(header_cells):
        sys.exit(
            f"строка несёт {len(given_cells)} колонок(-у), раздел "
            f"«{section_key}» ожидает {len(header_cells)} (по шапке таблицы)")
    new_line = "| " + " | ".join(given_cells) + " |"
    sep_idx = header_idx + 1
    lines.insert(sep_idx + 1, new_line)
    return "\n".join(lines), section_key


def _iter_matching_rows(lines: list[str], key: str):
    for section_key, heading in SECTION_HEADINGS.items():
        try:
            heading_idx = lines.index(heading)
        except ValueError:
            continue
        j = heading_idx + 1
        while j < len(lines) and not lines[j].strip().startswith("|"):
            if lines[j].startswith("## ") and lines[j] != heading:
                break
            j += 1
        if j >= len(lines) or not lines[j].strip().startswith("|"):
            continue
        k = j + 2  # пропускает шапку (j) и строку-разделитель (j+1)
        while k < len(lines):
            line = lines[k]
            if line.startswith("## "):
                break
            if line.strip().startswith("|") and key in line:
                yield section_key, k
            k += 1


def _find_unique_row(lines: list[str], key: str) -> tuple[str, int]:
    matches = list(_iter_matching_rows(lines, key))
    if len(matches) != 1:
        sys.exit(
            f"ключ «{key}» найден в {len(matches)} строках — нужна ровно "
            f"одна совпадающая строка, файл не изменён")
    return matches[0]


def _apply_append(original: str, key: str, text: str) -> tuple[str, str]:
    lines = original.split("\n")
    section_key, idx = _find_unique_row(lines, key)
    cells = _row_cells(lines[idx])
    cells[-1] = f"{cells[-1]} {text}".strip()
    lines[idx] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines), section_key


def _apply_drop(original: str, key: str) -> tuple[str, str, str]:
    lines = original.split("\n")
    section_key, idx = _find_unique_row(lines, key)
    observation = " | ".join(_row_cells(lines[idx]))
    del lines[idx]
    return "\n".join(lines), section_key, observation


def _apply_set_state(original: str, key: str, text: str) -> tuple[str, str]:
    lines = original.split("\n")
    section_key, idx = _find_unique_row(lines, key)
    cells = _row_cells(lines[idx])
    cells[-1] = text
    lines[idx] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines), section_key


def _apply_set_priority(original: str, key: str, text: str) -> tuple[str, str]:
    try:
        value = int(text)
    except ValueError:
        value = None
    if value is None or not 1 <= value <= 4:
        sys.exit(f"приоритет «{text}» вне диапазона 1..4")
    lines = original.split("\n")
    section_key, idx = _find_unique_row(lines, key)
    cells = _row_cells(lines[idx])
    cells[0] = text
    lines[idx] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines), section_key


def _build_for(request: dict, original: str) -> tuple[str, str, str | None]:
    kind = request["kind"]
    if kind == "insert":
        new_text, section_key = _apply_insert(
            original, request["section"], request["text"])
        return new_text, section_key, None
    if kind == "append":
        new_text, section_key = _apply_append(
            original, request["key"], request["text"])
        return new_text, section_key, None
    if kind == "drop":
        return _apply_drop(original, request["key"])
    if kind == "set-state":
        new_text, section_key = _apply_set_state(
            original, request["key"], request["text"])
        return new_text, section_key, None
    new_text, section_key = _apply_set_priority(
        original, request["key"], request["text"])
    return new_text, section_key, None


def _commit_message(section_key: str, request: dict,
                    observation: str | None) -> str:
    kind = request["kind"]
    if kind == "drop":
        return f"оператор: {section_key} — снята: {observation[:80]}"
    if kind == "set-state":
        return f"оператор: {section_key} — состояние: {request['text'][:80]}"
    if kind == "set-priority":
        return f"оператор: {section_key} — приоритет: {request['text'][:80]}"
    return f"оператор: {section_key} — {request['text'][:80]}"


def _origin_url() -> str:
    res = gitcmd.git("remote", "get-url", "origin")
    if res is None or res.returncode != 0:
        sys.exit("origin не настроен в репозитории пульта — note недоступна")
    return res.stdout.strip()


def _ensure_work_repo() -> Path:
    work_dir = _work_dir()
    if not (work_dir / ".git").exists():
        gitcmd.git("init", "-q", str(work_dir))
    url = _origin_url()
    existing = gitcmd.in_repo(work_dir, "remote", "get-url", "origin")
    if existing is not None and existing.returncode == 0:
        gitcmd.in_repo(work_dir, "remote", "set-url", "origin", url)
    else:
        gitcmd.in_repo(work_dir, "remote", "add", "origin", url)
    return work_dir


def _read_backlog(work_dir: Path) -> str:
    path = work_dir / BACKLOG_REL
    if not path.exists():
        sys.exit(f"{BACKLOG_REL} не найден в origin/{config.MAIN_BRANCH}")
    return path.read_text(encoding="utf-8")


def _write_backlog(work_dir: Path, text: str) -> None:
    (work_dir / BACKLOG_REL).write_text(text, encoding="utf-8")


def _attempt(request: dict) -> str | None:
    """Полный цикл fetch/правка/commit/push с повтором non-fast-forward
    (требование 4). `None` — сетевой отказ fetch либо исчерпание попыток
    push: вызывающий код обязан удержать `request` (требование 5).

    Валидационные отказы (`sys.exit` внутри `_build_for`) НЕ перехватываются
    здесь и распространяются прямо наружу — они происходят ДО первого push
    и не должны трактоваться как «сетевой отказ, удержать заметку»
    (AC-3/AC-9: коммит вовсе не создаётся, файл origin не меняется).
    """
    work_dir = _ensure_work_repo()
    for _attempt_no in range(1, MAX_PUSH_ATTEMPTS + 1):
        fetch = gitcmd.in_repo(work_dir, "fetch", "-q", "origin",
                               config.MAIN_BRANCH)
        if fetch is None or fetch.returncode != 0:
            return None
        gitcmd.in_repo(work_dir, "checkout", "-q", "-B", config.MAIN_BRANCH,
                       "FETCH_HEAD")
        original = _read_backlog(work_dir)
        new_text, section_key, observation = _build_for(request, original)
        _write_backlog(work_dir, new_text)
        message = _commit_message(section_key, request, observation)
        gitcmd.in_repo(work_dir, "add", BACKLOG_REL)
        commit = gitcmd.in_repo(
            work_dir, "-c", f"user.name={NOTE_AUTHOR_NAME}",
            "-c", f"user.email={NOTE_AUTHOR_EMAIL}",
            "commit", "-q", "-m", message)
        if commit is None or commit.returncode != 0:
            return None
        push = gitcmd.in_repo(work_dir, "push", "-q", "origin",
                              f"HEAD:{config.MAIN_BRANCH}")
        if push is not None and push.returncode == 0:
            sha = gitcmd.head_sha(work_dir)
            store.journal(store.db(), None, "operator",
                         f"заметка: {section_key} {sha}")
            return sha
    return None


def _flush_pending() -> None:
    """Оппортунистический допуш всех удержанных заметок (требование 7,
    AC-8) — вызывается в начале КАЖДОГО `cmd_note`, не только `--flush`.

    Отказ одной заметки (сеть всё ещё недоступна, либо устаревшая
    заметка больше не проходит собственную валидацию) не должен рушить
    текущий вызов `note` — файл просто остаётся висеть.
    """
    for path in _pending_paths():
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            sha = _attempt(request)
        except (SystemExit, OSError, json.JSONDecodeError):
            continue
        if sha is not None:
            path.unlink(missing_ok=True)


def _run(request: dict) -> None:
    sha = _attempt(request)
    if sha is None:
        _hold_pending(request)
        sys.exit(
            "не удалось отправить заметку в origin — коммит удержан "
            "(.artel/notes-pending/), повтори note позже либо note --flush")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="note", add_help=False)
    parser.add_argument("section", nargs="?", choices=list(SECTION_HEADINGS))
    parser.add_argument("--text")
    parser.add_argument("--append")
    parser.add_argument("--drop")
    parser.add_argument("--set-state")
    parser.add_argument("--set-priority")
    parser.add_argument("--flush", action="store_true")
    # Принимается, поведения не несёт сверх приёма (SPEC «Не входит»).
    parser.add_argument("--task")
    return parser.parse_args(argv)


def cmd_note(argv: list[str]) -> None:
    args = _parse_args(argv)
    _flush_pending()
    if args.append is not None:
        if not args.text:
            sys.exit("--append требует --text")
        _run({"kind": "append", "key": args.append, "text": args.text})
    elif args.drop is not None:
        _run({"kind": "drop", "key": args.drop})
    elif args.set_state is not None:
        if not args.text:
            sys.exit("--set-state требует --text")
        _run({"kind": "set-state", "key": args.set_state, "text": args.text})
    elif args.set_priority is not None:
        if not args.text:
            sys.exit("--set-priority требует --text")
        _run({"kind": "set-priority", "key": args.set_priority,
             "text": args.text})
    elif args.section is not None:
        if not args.text:
            sys.exit("--text обязателен")
        _run({"kind": "insert", "section": args.section, "text": args.text})
    elif args.flush:
        return
    else:
        sys.exit("укажи раздел с --text, --append/--drop/--set-state/"
                 "--set-priority <ключ>, либо --flush")
