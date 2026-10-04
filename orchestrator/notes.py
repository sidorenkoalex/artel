"""Команда `note`: строка в копилку/бэклог/очередь изолированным коммитом
от `origin/<config.MAIN_BRANCH>`, минуя пин HEAD главной копии (ADR-0013;
tasks/01M1VBEHTDYPK3E4RRFHWYYYW3).

Правка `docs/backlog.md` идёт не в рабочей копии `config.ROOT`, а в клоне
артели `.artel/projects/artel/repo` (`_work_dir()`, ADR-0021 п.1; SPEC
01M42PENCS26D0656X8FR7DFA7, требование 5 — до него отдельный
`.artel/notes-work`, упразднён) — HEAD/ветка/рабочее дерево и git главной
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
blob-sha пути в свежем `origin/<MAIN_BRANCH>` против того же пути в
`origin/<MAIN_BRANCH>` клона, каким клон знал его ДО fetch этой команды
(`_known_origin_main`; до SPEC 01M42PENCS26D0656X8FR7DFA7 — `HEAD:<путь>`
главной копии), чтобы правка поверх устаревшей версии не затёрла чужую.

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
Сверка базы у `--apply` СВОЯ, не пиновая (`_foreign_base_refusal`,
требование 10): `docs/backlog.md` правит сама `note`, коммитя прямо в
origin мимо главной копии, поэтому пин отстаёт от origin уже после
первой же заметки — пиновая сверка `doc-commit` закрывала бы `--apply` в
штатном состоянии пульта. Отказ выносится на ЧУЖУЮ правку документа
после базы и на расхождение origin с blob'ом, от которого построена
заготовка (`base_blob` записи — «изменился между чтением заготовки и
коммитом»).

Гейт полного набора `tests/` перед отправкой правки конфигурации
Оператора (требования 13-16, `_suite_gate_refusal`): правка `roles.yaml`
27.09 (a6da0abe) сделала главную ветку красной, потребовался откат
(d910c523) и встали ветки волны. Прогон идёт по дереву рабочего
репозитория, в котором правка УЖЕ записана, — поэтому гейт стоит в
`_commit_and_push` после записи файла и до `git commit`. Путь `docs/**`
прогона не заводит вовсе (требование 16), осознанный обход —
`--accept-red "<основание>"` с записью журнала (требование 15).

Чистота общего рабочего репозитория — предусловие всей механики: отказ
гейта выходит `sys.exit`'ом ПОСЛЕ записи правки в дерево, поэтому он
снимает её (`_restore_tree`), а каждая сборка приводит дерево к
`FETCH_HEAD` принудительно и с проверкой кода возврата
(`_fetch_and_build`). Сверка «содержимое уже совпадает» сравнивает
blob-sha, а не файл дерева (`_content_already_in_origin`). Без этих трёх
вещей грязный файл читался бы следующей командой как содержимое origin, и
правка конфигурации после отказа гейта не проходила бы уже никогда
(R1-F1 ревью итерации 1).
"""
import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import date
from pathlib import Path, PurePosixPath

from . import acceptance, config, gitcmd, merge_lock, runner, store, workspace

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
# `model_sets.yaml` — наборы моделей и допуск пар (SPEC
# 01M3YCHP14179R32SFJVKQB32G, требование 2): его же пишет `admit` через
# `doc_commit_content`.
DOC_COMMIT_CONFIG_PATHS = ("roles.yaml", "gates.yaml", "targets.yaml",
                           "models.yaml", config.MODEL_SETS_REL)

DOC_COMMIT_FOREIGN_REFUSAL = ("код и артефакты меняются задачами, не "
                              "doc-commit")
DOC_COMMIT_ROLE_REFUSAL = ("doc-commit отказана — вызов из окружения роли "
                           "(role_env): документы и конфигурация Оператора "
                           "коммитятся Оператором")
DOC_COMMIT_BASE_REFUSAL = ("файл изменился в origin после пина — сначала "
                           "pin-update")

# База удержанной записи `doc-commit` (SPEC 01M3Y75X6K2ZMD85971TCWV41E,
# требование 1): blob-sha пути в HEAD главной копии в момент вызова, `None`
# — «файла не было». Отсутствие самого поля — запись, удержанная до этой
# задачи (требование 4). Пиновая сверка удержанной записи не защищает:
# 02.10 пин и origin совпали после `pin-update`, и флаш стёр 21 чужую
# строку (28b09389) — сверять надо с той версией, на которой собрано
# содержимое.
HELD_BASE_KEY = "held_base"
DOC_COMMIT_STALE_REFUSAL = "файл изменился в origin после сборки записи"
NO_BASE_WARNING = ("база не сохранена (запись удержана до сверки по базе) — "
                   "сверка origin против пина")
