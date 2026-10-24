"""Тесты `orchestrator/notes.py`: копилка и бэклог `note`, окно тишины,
удержание, `note --apply`, формат строки (волна 1а сведения тестов,
SPEC 01M5NNDYGQ8G6VFDEEXYBB0W3D; ADR-0027 пп. 2, 3, 8).

Свод четырёх прежних файлов: `tests/test_notes.py` (чистые функции
разбора таблицы, хранилище удержанных записей, разбор аргументов
`cmd_note`, окно тишины на настоящем bare `origin`),
`tests/test_notes_apply.py` (`note --apply`, tasks/01M3HST4SGX0SPKAGNHVY7DWHM,
требования 9-12), `tests/test_notes_row_format.py` (единый формат строки,
та же задача, требования 1-8) и долгоживущего
`tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py` (окно
тишины по проекту задачи; удалён решением Оператора, ADR-0020 п. 8,
свойства перенесены сюда). Доказательство неослабления — таблицы
`mutation-run` «до» и «после» в PLAN задачи.

Стенды на настоящем git: `silence_box` (бывший `NoteSilenceSandbox`),
`apply_box` (бывший `ApplySandbox` — трёхраздельный документ, `--apply`
сверяет три раздела) и `window_box` (бывший стенд окна по проекту:
идентификаторы задач, сессий и проектов случайны на каждый запуск, зерно
печатается и входит в текст провала).
"""
import ast
import contextlib
import io
import os
import random
import re
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import config, doctor, notes, store
from tests.sandbox import capture, clone_artel_from_origin, declare_target, init_bare_origin

NOTES_BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое УНИКАЛЬНЫЙКЛЮЧ | orchestrator/x.py |
| 2 | 01.01 | повтор ПОВТОРКЛЮЧ один | orchestrator/y.py |
| 2 | 01.01 | повтор ПОВТОРКЛЮЧ два | orchestrator/z.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""

# Ячейка приоритета вставляемых ниже строк — цифра РАЗРЕШЁННОГО диапазона
# (01M3HST4SGX0SPKAGNHVY7DWHM, требования 3-4): колонка «П» нормализуется
# и на пути вставки строки, а не только у `--set-priority`. Предмет тестов
# окна тишины (место вставки, окно, общий флаш двух видов записей) от
# самого значения не зависит.

# --- `note --apply`: трёхраздельный документ ---

KOPILKA_HEADER = "| П | Дата | Наблюдение | Где | Состояние |"
KOPILKA_HEADER_WIDE = "| П | Дата | Наблюдение | Где | Состояние | Лишняя |"

# Ячейка «Наблюдение» первой снимаемой строки длиннее 80 знаков: маркер
# ХВОСТ стоит ЗА границей усечения записи журнала (требование 12), маркер
# СНЯТАЯОДИН — до неё.
LONG_DROPPED_CELL = "СНЯТАЯОДИН " + "х" * 70 + " ХВОСТ"

APPLY_BACKLOG_TEXT = f"""# Бэклог пульта

## Копилка

{KOPILKA_HEADER}
|---|---|---|---|---|
| 1 | 01.01 | ОСТАЁТСЯ наблюдение | orchestrator/x.py | состояние |
| 3 | 07.07 | {LONG_DROPPED_CELL} | orchestrator/d1.py | состояние |
| 4 | 07.07 | СНЯТАЯДВА наблюдение | orchestrator/d2.py | состояние |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта |
|---|---|---|---|---|---|
| 1 | Кандидат А | Суть А | $10 | orchestrator/a.py | сразу |

## Очередь Оператора

| П | Действие | Условие |
|---|---|---|
| 1 | Действие А | сразу |
"""

REASON = "разнос бэклога по решению Оператора"

# --- формат строки: пятиколоночная «Копилка» с колонками «П» и «Дата» ---

ROW_BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где | Состояние |
|---|---|---|---|---|
| 1 | 01.01 | СОСТОЯНИЕЕСТЬ | orchestrator/x.py | прежнее состояние |
| 2 | 01.01 | СОСТОЯНИЕПУСТО | orchestrator/y.py |  |
| 3 | 01.01 | СОСТОЯНИЕПРОЧЕРК | orchestrator/z.py | — |
"""

# Раздел БЕЗ колонки «П», но С колонкой «Дата»: нормализация приоритета
# такому разделу не полагается (требование 5), нормализация даты — да.
NO_PRIORITY_TEXT = """## Бэклог

| Кандидат | Дата |
|---|---|
| Кандидат A | 01.01 |
"""

# Раздел С колонкой «П», но БЕЗ колонки «Дата»: дата в ячейке другой
# колонки не трогается (требование 6 привязан к заголовку, не к виду
# содержимого).
NO_DATE_TEXT = """## Очередь Оператора

| П | Действие | Условие |
|---|---|---|
| 1 | Действие A | сразу |
"""

ROW_CELLS = ("2", "27.09", "текст", "где", "состояние")
FRAMED = "| " + " | ".join(ROW_CELLS) + " |"
BARE = " | ".join(ROW_CELLS)

STATE_FILLED = re.compile(r"(?P<old>.*) — (?P<stamp>\d\d\.\d\d): (?P<new>.*)")
STATE_EMPTY = re.compile(r"(?P<stamp>\d\d\.\d\d): (?P<new>.*)")

# --- окно тишины по проекту задачи ---

WINDOW_BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое наблюдение | orchestrator/x.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""

HELD_PREFIX = "заметка удержана: "
HELD_SUFFIX = "; отправка"

# Состояния вне окна тишины — для задачи держателя мьютекса (чтобы
# держатель был единственным триггером) и для AC-5. Список фильтруется
# по набору окна динамически: переживает правку набора Оператором.
OUTSIDE_WINDOW = tuple(s for s in ("done", "killed", "escalated")
                       if s not in config.NOTE_SILENCE_WINDOW_STATES)

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Имя удалённого класса-рудимента (01M3FTQ16M3VVXPPFCC0BGA39V, требование
# 6; находка CR-2026-09-26-12 седьмой ревизии) собирается из кусков
# намеренно: критерий AC-8 той задачи запрещает его литерал где бы то ни
# было в дереве вне `tasks/` и `docs/audits/` — включая этот регресс.
RUDIMENT_CLASS = "Note" + "Error"


# ------------------------------------------------------------- фикстуры

@pytest.fixture
def no_role(monkeypatch):
    """Окружение без признака роли: `cmd_note` отказывает шагу роли
    первым действием."""
    monkeypatch.setenv(config.ARTEL_ROLE_ENV, "")


@pytest.fixture
def schema_root(tmp_root):
    """Замена `SchemaTmpRootTest`: `tmp_root` + схема БД, без задач.

    Схема заведена явно (`store.create_schema`, не полновесный
    `catalog.cmd_init`): `cmd_note` читает `merge_locks`/`tasks` на КАЖДЫЙ
    вызов (проверка окна тишины) — без схемы `store.merge_lock_row`/
    `store.all_tasks` падали бы `sqlite3.OperationalError` раньше
    ожидаемого `SystemExit` разбора аргументов."""
    store.create_schema(store.db())
    return tmp_root


def _origin_with_backlog(box, origin: str, rel: str, text: str) -> None:
    """Bare `origin` песочницы `box`, синхронный с документом `rel`."""
    init_bare_origin(origin, box.git)
    box.git("remote", "add", "origin", origin)
    path = box.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    box.git("add", "-A")
    box.git("commit", "-q", "-m", "backlog")
    box.git("push", "-q", "origin",
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")


@pytest.fixture
def silence_box(real_git, no_role):
    """Стенд окна тишины `note` (01M2B6JS2BZNBW9WSHT1RPFXTE, AC-9): bare
    `origin` синхронный с `NOTES_BACKLOG_TEXT`, схема БД уже создана
    (`RealGitSandbox.setUp`) — пустая, без задач и без держателя
    `merge_locks`: окно тишины закрыто по умолчанию, пока тест сам не
    заведёт задачу нужного состояния/держателя мьютекса merge-окна."""
    real_git.origin = tempfile.mkdtemp()
    _origin_with_backlog(real_git, real_git.origin, "docs/backlog.md",
                         NOTES_BACKLOG_TEXT)
    yield real_git
    shutil.rmtree(real_git.origin, ignore_errors=True)


@pytest.fixture
def apply_box(real_git, no_role):
    """Главная копия с трёхраздельным `docs/backlog.md`, синхронная с bare
    `origin`: сверка базы проходит, окно тишины закрыто (БД пуста). Клон
    артели — из origin, как его заводит `init` (ADR-0021 п.1, этап 2):
    команды Оператора коммитят и пушат через него."""
    real_git.origin = tempfile.mkdtemp()
    _origin_with_backlog(real_git, real_git.origin, notes.BACKLOG_REL,
                         APPLY_BACKLOG_TEXT)
    clone_artel_from_origin(real_git.origin)
    real_git.source_dir = tempfile.mkdtemp()
    yield real_git
    shutil.rmtree(real_git.source_dir, ignore_errors=True)
    shutil.rmtree(real_git.origin, ignore_errors=True)


@pytest.fixture
def window_box(real_git, no_role):
    """Стенд окна по проекту: bare `origin` с `docs/backlog.md`, пустая БД,
    без держателя мьютекса; внешний проект объявлен в `config.TARGETS`
    песочницы, неразрешённый — нет. Зерно случайных идентификаторов
    печатается."""
    real_git.seed = random.randrange(1 << 32)
    print(f"зерно: {real_git.seed}")
    real_git.rng = random.Random(real_git.seed)
    real_git.origin = tempfile.mkdtemp()
    _origin_with_backlog(real_git, real_git.origin, "docs/backlog.md",
                         WINDOW_BACKLOG_TEXT)
    real_git.external = "ext" + token(real_git, 6).lower()
    real_git.ghost = "ghost" + token(real_git, 6).lower()
    declare_target(real_git.external)
    real_git.calls = 0
    yield real_git
    shutil.rmtree(real_git.origin, ignore_errors=True)


# ------------------------------------------------- помощники стендов git

def origin_run(box, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", box.origin, *args],
                          capture_output=True, text=True)


def origin_head(box) -> str:
    res = origin_run(box, "rev-parse", config.MAIN_BRANCH)
    return res.stdout.strip() if res.returncode == 0 else ""


def origin_backlog(box) -> str:
    res = origin_run(box, "show", f"{config.MAIN_BRANCH}:{notes.BACKLOG_REL}")
    assert res.returncode == 0, res.stderr
    return res.stdout


def insert_task_in_state(state: str, task_id: str = "T-WIN") -> None:
    store.insert_task(store.db(), task_id, "окно тишины", state,
                      f"task/{task_id}", config.DEFAULT_TARGET, 10.0)


def set_live_merge_lock(task_id: str = "T-LOCK",
                        session_id: str = "s-live") -> None:
    store.set_merge_lock(store.db(), task_id, session_id, os.getpid(),
                         socket.gethostname(), store.now())


# --- `note --apply` ---

def draft_with_extra_row() -> str:
    """Корректная заготовка: те же три раздела и те же шапки, в «Копилке»
    на одну строку больше."""
    extra = ("| 2 | 27.09 | ЗАГОТОВКАПРИМЕНЕНА | orchestrator/n.py | новое |")
    lines = APPLY_BACKLOG_TEXT.split("\n")
    lines.insert(lines.index(KOPILKA_HEADER) + 2, extra)
    return "\n".join(lines)


def draft_without_dropped_rows() -> str:
    """Корректная заготовка, потерявшая обе строки-маркера СНЯТАЯ*."""
    return "\n".join(line for line in APPLY_BACKLOG_TEXT.split("\n")
                     if "СНЯТАЯ" not in line)


def source_file(box, text: str, name: str = "draft-backlog.md") -> Path:
    path = Path(box.source_dir) / name
    path.write_text(text, encoding="utf-8")
    return path


def apply_draft(box, text: str, message: str = REASON) -> str:
    return capture(notes.cmd_note,
                   ["--apply", str(source_file(box, text)),
                    "--message", message])


def refusal(*argv: str) -> str:
    """Текст отказа `cmd_note` (`SystemExit`); stdout подавлен — отказ
    может печатать по дороге, и это не предмет проверки."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), \
            pytest.raises(SystemExit) as ctx:
        notes.cmd_note(list(argv))
    return str(ctx.value)


