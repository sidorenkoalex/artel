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

Окно тишины (01M2B6JS2BZNBW9WSHT1RPFXTE): помимо сетевого отказа, валидная
запись удерживается тем же путём (`_hold_pending`, тот же формат JSON и
каталог), когда открыто «окно тишины» — живой держатель мьютекса
merge-окна либо задача в состоянии из `config.NOTE_SILENCE_WINDOW_STATES`
(`_silence_window_reason`). Валидация (`_build_for`, внутри
`_fetch_and_build`) происходит ДО проверки окна независимо от его
состояния — отказ валидации `sys.exit`'ит раньше любого решения о push
или удержании. `note --flush`/`note --now` обходят окно явно (решение
Оператора), оппортунистический допуш в начале `cmd_note` — нет.

Пути `_work_dir()`/`_pending_dir()` читают `config.ROOT` заново при
каждом вызове, не кэшируются модульной константой при импорте:
`tests/sandbox.ALL_CONFIG_ATTRS` патчит только перечисленный список
атрибутов `config` по имени, а функция, читающая `config.ROOT` в момент
вызова, корректно видит патч песочницы без правки общего тестового
файла (тот же приём, что применяют модули пакета к `config.TASKS` и
остальным путям).

Команда `doc-commit` (01M2XMCG167615YS9EZD9TYJWV): та же механика — тот
же рабочий репозиторий, тот же цикл fetch/пересборка/commit/push с
повторами (`_run`), то же удержание в `_pending_dir()` при сетевом
отказе и в окне тишины, тот же `_flush_pending` — но содержимое целого
файла вместо строки бэклога. Запись — тот же JSON с полем `kind`
(`DOC_COMMIT_KIND`) и полями `path`/`content`/`message`: она
самодостаточна, флаш воспроизводит коммит от актуального
`origin/<MAIN_BRANCH>`, не обращаясь к исходному `--from`-файлу (тот мог
исчезнуть). Ветвление по виду записи — в `_fetch_and_build`
(`_build_doc_commit` вместо `_read_backlog`+`_build_for`) и в
`_commit_and_push` (`_target_rel`, `_commit_message`); пути `note` не
меняются (требование 9). Допустимые пути — `docs/**` кроме
`BACKLOG_REL` (для него `note`) и конфигурация Оператора
`DOC_COMMIT_CONFIG_PATHS` (требование 3); сверка базы (требование 5) —
blob-sha пути в `origin/<MAIN_BRANCH>` против `HEAD:<путь>` главной копии
(пина), чтобы правка поверх устаревшей версии не затёрла чужую.
"""
import argparse
import json
import sys
import time
import uuid
from pathlib import Path, PurePosixPath

from . import config, gitcmd, merge_lock, runner, store

BACKLOG_REL = "docs/backlog.md"

DOC_COMMIT_KIND = "doc-commit"

# Конфигурация Оператора, которой `doc-commit` даёт канал мимо главной
# копии (требование 3 SPEC; решение Оператора 19.09). Всё прочее вне
# `docs/**` — код и артефакты, они меняются задачами.
DOC_COMMIT_CONFIG_PATHS = ("roles.yaml", "gates.yaml", "targets.yaml")

DOC_COMMIT_FOREIGN_REFUSAL = ("код и артефакты меняются задачами, не "
                              "doc-commit")
DOC_COMMIT_BASE_REFUSAL = ("файл изменился в origin после пина — сначала "
                           "pin-update")

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


def _silence_window_reason() -> str | None:
    """Открытое «окно тишины» (требование 1, AC-1): живой держатель
    мьютекса `merge_locks` (тот же признак живости, что
    `merge_lock._holder_is_dead`) ЛИБО хоть одна задача (`store.all_tasks`)
    в состоянии из `config.NOTE_SILENCE_WINDOW_STATES` — условие ИЛИ,
    любой из двух триггеров срабатывает независимо от другого (живой
    держатель без единой задачи в этих состояниях — уже открытое окно).
    `None` — окна нет, push идёт как сегодня (AC-5)."""
    conn = store.db()
    lock_row = store.merge_lock_row(conn)
    if lock_row is not None and not merge_lock._holder_is_dead(lock_row):
        return (f"держатель merge-окна жив (сессия {lock_row['session_id']}, "
               f"задача {lock_row['task_id']})")
    for task in store.all_tasks(conn):
        if task["state"] in config.NOTE_SILENCE_WINDOW_STATES:
            return f"задача {task['id']} в состоянии {task['state']}"
    return None


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
    if kind == DOC_COMMIT_KIND:
        # Ровно `docs: <путь> — <message>` / `config: <путь> — <message>`
        # (требование 6, AC-7) — без усечения: основание правки Оператора
        # читается из истории целиком.
        rel = request["path"]
        return f"{_doc_commit_prefix(rel)}: {rel} — {request['message']}"
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


def _doc_commit_path_refusal(rel: str) -> str | None:
    """Текст отказа для пути `doc-commit`, либо `None` — путь допустим
    (требование 3, AC-2/AC-3). Допустимы `docs/**` кроме `BACKLOG_REL` и
    ровно `DOC_COMMIT_CONFIG_PATHS`; путь читается как относительный
    POSIX-путь внутри репозитория — абсолютный, с `..` или голый каталог
    `docs` не проходят раньше сверки со списком."""
    p = PurePosixPath(rel)
    if not rel or p.is_absolute() or ".." in p.parts:
        return (f"{rel!r}: путь должен быть относительным путём внутри "
                f"репозитория без «..»")
    normalized = str(p)
    if normalized == BACKLOG_REL:
        return f"{BACKLOG_REL} меняется командой note, не doc-commit"
    if p.parts[0] == "docs" and len(p.parts) >= 2:
        return None
    if normalized in DOC_COMMIT_CONFIG_PATHS:
        return None
    return f"{normalized}: {DOC_COMMIT_FOREIGN_REFUSAL}"


def _doc_commit_prefix(rel: str) -> str:
    """`docs` для `docs/**`, `config` для конфигурации Оператора
    (требование 6). Зовётся только для путей, прошедших
    `_doc_commit_path_refusal`."""
    return "docs" if PurePosixPath(rel).parts[0] == "docs" else "config"


def _blob_sha(repo: Path, revision_path: str) -> str | None:
    """sha объекта `<ревизия>:<путь>` в `repo`, `None` — пути в этой
    ревизии нет (или git не ответил: сверка тогда отказывает на
    расхождении, не пропускает молча)."""
    res = gitcmd.in_repo(repo, "rev-parse", "--verify", "--quiet",
                         revision_path)
    if res is None or res.returncode != 0:
        return None
    return res.stdout.strip() or None


def _build_doc_commit(work_dir: Path,
                      request: dict) -> tuple[str, str, str | None]:
    """Валидация записи `doc-commit` от свежего `FETCH_HEAD` (требование
    5, AC-4): blob-sha пути в `origin/<MAIN_BRANCH>` должен совпадать с
    blob-sha того же пути в HEAD главной копии — иначе правка сделана
    поверх устаревшей версии и затёрла бы чужую. Оба отсутствуют — новый
    файл, допустим. Сравниваются sha объектов, не декодированный текст:
    точная сверка без вопросов кодировки и переводов строк.

    Отдельный отказ «содержимое уже совпадает»: иначе `git commit` не
    нашёл бы изменений, `MAX_PUSH_ATTEMPTS` повторов провалились бы, и
    запись повисла бы в `_pending_dir()` без внятной причины.

    Возвращает тройку той же формы, что `_build_for` (`(текст, ключ,
    наблюдение)`): ключом служит сам путь — он идёт в сообщение коммита.
    """
    rel = request["path"]
    origin_sha = _blob_sha(work_dir, f"FETCH_HEAD:{rel}")
    pin_sha = _blob_sha(config.ROOT, f"HEAD:{rel}")
    if origin_sha != pin_sha:
        sys.exit(f"{rel}: {DOC_COMMIT_BASE_REFUSAL}")
    content = request["content"]
    target = work_dir / rel
    if target.is_file() and target.read_bytes() == content.encode("utf-8"):
        sys.exit(f"{rel}: содержимое уже совпадает с "
                 f"origin/{config.MAIN_BRANCH} — коммитить нечего")
    return content, rel, None


def _target_rel(request: dict) -> str:
    """Путь в репозитории, который меняет запись: свой у `doc-commit`,
    `BACKLOG_REL` у всех видов `note`."""
    if request["kind"] == DOC_COMMIT_KIND:
        return request["path"]
    return BACKLOG_REL


def _write_doc(work_dir: Path, rel: str, text: str) -> None:
    """Байтами, не `write_text`: содержимое `--from` должно попасть в
    origin без пересчёта переводов строк; каталог нового пути
    (`docs/research/…`) заводится по дороге."""
    target = work_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))


def _fetch_and_build(work_dir: Path,
                     request: dict) -> tuple[str, str, str | None] | None:
    """Fetch+checkout свежего `origin/<MAIN_BRANCH>` и валидация+построение
    правки (`_build_for`) — общая точка для немедленного push (`_attempt`,
    `_run`) и для решения «push или удержание» при окне тишины (требование
    2, AC-4): отказ валидации (`sys.exit` внутри `_build_for`) происходит
    здесь, ДО commit/push и ДО проверки окна тишины, и распространяется
    наружу нетронутым — коммит не создаётся, файл в `_pending_dir()` не
    появляется, независимо от состояния окна.

    `None` — сетевой отказ fetch: вызывающий код обязан трактовать это как
    удержание (требование 5), окно тишины здесь не участвует вовсе.
    """
    fetch = gitcmd.in_repo(work_dir, "fetch", "-q", "origin",
                           config.MAIN_BRANCH)
    if fetch is None or fetch.returncode != 0:
        return None
    gitcmd.in_repo(work_dir, "checkout", "-q", "-B", config.MAIN_BRANCH,
                   "FETCH_HEAD")
    if request["kind"] == DOC_COMMIT_KIND:
        return _build_doc_commit(work_dir, request)
    original = _read_backlog(work_dir)
    return _build_for(request, original)


def _commit_and_push(work_dir: Path, request: dict, new_text: str,
                     section_key: str, observation: str | None) -> str | None:
    """Коммит+push уже построенной правки. `None` — коммит или push
    отказали (non-fast-forward и подобное) — вызывающий код решает:
    повторить с новым `_fetch_and_build` либо удержать (требование 4/5).

    Запись `doc-commit` пишет свой путь (`_target_rel`) и журнал пульта не
    трогает (требование 7 её SPEC); пути `note` — как прежде."""
    rel = _target_rel(request)
    is_doc_commit = request["kind"] == DOC_COMMIT_KIND
    if is_doc_commit:
        _write_doc(work_dir, rel, new_text)
    else:
        _write_backlog(work_dir, new_text)
    message = _commit_message(section_key, request, observation)
    gitcmd.in_repo(work_dir, "add", rel)
    commit = gitcmd.in_repo(
        work_dir, "-c", f"user.name={NOTE_AUTHOR_NAME}",
        "-c", f"user.email={NOTE_AUTHOR_EMAIL}",
        "commit", "-q", "-m", message)
    if commit is None or commit.returncode != 0:
        return None
    push = gitcmd.in_repo(work_dir, "push", "-q", "origin",
                          f"HEAD:{config.MAIN_BRANCH}")
    if push is None or push.returncode != 0:
        return None
    sha = gitcmd.head_sha(work_dir)
    if not is_doc_commit:
        store.journal(store.db(), None, "operator",
                     f"заметка: {section_key} {sha}")
    return sha


def _attempt(request: dict) -> str | None:
    """Полный цикл fetch/правка/commit/push с повтором non-fast-forward
    (требование 4). `None` — сетевой отказ fetch либо исчерпание попыток
    push: вызывающий код обязан удержать `request` (требование 5).

    Валидационные отказы (`sys.exit` внутри `_build_for`, через
    `_fetch_and_build`) НЕ перехватываются здесь и распространяются прямо
    наружу — они происходят ДО первого push и не должны трактоваться как
    «сетевой отказ, удержать заметку» (AC-3/AC-9: коммит вовсе не
    создаётся, файл origin не меняется).

    Используется только `_flush_pending` (флаш уже решил отправлять —
    без понятия окна тишины здесь, требование 7/AC-6/AC-8 решают на
    уровне вызывающего кода, не здесь).
    """
    work_dir = _ensure_work_repo()
    for _attempt_no in range(1, MAX_PUSH_ATTEMPTS + 1):
        prepared = _fetch_and_build(work_dir, request)
        if prepared is None:
            return None
        new_text, section_key, observation = prepared
        sha = _commit_and_push(work_dir, request, new_text, section_key,
                               observation)
        if sha is not None:
            return sha
    return None


def _flush_pending() -> None:
    """Безусловный допуш всех удержанных заметок, независимо от окна
    тишины (требование 5/7, AC-6): и оппортунистический вызов в начале
    `cmd_note` (когда окно уже проверено закрытым вызывающим кодом), и
    явный `note --flush` (обходит окно решением Оператора, AC-6) зовут
    эту же функцию — разница только в том, вызывает ли её `cmd_note`
    вообще (см. `_silence_window_reason` там).

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