ABSENT_BLOB_TEXT = "файла не было"

# Длина выдержки содержимого в строке `note --pending` (требование 5).
PENDING_EXCERPT_LEN = 80

# Именованные отказы сверки базы `note --apply` (требование 10). Пиновый
# текст `DOC_COMMIT_BASE_REFUSAL` здесь не годится: «сначала pin-update»
# для бэклога не лечение — origin уходит от пина при каждой заметке
# (`_foreign_base_refusal`).
APPLY_FOREIGN_BASE_REFUSAL = (
    "документ изменился в origin ЧУЖОЙ правкой после базы главной копии — "
    "пересобери заготовку от свежего origin/main")
APPLY_STALE_BASE_REFUSAL = (
    "документ изменился в origin после чтения заготовки — пересобери "
    "заготовку от свежего origin/main")
APPLY_UNKNOWN_BASE_REFUSAL = (
    "историю документа в origin относительно базы главной копии прочитать не "
    "удалось — сверка базы закрыта по умолчанию, коммита нет")

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

# Префикс сообщения коммита, которым пульт правит `docs/backlog.md`
# (`_commit_message` ниже строит им все виды записи `note`). По нему
# сверка базы `--apply` отличает свою правку документа от чужой
# (`_foreign_backlog_commits`, требование 10). Идентичности коммита
# (`NOTE_AUTHOR_EMAIL`) для этого мало: `GIT_AUTHOR_EMAIL`/
# `GIT_COMMITTER_EMAIL` окружения перебивают `-c user.email` самой
# команды, и коммит `note` уносит адрес того окружения, из которого пульт
# запущен, — на живом пульте адреса Оператора, не этой константы.
NOTE_COMMIT_SUBJECT_PREFIX = "оператор: "


def _work_dir() -> Path:
    """Клон артели — рабочий репозиторий `note`/`doc-commit` (SPEC
    01M42PENCS26D0656X8FR7DFA7, требование 5)."""
    return workspace.repo(config.DEFAULT_TARGET)


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


def _hold_pending(request: dict, known: str = "") -> None:
    """Удержать запись файлом в `_pending_dir()`. Запись `doc-commit`
    получает базу (`HELD_BASE_KEY`) здесь, а не при сборке запроса:
    немедленная отправка сверяется с базой без поля (требование 3), и поле
    базы в ней перевело бы её на сверку удержанной записи. База — blob
    пути в `origin/<MAIN_BRANCH>` клона артели, каким клон знал его до
    fetch этого вызова (`known`, SPEC 01M42PENCS26D0656X8FR7DFA7, требование
    5, AC-10), не HEAD главной копии. Уже несущая поле запись (повторное
    удержание) базу не переписывает."""
    if request["kind"] == DOC_COMMIT_KIND and HELD_BASE_KEY not in request:
        request = {**request, HELD_BASE_KEY: _known_blob(
            _work_dir(), known, request["path"])}
    d = _pending_dir()
    d.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time() * 1000):013d}-{uuid.uuid4().hex[:8]}.json"
    (d / name).write_text(json.dumps(request, ensure_ascii=False),
                          encoding="utf-8")


def _held_at(record_id: str) -> str:
    """Время удержания из имени файла записи (миллисекунды эпохи — так их
    пишет `_hold_pending`), местное: список читает Оператор."""
    stamp = record_id.split("-", 1)[0]
    if not stamp.isdigit():
        return "время неизвестно"
    return time.strftime("%Y-%m-%d %H:%M:%S",
                         time.localtime(int(stamp) / 1000))


def _pending_line(record_id: str, request: dict) -> str:
    """Строка `note --pending` (требование 5): id, вид, путь (у
    `doc-commit`/`--apply`) либо раздел/ключ (у заметки), время и первые
    `PENDING_EXCERPT_LEN` знаков содержимого — в одну строку, иначе
    перевод строки содержимого разорвал бы запись на несколько строк
    вывода."""
    kind = request.get("kind", "?")
    if kind == DOC_COMMIT_KIND:
        where = request.get("path", "?")
    elif kind == APPLY_KIND:
        where = BACKLOG_REL
    elif "section" in request:
        where = request["section"]
    else:
        where = f"ключ {request.get('key', '?')}"
    body = request.get("content", request.get("text", ""))
    excerpt = str(body)[:PENDING_EXCERPT_LEN].replace("\n", " ")
    return f"{record_id}  {kind}  {where}  {_held_at(record_id)}  {excerpt}"


