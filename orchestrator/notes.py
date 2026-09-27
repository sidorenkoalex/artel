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

Единый формат строки бэклога (01M3HST4SGX0SPKAGNHVY7DWHM): текст `--text`
разбирается ТЕМ ЖЕ `_row_cells`, которым читается шапка раздела, — форма
с обрамляющими чертами («| a | b |», ровно так строка выглядит в
документе) и без них дают одну и ту же строку (требования 1-2; до этой
задачи `_apply_insert` делил текст своим `text.split("|")`, и обрамлённая
форма отказывала по числу колонок — три отказа `note` 27.09). Формы
ячеек приводятся к одной, выбранной по большинству строк документа:
приоритет — цифра без буквы (159 строк против 43 на вершине b21f01e6),
дата — «ДД.ММ» (134 против 7). Колонки находятся по ЗАГОЛОВКУ шапки
раздела («П», «Дата»), не по номеру: колонка «Дата» есть у «Копилки» и
отсутствует у «Бэклога»/«Очереди Оператора» (требования 3-6). Дописка
состояния отделяется от прежнего текста ячейки разделителем с датой
(требование 7) — прежде новый текст склеивался с прежним одним пробелом,
и колонка «Состояние» превращалась в слипшийся абзац без границ дописок.

`note --apply <файл> --message "<основание>"` (требования 9-12) — третий
вид записи (`APPLY_KIND`) рядом с `note` и `doc-commit`: заменяет
`docs/backlog.md` содержимым файла-заготовки целиком, тем же
изолированным путём и с теми же сверками, что `doc-commit` (база, окно
тишины, изменение файла в origin), плюс сверка формы самой заготовки
(`_apply_shape_refusal`) и запись журнала с перечнем удалённых строк.