def _run(request: dict, bypass_window: bool = False) -> str | None:
    """Путь одной новой записи. `bypass_window=True` — `--now` (требование
    6/AC-7): та же валидация, но окно тишины не проверяется вовсе, запись
    никогда не удерживается им.

    Иначе (требования 1-3, AC-1..AC-3): каждая итерация повтора
    non-fast-forward сперва валидирует и строит правку (`_fetch_and_build`
    — отказ валидации распространяется наружу, не доходя до проверки окна,
    AC-4), затем проверяет окно тишины — открыто, удерживает `request`
    (не построенный текст: тот же формат, что и сетевое удержание,
    требование 3/AC-9) и печатает причину, ничего не коммитя и не пушя.

    Возвращает sha коммита в origin (его называет вывод `doc-commit`,
    требование 7 её SPEC) либо `None` при удержании окном; `note`
    результат не использует. Тексты удержания и финального отказа
    названы по виду записи (`заметка`/`note` против `doc-commit`), у
    `note` — буквально прежние.
    """
    if request["kind"] == DOC_COMMIT_KIND:
        held, accusative, command = "doc-commit удержан", "doc-commit", "doc-commit"
    else:
        held, accusative, command = "заметка удержана", "заметку", "note"
    work_dir = _ensure_work_repo()
    for _attempt_no in range(1, MAX_PUSH_ATTEMPTS + 1):
        prepared = _fetch_and_build(work_dir, request)
        if prepared is None:
            break
        new_text, section_key, observation = prepared
        if not bypass_window:
            reason = _silence_window_reason()
            if reason is not None:
                _hold_pending(request)
                print(f"{held}: {reason}; отправка — {command} --flush "
                      f"либо автоматически следующим {command} вне окна")
                return None
        sha = _commit_and_push(work_dir, request, new_text, section_key,
                               observation)
        if sha is not None:
            return sha
    _hold_pending(request)
    sys.exit(
        f"не удалось отправить {accusative} в origin — коммит удержан "
        f"(.artel/notes-pending/), повтори {command} позже либо {command} "
        f"--flush")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="note", add_help=False)
    parser.add_argument("section", nargs="?", choices=list(SECTION_HEADINGS))
    parser.add_argument("--text")
    parser.add_argument("--append")
    parser.add_argument("--drop")
    parser.add_argument("--set-state")
    parser.add_argument("--set-priority")
    # Обход окна тишины (требование 6, AC-7) — тот же раздел, что и
    # позиционный `section`, но под явным флагом: запись пишется и
    # пушится немедленно, не удерживаясь.
    parser.add_argument("--now", choices=list(SECTION_HEADINGS))
    parser.add_argument("--flush", action="store_true")
    # Принимается, поведения не несёт сверх приёма (SPEC «Не входит»).
    parser.add_argument("--task")
    return parser.parse_args(argv)