def draft_refusal(box, text: str) -> str:
    return refusal("--apply", str(source_file(box, text)),
                   "--message", REASON)


def origin_commit_count(box) -> int:
    res = origin_run(box, "rev-list", "--count", config.MAIN_BRANCH)
    return int(res.stdout.strip()) if res.returncode == 0 else -1


def origin_message(box) -> str:
    return origin_run(box, "log", "-1", "--format=%B",
                      config.MAIN_BRANCH).stdout


def main_copy_snapshot(box) -> tuple:
    return (box.git("rev-parse", "HEAD").strip(),
            box.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
            box.git("status", "--porcelain"))


def journal_text() -> str:
    rows = store.db().execute(
        "SELECT actor, action, detail FROM steps ORDER BY id").fetchall()
    return "\n".join(" ".join(str(col) for col in row) for row in rows)


def open_silence_window(task_id: str = "T-WIN") -> None:
    store.insert_task(store.db(), task_id, "окно тишины",
                      config.NOTE_SILENCE_WINDOW_STATES[0],
                      f"task/{task_id}", config.DEFAULT_TARGET, 10.0)


def push_foreign_backlog_change(box, text: str) -> None:
    """Чужая правка `docs/backlog.md`, уехавшая в origin ПОЗЖЕ базы
    главной копии (тот же приём, что `tests/test_doc_commit.py::
    PinBaseCheckTest._push_foreign_change_past_the_pin`)."""
    (box.root / notes.BACKLOG_REL).write_text(text, encoding="utf-8")
    box.git("commit", "-a", "-q", "-m", "чужая правка бэклога")
    box.git("push", "-q", "origin",
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    box.git("reset", "-q", "--hard", "HEAD~1")


# --- формат строки ---

def inserted_row(text: str, source: str = ROW_BACKLOG_TEXT,
                 section: str = "копилка", marker: str = "текст") -> str:
    """Строка, которую `_apply_insert` вставила в документ."""
    new_text, _section_key = notes._apply_insert(source, section, text)
    rows = [line for line in new_text.split("\n")
            if marker in line and line.strip().startswith("|")]
    assert len(rows) == 1, rows
    return rows[0]


def cells(line: str) -> list:
    """Ячейки строки — собственным разбором, не `notes._row_cells`:
    проверять нормализацию инструментом самой реализации значило бы не
    проверять её вовсе."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def appended_cell(key: str, text: str) -> str:
    new_text, _key = notes._apply_append(ROW_BACKLOG_TEXT, key, text)
    row = [line for line in new_text.split("\n") if key in line][0]
    return cells(row)[-1]


# --- окно по проекту ---

def token(box, n: int = 10) -> str:
    return "".join(box.rng.choice(_ALPHABET) for _ in range(n))


def task_id(box, prefix: str = "") -> str:
    return prefix + token(box, 16)


def insert_project_task(task_id: str, state: str, target) -> None:
    """`target` — имя проекта, `""` либо `None` (пустая колонка)."""
    conn = store.db()
    store.insert_task(conn, task_id, "окно тишины", state,
                      f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                      10.0)
    if target != config.DEFAULT_TARGET:
        store.update_task(conn, task_id, target=target)


def set_state(task_id: str, state: str) -> None:
    store.update_task(store.db(), task_id, state=state)


def live_lock(box, task_id: str) -> str:
    session = "s-" + token(box, 8).lower()
    store.set_merge_lock(store.db(), task_id, session, os.getpid(),
                         socket.gethostname(), store.now())
    return session


def window_origin_backlog(box) -> str:
    return box.git("--git-dir", box.origin, "show",
                   f"{config.MAIN_BRANCH}:docs/backlog.md")


def window_note(box) -> tuple[str, str]:
    """Одна обычная запись копилки; (уникальный текст, вывод команды)."""
    box.calls += 1
    marker = f"запись{box.calls}-{token(box, 8)}"
    text = f"2 | 18.10 | {marker} | orchestrator/n.py"
    out = capture(notes.cmd_note, ["копилка", "--text", text])
    return marker, out


def assert_pushed(box, marker: str, out: str, ctx: str) -> None:
    msg = f"{ctx}; зерно {box.seed}; вывод: {out!r}"
    assert HELD_PREFIX not in out, msg
    assert marker in window_origin_backlog(box), msg
    assert notes.pending_notes() == [], msg


def held_reason(box, marker: str, out: str, ctx: str) -> str:
    msg = f"{ctx}; зерно {box.seed}; вывод: {out!r}"
    assert HELD_PREFIX in out, msg
    assert marker not in window_origin_backlog(box), msg
    return out.split(HELD_PREFIX, 1)[1].split(HELD_SUFFIX, 1)[0]


# ------------------------------------------- разбор и правка таблицы

def test_row_cells_strips_outer_pipes_and_whitespace():
    """Обрамляющие черты и пробелы ячеек снимаются.

    Ловит мутацию: `_row_cells` не снимает обрамляющие черты
    (`inner = s`) — по краям появляются пустые ячейки, список длиннее.
    """
    assert notes._row_cells("| 1 | два | 3 |") == ["1", "два", "3"]


def test_insert_right_after_separator():
    """Новая строка встаёт сразу под строкой-разделителем шапки, а
    прежняя первая строка данных сдвигается, не теряется.

    Ловит мутацию: индекс вставки посчитан от шапки, а не от
    строки-разделителя (`lines.insert(header_idx + 1, …)`) — новая
    строка встаёт НА место разделителя, и таблица перестаёт быть
    таблицей; вставка в конец раздела красит тот же ассерт.
    """
    new_text, section_key = notes._apply_insert(
        NOTES_BACKLOG_TEXT, "копилка",
        "4 | 09.09 | новое | orchestrator/new.py")
    assert section_key == "копилка"
    lines = new_text.splitlines()
    sep_idx = lines.index("|---|---|---|---|")
    assert lines[sep_idx + 1] == "| 4 | 09.09 | новое | orchestrator/new.py |"
    # Прежняя первая строка данных сдвинута, не потеряна.
    assert "старое УНИКАЛЬНЫЙКЛЮЧ" in lines[sep_idx + 2]


def test_insert_column_count_mismatch_refuses_naming_expected_count():
    """Строка не той ширины — отказ, называющий ожидаемое число колонок.

    Ловит мутацию: текст отказа не называет ожидаемое число колонок
    шапки (`ожидает {len(header_cells)}` убрано) — «4» в отказе нет.
    """
    with pytest.raises(SystemExit, match=re.escape("4")):
        notes._apply_insert(NOTES_BACKLOG_TEXT, "копилка", "1 | 2 | 3")


def test_insert_unknown_section_heading_refuses():
    """Документ без заголовка раздела — отказ, не молчаливый возврат.

    Ловит мутацию: ненайденный раздел возвращает документ без изменений
    (`return original, section_key` вместо `sys.exit`) — отказа нет.
    """
    with pytest.raises(SystemExit):
        notes._apply_insert("без разделов вовсе", "копилка", "1|2|3|4")


def test_append_unique_key_appends_to_last_column_only():
    """Дописка по уникальному ключу — в последнюю колонку, прежний текст
    ячейки и соседние строки целы.

    Ловит мутацию: дописка затирает прежний текст последней ячейки
    (`cells[-1] = text`, путь `--set-state`) — «orchestrator/x.py» из
    строки пропадает.
    """
    new_text, section_key = notes._apply_append(
        NOTES_BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "доп. текст")
    assert section_key == "копилка"
    matched = [ln for ln in new_text.splitlines()
               if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
    assert "orchestrator/x.py" in matched
    assert "доп. текст" in matched
    # Остальные строки раздела не задеты байт-в-байт.
    untouched = [ln for ln in NOTES_BACKLOG_TEXT.splitlines()
                 if "ПОВТОРКЛЮЧ один" in ln][0]
    assert untouched in new_text


def test_append_zero_matches_refuses_without_changing_text():
    """Ключ не найден ни в одной строке — отказ.

    Ловит мутацию: `_find_unique_row` отказывает только на нескольких
    совпадениях (`len(matches) > 1`) — ноль совпадений падает
    `IndexError`, а не именованным отказом.
    """
    with pytest.raises(SystemExit):
        notes._apply_append(NOTES_BACKLOG_TEXT, "НЕТТАКОГОКЛЮЧА", "текст")


def test_append_multiple_matches_refuses_without_changing_text():
    """Ключ совпал в двух строках — отказ.

    Ловит мутацию: `_find_unique_row` отказывает только на нуле
    совпадений (`len(matches) == 0`) — из двух строк молча берётся
    первая.
    """
    with pytest.raises(SystemExit):
        notes._apply_append(NOTES_BACKLOG_TEXT, "ПОВТОРКЛЮЧ", "текст")


def test_drop_removes_matched_row_only_neighbours_untouched():
    """`--drop` снимает ровно совпавшую строку, соседи и другой раздел целы.

    Ловит мутацию: удаляется соседняя строка (`del lines[idx + 1]`) —
    ключ остаётся в тексте, а «ПОВТОРКЛЮЧ один» пропадает.
    """
    new_text, section_key, observation = notes._apply_drop(
        NOTES_BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ")
    assert section_key == "копилка"
    assert "УНИКАЛЬНЫЙКЛЮЧ" not in new_text
    assert "orchestrator/x.py" in observation
    # Соседние строки раздела остаются байт-в-байт прежними.
    for marker in ("ПОВТОРКЛЮЧ один", "ПОВТОРКЛЮЧ два"):
        untouched = [ln for ln in NOTES_BACKLOG_TEXT.splitlines()
                     if marker in ln][0]
        assert untouched in new_text
    # Другой раздел не задет.
    assert "Кандидат A" in new_text


def test_drop_zero_matches_refuses_without_changing_text():
    """`--drop` по ненайденному ключу — отказ.

    Ловит мутацию: `_find_unique_row` отказывает только на нескольких
    совпадениях (`len(matches) > 1`) — ноль совпадений падает
    `IndexError`, а не именованным отказом.
    """
    with pytest.raises(SystemExit):
        notes._apply_drop(NOTES_BACKLOG_TEXT, "НЕТТАКОГОКЛЮЧА")


def test_drop_multiple_matches_refuses_without_changing_text():
    """`--drop` по ключу двух строк — отказ.

    Ловит мутацию: `_find_unique_row` отказывает только на нуле
    совпадений (`len(matches) == 0`) — снимается первая из двух строк.
    """
    with pytest.raises(SystemExit):
        notes._apply_drop(NOTES_BACKLOG_TEXT, "ПОВТОРКЛЮЧ")


def test_set_state_replaces_last_column_entirely_not_appends():
    """`--set-state` заменяет последнюю ячейку целиком.

    Ловит мутацию: `--set-state` дописывает, а не заменяет
    (`_appended_state(cells[-1], text)`) — в ячейке остаётся прежний
    текст и метка даты.
    """
    new_text, section_key = notes._apply_set_state(
        NOTES_BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "новое состояние")
    assert section_key == "копилка"
    matched = [ln for ln in new_text.splitlines()
               if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
    row = notes._row_cells(matched)
    assert row[-1] == "новое состояние"
    assert "orchestrator/x.py" not in row[-1]


def test_set_state_multiple_matches_refuses_without_changing_text():
    """`--set-state` по ключу двух строк — отказ.

    Ловит мутацию: `_find_unique_row` отказывает только на нуле
    совпадений (`len(matches) == 0`) — правится первая из двух строк.
    """
    with pytest.raises(SystemExit):
        notes._apply_set_state(NOTES_BACKLOG_TEXT, "ПОВТОРКЛЮЧ", "текст")


def test_set_priority_replaces_first_column_with_valid_value():
    """`--set-priority` пишет значение в колонку «П».

    Ловит мутацию: значение пишется в соседнюю колонку
    (`header_cells.index(PRIORITY_HEADER) + 1`) — первая ячейка прежняя.
    """
    new_text, section_key = notes._apply_set_priority(
        NOTES_BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "3")
    assert section_key == "копилка"
    matched = [ln for ln in new_text.splitlines()
               if "УНИКАЛЬНЫЙКЛЮЧ" in ln][0]
    row = notes._row_cells(matched)
    assert row[0] == "3"


def test_set_priority_value_above_range_refuses_without_changing_text():
    """«5» вне диапазона 1..4 — отказ.

    Ловит мутацию: диапазон приоритета не сверяется (`_PRIORITY_RE` с
    `[0-9]`) — «5» проходит.
    """
    with pytest.raises(SystemExit):
        notes._apply_set_priority(NOTES_BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "5")


def test_set_priority_value_below_range_refuses_without_changing_text():
    """«0» вне диапазона 1..4 — отказ.

    Ловит мутацию: диапазон приоритета не сверяется (`_PRIORITY_RE` с
    `[0-9]`) — «0» проходит.
    """
    with pytest.raises(SystemExit):
        notes._apply_set_priority(NOTES_BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "0")


def test_set_priority_non_numeric_value_refuses_without_changing_text():
    """Нечисловое значение — отказ.

    Ловит мутацию: отказ `_priority_or_refuse` только для цифр вне
    диапазона (`value is None and cell.strip().isdigit()`) — «х» не
    отказывает.
    """
    with pytest.raises(SystemExit):
        notes._apply_set_priority(NOTES_BACKLOG_TEXT, "УНИКАЛЬНЫЙКЛЮЧ", "х")


# ------------------------------------------- хранилище удержанных записей

def test_pending_notes_empty_by_default(tmp_root):
    """Без удержанных записей — пустой список.

    Ловит мутацию: `pending_notes` отдаёт пустой перечень как `None`
    (`return result or None`) — равенство `[]` ломается.
    """
    assert notes.pending_notes() == []


def test_pending_notes_hold_then_read_back_round_trips(tmp_root):
    """Удержанная запись читается обратно той же.

    Ловит мутацию: `_hold_pending` теряет поле `text` записи — прочитанная
    запись не равна удержанной.
    """
    request = {"kind": "insert", "section": "копилка", "text": "x"}
    notes._hold_pending(request)
    pending = notes.pending_notes()
    assert pending == [request]


def test_pending_notes_two_holds_are_both_visible(tmp_root):
    """Две удержанные записи — обе видны.

    Ловит мутацию: имя файла записи не уникально (`"pending.json"`) —
    вторая запись затирает первую, видна одна.
    """
    notes._hold_pending({"kind": "insert", "section": "копилка", "text": "a"})
    notes._hold_pending({"kind": "append", "key": "k", "text": "b"})
    assert len(notes.pending_notes()) == 2


# --------------------------------------------- разбор аргументов cmd_note
# Отказы разбора аргументов, не доходящие до git вовсе (пустая
# `pending_notes()` — оппортунистический flush внутри `cmd_note` не
# находит, что отправлять, и не трогает сеть).

def test_cmd_note_no_arguments_at_all_refuses(schema_root, no_role):
    """`note` без аргументов — именованный отказ.

    Ловит мутацию: итоговый отказ «укажи раздел…» бросает `ValueError`
    вместо `SystemExit` — трассировка вместо текста отказа.
    """
    with pytest.raises(SystemExit):
        notes.cmd_note([])


def test_cmd_note_section_without_text_refuses(schema_root, no_role):
    """Раздел без `--text` — отказ.

    Ловит мутацию: отказ «--text обязателен» у раздела бросает
    `ValueError` вместо `SystemExit`.
    """
    with pytest.raises(SystemExit):
        notes.cmd_note(["копилка"])


def test_cmd_note_append_without_text_refuses(schema_root, no_role):
    """`--append` без `--text` — отказ.

    Ловит мутацию: отказ «--append требует --text» бросает `ValueError`
    вместо `SystemExit`.
    """
    with pytest.raises(SystemExit):
        notes.cmd_note(["--append", "ключ"])


def test_cmd_note_set_state_without_text_refuses(schema_root, no_role):
    """`--set-state` без `--text` — отказ.

    Ловит мутацию: отказ «--set-state требует --text» бросает
    `ValueError` вместо `SystemExit`.
    """
    with pytest.raises(SystemExit):
        notes.cmd_note(["--set-state", "ключ"])


def test_cmd_note_set_priority_without_text_refuses(schema_root, no_role):
    """`--set-priority` без `--text` — отказ.

    Ловит мутацию: отказ «--set-priority требует --text» бросает
    `ValueError` вместо `SystemExit`.
    """
    with pytest.raises(SystemExit):
        notes.cmd_note(["--set-priority", "ключ"])


def test_cmd_note_flush_with_nothing_pending_is_a_noop(schema_root, no_role):
    """`--flush` при пустом перечне — тихо, без исключения.

    Ловит мутацию: `--flush` без удержанных записей отказывает
    (`sys.exit` вместо `return`) — тест падает на `SystemExit`.
    """
    notes.cmd_note(["--flush"])  # не должно поднять исключение


@pytest.mark.parametrize("argv", [
    [], ["--flush"], ["копилка", "--text", "строка"],
    ["--append", "ключ", "--text", "строка"],
    ["--apply", "draft.md", "--message", "основание"],
])
def test_cmd_note_role_refuses_every_form_before_parsing(argv):
    """Шаг роли не доходит до разбора ни одной формы note.

    Ловит мутацию: проверка роли удалена или перенесена после разбора
    аргументов — подмена разбора поднимет AssertionError.
    """
    with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}), \
            mock.patch.object(notes, "_parse_args",
                              side_effect=AssertionError("разбор вызван")):
        with pytest.raises(SystemExit, match=re.escape("роли")):
            notes.cmd_note(argv)


# ---------------------------------------------- doctor: удержанные записи

def test_check_pending_notes_ok_when_nothing_pending(tmp_root):
    """Без удержанных записей проверка `doctor` — `ok`.

    Ловит мутацию: `check_pending_notes` предупреждает и на пустом
    перечне (`if pending is None` вместо `if not pending`) — статус
    `warn`.
    """
    assert doctor.check_pending_notes().status == "ok"


def test_check_pending_notes_warn_when_something_pending(tmp_root):
    """Удержанная запись — `warn` с подсказкой `note --flush`.

    Ловит мутацию: подсказка отправки из текста предупреждения убрана
    (`artel.py отправит их…` без `note --flush`).
    """
    notes._hold_pending({"kind": "insert", "section": "копилка", "text": "x"})
    check = doctor.check_pending_notes()
    assert check.status == "warn"
    assert "note --flush" in check.detail


# ------------------------------------------------- окно тишины: причина

def test_silence_ac1_live_merge_lock_alone_without_any_task_state_opens_window(silence_box):
    """Живой держатель `merge_locks` — единственный триггер (`store.
    all_tasks` пуст) — окно тишины уже открыто (условие ИЛИ, AC-1).

    Ловит мутацию: реализация проверяет только `store.all_tasks` и
    игнорирует держателя `merge_locks` — при пустом наборе задач
    такая версия ошибочно вернула бы `None` (окна нет)."""
    set_live_merge_lock()
    assert notes._silence_window_reason() is not None


def test_silence_no_holder_and_no_task_in_set_closes_window(silence_box):
    """База: пустая БД — окна нет (AC-5).

    Ловит мутацию: удержание навсегда (условие открытия окна
    перевёрнуто) — здесь уже красно на непустом результате."""
    assert notes._silence_window_reason() is None


def test_silence_escalated_state_does_not_open_window(silence_box):
    """`escalated` НЕ входит в `config.NOTE_SILENCE_WINDOW_STATES`
    (ровно пять состояний AC-1, не шесть состояний `zone_lock.
    BLOCKING_STATES`) — задача в `escalated` не открывает окно.

    Ловит мутацию: набор состояний случайно берёт чужую константу
    (`zone_lock.BLOCKING_STATES`, несущую `escalated`) — тест красен
    на непустом результате."""
    insert_task_in_state("escalated")
    assert notes._silence_window_reason() is None


def test_silence_dead_merge_lock_holder_does_not_open_window(silence_box):
    """Протухший heartbeat держателя `merge_locks` — тот же признак
    мёртвости, что `merge_lock._holder_is_dead` — не открывает окно
    сам по себе (без задачи в состоянии набора).

    Ловит мутацию: реализация не проверяет живость держателя (любая
    строка `merge_locks` трактуется как открытое окно) — тест красен
    на непустом результате."""
    old_heartbeat = "2000-01-01 00:00:00Z"
    store.set_merge_lock(store.db(), "T-DEAD", "s-dead", 999999,
                         "иной-хост", old_heartbeat)
    assert notes._silence_window_reason() is None


def test_silence_artel_task_and_holder_not_resolved_through_targets(silence_box):
    """Задача артели с пустой колонкой `target` и держатель с той же
    задачей узнаются по `repo_context.is_artel`, без `resolve`: даже
    когда записи проектов не разрешаются (сломанный `targets.yaml`),
    причина — прежний текст артели, не «проект задачи не определён».

    Ловит мутацию: `resolve(task["target"])` зовётся первым (или
    вместо `is_artel`) — для пустого `target` он даёт `None`, задача
    артели становится «не определён», и тест краснеет на подстроке."""
    conn = store.db()
    store.insert_task(conn, "T-ART", "окно тишины", "in_dev",
                      "task/T-ART", config.DEFAULT_TARGET, 10.0)
    conn.execute("UPDATE tasks SET target='' WHERE id='T-ART'")
    conn.commit()
    with mock.patch.object(notes.repo_context, "resolve",
                           return_value=None):
        assert notes._silence_window_reason() == "задача T-ART в состоянии in_dev"
        set_live_merge_lock(task_id="T-ART")
        assert notes._silence_window_reason() == (
            "держатель merge-окна жив (сессия s-live, "
            "задача T-ART)")


# ------------------------------------------- окно тишины: удержание записи

def test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev(silence_box):
    """Задача в `in_dev` держит окно тишины открытым — все пять видов
    записи по очереди удерживаются, `origin` не сдвигается ни разу.

    Ловит мутацию: окно проверяется только для вида `insert` (ветка
    удержания добавлена лишь в путь раздела с `--text`, а `--append`/
    `--drop`/`--set-state`/`--set-priority` продолжают пушить
    немедленно) — тест красен на изменившемся `origin_head()` уже на
    втором вызове."""
    insert_task_in_state("in_dev")
    before = origin_head(silence_box)

    capture(notes.cmd_note,
            ["копилка", "--text",
             "4 | 09.09 | вставка при окне | orchestrator/i.py"])
    capture(notes.cmd_note,
            ["--append", "УНИКАЛЬНЫЙКЛЮЧ", "--text", "доп-текст"])
    capture(notes.cmd_note, ["--drop", "УНИКАЛЬНЫЙКЛЮЧ"])
    capture(notes.cmd_note,
            ["--set-state", "ПОВТОРКЛЮЧ один", "--text", "новое"])
    capture(notes.cmd_note,
            ["--set-priority", "ПОВТОРКЛЮЧ один", "--text", "3"])

    assert before == origin_head(silence_box)
    pending = notes.pending_notes()
    assert [p["kind"] for p in pending] == ["insert", "append", "drop",
                                            "set-state", "set-priority"]


def test_window_ac3_hold_message_prefix_and_suffix(silence_box):
    """Сообщение удержания несёт фиксированные пролог/эпилог и
    непустую причину между ними (AC-3).

    Ловит мутацию: реализация молчит при удержании (не печатает
    ничего) — тест красен на пустом `captured`."""
    insert_task_in_state("acceptance")

    captured = capture(
        notes.cmd_note,
        ["копилка", "--text", "4 | 09.09 | сообщение | orchestrator/m.py"])

    assert "заметка удержана:" in captured, captured
    assert ("отправка — note --flush либо автоматически "
            "следующим note вне окна") in captured, captured
    reason = captured.split("заметка удержана:", 1)[1].split(";", 1)[0]
    assert reason.strip()


def test_window_ac4_unmatched_key_refuses_before_hold_even_with_window_open(silence_box):
    """Окно открыто (`merge_gate`), `--append` нацелен на
    несуществующий ключ: отказ валидации происходит раньше решения
    об удержании — `origin` не меняется, `notes-pending/` пуст
    (AC-4).

    Ловит мутацию: проверка окна тишины перенесена ПЕРЕД валидацией
    — тест красен на непустом `pending_notes()` вместо `SystemExit`."""
    insert_task_in_state("merge_gate")
    before = origin_head(silence_box)

    with pytest.raises(SystemExit):
        notes.cmd_note(["--append", "НЕТТАКОГОКЛЮЧА", "--text", "текст"])

    assert before == origin_head(silence_box)
    assert notes.pending_notes() == []


def test_window_ac9_held_note_uses_existing_pending_json_shape(silence_box):
    """Запись, удержанная окном тишины, лежит в `.artel/notes-pending/`
    и несёт те же поля, что и удержание по сетевому отказу — общий
    формат `_hold_pending`, не параллельный (AC-9).

    Ловит мутацию: окно тишины удерживает запись собственным,
    параллельным путём/форматом — тест красен на пустом
    `pending_notes()`."""
    insert_task_in_state("review")

    capture(notes.cmd_note,
            ["копилка", "--text", "4 | 09.09 | формат | orchestrator/fmt.py"])

    pending = notes.pending_notes()
    assert len(pending) == 1, pending
    assert pending[0]["kind"] == "insert"
    assert pending[0]["section"] == "копилка"


# ------------------------------------- окно тишины: обходы и отсутствие окна

def test_window_ac5_no_window_pushes_immediately_unchanged(silence_box):
    """Без держателя `merge_locks` и без задач в состояниях набора —
    push немедленный, как до этой задачи (AC-5).

    Ловит мутацию: условие удержания перевёрнуто (держит всегда) —
    тест красен на пустом `origin_backlog()`."""
    capture(notes.cmd_note,
            ["копилка", "--text",
             "4 | 09.09 | без окна | orchestrator/nw.py"])

    assert "без окна" in origin_backlog(silence_box)
    assert notes.pending_notes() == []


def test_window_ac6_flush_pushes_held_note_while_window_stays_open(silence_box):
    """`note --flush` допушивает удержанную запись, даже когда окно
    ОСТАЁТСЯ открытым той же задачей (AC-6, явный обход).

    Ловит мутацию: `--flush` делегирует оппортунистическому флашу,
    уважающему окно (требование 7), вместо безусловного пути — тест
    красен на непустом `pending_notes()` после вызова."""
    insert_task_in_state("review")
    capture(notes.cmd_note,
            ["копилка", "--text",
             "4 | 09.09 | до флаша | orchestrator/f.py"])
    assert len(notes.pending_notes()) == 1

    capture(notes.cmd_note, ["--flush"])

    assert "до флаша" in origin_backlog(silence_box)
    assert notes.pending_notes() == []


def test_window_ac7_now_pushes_immediately_and_does_not_hold(silence_box):
    """`note --now <раздел> --text …` пушит немедленно в обход
    открытого окна, не удерживая запись вовсе (AC-7).

    Ловит мутацию: `--now` принят флагом, но обход не реализован
    (запись удерживается как обычная) — тест красен на пустом
    `origin_backlog()` и непустом `pending_notes()`."""
    insert_task_in_state("acceptance")

    capture(
        notes.cmd_note,
        ["--now", "копилка", "--text",
         "4 | 09.09 | срочно | orchestrator/now.py"])

    assert "срочно" in origin_backlog(silence_box)
    assert notes.pending_notes() == []


def test_window_ac8_open_window_leaves_previously_held_note_untouched(silence_box):
    """Заметка уже удержана ДО вызова; окно открыто (`verifying`) —
    обычный вызов `note` не допушивает старую удержанную заметку,
    новая тоже уходит в удержание (AC-8, оппортунистический флаш
    уважает окно).

    Ловит мутацию: оппортунистический флаш безусловен — тест красен
    на изменившемся `origin_head()` либо на потере старой заметки."""
    notes._hold_pending({"kind": "insert", "section": "копилка",
                         "text": "4 | 09.09 | старая | orchestrator/o.py"})
    insert_task_in_state("verifying")
    before = origin_head(silence_box)

    capture(notes.cmd_note,
            ["копилка", "--text",
             "4 | 09.09 | новая при открытом окне | orchestrator/p.py"])

    assert before == origin_head(silence_box)
    pending = notes.pending_notes()
    assert len(pending) == 2, pending


def test_window_ac8_closed_window_still_flushes_previously_held_note(silence_box):
    """Та же предпосылка, но БЕЗ открытого окна — обычный вызов
    `note` допушивает старую удержанную заметку оппортунистически
    (AC-8, поведение вне окна не меняется).

    Ловит мутацию: условие инвертировано (флаш только при открытом
    окне) — тест красен на непустом `pending_notes()`."""
    notes._hold_pending({"kind": "insert", "section": "копилка",
                         "text": "4 | 09.09 | старая без окна | orchestrator/q.py"})

    capture(notes.cmd_note,
            ["копилка", "--text",
             "4 | 09.09 | новая без окна | orchestrator/r.py"])

    text = origin_backlog(silence_box)
    assert "старая без окна" in text
    assert "новая без окна" in text
    assert notes.pending_notes() == []


# --------------------------------------------------- рудимент исключения

def test_notes_module_declares_no_rudiment_exception():
    """Ни атрибута модуля, ни объявления класса в исходнике —
    исключение не ловилось нигде и существовало «для читаемости».

    Ловит мутацию: класс возвращён в модуль (например, вместе с
    попыткой завести обработку ошибок, не доведённой до `except`) —
    и `hasattr`, и разбор `ast` снова его найдут."""
    assert not hasattr(notes, RUDIMENT_CLASS)
    source = Path(notes.__file__).read_text(encoding="utf-8")
    classes = [node.name for node in ast.parse(source).body
               if isinstance(node, ast.ClassDef)]
    assert RUDIMENT_CLASS not in classes


# ------------------------------------------------- note --apply: успех

def test_apply_draft_becomes_the_document_in_one_commit(apply_box):
    """Корректная заготовка приезжает в `origin/main` целиком:
    содержимое пути равно заготовке байт-в-байт, добавлен РОВНО один
    коммит, сообщение коммита несёт основание `--message` целиком, а
    HEAD, ветка и рабочее дерево главной копии прежние (требование 9).

    Ловит мутацию: `--apply` правит и коммитит документ в рабочей
    копии пульта (`config.ROOT`) вместо изолированного рабочего
    репозитория — снимок главной копии меняется; либо основание
    усекается до 80 знаков, как у строки `note`.
    """
    draft = draft_with_extra_row()
    before_commits = origin_commit_count(apply_box)
    before_main = main_copy_snapshot(apply_box)

    output = apply_draft(apply_box, draft)

    assert origin_backlog(apply_box) == draft
    assert origin_commit_count(apply_box) == before_commits + 1
    assert REASON in origin_message(apply_box)
    assert before_main == main_copy_snapshot(apply_box)
    assert notes.pending_notes() == []
    assert origin_head(apply_box) in output, output


def test_apply_journal_names_dropped_row_count_and_truncated_rows(apply_box):
    """Журнал пульта после успеха несёт число удалённых строк (2) и
    сами строки, причём длинная усечена — маркер за границей 80 знаков
    в журнал не попадает (требование 12).

    Ловит мутацию: перечисляются ДОБАВЛЕННЫЕ строки вместо удалённых
    (стороны сравнения перепутаны) — ни одного маркера СНЯТАЯ* в
    журнале нет; либо усечение снято — в журнал уезжает ХВОСТ.
    """
    draft = draft_without_dropped_rows()

    apply_draft(apply_box, draft)

    journal = journal_text()
    assert "удалено строк: 2" in journal, journal
    assert "СНЯТАЯОДИН" in journal, journal
    assert "СНЯТАЯДВА" in journal, journal
    assert "ХВОСТ" not in journal, journal


def test_apply_untouched_draft_counts_zero_dropped_rows(apply_box):
    """Заготовка, которая ничего не снимает, даёт в журнале «удалено
    строк: 0» — запись пишется всегда, а не только когда есть что
    перечислять (требование 12).

    Ловит мутацию: запись журнала пишется только при непустом
    перечне — успешный `--apply` без удалений уходит бесследно, и
    Оператор не может отличить его от неисполненного.
    """
    apply_draft(apply_box, draft_with_extra_row())

    assert "удалено строк: 0" in journal_text()


# ------------------------------------------------ note --apply: отказы

def test_apply_document_changed_in_origin_past_the_base_refuses(apply_box):
    """Чужая правка документа уехала в origin позже базы главной
    копии: `--apply` отказывает, коммита нет, в origin чужой текст,
    удержанной записи не появилось (требование 10).

    Ловит мутацию: `--apply` коммитит заготовку поверх свежего origin,
    не сверяя базу (сверка доехала только до `doc-commit`) — чужая
    правка молча затирается ЦЕЛИКОМ, не одной строкой.
    """
    foreign = APPLY_BACKLOG_TEXT + "\n<!-- чужая правка в origin -->\n"
    push_foreign_backlog_change(apply_box, foreign)
    before = origin_head(apply_box)

    message = draft_refusal(apply_box, draft_with_extra_row())

    assert notes.APPLY_FOREIGN_BASE_REFUSAL in message, message
    assert before == origin_head(apply_box)
    assert origin_backlog(apply_box) == foreign
    assert notes.pending_notes() == []


def test_apply_own_note_commit_past_the_pin_does_not_block_apply(apply_box):
    """Обычная заметка уехала в origin (пин главной копии при этом не
    двигается — так работает `note`), и `--apply` ПОСЛЕ неё проходит:
    сверка базы отличает свою правку от чужой (требование 10, R1-F2
    ревью итерации 1).

    Ловит мутацию: сверка базы `--apply` сведена к пиновой сверке
    `doc-commit` (`origin_sha != pin_sha` — отказ) — после первой же
    заметки `--apply` отказывает «сначала pin-update», и тест красен на
    `SystemExit` вместо заменённого документа.
    """
    capture(notes.cmd_note, ["--now", "копилка", "--text",
                             "| 2 | 27.09 | ЗАМЕТКАПОСЛЕБАЗЫ | o.py | — |"])
    assert "ЗАМЕТКАПОСЛЕБАЗЫ" in origin_backlog(apply_box)
    # Заготовка собрана от СВЕЖЕГО содержимого origin — тот порядок,
    # который предписывает docs/operator-session.md.
    fresh = origin_backlog(apply_box)
    lines = fresh.split("\n")
    lines.insert(lines.index(KOPILKA_HEADER) + 2,
                 "| 1 | 27.09 | РАЗНОС | orchestrator/n.py | новое |")
    draft = "\n".join(lines)

    apply_draft(apply_box, draft)

    assert origin_backlog(apply_box) == draft
    assert "ЗАМЕТКАПОСЛЕБАЗЫ" in origin_backlog(apply_box)
    assert "удалено строк: 0" in journal_text()


def test_apply_origin_changed_while_the_record_was_held_refuses_on_flush(apply_box):
    """Заготовка удержана окном тишины, документ в origin за это время
    уехал (заметка `--now` обходит окно): явный флаш отказывает, назвав
    причину, запись остаётся удержанной, а уехавшая строка в origin
    цела — «изменился между чтением заготовки и коммитом» (требование
    10).

    Ловит мутацию: сверка базы смотрит только на состояние ПЕРВОГО
    построения (`base_blob` в записи не хранится либо не сверяется при
    флаше) — заготовка уезжает поверх новой строки и стирает её, и тест
    красен на содержимом origin.
    """
    draft = draft_with_extra_row()
    open_silence_window()
    capture(notes.cmd_note, ["--apply", str(source_file(apply_box, draft)),
                             "--message", REASON])
    assert len(notes.pending_notes()) == 1, notes.pending_notes()
    capture(notes.cmd_note, ["--now", "копилка", "--text",
                             "| 2 | 27.09 | ПОСЛЕЗАГОТОВКИ | o.py | — |"])
    before = origin_head(apply_box)

    output = capture(notes.cmd_note, ["--flush"])

    assert notes.APPLY_STALE_BASE_REFUSAL in output, output
    assert before == origin_head(apply_box)
    assert "ПОСЛЕЗАГОТОВКИ" in origin_backlog(apply_box)
    assert len(notes.pending_notes()) == 1, notes.pending_notes()


def test_apply_draft_without_a_section_refuses_before_commit(apply_box):
    """Заготовка, потерявшая раздел «## Очередь Оператора» целиком, —
    именованный отказ до коммита; документ в origin прежний, удержанной
    записи нет (требование 11).

    Ловит мутацию: проверяется только число колонок шапок, а наличие
    самих разделов — нет; тогда заготовка, из которой раздел выпал,
    доезжает до коммита и уносит его из документа.
    """
    before = origin_head(apply_box)
    draft = APPLY_BACKLOG_TEXT.split("## Очередь Оператора")[0]

    message = draft_refusal(apply_box, draft)

    assert "Очередь Оператора" in message, message
    assert before == origin_head(apply_box)
    assert origin_backlog(apply_box) == APPLY_BACKLOG_TEXT
    assert notes.pending_notes() == []


def test_apply_draft_with_section_heading_but_no_table_refuses(apply_box):
    """Раздел на месте, а таблицы у него нет — тоже отказ (требование
    11: «у каждого есть таблица»).

    Ловит мутацию: проверка ограничена наличием заголовка раздела
    (`heading in draft`) — раздел без таблицы проходит, и следующий
    `note` в него отказывает уже на живом документе.
    """
    draft = APPLY_BACKLOG_TEXT.replace(
        "| П | Действие | Условие |\n|---|---|---|\n"
        "| 1 | Действие А | сразу |\n", "текста таблицы больше нет\n")

    message = draft_refusal(apply_box, draft)

    assert "Очередь Оператора" in message, message
    assert origin_backlog(apply_box) == APPLY_BACKLOG_TEXT
    assert notes.pending_notes() == []


def test_apply_draft_with_widened_header_refuses(apply_box):
    """Шапка «Копилки» на одну колонку шире, чем в origin, —
    именованный отказ до коммита (требование 11).

    Ловит мутацию: сверяется только наличие разделов, а число колонок
    шапки — нет; расширенная шапка уезжает в документ, и все
    существующие строки раздела перестают ей соответствовать.
    """
    before = origin_head(apply_box)

    message = draft_refusal(
        apply_box, APPLY_BACKLOG_TEXT.replace(KOPILKA_HEADER, KOPILKA_HEADER_WIDE))

    assert "Копилка" in message, message
    assert before == origin_head(apply_box)
    assert origin_backlog(apply_box) == APPLY_BACKLOG_TEXT
    assert notes.pending_notes() == []


def test_apply_draft_equal_to_origin_refuses_instead_of_hanging_in_pending(apply_box):
    """Заготовка байт-в-байт равна содержимому в origin — именованный
    отказ, а не три провала `git commit` с удержанием записи (тот же
    класс, что отказ «содержимое уже совпадает» у `doc-commit`).

    Ловит мутацию: проверка отсутствует — `_run` исчерпывает попытки,
    удерживает запись и отказывает текстом «не удалось отправить»;
    тест красен на непустом `pending_notes()`.
    """
    message = draft_refusal(apply_box, APPLY_BACKLOG_TEXT)

    assert "совпадает" in message, message
    assert notes.pending_notes() == []


def test_apply_missing_message_and_missing_file_refuse_naming_the_flag(apply_box):
    """`--apply` без `--message` и с пустым `--message` — отказ,
    называющий `--message` (требование 9); несуществующий файл — отказ,
    называющий `--apply`, а не соседний `--from` `doc-commit`.

    Ловит мутацию: `--message` получает дефолт либо пробельная строка
    проходит — документ заменяется коммитом без основания; текст
    отказа о файле захардкожен на `--from`, и Оператор читает про флаг,
    которым не пользовался.
    """
    before = origin_head(apply_box)
    source = str(source_file(apply_box, draft_with_extra_row()))

    assert "--message" in refusal("--apply", source)
    assert "--message" in refusal("--apply", source, "--message", "  ")
    missing = refusal("--apply", str(Path(apply_box.source_dir) / "нет.md"),
                      "--message", REASON)
    assert "--apply" in missing, missing
    assert "не найден" in missing, missing

    assert before == origin_head(apply_box)
    assert notes.pending_notes() == []


# ------------------------------------------- note --apply: окно тишины

def test_apply_open_window_holds_apply_until_flush(apply_box):
    """Окно тишины открыто: `--apply` не двигает origin, печатает
    причину удержания и оставляет ОДНУ запись в общем каталоге
    удержанных; `note --flush` доводит заготовку до origin целиком
    (требование 10).

    Ловит мутацию: `--apply` проверяет окно ПОСЛЕ коммита и push (или
    не проверяет вовсе, отдельным от `_run` путём) — документ уезжает
    в origin сразу, ещё до `--flush`.
    """
    draft = draft_with_extra_row()
    open_silence_window()
    before = origin_head(apply_box)

    output = apply_draft(apply_box, draft, "разнос под окном")

    assert before == origin_head(apply_box)
    assert "удержан" in output, output
    assert len(notes.pending_notes()) == 1, notes.pending_notes()
    assert notes.pending_notes()[0]["kind"] == notes.APPLY_KIND

    capture(notes.cmd_note, ["--flush"])

    assert origin_backlog(apply_box) == draft
    assert notes.pending_notes() == []


def test_apply_held_record_is_self_sufficient_without_the_source_file(apply_box):
    """Удержанная запись несёт содержимое заготовки, а не путь к
    файлу: файл удалён до флаша — содержимое всё равно приезжает в
    origin (тот же контракт, что у удержанной записи `doc-commit`).

    Ловит мутацию: запись хранит путь `--apply` и перечитывает файл
    при флаше — запись висит, а документ в origin остаётся старым.
    """
    draft = draft_with_extra_row()
    source = source_file(apply_box, draft)
    open_silence_window()
    capture(notes.cmd_note, ["--apply", str(source),
                             "--message", "под окном"])
    source.unlink()

    capture(notes.cmd_note, ["--flush"])

    assert origin_backlog(apply_box) == draft
    assert notes.pending_notes() == []


# ------------------------------------------------ формат строки: формы

def test_row_framed_and_bare_text_give_the_same_row():
    """Текст с обрамляющими чертами и тот же текст без них дают
    байт-в-байт одну и ту же строку таблицы — и это форма
    `| ячейка | … |`, которую документ несёт сегодня (требование 1).

    Ловит мутацию: обрамление снимается безусловным `text.strip("|")`
    либо не снимается вовсе — обрамлённая форма тогда либо отказывает
    по числу колонок, либо даёт строку с пустыми крайними ячейками, и
    равенство двух строк ломается.
    """
    assert inserted_row(FRAMED) == inserted_row(BARE)
    assert inserted_row(FRAMED) == FRAMED


def test_row_single_leading_pipe_is_not_treated_as_framing():
    """Черта только в начале (обрамления нет) — ячейки считаются как
    есть: `| 2 | 27.09 | текст | где | состояние` даёт ШЕСТЬ ячеек
    против пятиколоночной шапки, то есть отказ (требование 1: черты
    снимаются, только когда текст И начинается, И заканчивается ими).

    Ловит мутацию: снятие обрамления сделано через `strip("|")` или
    `lstrip("|")` — односторонняя черта тогда молча съедается, и
    строка с лишней пустой ячейкой уезжает в документ.
    """
    with pytest.raises(SystemExit, match=re.escape("5")):
        notes._apply_insert(ROW_BACKLOG_TEXT, "копилка", f"| {BARE}")


def test_row_cell_count_is_checked_after_unframing():
    """Обрамлённая строка из трёх ячеек против пятиколоночной шапки —
    отказ, называющий ожидаемое число колонок (требование 2).

    Ловит мутацию: число ячеек сверяется с шапкой ДО снятия
    обрамления — три ячейки плюс два пустых обрамляющих поля дают
    ровно пять, и строка молча вставляется вместо отказа.
    """
    with pytest.raises(SystemExit, match=re.escape("5")):
        notes._apply_insert(ROW_BACKLOG_TEXT, "копилка", "| 1 | 2 | 3 |")


# ---------------------------------------- формат строки: приоритет вставки

@pytest.mark.parametrize("value", ["П2", "п2", " П 2 ", "2"])
def test_row_letter_and_digit_forms_both_give_the_digit(value):
    """Ячейка приоритета «П2», «п2», « П 2 » и «2» дают в документе
    «2» (требования 3, 5).

    Ловит мутацию: нормализация применена только к пути
    `--set-priority` и забыта у вставки строки — буква приезжает в
    документ как есть.
    """
    row = inserted_row(f"{value} | 27.09 | текст | где | состояние")
    assert cells(row)[0] == "2", row


@pytest.mark.parametrize("value", ["высокий", "5", "0", "П7", ""])
def test_row_unrecognized_priority_refuses_naming_a_valid_form(value):
    """«высокий», «5», «0», «П7» и пустая ячейка — отказ, текст
    которого несёт пример допустимой формы (требование 4); диапазон
    1..4 не расширяется вместе с приёмом формы «П<цифра>».

    Ловит мутацию: разбор стал `int(text.lstrip("Пп"))` без сверки
    границ — «5» и «П7» проходят вместо отказа; либо пример формы из
    текста отказа убран (`assertRegex(…, r"[1-4]")` проходил и на
    прежнем тексте «вне диапазона 1..4», замечание R1-F5 ревью итерации
    1) — тест красен на отсутствии `PRIORITY_FORM_EXAMPLE`.
    """
    with pytest.raises(SystemExit,
                       match=re.escape(notes.PRIORITY_FORM_EXAMPLE)):
        notes._apply_insert(
            ROW_BACKLOG_TEXT, "копилка",
            f"{value} | 27.09 | текст | где | состояние")


def test_row_section_without_priority_column_is_not_normalized():
    """Раздел без колонки «П» нормализации приоритета не получает:
    «высокий» в первой колонке «Бэклога» — не отказ, а обычный текст
    (требование 5, «раздел без такой колонки нормализации не
    получает»); дата в колонке «Дата» того же раздела при этом
    нормализуется.

    Ловит мутацию: колонка приоритета определяется НОМЕРОМ (нулевой
    ячейкой), а не заголовком шапки — тест красен на `SystemExit`
    вместо вставленной строки.
    """
    row = inserted_row("высокий | 22.09.2026", NO_PRIORITY_TEXT, "бэклог",
                       "высокий")
    assert cells(row) == ["высокий", "22.09"], row


# --------------------------------------------- формат строки: дата вставки

@pytest.mark.parametrize("given, expected", [
    ("22.09.2026", "22.09"), ("27.09", "27.09"),
    ("22.9.26", "22.9"), ("сразу", "сразу"),
])
def test_row_year_is_dropped_short_form_and_non_dates_survive(given, expected):
    """Ячейка даты «22.09.2026» теряет год, «27.09» не меняется,
    «сразу» (датой не является ни в одной форме) остаётся как есть и
    отказом не считается (требование 6).

    Ловит мутацию: ячейка разбирается строго как «ДД.ММ.ГГГГ»
    (`cell.split(".")` с обращением к третьему элементу) — уже
    краткая форма теряет содержимое либо роняет команду; отказ на
    не-дату красит третий случай.
    """
    row = inserted_row(f"2 | {given} | текст | где | состояние")
    assert cells(row)[1] == expected, row


def test_row_date_shaped_cell_of_another_column_is_untouched():
    """Дата с годом в колонке, чей заголовок не «Дата», не трогается:
    раздел «Очередь Оператора» колонки «Дата» не несёт вовсе
    (требование 6).

    Ловит мутацию: нормализация даты применяется к ЛЮБОЙ ячейке,
    похожей на дату, вместо ячейки названной колонки — «22.09.2026» в
    колонке «Действие» теряет год.
    """
    row = inserted_row("П3 | 22.09.2026 | сразу", NO_DATE_TEXT, "очередь",
                       "22.09.2026")
    assert cells(row) == ["3", "22.09.2026", "сразу"], row


# ------------------------------------------ формат строки: --set-priority

@pytest.mark.parametrize("value", ["П2", "2"])
def test_row_set_priority_both_forms_write_the_digit(value):
    """`--set-priority` с «П2» и с «2» — в документе «2» (требование
    5, второй путь нормализации).

    Ловит мутацию: ведущая «П» снимается при ПРОВЕРКЕ, а в файл
    пишется исходный текст ячейки (`cells[col] = text` вместо
    нормализованного значения).
    """
    new_text, _key = notes._apply_set_priority(
        ROW_BACKLOG_TEXT, "СОСТОЯНИЕЕСТЬ", value)
    row = [line for line in new_text.split("\n")
           if "СОСТОЯНИЕЕСТЬ" in line][0]
    assert cells(row)[0] == "2", row


@pytest.mark.parametrize("value", ["5", "П7", "0", "высокий"])
def test_row_set_priority_range_is_not_widened_by_the_letter_form(value):
    """«5», «П7», «0» и «высокий» по-прежнему отказ с примером формы.

    Ловит мутацию: сверка границ снята вместе с заменой `int(text)` на
    разбор формы «П<цифра>» — значения вне 1..4 проходят; либо пример
    формы из текста отказа убран на этом втором пути нормализации
    (замечание R1-F5 ревью итерации 1).
    """
    with pytest.raises(SystemExit,
                       match=re.escape(notes.PRIORITY_FORM_EXAMPLE)):
        notes._apply_set_priority(ROW_BACKLOG_TEXT, "СОСТОЯНИЕЕСТЬ", value)


def test_row_set_priority_section_without_priority_column_refuses_instead_of_cell_zero():
    """Раздел без колонки «П» — именованный отказ «менять негде», а не
    молчаливая правка нулевой ячейки (требование 5).

    Ловит мутацию: колонка приоритета по-прежнему `cells[0]` — вместо
    отказа затирается колонка «Кандидат».
    """
    with pytest.raises(SystemExit, match=re.escape(notes.PRIORITY_HEADER)):
        notes._apply_set_priority(NO_PRIORITY_TEXT, "Кандидат A", "2")


# ------------------------------------- формат строки: дописка состояния

def test_row_filled_cell_keeps_old_text_and_gets_dated_separator():
    """Дописка к непустой ячейке даёт `<прежний текст> — <ДД.ММ>:
    <новый текст>`: прежний текст цел, новый отделён разделителем с
    текущей датой пульта (требование 7).

    Ловит мутацию: прежний текст затёрт (дописка реализована через
    путь `--set-state`, заменяющий ячейку целиком) либо разделителя
    нет вовсе (прежнее склеивание одним пробелом) — `fullmatch` не
    проходит или группа «old» не совпадает.
    """
    cell = appended_cell("СОСТОЯНИЕЕСТЬ", "ДОПИСКА")

    match = STATE_FILLED.fullmatch(cell)
    assert match is not None, cell
    assert match.group("old") == "прежнее состояние", cell
    assert match.group("new") == "ДОПИСКА", cell
    assert match.group("stamp") == notes._today_stamp(), cell


@pytest.mark.parametrize("key", ["СОСТОЯНИЕПУСТО", "СОСТОЯНИЕПРОЧЕРК"])
def test_row_empty_and_dash_cells_get_no_leading_separator(key):
    """Дописка к пробельной ячейке и к ячейке с прочерком «—» даёт
    `<ДД.ММ>: <новый текст>` без ведущего разделителя (требование 7).

    Ловит мутацию: пустой признан только пробельный случай, прочерк
    «—» трактуется как обычный текст — ячейка получает `— — <ДД.ММ>:
    …`, и `fullmatch` без ведущего разделителя её не принимает.
    """
    cell = appended_cell(key, "ДОПИСКА")

    match = STATE_EMPTY.fullmatch(cell)
    assert match is not None, cell
    assert match.group("new") == "ДОПИСКА", cell


def test_row_second_append_keeps_the_first_one_whole():
    """Вторая дописка не съедает первую: обе даты и оба текста в
    ячейке (требование 7 — «прежний текст ячейки сохраняется
    целиком», в том числе уже дописанный).

    Ловит мутацию: разделитель ставится, но прежний текст обрезается
    по первому разделителю (попытка «нормализовать» ячейку) — первая
    дописка теряется.
    """
    once, _key = notes._apply_append(ROW_BACKLOG_TEXT, "СОСТОЯНИЕПУСТО",
                                     "ПЕРВАЯ")
    twice, _key = notes._apply_append(once, "СОСТОЯНИЕПУСТО", "ВТОРАЯ")

    cell = cells([line for line in twice.split("\n")
                  if "СОСТОЯНИЕПУСТО" in line][0])[-1]
    assert "ПЕРВАЯ" in cell
    assert "ВТОРАЯ" in cell


# ---------------------------------------- формат строки: --state = --append
# `cmd_note` читает `merge_locks`/`tasks` на каждый вызов (окно тишины), а
# сам `_run` здесь подменён — до git дело не доходит.

def test_row_state_and_append_build_the_same_request(schema_root, no_role):
    """`note --state <ключ> --text …` и `note --append <ключ> --text …`
    строят одну и ту же запись вида `append`.

    Ловит мутацию: `--state` принят отдельным флагом и ведёт в свой
    путь (например в `set-state`, заменяющий ячейку целиком) — записи
    перестают совпадать.
    """
    seen = []
    with mock.patch.object(notes, "_run", side_effect=seen.append):
        notes.cmd_note(["--state", "КЛЮЧ", "--text", "текст"])
        notes.cmd_note(["--append", "КЛЮЧ", "--text", "текст"])

    assert seen[0] == seen[1], seen
    assert seen[0]["kind"] == "append", seen


def test_row_state_without_text_refuses_naming_the_flag_that_was_used(schema_root, no_role):
    """`--state` без `--text` — отказ, называющий `--state`, а не
    соседний `--append`.

    Ловит мутацию: текст отказа захардкожен на `--append` — Оператор
    читает про флаг, которым не пользовался.
    """
    with pytest.raises(SystemExit, match=re.escape("--state")):
        notes.cmd_note(["--state", "КЛЮЧ"])


# ------------------------------------------ окно тишины по проекту задачи
# Сценарий целиком через публичную `notes.cmd_note` на настоящем bare
# `origin`: решение окна наблюдается по тому, ушла ли запись в
# `origin/main` сразу (окна нет), либо удержана с текстом «заметка
# удержана: <причина>; отправка — …». Проект задачи — колонка `target`
# строки задачи; внешний проект разрешён записью `config.TARGETS`
# песочницы (`declare_target`), неразрешённый — записи там нет.

def test_project_ac1_external_task_in_every_window_state_does_not_hold(window_box):
    """Задача разрешённого внешнего проекта проходит по очереди все
    состояния `config.NOTE_SILENCE_WINDOW_STATES`; в каждом обычный
    `note` уходит в `origin/main` сразу, удержанных записей нет.

    Ловит мутацию: перебор задач окна не фильтрует по проекту (как до
    правки) — первая же запись удержана текстом «задача <id> в
    состоянии …», `origin` её не видит."""
    tid = task_id(window_box)
    insert_project_task(tid, config.NOTE_SILENCE_WINDOW_STATES[0],
                        window_box.external)
    for state in config.NOTE_SILENCE_WINDOW_STATES:
        set_state(tid, state)
        marker, out = window_note(window_box)
        assert_pushed(window_box, marker, out,
                      f"внешняя задача {tid} в {state}")


def test_project_ac2_live_holder_with_external_task_does_not_hold(window_box):
    """Живой держатель мьютекса мержа, чья задача — задача внешнего
    разрешённого проекта (сама в `merge_gate`); других триггеров нет —
    `note` пушит сразу.

    Ловит мутацию: держатель мьютекса учитывается без проверки
    проекта его задачи (как до правки) — запись удержана текстом
    «держатель merge-окна жив …»."""
    tid = task_id(window_box)
    state = ("merge_gate" if "merge_gate" in config.NOTE_SILENCE_WINDOW_STATES
             else window_box.rng.choice(OUTSIDE_WINDOW))
    insert_project_task(tid, state, window_box.external)
    live_lock(window_box, tid)
    marker, out = window_note(window_box)
    assert_pushed(window_box, marker, out, f"держатель с внешней задачей {tid}")


def test_project_ac3_artel_task_in_every_window_state_holds_with_old_text(window_box):
    """Задача артели — с `target` артели, с пустой строкой и с NULL —
    в каждом состоянии окна удерживает запись; причина удержания
    буквально «задача <id> в состоянии <state>».

    Ловит мутацию: принадлежность артели проверяется сравнением
    `target == DEFAULT_TARGET` вместо `repo_context.is_artel` — пустой
    или NULL `target` уходит в `resolve`, получает `None`, и причина
    становится «проект задачи не определён» вместо прежнего текста
    (либо, при фильтре «только известные проекты», запись уходит в
    `origin`)."""
    for target in (config.DEFAULT_TARGET, "", None):
        tid = task_id(window_box)
        insert_project_task(tid, config.NOTE_SILENCE_WINDOW_STATES[0], target)
        for state in config.NOTE_SILENCE_WINDOW_STATES:
            set_state(tid, state)
            marker, out = window_note(window_box)
            ctx = f"задача артели {tid} target={target!r} в {state}"
            assert held_reason(window_box, marker, out, ctx) == \
                f"задача {tid} в состоянии {state}", \
                f"{ctx}; зерно {window_box.seed}"
        set_state(tid, window_box.rng.choice(OUTSIDE_WINDOW))


def test_project_ac3_live_holder_with_artel_task_holds_with_old_text(window_box):
    """Живой держатель мьютекса с задачей артели (`target` артели,
    пустой, NULL; сама задача вне состояний окна) удерживает запись;
    причина буквально «держатель merge-окна жив (сессия <s>, задача
    <id>)».

    Ловит мутацию: проект задачи держателя берётся сравнением колонки
    `target` с `DEFAULT_TARGET` (пустая/NULL — не артель) либо
    держатель вовсе не проверяется — причина иная или запись ушла в
    `origin`."""
    for target in (config.DEFAULT_TARGET, "", None):
        tid = task_id(window_box)
        insert_project_task(tid, window_box.rng.choice(OUTSIDE_WINDOW), target)
        session = live_lock(window_box, tid)
        marker, out = window_note(window_box)
        ctx = f"держатель {session} с задачей артели {tid} target={target!r}"
        assert held_reason(window_box, marker, out, ctx) == \
            f"держатель merge-окна жив (сессия {session}, задача {tid})", \
            f"{ctx}; зерно {window_box.seed}"
        store.release_merge_lock(store.db(), session, os.getpid())


def test_project_ac3a_external_holder_does_not_mask_artel_task(window_box):
    """Живой держатель с внешней задачей и одновременно задача артели в
    `in_dev`: запись удержана, причина — «задача <id артели> в
    состоянии in_dev».

    Ловит мутацию: держатель с внешней задачей даёт досрочный
    `return None` вместо перехода к перебору задач — запись уходит в
    `origin` (а до правки причина — текст держателя, не задачи)."""
    ext = task_id(window_box)
    insert_project_task(ext, window_box.rng.choice(OUTSIDE_WINDOW),
                        window_box.external)
    live_lock(window_box, ext)
    art = task_id(window_box)
    insert_project_task(art, "in_dev", config.DEFAULT_TARGET)
    marker, out = window_note(window_box)
    ctx = f"внешний держатель {ext} + задача артели {art}"
    assert held_reason(window_box, marker, out, ctx) == \
        f"задача {art} в состоянии in_dev", f"{ctx}; зерно {window_box.seed}"


def test_project_ac3b_earlier_external_task_does_not_mask_artel_task(window_box):
    """Задача внешнего проекта в `verifying` с id МЕНЬШЕ id задачи
    артели в `in_dev` (перебор по возрастанию id встречает внешнюю
    первой): запись удержана, причина — «задача <id артели> в
    состоянии in_dev».

    Ловит мутацию: первая встреченная задача окна внешнего проекта
    даёт досрочный `return None` — запись уходит в `origin` (а до
    правки причина называет внешнюю задачу)."""
    ext = task_id(window_box, prefix="A")
    art = task_id(window_box, prefix="B")
    assert ext < art
    insert_project_task(ext, "verifying", window_box.external)
    insert_project_task(art, "in_dev", config.DEFAULT_TARGET)
    marker, out = window_note(window_box)
    ctx = f"внешняя {ext} в verifying + задача артели {art}"
    assert held_reason(window_box, marker, out, ctx) == \
        f"задача {art} в состоянии in_dev", f"{ctx}; зерно {window_box.seed}"


def test_project_ac4_unresolved_project_holds_naming_task_and_reason(window_box):
    """Три случая по отдельности: (1) задача с неразрешаемым проектом
    в случайном состоянии окна; (2) живой держатель, чья задача (вне
    состояний окна) с неразрешаемым проектом; (3) живой держатель,
    строки задачи которого нет в БД. В каждом запись удержана, причина
    содержит id задачи (держателя — id его задачи) и «проект задачи не
    определён».

    Ловит мутацию: неизвестный проект молча приравнен к артели
    (`store.task_target` с умолчанием `DEFAULT_TARGET` для
    отсутствующей строки, `resolve(...) is None` трактуется как
    артель) — запись удержана прежним текстом без «проект задачи не
    определён»; либо приравнен к внешнему проекту — запись ушла в
    `origin`."""
    cases = ("задача в окне", "держатель с задачей", "держатель без строки")
    for case in cases:
        tid = task_id(window_box)
        session = None
        if case == "задача в окне":
            insert_project_task(
                tid, window_box.rng.choice(config.NOTE_SILENCE_WINDOW_STATES),
                window_box.ghost)
        elif case == "держатель с задачей":
            insert_project_task(tid, window_box.rng.choice(OUTSIDE_WINDOW),
                                window_box.ghost)
            session = live_lock(window_box, tid)
        else:
            session = live_lock(window_box, tid)
        marker, out = window_note(window_box)
        ctx = f"{case}: {tid}"
        reason = held_reason(window_box, marker, out, ctx)
        msg = f"{ctx}; причина {reason!r}; зерно {window_box.seed}"
        assert tid in reason, msg
        assert "проект задачи не определён" in reason, msg
        if session is not None:
            store.release_merge_lock(store.db(), session, os.getpid())
        if case == "задача в окне":
            set_state(tid, window_box.rng.choice(OUTSIDE_WINDOW))
        notes.cmd_note(["--flush"])


def test_project_ac5_unresolved_project_outside_window_does_not_hold(window_box):
    """Задача с неразрешаемым проектом в каждом состоянии вне окна
    (`done`, `killed`, …) — других триггеров нет — `note` пушит сразу.

    Ловит мутацию: проверка проекта стоит раньше проверки состояния
    (неразрешаемый проект открывает окно в любом состоянии) — запись
    удержана с причиной «проект задачи не определён»."""
    tid = task_id(window_box)
    insert_project_task(tid, OUTSIDE_WINDOW[0], window_box.ghost)
    for state in OUTSIDE_WINDOW:
        set_state(tid, state)
        marker, out = window_note(window_box)
        assert_pushed(window_box, marker, out,
                      f"неразрешённая задача {tid} в {state}")