def _print_pending() -> None:
    paths = _pending_paths()
    if not paths:
        print("удержанных записей нет")
        return
    for path in paths:
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{path.stem}  запись не читается: {exc}")
            continue
        print(_pending_line(path.stem, request))


def _drop_pending(record_id: str) -> None:
    """Снять одну удержанную запись по id файла (требование 6). Id
    сверяется с перечнем файлов каталога, а не склеивается в путь: иначе
    «../…» снимал бы файл вне `_pending_dir()`."""
    found = [p for p in _pending_paths() if p.stem == record_id]
    if not found:
        sys.exit(f"удержанной записи {record_id} нет — перечень: "
                 f"note --pending")
    path = found[0]
    try:
        line = _pending_line(record_id, json.loads(
            path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        line = f"{record_id}  запись не читается"
    path.unlink()
    store.journal(store.db(), None, "operator",
                  f"удержанная запись снята: {record_id}", line)
    print(f"удержанная запись снята: {line}")


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
    """Сообщение коммита по виду записи. Все виды `note` (включая
    `--apply`) начинаются `NOTE_COMMIT_SUBJECT_PREFIX` — по нему сверка
    базы `--apply` узнаёт правку документа, сделанную самим пультом, и
    константа взята здесь же, чтобы два места не разошлись."""
    kind = request["kind"]
    if kind == DOC_COMMIT_KIND:
        # Ровно `docs: <путь> — <message>` / `config: <путь> — <message>`
        # (требование 6, AC-7) — без усечения: основание правки Оператора
        # читается из истории целиком.
        rel = request["path"]
        return f"{_doc_commit_prefix(rel)}: {rel} — {request['message']}"
    prefix = NOTE_COMMIT_SUBJECT_PREFIX
    if kind == APPLY_KIND:
        # Основание `--message` целиком, без усечения (требование 9, AC-8) —
        # тот же довод, что у `doc-commit`: основание замены документа
        # целиком читается из истории, а не угадывается по обрезку.
        return (f"{prefix}{BACKLOG_REL} заменён заготовкой — "
                f"{request['message']}")
    if kind == "drop":
        return f"{prefix}{section_key} — снята: {observation[:80]}"
    if kind == "set-state":
        return f"{prefix}{section_key} — состояние: {request['text'][:80]}"
    if kind == "set-priority":
        return f"{prefix}{section_key} — приоритет: {request['text'][:80]}"
    return f"{prefix}{section_key} — {request['text'][:80]}"


def _ensure_work_repo() -> Path:
    """Клон артели есть (заводится, если нет); не заводится — отказ без
    отката на главную копию."""
    work_dir, error = workspace.ensure_clone(config.DEFAULT_TARGET)
    if error is not None:
        sys.exit(f"{error} — note недоступна")
    return work_dir


def _known_origin_main(work_dir: Path) -> str:
    """sha `origin/<MAIN_BRANCH>` клона, каким он известен ДО fetch этой
    команды — база сверки «правка поверх устаревшей версии» (до SPEC
    01M42PENCS26D0656X8FR7DFA7 — HEAD главной копии). Пустая строка —
    ссылки нет."""
    res = gitcmd.in_repo(work_dir, "rev-parse", "--verify", "--quiet",
                         f"refs/remotes/origin/{config.MAIN_BRANCH}")
    if res is None or res.returncode != 0:
        return ""
    return res.stdout.strip()


def _known_blob(work_dir: Path, known: str, rel: str) -> str | None:
    """blob-sha `rel` в коммите `known`; `None` — пути там нет либо базы
    нет вовсе."""
    return _blob_sha(work_dir, f"{known}:{rel}") if known else None


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


def _content_blob_sha(work_dir: Path, content: str) -> str | None:
    """blob-sha содержимого — счётом самого git (`hash-object --stdin`) по
    байтам: сравнение с blob'ом пути в origin обязано считаться тем же
    алгоритмом, каким репозиторий хранит объекты.

    `None` — git не ответил: вызывающий код трактует это как «не
    совпадает» и идёт коммитить (пустой коммит git сам не сделает), а не
    как молчаливое совпадение.
    """
    res = gitcmd.carpentry(work_dir, ["hash-object", "--stdin"],
                           dict(os.environ),
                           input=content.encode("utf-8"), text=False)
    if res is None or res.returncode != 0:
        return None
    return res.stdout.decode("utf-8", "replace").strip() or None


def _content_already_in_origin(work_dir: Path, rel: str,
                               content: str) -> bool:
    """Содержимое уже лежит в свежем `origin/<MAIN_BRANCH>` по пути `rel` —
    сравнением blob-sha `FETCH_HEAD:<rel>` с blob-sha самого содержимого.

    Не файлом рабочего дерева, как было до итерации 2 ревью: общий рабочий
    репозиторий `.artel/notes-work` мог остаться грязным от прошлого
    отказа, и тогда сравнение с файлом отвечало бы про чужое содержимое
    вместо содержимого origin — правка конфигурации после отказа гейта
    набора не проходила уже никогда (R1-F1).
    """
    origin_sha = _blob_sha(work_dir, f"FETCH_HEAD:{rel}")
    if origin_sha is None:
        return False
    return _content_blob_sha(work_dir, content) == origin_sha


def _restore_tree(work_dir: Path, rel: str) -> None:
    """Снять записанную правку пути `rel` в общем рабочем репозитории:
    вернуть дерево к состоянию текущего коммита (`checkout -- <rel>`), а
    путь, которого в коммите нет вовсе, удалить (`clean -f -- <rel>`).

    Зовётся на единственном пути, который выходит `sys.exit`'ом ПОСЛЕ
    записи правки в дерево, — отказе гейта полного набора. Без этого общий
    репозиторий оставался грязным (R1-F1 ревью итерации 1), и следующая
    команда либо читала грязный файл как содержимое origin, либо спотыкалась
    на `checkout` поверх локальных изменений.
    """
    gitcmd.in_repo(work_dir, "checkout", "-q", "--", rel)
    gitcmd.in_repo(work_dir, "clean", "-q", "-f", "--", rel)


def _build_doc_commit(work_dir: Path, request: dict,
                      known: str = "") -> tuple[str, str, str | None]:
    """Валидация записи `doc-commit` от свежего `FETCH_HEAD` (требование
    5, AC-4): blob-sha пути в `origin/<MAIN_BRANCH>` должен совпадать с
    blob-sha того же пути в `origin/<MAIN_BRANCH>` клона до fetch этой
    команды (`known`; до SPEC 01M42PENCS26D0656X8FR7DFA7 — HEAD главной
    копии) — иначе правка сделана
    поверх устаревшей версии и затёрла бы чужую. Оба отсутствуют — новый
    файл, допустим. Сравниваются sha объектов, не декодированный текст:
    точная сверка без вопросов кодировки и переводов строк.

    Отдельный отказ «содержимое уже совпадает»: иначе `git commit` не
    нашёл бы изменений, `MAX_PUSH_ATTEMPTS` повторов провалились бы, и
    запись повисла бы в `_pending_dir()` без внятной причины. Сверка — по
    blob'у origin (`_content_already_in_origin`), не по файлу рабочего
    дерева: тот мог остаться грязным от прошлого отказа гейта набора.

    Возвращает тройку той же формы, что `_build_for` (`(текст, ключ,
    наблюдение)`): ключом служит сам путь — он идёт в сообщение коммита.

    Удержанная запись с базой (`HELD_BASE_KEY`, SPEC
    01M3Y75X6K2ZMD85971TCWV41E, требование 2) сверяет origin не с пином, а
    с базой, на которой собрано содержимое: пин к флашу мог уйти вперёд
    вместе с чужой правкой (сценарий 02.10), и пиновая сверка тогда
    проходит, затирая её.
    """
    rel = request["path"]
    origin_sha = _blob_sha(work_dir, f"FETCH_HEAD:{rel}")
    if HELD_BASE_KEY in request:
        base_sha = request[HELD_BASE_KEY]
        if origin_sha != base_sha:
            sys.exit(f"{rel}: {DOC_COMMIT_STALE_REFUSAL} (база "
                     f"{base_sha or ABSENT_BLOB_TEXT}, origin "
                     f"{origin_sha or 'файла нет'}) — собери заново от "
                     f"origin")
    else:
        pin_sha = _known_blob(work_dir, known, rel)
        if origin_sha != pin_sha:
            sys.exit(f"{rel}: {DOC_COMMIT_BASE_REFUSAL}")
    content = request["content"]
    if _content_already_in_origin(work_dir, rel, content):
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


def _foreign_backlog_commits(work_dir: Path,
                             pin_commit: str) -> list[str] | None:
    """Коммиты origin, тронувшие `BACKLOG_REL` после базы главной копии и
    сделанные НЕ самим пультом.

    Свой коммит узнаётся по сообщению (`NOTE_COMMIT_SUBJECT_PREFIX`, тем
    же, которым его строит `_commit_message`) ЛИБО по идентичности
    (`NOTE_AUTHOR_EMAIL`). Двух признаков не из перестраховки: адрес автора
    задаётся `-c user.email`, а его перебивает `GIT_AUTHOR_EMAIL` окружения
    пульта, так что на живом пульте коммит `note` несёт адрес Оператора —
    одного адреса не хватило бы; сообщение же строит сам пульт всегда.

    `None` — git не ответил (коммита базы нет в истории origin, `log`
    отказал): вызывающий код закрывает сверку, а не считает список пустым.
    """
    res = gitcmd.in_repo(work_dir, "log", "--format=%H%x00%ae%x00%s",
                         f"{pin_commit}..FETCH_HEAD", "--", BACKLOG_REL)
    if res is None or res.returncode != 0:
        return None
    foreign = []
    for line in res.stdout.split("\n"):
        parts = line.split("\0")
        if len(parts) != 3 or not parts[0].strip():
            continue
        sha, email, subject = (p.strip() for p in parts)
        own = (subject.startswith(NOTE_COMMIT_SUBJECT_PREFIX)
               or email == NOTE_AUTHOR_EMAIL)
        if not own:
            foreign.append(sha)
    return foreign


def _foreign_base_refusal(work_dir: Path, origin_sha: str | None,
                          known: str = "") -> str | None:
    """Текст отказа сверки базы `--apply` при ПЕРВОМ построении правки,
    либо `None` — база годна (требование 10).

    Расхождение blob'а `docs/backlog.md` в свежем origin с blob'ом того же
    пути в HEAD главной копии (пине) само по себе отказом НЕ является — в
    отличие от `doc-commit` (`_build_doc_commit`). Документ правит сама
    `note`, коммитя прямо в origin мимо главной копии: пин отстаёт от
    origin уже после первой же заметки, и пиновая сверка закрывала бы
    `--apply` в штатном состоянии пульта (замер 27.09: пин b21f01e6 нёс
    blob 464e4fae, origin — 68e33dae, расхождение внесено коммитом самой
    `note`; R1-F2 ревью итерации 1). «Сначала pin-update» тут и не
    лечение: следующая заметка снова уводит origin от пина.

    Отказ выносится, когда документ после базы тронула ЧУЖАЯ правка —
    коммит не пультовой идентичности: заготовка готовилась от другой версии
    документа и стёрла бы такую правку ЦЕЛИКОМ, а не одной строкой. Git не
    ответил — тоже отказ: сверка закрыта по умолчанию.

    База — `origin/<MAIN_BRANCH>` клона артели до fetch этой команды
    (`known`, SPEC 01M42PENCS26D0656X8FR7DFA7, требование 5), не HEAD
    главной копии.
    """
    if origin_sha is not None and origin_sha == _known_blob(
            work_dir, known, BACKLOG_REL):
        return None
    pin_commit = known
    foreign = (_foreign_backlog_commits(work_dir, pin_commit)
               if pin_commit else None)
    if foreign is None:
        return APPLY_UNKNOWN_BASE_REFUSAL
    if foreign:
        return f"{APPLY_FOREIGN_BASE_REFUSAL} (коммит {foreign[0][:12]})"
    return None


def _build_apply(work_dir: Path, request: dict,
                 original: str, known: str = "") -> tuple[str, str, str | None]:
    """Валидация и построение правки `note --apply` (требования 9-12).

    Сверка базы — двумя шагами (требование 10: «если `docs/backlog.md` в
    `origin/main` изменился между чтением заготовки и коммитом»):

    1. Первое построение — `_foreign_base_refusal`: чужая правка документа
       после базы главной копии закрывает команду, своя (коммит `note`) —
       нет.
    2. Всякое последующее — сверка с `base_blob`, blob'ом origin,
       запомненным в записи при первом построении: это и есть «между
       чтением заготовки и коммитом» для повтора non-fast-forward и для
       записи, удержанной окном тишины и отправляемой флашем. Разошлись —
       документ в origin уехал, заготовка стёрла бы уехавшее целиком.

    `base_blob` кладётся в саму запись (`request`), поэтому переживает
    удержание: `_hold_pending` пишет тот же словарь в JSON.

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
    recorded = request.get("base_blob")
    if recorded is None:
        refusal = _foreign_base_refusal(work_dir, origin_sha, known)
        if refusal is not None:
            sys.exit(f"{BACKLOG_REL}: {refusal}")
        request["base_blob"] = origin_sha
    elif recorded != origin_sha:
        sys.exit(f"{BACKLOG_REL}: {APPLY_STALE_BASE_REFUSAL}")
    draft = request["content"]
    if _content_already_in_origin(work_dir, BACKLOG_REL, draft):
        sys.exit(f"{BACKLOG_REL}: заготовка совпадает с содержимым в "
                 f"origin/{config.MAIN_BRANCH} — коммитить нечего")
    refusal = _apply_shape_refusal(draft, original)
    if refusal is not None:
        sys.exit(refusal)
    return draft, BACKLOG_REL, _apply_journal_detail(
        _dropped_rows(original, draft))


def _config_path_request(request: dict) -> bool:
    """Запись правит файл конфигурации Оператора. Только на таких путях
    стоит гейт полного набора (требования 13, 16) — и только на них
    осознанному обходу есть что записывать журналом (требование 15):
    на пути `docs/**` гейта нет вовсе, и запись об обходе была бы ложной
    (R1-F4 ревью итерации 1)."""
    return (request["kind"] == DOC_COMMIT_KIND
            and request["path"] in DOC_COMMIT_CONFIG_PATHS)


def _suite_gate_applies(request: dict) -> bool:
    """Отправка этой записи заведёт прогон полного набора: путь
    конфигурации, обхода `--accept-red` в записи нет.

    Знать это ЗАРАНЕЕ нужно флашу (`_flush_pending`): оппортунистический
    допуш не вправе увести произвольную команду `note` в многоминутный
    прогон (R1-F3 ревью итерации 1).
    """
    return _config_path_request(request) and not request.get("accept_red")


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
    if not _suite_gate_applies(request):
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


def _fetch_and_build(work_dir: Path, request: dict,
                     known: str = "") -> tuple[str, str, str | None] | None:
    """Fetch+checkout свежего `origin/<MAIN_BRANCH>` и валидация+построение
    правки (`_build_for`) — общая точка для немедленного push (`_attempt`,
    `_run`) и для решения «push или удержание» при окне тишины (требование
    2, AC-4): отказ валидации (`sys.exit` внутри `_build_for`) происходит
    здесь, ДО commit/push и ДО проверки окна тишины, и распространяется
    наружу нетронутым — коммит не создаётся, файл в `_pending_dir()` не
    появляется, независимо от состояния окна.

    `None` — сетевой отказ fetch ЛИБО дерево рабочего репозитория не
    удалось привести к `FETCH_HEAD`: вызывающий код обязан трактовать это
    как удержание (требование 5), окно тишины здесь не участвует вовсе.

    Checkout — принудительный (`-f`) и с проверкой кода возврата: без
    первого он спотыкался о локальные изменения, оставшиеся от прошлого
    отказа, а без второй сборка шла на дереве ПРОШЛОГО коммита молча, и
    каждая заметка отказывала «не удалось отправить» (R1-F1 ревью итерации
    1, второй сценарий). Путь записи дочищается от невыслеженного мусора
    (`clean`): файла, которого в `FETCH_HEAD` нет, принудительный checkout
    не снимает, а сборка прочла бы его как содержимое origin.
    """
    fetch = gitcmd.in_repo(work_dir, "fetch", "-q", "origin",
                           config.MAIN_BRANCH)
    if fetch is None or fetch.returncode != 0:
        return None
    checkout = gitcmd.in_repo(work_dir, "checkout", "-q", "-f", "-B",
                              config.MAIN_BRANCH, "FETCH_HEAD")
    if checkout is None or checkout.returncode != 0:
        detail = (checkout.stderr or "").strip() if checkout else "нет ответа"
        print(f"рабочий репозиторий {work_dir} не приведён к "
              f"origin/{config.MAIN_BRANCH}: {detail}")
        return None
    gitcmd.in_repo(work_dir, "clean", "-q", "-f", "--", _target_rel(request))
    if request["kind"] == DOC_COMMIT_KIND:
        return _build_doc_commit(work_dir, request, known)
    original = _read_backlog(work_dir)
    if request["kind"] == APPLY_KIND:
        return _build_apply(work_dir, request, original, known)
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
    поэтому три красных прогона подряд невозможны. Перед выходом записанная
    правка СНИМАЕТСЯ с дерева (`_restore_tree`): это единственное место,
    которое выходит из команды после записи файла, и грязный общий
    репозиторий ломал бы и повтор той же команды, и любую следующую
    заметку (R1-F1 ревью итерации 1)."""
    rel = _target_rel(request)
    is_doc_commit = request["kind"] == DOC_COMMIT_KIND
    if is_doc_commit:
        _write_doc(work_dir, rel, new_text)
    else:
        _write_backlog(work_dir, new_text)
    gate = _suite_gate_refusal(work_dir, request)
    if gate is not None:
        _restore_tree(work_dir, rel)
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
    01M3HST4SGX0SPKAGNHVY7DWHM). Обход записывается только на пути
    конфигурации (`_config_path_request`): на `docs/**` гейта нет вовсе, и
    запись об обходе была бы ложной — а именно по этим записям Оператор
    обходы и ищет (R1-F4 ревью итерации 1). `--apply` пишет перечень
    удалённых строк (требование 12), пути `note` — прежнюю строку,
    буквально.
    """
    conn = store.db()
    kind = request["kind"]
    if kind == DOC_COMMIT_KIND:
        reason = request.get("accept_red")
        if reason and _config_path_request(request):
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
    known = _known_origin_main(work_dir)
    for _attempt_no in range(1, MAX_PUSH_ATTEMPTS + 1):
        prepared = _fetch_and_build(work_dir, request, known)
        if prepared is None:
            return None
        new_text, section_key, observation = prepared
        sha = _commit_and_push(work_dir, request, new_text, section_key,
                               observation)
        if sha is not None:
            return sha
    return None


def _flush_pending(explicit: bool = False) -> None:
    """Допуш удержанных заметок независимо от окна тишины (требование 5/7,
    AC-6): и оппортунистический вызов в начале `cmd_note` (когда окно уже
    проверено закрытым вызывающим кодом), и явный `note --flush` (обходит
    окно решением Оператора, AC-6) зовут эту же функцию — разница в
    `explicit` и в том, вызывает ли её `cmd_note` вообще (см.
    `_silence_window_reason` там).

    `explicit=False` (попутный допуш) НЕ трогает запись, отправка которой
    заведёт прогон полного набора `tests/` (`_suite_gate_applies`), — она
    ждёт явного флаша, и причина печатается. Иначе одна удержанная правка
    `roles.yaml` при красном наборе превращала бы КАЖДУЮ следующую `note`
    в молчаливый многоминутный прогон (R1-F3 ревью итерации 1): Оператор
    просил записать наблюдение, а не прогнать набор.

    Отказ одной заметки (сеть всё ещё недоступна, либо устаревшая заметка
    больше не проходит собственную валидацию) не рушит текущий вызов
    `note` — файл остаётся висеть, — но и не молчит: причина печатается.
    Прежде `SystemExit` глотался целиком, и запись висела без объяснения,
    а `doctor` сообщал только сам факт удержания.
    """
    for path in _pending_paths():
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not explicit and _suite_gate_applies(request):
            print(f"{request['path']}: удержанная правка конфигурации попутно "
                  f"не отправляется — её отправка гоняет полный набор "
                  f"tests/; отправка — doc-commit --flush либо note --flush")
            continue
        if (request.get("kind") == DOC_COMMIT_KIND
                and HELD_BASE_KEY not in request):
            # Запись, удержанная до сверки по базе (требование 4): идёт по
            # пиновой сверке, но Оператор видит, что защиты сценария 02.10
            # у неё нет.
            print(f"{request.get('path')}: {NO_BASE_WARNING}")
        try:
            sha = _attempt(request)
        except SystemExit as exc:
            detail = str(exc)
            if detail:
                print(f"удержанная запись не отправлена: {detail}")
            continue
        except OSError:
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
    known = _known_origin_main(work_dir)
    for _attempt_no in range(1, MAX_PUSH_ATTEMPTS + 1):
        prepared = _fetch_and_build(work_dir, request, known)
        if prepared is None:
            break
        new_text, section_key, observation = prepared
        if not bypass_window:
            reason = _silence_window_reason()
            if reason is not None:
                _hold_pending(request, known)
                print(f"{held}: {reason}; отправка — {command} --flush "
                      f"либо автоматически следующим {command} вне окна")
                return None
        sha = _commit_and_push(work_dir, request, new_text, section_key,
                               observation)
        if sha is not None:
            return sha
    _hold_pending(request, known)
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
    # Просмотр и снятие одной удержанной записи (SPEC
    # 01M3Y75X6K2ZMD85971TCWV41E, требования 5-6) — `--drop` занят строками
    # бэклога.
    parser.add_argument("--pending", action="store_true")
    parser.add_argument("--drop-pending", dest="drop_pending")
    # Принимается, поведения не несёт сверх приёма (SPEC «Не входит»).
    parser.add_argument("--task")
    return parser.parse_args(argv)


def cmd_note(argv: list[str]) -> None:
    if runner.in_role_environment():
        sys.exit("note отказана — вызов из окружения роли (role_env): "
                 "записи копилки и бэклога вносит Оператор")
    args = _parse_args(argv)
    # Просмотр и снятие удержанных записей — до попутного допуша: иначе он
    # отправил бы запись, которую Оператор как раз пришёл снять.
    if args.pending:
        _print_pending()
        return
    if args.drop_pending is not None:
        _drop_pending(args.drop_pending)
        return
    # Оппортунистический допуш уважает окно тишины (требование 7, AC-8):
    # при открытом окне удержанные записи остаются нетронутыми, вне окна —
    # допушиваются, как и сегодня. `--flush` форсирует его безусловно
    # (короткое замыкание `or` — окно вовсе не проверяется, требование
    # 5/AC-6, не смешивается с оппортунистическим путём). `explicit` —
    # только для явного флаша: попутный не вправе увести `note` в прогон
    # полного набора за удержанную правку конфигурации (см.
    # `_flush_pending`).
    if args.flush or _silence_window_reason() is None:
        _flush_pending(explicit=args.flush)
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
                 "--apply <файл> --message \"<основание>\", --pending, "
                 "--drop-pending <id>, либо --flush")


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
    обходить ему нечего — и записи журнала об обходе на таком пути не
    появляется (`_journal_commit`, R1-F4 ревью итерации 1).
    """
    if runner.in_role_environment():
        sys.exit(DOC_COMMIT_ROLE_REFUSAL)
    args = _parse_doc_commit_args(argv)
    if args.flush or _silence_window_reason() is None:
        _flush_pending(explicit=args.flush)
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
    accept_red = (args.accept_red.strip() if args.accept_red is not None
                  else None)
    _doc_commit_request(rel, content, args.message.strip(), accept_red)


def _doc_commit_request(rel: str, content: str, message: str,
                        accept_red: str | None = None) -> str | None:
    """Запись `doc-commit` уже проверенного пути — в `_run` (окно тишины,
    удержание, гейт полного набора) и строка итога. Общий хвост
    `cmd_doc_commit` и `doc_commit_content`."""
    request = {"kind": DOC_COMMIT_KIND, "path": rel, "content": content,
               "message": message}
    if accept_red is not None:
        request["accept_red"] = accept_red
    sha = _run(request)
    if sha is not None:
        print(f"{rel} закоммичен в origin/{config.MAIN_BRANCH}: {sha}")
    return sha


def doc_commit_content(rel: str, content: str, message: str) -> str | None:
    """Изолированный коммит содержимого `content` по пути `rel` тем же
    механизмом, что `doc-commit` (SPEC 01M3YCHP14179R32SFJVKQB32G,
    требование 3: команда `admit` пишет `model_sets.yaml`): сверка базы с
    пином, окно тишины и удержание, гейт полного набора на пути
    конфигурации, допуш удержанных записей. Отличие от `cmd_doc_commit` —
    только источник содержимого: строка вызывающего кода, а не файл
    `--from`.

    sha коммита в origin; `None` — запись удержана окном тишины. Отказы —
    `sys.exit`, как у самой команды.
    """
    if runner.in_role_environment():
        sys.exit(DOC_COMMIT_ROLE_REFUSAL)
    if _silence_window_reason() is None:
        _flush_pending()
    refusal = _doc_commit_path_refusal(rel)
    if refusal is not None:
        sys.exit(refusal)
    return _doc_commit_request(str(PurePosixPath(rel)), content, message)