def cmd_note(argv: list[str]) -> None:
    args = _parse_args(argv)
    # Оппортунистический допуш уважает окно тишины (требование 7, AC-8):
    # при открытом окне удержанные записи остаются нетронутыми, вне окна —
    # допушиваются, как и сегодня. `--flush` форсирует его безусловно
    # (короткое замыкание `or` — окно вовсе не проверяется, требование
    # 5/AC-6, не смешивается с оппортунистическим путём).
    if args.flush or _silence_window_reason() is None:
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
    elif args.now is not None:
        if not args.text:
            sys.exit("--text обязателен")
        _run({"kind": "insert", "section": args.now, "text": args.text},
            bypass_window=True)
    elif args.section is not None:
        if not args.text:
            sys.exit("--text обязателен")
        _run({"kind": "insert", "section": args.section, "text": args.text})
    elif args.flush:
        return
    else:
        sys.exit("укажи раздел с --text, --append/--drop/--set-state/"
                 "--set-priority <ключ>, --now <раздел> --text, либо "
                 "--flush")


def _parse_doc_commit_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="doc-commit", add_help=False)
    parser.add_argument("path", nargs="?")
    parser.add_argument("--from", dest="source")
    parser.add_argument("--message")
    parser.add_argument("--flush", action="store_true")
    return parser.parse_args(argv)