Гейт полного набора `tests/` перед отправкой правки конфигурации
Оператора (требования 13-16, `_suite_gate_refusal`): правка `roles.yaml`
27.09 (a6da0abe) сделала главную ветку красной, потребовался откат
(d910c523) и встали ветки волны. Прогон идёт по дереву рабочего
репозитория, в котором правка УЖЕ записана, — поэтому гейт стоит в
`_commit_and_push` после записи файла и до `git commit`. Путь `docs/**`
прогона не заводит вовсе (требование 16), осознанный обход —
`--accept-red "<основание>"` с записью журнала (требование 15).
"""
import argparse
import json
import re
import sys
import time
import uuid
from datetime import date
from pathlib import Path, PurePosixPath

from . import acceptance, config, gitcmd, merge_lock, runner, store

BACKLOG_REL = "docs/backlog.md"

DOC_COMMIT_KIND = "doc-commit"

# Вид записи `note --apply` (требование 9): замена `docs/backlog.md`
# содержимым файла-заготовки целиком.
APPLY_KIND = "apply"

# Конфигурация Оператора, которой `doc-commit` даёт канал мимо главной
# копии (требование 3 SPEC; решение Оператора 19.09). Всё прочее вне
# `docs/**` — код и артефакты, они меняются задачами.
# `models.yaml` — каталог моделей (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,
# требование 4): та же конфигурация Оператора, что roles.yaml рядом, и
# тот же канал правки мимо главной копии (префикс коммита `config:` —
# `_doc_commit_prefix` отдаёт его всему, что вне `docs/`).
DOC_COMMIT_CONFIG_PATHS = ("roles.yaml", "gates.yaml", "targets.yaml",
                           "models.yaml")

DOC_COMMIT_FOREIGN_REFUSAL = ("код и артефакты меняются задачами, не "
                              "doc-commit")
DOC_COMMIT_BASE_REFUSAL = ("файл изменился в origin после пина — сначала "
                           "pin-update")

# Именованное действие журнала об осознанном обходе гейта полного набора
# (требование 15): коммит проходит при необеспеченном наборе, но обход
# обязан остаться видимым Оператору вместе с путём и основанием.
ACCEPT_RED_JOURNAL_ACTION = ("doc-commit конфигурации с необеспеченным "
                             "набором tests/")

# Имена разделов — как заголовки docs/backlog.md (требование 1).
SECTION_HEADINGS = {
    "копилка": "## Копилка",
    "бэклог": "## Бэклог",
    "очередь": "## Очередь Оператора",
}

# Заголовки колонок, форма которых нормализуется (требования 3, 5, 6).
# Колонка ищется по заголовку шапки раздела, а не по номеру: «Дата» есть у
# «Копилки» и отсутствует у «Бэклога»/«Очереди Оператора», а раздел без
# колонки нормализации соответствующей формы просто не получает.
PRIORITY_HEADER = "П"
DATE_HEADER = "Дата"

# Приоритет: цифра 1-4, допускается ведущая «П»/«п» и произвольные пробелы
# (требование 3). В файл пишется цифра — форма большинства строк документа.
_PRIORITY_RE = re.compile(r"^[Пп]?([1-4])$")
# Пример допустимой формы в тексте отказа (требование 4): без него
# Оператор узнаёт только то, что его значение не подошло.
PRIORITY_FORM_EXAMPLE = "цифра 1..4 («2»), допускается ведущая «П» («П2»)"

# Дата с годом: «22.09.2026» -> «22.09» (требование 6). Сами числа дня и
# месяца не переписываются — ни дополнения нулями, ни сверки календаря:
# нормализуется ФОРМА, а не содержимое ячейки.
_DATE_WITH_YEAR_RE = re.compile(r"^(\d\d?)\.(\d\d?)\.\d\d+$")

# Пустая ячейка состояния (требование 7): пробелы либо прочерк — к такой
# ячейке дописка идёт без ведущего разделителя.
STATE_EMPTY_CELLS = ("", "—")

MAX_PUSH_ATTEMPTS = 3

# Идентичность коммитов note — служебное действие оркестратора, не роли и
# не Оператора лично (тот же приём, что fixation.FIXATION_AUTHOR_*):
# коммитит и там, где `git config user.email` не настроен вовсе.
NOTE_AUTHOR_NAME = "Artel Operator Note"
NOTE_AUTHOR_EMAIL = "operator-note@artel.invalid"


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


def _table_header_index(lines: list[str], heading_idx: int,
                        heading: str) -> int | None:
    """Индекс строки-шапки таблицы раздела; `None` — раздел кончился
    (следующий `## `) или текст кончился раньше таблицы."""
    j = heading_idx + 1
    while j < len(lines):
        line = lines[j]
        if line.startswith("## ") and line != heading:
            return None
        if line.strip().startswith("|"):
            return j
        j += 1
    return None


def _find_table_header(lines: list[str], heading_idx: int, heading: str) -> int:
    idx = _table_header_index(lines, heading_idx, heading)
    if idx is None:
        sys.exit(f"таблица раздела «{heading}» не найдена в {BACKLOG_REL}")
    return idx


def _table_header_cells(text: str, heading: str) -> list[str] | None:
    """Ячейки шапки таблицы раздела `heading` в `text`; `None` — раздела
    нет вовсе либо у него нет таблицы.

    Немой вариант `_find_table_header` для мест, где отсутствие раздела —
    предмет проверки, а не отказ на месте: сверка формы заготовки
    `--apply` (требование 11) и поиск колонки приоритета по шапке
    (требование 5). Разбор строки — тот же `_row_cells`, один на модуль.
    """
    lines = text.split("\n")
    try:
        heading_idx = lines.index(heading)
    except ValueError:
        return None
    idx = _table_header_index(lines, heading_idx, heading)
    return _row_cells(lines[idx]) if idx is not None else None


def _today_stamp() -> str:
    """Текущая дата пульта в нормализованной форме «ДД.ММ» (требование 7).

    Местная, не UTC (в отличие от `store.now` — там машинная метка
    времени журнала): `docs/backlog.md` читает и пишет Оператор, и все
    даты в нём — его календарные.
    """
    return date.today().strftime("%d.%m")


def _normalized_priority(cell: str) -> str | None:
    """Ячейка приоритета в нормализованной форме — цифра без буквы
    (требование 3); `None` — форма не распознана (отказывает вызывающий
    код, требование 4). Пробелы снимаются и внутри: «П 2» — та же форма,
    что «П2»."""
    match = _PRIORITY_RE.match("".join(cell.split()))
    return match.group(1) if match else None


def _priority_or_refuse(cell: str) -> str:
    """Нормализованный приоритет либо именованный отказ с примером
    допустимой формы (требование 4): файл не меняется, коммит не
    создаётся — отказ происходит до записи."""
    value = _normalized_priority(cell)
    if value is None:
        sys.exit(f"приоритет «{cell}» не распознан — ожидается "
                 f"{PRIORITY_FORM_EXAMPLE}; файл не изменён")
    return value


def _normalized_date(cell: str) -> str:
    """Ячейка даты в нормализованной форме «ДД.ММ» (требование 6): год
    снимается; уже краткая форма и содержимое, датой не являющееся ни в
    одной из двух форм, остаются как есть — отказ требование 6 для даты
    не предусматривает (в отличие от приоритета)."""
    match = _DATE_WITH_YEAR_RE.match(cell)
    return f"{match.group(1)}.{match.group(2)}" if match else cell


def _normalized_row(header_cells: list[str], cells: list[str]) -> list[str]:
    """Ячейки строки с нормализованными приоритетом и датой (требования
    3-6). Колонки находятся по заголовку шапки раздела: раздела без
    колонки «П» нормализация приоритета не касается, без «Дата» — даты."""
    result = list(cells)
    for i, head in enumerate(header_cells[:len(result)]):
        if head == PRIORITY_HEADER:
            result[i] = _priority_or_refuse(result[i])
        elif head == DATE_HEADER:
            result[i] = _normalized_date(result[i])
    return result


def _apply_insert(original: str, section_key: str, text: str) -> tuple[str, str]:
    heading = SECTION_HEADINGS[section_key]
    lines = original.split("\n")
    try:
        heading_idx = lines.index(heading)
    except ValueError:
        sys.exit(f"раздел «{heading}» не найден в {BACKLOG_REL}")
    header_idx = _find_table_header(lines, heading_idx, heading)
    header_cells = _row_cells(lines[header_idx])
    # Тем же разбором, что и шапка раздела (требование 1): обрамляющие
    # черты снимаются только когда текст И начинается, И заканчивается
    # чертой, поэтому обе формы дают одни и те же ячейки. Число колонок
    # сверяется ПОСЛЕ снятия обрамления (требование 2) — иначе «| 1 | 2 |
    # 3 |» проходило бы как пять ячеек с двумя пустыми.
    given_cells = _row_cells(text)
    if len(given_cells) != len(header_cells):
        sys.exit(
            f"строка несёт {len(given_cells)} колонок(-у), раздел "
            f"«{section_key}» ожидает {len(header_cells)} (по шапке таблицы)")
    new_line = "| " + " | ".join(
        _normalized_row(header_cells, given_cells)) + " |"
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


def _appended_state(previous: str, text: str) -> str:
    """Ячейка состояния после дописки (требование 7): `<прежний текст> —
    <ДД.ММ>: <новый текст>`; прежняя ячейка пуста (пробелы либо прочерк) —
    без ведущего разделителя.

    Прежний текст сохраняется целиком: до этой задачи новый склеивался с
    прежним одним пробелом, и колонка «Состояние» ряда строк превратилась
    в слипшийся абзац, в котором границы дописок уже не читаются.
    """
    stamped = f"{_today_stamp()}: {text}"
    old = previous.strip()
    if old in STATE_EMPTY_CELLS:
        return stamped
    return f"{old} — {stamped}"


def _apply_append(original: str, key: str, text: str) -> tuple[str, str]:
    lines = original.split("\n")
    section_key, idx = _find_unique_row(lines, key)
    cells = _row_cells(lines[idx])
    cells[-1] = _appended_state(cells[-1], text)
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
    """Второй путь нормализации приоритета (требование 5): в файл пишется
    цифра, какая бы из двух допустимых форм ни пришла в `--text`; диапазон
    1..4 тот же, что был. Колонка — с заголовком «П» по шапке раздела
    найденной строки (во всех трёх разделах документа она первая, но
    номер колонки — не правило, а совпадение)."""
    value = _priority_or_refuse(text)
    lines = original.split("\n")
    section_key, idx = _find_unique_row(lines, key)
    header_cells = _table_header_cells(original, SECTION_HEADINGS[section_key])
    if header_cells is None or PRIORITY_HEADER not in header_cells:
        sys.exit(f"раздел «{section_key}» не несёт колонки "
                 f"«{PRIORITY_HEADER}» — приоритет менять негде")
    cells = _row_cells(lines[idx])
    cells[header_cells.index(PRIORITY_HEADER)] = value
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
    if kind == APPLY_KIND:
        # Основание `--message` целиком, без усечения (требование 9, AC-8) —
        # тот же довод, что у `doc-commit`: основание замены документа
        # целиком читается из истории, а не угадывается по обрезку.
        return (f"оператор: {BACKLOG_REL} заменён заготовкой — "
                f"{request['message']}")
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


APPLY_SHAPE_REFUSAL = "заготовка --apply негодна"


def _apply_shape_refusal(draft: str, original: str) -> str | None:
    """Текст отказа по форме заготовки `--apply`, либо `None` — форма
    годна (требование 11): в заготовке присутствуют все три раздела,
    которые знает `note`, у каждого есть таблица, и число колонок шапки
    каждого раздела совпадает с числом колонок того же раздела в текущем
    `origin/<MAIN_BRANCH>`.

    Раздела нет в САМОМ origin (документ в origin сам не по форме) —
    сверять число колонок не с чем, и отказ по этому поводу не выносится:
    предмет проверки — заготовка, а не состояние origin.
    """
    for _section_key, heading in SECTION_HEADINGS.items():
        draft_cells = _table_header_cells(draft, heading)
        if draft_cells is None:
            return (f"{APPLY_SHAPE_REFUSAL}: раздела «{heading}» нет либо у "
                    f"него нет таблицы — коммита нет")
        origin_cells = _table_header_cells(original, heading)
        if origin_cells is not None and len(draft_cells) != len(origin_cells):
            return (f"{APPLY_SHAPE_REFUSAL}: шапка раздела «{heading}» несёт "
                    f"{len(draft_cells)} колонок(-у), в "
                    f"origin/{config.MAIN_BRANCH} их {len(origin_cells)} — "
                    f"коммита нет")
    return None


def _dropped_rows(original: str, draft: str) -> list[str]:
    """Строки таблиц, которые были в прежнем содержимом документа и в
    заготовке отсутствуют — каждая усечённая до 80 знаков тем же приёмом,
    что сообщение коммита `note --drop` (требование 12)."""
    kept = set(draft.split("\n"))
    return [" | ".join(_row_cells(line))[:80]
            for line in original.split("\n")
            if line.strip().startswith("|") and line not in kept]


def _apply_journal_detail(rows: list[str]) -> str:
    """Колонка detail записи журнала об успешном `--apply` (требование
    12): число удалённых строк и сами строки."""
    return "; ".join([f"удалено строк: {len(rows)}", *rows])


def _build_apply(work_dir: Path, request: dict,
                 original: str) -> tuple[str, str, str | None]:
    """Валидация и построение правки `note --apply` (требования 9-12).

    Сверка базы — та же, что у `_build_doc_commit` (требование 10):
    blob-sha `docs/backlog.md` в свежем `origin/<MAIN_BRANCH>` против
    blob-sha того же пути в HEAD главной копии. Разошлись — документ в
    origin ушёл от базы, заготовка легла бы поверх чужой правки и стёрла
    бы её целиком (замена файла, не правка одной строки), поэтому отказ.

    Отказ «заготовка совпадает с origin» — тот же класс, что у
    `_build_doc_commit`: иначе `git commit` не нашёл бы изменений,
    `MAX_PUSH_ATTEMPTS` повторов провалились бы, и запись повисла бы в
    `_pending_dir()` без внятной причины.

    Третий элемент возврата (у `note` — снятая строка, у `doc-commit` —
    `None`) несёт здесь готовую колонку detail записи журнала: перечень
    удалённых строк считается ЗДЕСЬ, пока прежнее содержимое под рукой, —
    `_commit_and_push` его уже не увидит.
    """
    origin_sha = _blob_sha(work_dir, f"FETCH_HEAD:{BACKLOG_REL}")
    pin_sha = _blob_sha(config.ROOT, f"HEAD:{BACKLOG_REL}")
    if origin_sha != pin_sha:
        sys.exit(f"{BACKLOG_REL}: {DOC_COMMIT_BASE_REFUSAL}")
    draft = request["content"]
    if draft == original:
        sys.exit(f"{BACKLOG_REL}: заготовка совпадает с содержимым в "
                 f"origin/{config.MAIN_BRANCH} — коммитить нечего")
    refusal = _apply_shape_refusal(draft, original)
    if refusal is not None:
        sys.exit(refusal)
    return draft, BACKLOG_REL, _apply_journal_detail(
        _dropped_rows(original, draft))


def _suite_gate_refusal(work_dir: Path, request: dict) -> str | None:
    """Текст отказа гейта полного набора `tests/` перед отправкой правки
    конфигурации Оператора, либо `None` — гейт неприменим или пройден
    (требования 13-16).

    Гейт стоит на путях `DOC_COMMIT_CONFIG_PATHS` и только на них: путь
    `docs/**` прогона не заводит вовсе (требование 16) — документ не
    исполняется и красным набор сделать не может. Прогон идёт по дереву
    рабочего репозитория, в котором правка УЖЕ записана вызывающим кодом
    (требование 13): именно применённая правка и есть предмет проверки —
    прогон до записи проверял бы не её.

    Набор не удалось запустить вовсе (`tests/` в дереве нет, интерпретатор
    или pytest отсутствуют) — `acceptance.run_full_suite` отдаёт «не
    зелено», и гейт закрывается тем же отказом, что при красном наборе
    (требование 14): гейт закрыт по умолчанию, молчаливого пропуска нет.

    `--accept-red "<основание>"` (требование 15) снимает гейт целиком, не
    гоняя набор: решение Оператор уже принял, а минуты прогона ради
    заранее принятого исхода — чистая потеря. Сам обход пишет запись
    журнала (`_journal_commit`), а не молчит.
    """
    if request["kind"] != DOC_COMMIT_KIND:
        return None
    if request["path"] not in DOC_COMMIT_CONFIG_PATHS:
        return None
    if request.get("accept_red"):
        return None
    green, output = acceptance.run_full_suite(work_dir)
    if green:
        return None
    return (f"{request['path']}: полный набор tests/ не обеспечен на дереве "
            f"с применённой правкой — коммита нет; "
            f"{acceptance.run_digest(output)}; осознанный обход — "
            f"doc-commit <путь> --from <файл> --message \"<основание>\" "
            f"--accept-red \"<почему красный набор принят>\"")


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
    if request["kind"] == APPLY_KIND:
        return _build_apply(work_dir, request, original)
    return _build_for(request, original)


def _commit_and_push(work_dir: Path, request: dict, new_text: str,
                     section_key: str, observation: str | None) -> str | None:
    """Коммит+push уже построенной правки. `None` — коммит или push
    отказали (non-fast-forward и подобное) — вызывающий код решает:
    повторить с новым `_fetch_and_build` либо удержать (требование 4/5).

    Запись `doc-commit` пишет свой путь (`_target_rel`) и журнал пульта не
    трогает (требование 7 её SPEC); пути `note` — как прежде.

    Гейт полного набора `tests/` (требования 13-14 SPEC
    01M3HST4SGX0SPKAGNHVY7DWHM) стоит здесь: ПОСЛЕ записи правки в дерево
    рабочего репозитория и ДО `git commit` — «дерево с уже применённой
    правкой» требования 13 существует ровно в этом промежутке. Отсюда же
    получается верное поведение на обоих путях: при открытом окне тишины
    решение об удержании принимается раньше (`_run`), прогона не будет
    вовсе, и набор гоняется тогда, когда отправка действительно идёт
    (`--flush`). Цена — прогон на каждой попытке повтора
    non-fast-forward; отказ гейта выходит `sys.exit` с первой попытки,
    поэтому три красных прогона подряд невозможны."""
    rel = _target_rel(request)
    is_doc_commit = request["kind"] == DOC_COMMIT_KIND
    if is_doc_commit:
        _write_doc(work_dir, rel, new_text)
    else:
        _write_backlog(work_dir, new_text)
    gate = _suite_gate_refusal(work_dir, request)
    if gate is not None:
        sys.exit(gate)
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
    _journal_commit(request, section_key, observation, rel, sha)
    return sha


def _journal_commit(request: dict, section_key: str, observation: str | None,
                    rel: str, sha: str) -> None:
    """Запись журнала пульта по итогам успешного push — своя у каждого вида
    записи.

    `doc-commit` журнал не пишет (требование 7 её SPEC) — кроме
    осознанного обхода гейта набора: он обязан остаться видимым Оператору
    вместе с путём и основанием (требование 15 SPEC
    01M3HST4SGX0SPKAGNHVY7DWHM). `--apply` пишет перечень удалённых строк
    (требование 12), пути `note` — прежнюю строку, буквально.
    """
    conn = store.db()
    kind = request["kind"]
    if kind == DOC_COMMIT_KIND:
        reason = request.get("accept_red")
        if reason:
            store.journal(conn, None, "operator", ACCEPT_RED_JOURNAL_ACTION,
                          f"{rel}: {reason}")
        return
    if kind == APPLY_KIND:
        store.journal(conn, None, "operator",
                      f"{BACKLOG_REL} заменён заготовкой {sha}",
                      observation or "")
        return
    store.journal(conn, None, "operator", f"заметка: {section_key} {sha}")


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
    elif request["kind"] == APPLY_KIND:
        held, accusative, command = ("заготовка бэклога удержана",
                                     "заготовку бэклога", "note")
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
    # То же действие под именем из ТЗ (требование 8): `--state` и
    # `--append` — одна операция, не две, и оба имени дают один результат.
    parser.add_argument("--state")
    parser.add_argument("--drop")
    parser.add_argument("--set-state")
    parser.add_argument("--set-priority")
    # Замена документа заготовкой целиком (требование 9): `--message`
    # обязателен, его текст входит в сообщение коммита.
    parser.add_argument("--apply")
    parser.add_argument("--message")
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
    # `--state` — второе имя `--append` (требование 8): обе формы ведут в
    # один путь, а текст отказа называет то имя, которым позвали.
    append_flag = "--append" if args.append is not None else "--state"
    append_key = args.append if args.append is not None else args.state
    if args.apply is not None:
        if not args.message or not args.message.strip():
            sys.exit('--apply требует --message "<основание>": основание '
                     'замены документа — часть сообщения коммита')
        sha = _run({"kind": APPLY_KIND,
                    "content": _read_source_file(args.apply, "--apply"),
                    "message": args.message.strip()})
        if sha is not None:
            print(f"{BACKLOG_REL} заменён заготовкой в "
                  f"origin/{config.MAIN_BRANCH}: {sha}")
    elif append_key is not None:
        if not args.text:
            sys.exit(f"{append_flag} требует --text")
        _run({"kind": "append", "key": append_key, "text": args.text})
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
        sys.exit("укажи раздел с --text, --append/--state/--drop/"
                 "--set-state/--set-priority <ключ>, --now <раздел> --text, "
                 "--apply <файл> --message \"<основание>\", либо --flush")


def _parse_doc_commit_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="doc-commit", add_help=False)
    parser.add_argument("path", nargs="?")
    parser.add_argument("--from", dest="source")
    parser.add_argument("--message")
    # Осознанный обход гейта полного набора `tests/` (требование 15) —
    # идиома `orchestrator/artel.py::_accept_red_arg` (`approve
    # --accept-red`): основание обязательно, флаг без него отказывает.
    # `nargs="?"` с пустым `const` — чтобы голый флаг дошёл до ИМЕНОВАННОГО
    # отказа ниже, а не до кода выхода 2 самого argparse.
    parser.add_argument("--accept-red", dest="accept_red", nargs="?", const="")
    parser.add_argument("--flush", action="store_true")
    return parser.parse_args(argv)


def _read_source_file(source: str | None, flag: str = "--from") -> str:
    """Содержимое файла-источника — любой путь на диске (требование 1
    SPEC `doc-commit`). Байтами со строгим UTF-8: файл не в UTF-8 не
    сериализуется в JSON удержанной записи без потерь, поэтому отказ
    здесь, до git.

    `flag` — имя флага в текстах отказов: у `doc-commit` это `--from`, у
    `note --apply` — сам `--apply` (требование 9), и отказ обязан называть
    тот флаг, которым Оператор позвал команду, а не соседний."""
    if not source:
        sys.exit(f"{flag} <файл> обязателен: откуда брать содержимое")
    path = Path(source)
    if not path.is_file():
        sys.exit(f"{flag}: файл {source} не найден")
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        sys.exit(f"{flag}: файл {source} не в UTF-8")


def cmd_doc_commit(argv: list[str]) -> None:
    """`doc-commit <путь> --from <файл> --message "<текст>"` /
    `doc-commit --flush` (01M2XMCG167615YS9EZD9TYJWV).

    Рубеж окружения роли — ПЕРВЫМ действием, до разбора аргументов и до
    любого обращения к git (требование 4, AC-9): тот же
    `runner.in_role_environment()`, что у `answer`/`zones-extend`
    (`orchestrator/answer.py`). Далее отказы валидации в порядке путь →
    `--message` → `--accept-red` → `--from`, все — `sys.exit` до `_run`: ни
    коммита, ни удержанной записи (AC-2/AC-3/AC-8). Оппортунистический
    допуш и `--flush` — зеркально `cmd_note`: один каталог удержанных
    записей на оба вида (требование 8, AC-6).

    `--accept-red "<основание>"` (требование 15 SPEC
    01M3HST4SGX0SPKAGNHVY7DWHM) кладётся в запись отдельным полем: она
    самодостаточна, и обход доживает до отправки на `--flush`, когда
    гейт полного набора действительно срабатывает. На путях `docs/**`
    гейта нет вовсе (требование 16), так что флаг там принимается, но
    обходить ему нечего.
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
    if args.accept_red is not None and not args.accept_red.strip():
        sys.exit('--accept-red требует основание: doc-commit <путь> --from '
                 '<файл> --message "<основание>" --accept-red "<почему '
                 'красный набор tests/ принят>"')
    content = _read_source_file(args.source)
    request = {"kind": DOC_COMMIT_KIND, "path": rel, "content": content,
               "message": args.message.strip()}
    if args.accept_red is not None:
        request["accept_red"] = args.accept_red.strip()
    sha = _run(request)
    if sha is not None:
        print(f"{rel} закоммичен в origin/{config.MAIN_BRANCH}: {sha}")