def _read_source_file(source: str | None) -> str:
    """Содержимое `--from <файл>` — любой путь на диске (требование 1).
    Байтами со строгим UTF-8: файл не в UTF-8 не сериализуется в JSON
    удержанной записи без потерь, поэтому отказ здесь, до git."""
    if not source:
        sys.exit("--from <файл> обязателен: откуда брать содержимое")
    path = Path(source)
    if not path.is_file():
        sys.exit(f"--from: файл {source} не найден")
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        sys.exit(f"--from: файл {source} не в UTF-8")


def cmd_doc_commit(argv: list[str]) -> None:
    """`doc-commit <путь> --from <файл> --message "<текст>"` /
    `doc-commit --flush` (01M2XMCG167615YS9EZD9TYJWV).

    Рубеж окружения роли — ПЕРВЫМ действием, до разбора аргументов и до
    любого обращения к git (требование 4, AC-9): тот же
    `runner.in_role_environment()`, что у `answer`/`zones-extend`
    (`orchestrator/answer.py`). Далее отказы валидации в порядке путь →
    `--message` → `--from`, все — `sys.exit` до `_run`: ни коммита, ни
    удержанной записи (AC-2/AC-3/AC-8). Оппортунистический допуш и
    `--flush` — зеркально `cmd_note`: один каталог удержанных записей
    на оба вида (требование 8, AC-6).
    """
    if runner.in_role_environment():
        sys.exit("doc-commit отказана — вызов из окружения роли (role_env): "
                 "документы и конфигурация Оператора коммитятся Оператором")
    args = _parse_doc_commit_args(argv)
    if args.flush or _silence_window_reason() is None:
        _flush_pending()
    if args.path is None:
        if args.flush:
            return
        sys.exit("укажи <путь-в-репозитории> --from <файл> --message "
                 "\"<основание>\", либо --flush")
    refusal = _doc_commit_path_refusal(args.path)
    if refusal is not None:
        sys.exit(refusal)
    rel = str(PurePosixPath(args.path))
    if not args.message or not args.message.strip():
        sys.exit("--message обязателен: основание правки — часть сообщения "
                 "коммита")
    content = _read_source_file(args.source)
    sha = _run({"kind": DOC_COMMIT_KIND, "path": rel, "content": content,
                "message": args.message.strip()})
    if sha is not None:
        print(f"{rel} закоммичен в origin/{config.MAIN_BRANCH}: {sha}")
