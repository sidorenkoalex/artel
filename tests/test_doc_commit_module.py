"""Тесты `doc-commit` и сверки удержанной записи по базе
(`orchestrator/notes.py`; волна 1б сведения тестов, SPEC
01M5PCB66D936FDGG7H09CVGA1; ADR-0027 пп. 2, 3, 8).

Свод шести прежних файлов: `tests/test_doc_commit.py` (команда
`doc-commit`, tasks/01M2XMCG167615YS9EZD9TYJWV: допустимые пути,
сообщение коммита, сверка базы с пином, окно тишины, общий флаш обоих
видов записей), `tests/test_doc_commit_suite_gate.py` (гейт полного набора
`tests/` перед коммитом конфигурации Оператора, tasks/
01M3HST4SGX0SPKAGNHVY7DWHM, требования 13-16), долгоживущего
`tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py` (удержанный
`doc-commit` сверяется с базой сборки; `note --pending`/`--drop-pending`),
`tests/test_doc_commit_held_base.py` (свойства той же задачи сверх
долгоживущего файла), долгоживущего
`tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py` (`doc-commit` файла
карточек `knowledge/<имя>.yaml`) и `tests/test_notes_batch_flush_edges.py`
(края пакетного сброса, SPEC 01M5N8A5JBEQ15DCHDP95EBDZR). Оба долгоживущих
файла удалены решением Оператора (ADR-0020 п. 8), их свойства перенесены
сюда. Доказательство неослабления — таблицы `mutation-run` «до» и «после»
в PLAN задачи.

Стенды на настоящем git (поверх `real_git`): `doc_box` (бывший
`DocCommitSandbox`: главная копия, синхронная с bare `origin`, посеянный
ЗЕЛЁНЫЙ набор `tests/`, клон артели из origin), `held_box` (бывший
`HeldBaseSandbox`: случайные тексты, зерно печатается и входит в текст
провала), `unit_box` (бывший `HeldBaseUnitSandbox`) и `knowledge_box`
(бывший `KnowledgeDocCommitSandbox`: шпион полного набора, случайные имена,
зерно печатается).
"""
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import acceptance, artel, config, notes, store
from orchestrator import knowledge_cards as kc
from tests.sandbox import capture, clone_artel_from_origin, init_bare_origin

# --- `doc-commit`: стенд `doc_box` ---

BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое УНИКАЛЬНЫЙКЛЮЧ | orchestrator/x.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |
"""
ROADMAP_TEXT = "# Роадмап\n\nСтарый раздел.\n"
ROLES_TEXT = "developer:\n  model: opus\n"
DOC_REL = "docs/roadmap.md"

# Тривиально ЗЕЛЁНЫЙ набор `tests/` в дереве стенда
# (01M3HST4SGX0SPKAGNHVY7DWHM, требования 13-14): с этой задачи
# `doc-commit` пути из `DOC_COMMIT_CONFIG_PATHS` гоняет полный набор
# перед отправкой, и дерево БЕЗ `tests/` — это «набор не запустился
# вовсе», то есть отказ. Стенд несёт набор, чтобы сценарии про сообщение
# коммита, сверку базы и окно тишины остались про свой предмет; красный
# и отсутствующий набор — предмет тестов гейта полного набора ниже.
GREEN_SUITE_REL = "tests/test_green.py"
GREEN_SUITE_TEXT = '''"""Набор стенда: зелёный при любом содержимом дерева."""


def test_green():
    assert True
'''

# --- гейт полного набора ---

CONFIG_REL = notes.DOC_COMMIT_CONFIG_PATHS[0]
NEW_CONFIG_TEXT = "developer:\n  model: sonnet\n"
MESSAGE = "поворот крутилки"
ACCEPT_REASON = "красный тест не про эту правку, чиню отдельной задачей"

RED_SUITE_TEXT = '''"""Набор стенда: красен всегда."""


def test_seed_always_red():
    assert False, "набор красный намеренно"
'''

# --- сверка удержанной записи по базе: стенд `held_box` ---

GUIDE_REL = "docs/guide.md"
HELD_BACKLOG_TEXT = """## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое | orchestrator/x.py |
"""
LEGACY_KEYS = {"kind", "path", "content", "message", "accept_red"}
STALE_PHRASE = "файл изменился в origin после сборки записи"
REBUILD_PHRASE = "собери заново от origin"
NO_BASE_PHRASE = "база не сохранена"
ALPHABET = "абвгдежзиклмнопрстуфхцчшщэюяabcdefghijklmnopqrstuvwxyz0123456789"
TIME_RE = re.compile(r"\d{1,2}:\d{2}|\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}")

# --- файл карточек `knowledge/<имя>.yaml`: стенд `knowledge_box` ---

LATIN = "abcdefghijklmnopqrstuvwxyz"


def run_command(fn, argv) -> str:
    """Вывод команды (stdout и stderr) вместе с текстом отказа, если он был."""
    buf = io.StringIO()
    exit_text = ""
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(list(argv))
        except SystemExit as exc:
            exit_text = "" if exc.code is None else str(exc.code)
    return buf.getvalue() + "\n" + exit_text


def run_command_exited(fn, *args) -> tuple:
    """(вывод вместе с текстом отказа, был ли выход `SystemExit`)."""
    buf = io.StringIO()
    exit_text, exited = "", False
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(*args)
        except SystemExit as exc:
            exited = True
            exit_text = "" if exc.code is None else str(exc.code)
    return buf.getvalue() + "\n" + exit_text, exited


def _no_role(box) -> None:
    role_patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
    role_patcher.start()
    box.addCleanup(role_patcher.stop)


def _temp_dir(box) -> str:
    path = tempfile.mkdtemp()
    box.addCleanup(shutil.rmtree, path, ignore_errors=True)
    return path


# ------------------------------------------------------------- фикстуры

@pytest.fixture
def doc_box(real_git):
    """Главная копия с `docs/backlog.md`, `docs/roadmap.md`, `roles.yaml`,
    синхронная с bare `origin`: сверка базы по умолчанию проходит, окно
    тишины закрыто (БД пуста)."""
    box = real_git
    _no_role(box)
    box.origin = _temp_dir(box)
    init_bare_origin(box.origin, box.git)
    box.git("remote", "add", "origin", box.origin)
    for rel, text in ((notes.BACKLOG_REL, BACKLOG_TEXT),
                      (DOC_REL, ROADMAP_TEXT),
                      ("roles.yaml", ROLES_TEXT),
                      (GREEN_SUITE_REL, GREEN_SUITE_TEXT)):
        path = box.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    box.git("add", "-A")
    box.git("commit", "-q", "-m", "документы")
    box.git("push", "-q", "origin",
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    # Клон артели из origin, как его заводит `init` (ADR-0021 п.1,
    # этап 2): команды Оператора коммитят и пушат через него.
    clone_artel_from_origin(box.origin)
    box.source_dir = _temp_dir(box)
    return box


@pytest.fixture
def held_box(real_git):
    """Главная копия с `docs/backlog.md`, двумя документами и bare origin,
    синхронным с пином; окно тишины закрыто."""
    box = real_git
    _no_role(box)
    box.seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {box.seed}")
    box.rng = random.Random(box.seed)
    box.origin = _temp_dir(box)
    box.git("init", "-q", "--bare", box.origin)
    box.git("remote", "add", "origin", box.origin)
    box.doc_text = f"# Роадмап\n\n{words(box, 6)}\n"
    box.guide_text = f"# Руководство\n\n{words(box, 6)}\n"
    for rel, text in ((notes.BACKLOG_REL, HELD_BACKLOG_TEXT),
                      (DOC_REL, box.doc_text),
                      (GUIDE_REL, box.guide_text)):
        path = box.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    box.git("add", "-A")
    box.git("commit", "-q", "-m", "документы")
    push_main(box)
    # Клон артели из origin, как его заводит `init` (ADR-0021 п.1,
    # этап 2): команды Оператора коммитят и пушат через него.
    clone_artel_from_origin(box.origin)
    box.source_dir = _temp_dir(box)
    return box


@pytest.fixture
def unit_box(real_git):
    """Главная копия с одним `docs/roadmap.md`, без origin."""
    box = real_git
    _no_role(box)
    box.doc = box.root / "docs" / "roadmap.md"
    box.doc.parent.mkdir(parents=True, exist_ok=True)
    box.doc.write_text("# Роадмап\n", encoding="utf-8")
    box.git("add", "-A")
    box.git("commit", "-q", "-m", "документ")
    box.source_dir = _temp_dir(box)
    return box


@pytest.fixture
def knowledge_box(real_git):
    """Главная копия с документом и `roles.yaml`, синхронная с bare origin;
    клон артели из origin; окно тишины закрыто; шпион полного набора."""
    box = real_git
    _no_role(box)
    box.seed = random.SystemRandom().randrange(1 << 32)
    print(f"зерно: {box.seed}")
    box.rng = random.Random(box.seed)
    box.origin = _temp_dir(box)
    init_bare_origin(box.origin, box.git)
    box.git("remote", "add", "origin", box.origin)
    for rel, text in ((DOC_REL, "# Роадмап\n\nстарое\n"),
                      ("roles.yaml", ROLES_TEXT)):
        path = box.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    box.git("add", "-A")
    box.git("commit", "-q", "-m", "документы")
    box.git("push", "-q", "origin",
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    box.clone = clone_artel_from_origin(box.origin)
    box.source_dir = _temp_dir(box)
    suite = mock.patch.object(acceptance, "run_full_suite",
                              return_value=(True, "набор зелёный"))
    box.suite = suite.start()
    box.addCleanup(suite.stop)
    return box


# ------------------------------------------------- помощники `doc_box`

def source_file(box, text: str, name: str = "draft.md") -> Path:
    path = Path(box.source_dir) / name
    path.write_text(text, encoding="utf-8")
    return path


def doc_commit(*argv: str) -> str:
    return capture(notes.cmd_doc_commit, list(argv))


def origin_run(box, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", box.origin, *args],
                          capture_output=True, text=True)


def origin_head(box) -> str:
    res = origin_run(box, "rev-parse", config.MAIN_BRANCH)
    return res.stdout.strip() if res.returncode == 0 else ""


def origin_show_bytes(box, rel: str) -> bytes:
    res = subprocess.run(
        ["git", "-C", box.origin, "show", f"{config.MAIN_BRANCH}:{rel}"],
        capture_output=True)
    assert res.returncode == 0, res.stderr
    return res.stdout


def origin_show(box, rel: str) -> str:
    return origin_show_bytes(box, rel).decode("utf-8")


def origin_subject(box) -> str:
    res = origin_run(box, "log", "-1", "--format=%s", config.MAIN_BRANCH)
    return res.stdout.strip()


def main_copy_snapshot(box) -> tuple:
    return (box.git("rev-parse", "HEAD").strip(),
            box.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
            box.git("status", "--porcelain"))


def open_silence_window(task_id: str = "T-WIN") -> None:
    store.insert_task(store.db(), task_id, "окно тишины",
                      config.NOTE_SILENCE_WINDOW_STATES[0],
                      f"task/{task_id}", config.DEFAULT_TARGET, 10.0)


def close_silence_window(task_id: str = "T-WIN") -> None:
    conn = store.db()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()


def assert_refused(argv: list, phrase: str) -> None:
    with pytest.raises(SystemExit, match=re.escape(phrase)):
        notes.cmd_doc_commit(argv)


def push_foreign_change_past_the_pin(box, rel: str, text: str) -> None:
    (box.root / rel).write_text(text, encoding="utf-8")
    box.git("commit", "-a", "-q", "-m", "чужая правка")
    box.git("push", "-q", "origin",
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    box.git("reset", "-q", "--hard", "HEAD~1")


def hold_both_kinds(box) -> None:
    open_silence_window()
    capture(notes.cmd_note,
            ["копилка", "--text", "4 | 09.09 | из окна ОБЩИЙФЛАШ | o.py"])
    doc_commit(DOC_REL, "--from",
               str(source_file(box, "# Роадмап\n\nобщий флаш\n")),
               "--message", "общий флаш")
    kinds = sorted(p["kind"] for p in notes.pending_notes())
    assert kinds == [notes.DOC_COMMIT_KIND, "insert"]
    close_silence_window()


def assert_both_arrived(box) -> None:
    assert "ОБЩИЙФЛАШ" in origin_show(box, notes.BACKLOG_REL)
    assert origin_show(box, DOC_REL) == "# Роадмап\n\nобщий флаш\n"
    assert notes.pending_notes() == []


# --- гейт полного набора поверх `doc_box` ---

def reseed_suite(box, text: str | None) -> None:
    """Пересев набора `tests/` в дереве прогона: дерево рабочего
    репозитория `doc-commit` чекаутится из origin, поэтому набор меняется
    в главной копии и пушится."""
    path = box.root / GREEN_SUITE_REL
    if text is None:
        path.unlink()
    else:
        path.write_text(text, encoding="utf-8")
    box.git("add", "-A")
    box.git("commit", "-q", "-m", "набор tests/")
    box.git("push", "-q", "origin",
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")


def config_source(box) -> str:
    return str(source_file(box, NEW_CONFIG_TEXT, "config-draft.yaml"))


def commit_config(box, *extra: str) -> str:
    return doc_commit(CONFIG_REL, "--from", config_source(box),
                      "--message", MESSAGE, *extra)


def refuse_config(box, *extra: str) -> str:
    with pytest.raises(SystemExit) as ctx:
        notes.cmd_doc_commit([CONFIG_REL, "--from", config_source(box),
                              "--message", MESSAGE, *extra])
    return str(ctx.value)


def journal_text() -> str:
    rows = store.db().execute(
        "SELECT actor, action, detail FROM steps ORDER BY id").fetchall()
    return "\n".join(" ".join(str(col) for col in row) for row in rows)


def work_status(rel: str) -> str:
    """`git status --porcelain` пути в ОБЩЕМ рабочем репозитории
    `note`/`doc-commit`: грязный файл после отказа — предмет проверки
    (R1-F1 ревью итерации 1)."""
    work_dir = config.ROOT / ".artel" / "notes-work"
    return subprocess.run(
        ["git", "-C", str(work_dir), "status", "--porcelain", "--", rel],
        capture_output=True, text=True).stdout.strip()


def note_row(marker: str) -> str:
    return capture(notes.cmd_note,
                   ["копилка", "--text", f"4 | 09.09 | {marker} | o.py"])


def spy_suite(box, green: bool = True):
    """Шпион `acceptance.run_full_suite`: запоминает корень прогона и
    содержимое конфигурации в нём на момент вызова."""
    seen = []

    def run(root):
        seen.append((Path(root),
                     (Path(root) / CONFIG_REL).read_text(encoding="utf-8")))
        return green, "1 passed in 0.1s" if green else "FAILED шпион"

    patcher = mock.patch.object(notes.acceptance, "run_full_suite", run)
    patcher.start()
    box.addCleanup(patcher.stop)
    return seen


def push_foreign_config_change(box) -> None:
    """Сторонняя правка того же пути конфигурации, уехавшая в origin
    позже базы главной копии (тот же приём, что
    `push_foreign_change_past_the_pin`)."""
    (box.root / CONFIG_REL).write_text("developer:\n  model: haiku\n",
                                       encoding="utf-8")
    box.git("commit", "-a", "-q", "-m", "чужая правка конфигурации")
    box.git("push", "-q", "origin",
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    box.git("reset", "-q", "--hard", "HEAD~1")


def hold_config_without_base(box, text: str = NEW_CONFIG_TEXT) -> None:
    """Удержанная правка конфигурации без `held_base` — как запись
    старого формата либо после сетевого отказа fetch."""
    open_silence_window()
    doc_commit(CONFIG_REL, "--from",
               str(source_file(box, text, "config-draft.yaml")),
               "--message", "поворот крутилки")
    close_silence_window()
    pending = sorted((config.ROOT / ".artel" / "notes-pending").glob("*.json"))
    assert len(pending) == 1, pending
    record = json.loads(pending[0].read_text(encoding="utf-8"))
    record.pop(notes.HELD_BASE_KEY, None)
    pending[0].write_text(json.dumps(record, ensure_ascii=False),
                          encoding="utf-8")


# ------------------------------------------------- помощники `held_box`

def word(box, n: int = 8) -> str:
    return "".join(box.rng.choice(ALPHABET) for _ in range(n))


def words(box, k: int) -> str:
    return " ".join(word(box, box.rng.randrange(3, 10)) for _ in range(k))


def msg(box, text: str) -> str:
    return f"зерно: {box.seed}; {text}"


def push_main(box) -> None:
    box.git("push", "-q", "origin",
            f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")


def held_origin_git(box, *args) -> str:
    return box.git("-C", box.origin, *args)


def held_origin_head(box) -> str:
    return held_origin_git(box, "rev-parse", config.MAIN_BRANCH).strip()


def held_origin_show(box, rel: str) -> str | None:
    listed = held_origin_git(box, "ls-tree", "--name-only",
                             config.MAIN_BRANCH, "--", rel)
    if not listed.strip():
        return None
    return held_origin_git(box, "show", f"{config.MAIN_BRANCH}:{rel}")


def origin_blob(box, rel: str) -> str:
    return held_origin_git(box, "rev-parse",
                           f"{config.MAIN_BRANCH}:{rel}").strip()


def origin_commits_touching(box, since: str, rel: str) -> list:
    out = held_origin_git(box, "log", "--format=%H",
                          f"{since}..{config.MAIN_BRANCH}", "--", rel)
    return [line for line in out.split("\n") if line.strip()]


def advance_pin_and_origin(box, rel: str, text: str) -> None:
    """Чужая правка пути в главной копии, отправленная в origin: пин и
    голова origin совпадают — сверка с пином прошла бы."""
    path = box.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    box.git("add", rel)
    box.git("commit", "-q", "-m", "чужая правка")
    push_main(box)


def push_foreign_past_the_pin(box, rel: str, text: str) -> None:
    """Чужая правка пути в origin, пин остаётся прежним."""
    advance_pin_and_origin(box, rel, text)
    box.git("reset", "-q", "--hard", "HEAD~1")


def open_window() -> None:
    store.insert_task(store.db(), "T-WIN", "окно тишины",
                      config.NOTE_SILENCE_WINDOW_STATES[0], "task/t-win",
                      config.DEFAULT_TARGET, 10.0)


def close_window() -> None:
    conn = store.db()
    conn.execute("DELETE FROM tasks WHERE id=?", ("T-WIN",))
    conn.commit()


def held_source(box, text: str) -> Path:
    path = Path(box.source_dir) / f"{word(box)}.md"
    path.write_bytes(text.encode("utf-8"))
    return path


def held_doc_commit(box, rel: str, text: str) -> str:
    return run_command(notes.cmd_doc_commit,
                       [rel, "--from", str(held_source(box, text)),
                        "--message", words(box, 2)])


def hold_doc_commit(box, rel: str, text: str) -> None:
    before = len(notes.pending_notes())
    out = held_doc_commit(box, rel, text)
    assert len(notes.pending_notes()) == before + 1, (
        msg(box, f"запись не удержана: {out}"))


def hold_note(box, text: str) -> None:
    before = len(notes.pending_notes())
    out = run_command(notes.cmd_note, ["копилка", "--text", text])
    assert len(notes.pending_notes()) == before + 1, (
        msg(box, f"заметка не удержана: {out}"))


def pending_dir() -> Path:
    return config.ROOT / ".artel" / "notes-pending"


def pending_ids() -> list:
    return sorted(p.stem for p in pending_dir().glob("*.json"))


def pending_paths() -> list:
    return [r.get("path") for r in notes.pending_notes()]


def string_values(obj) -> list:
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in string_values(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in string_values(v)]
    return [obj] if isinstance(obj, str) else []


def stale_scenario(box, send) -> None:
    """Сценарий 02.10: запись удержана на базе B, затем путь изменён в
    origin и пин сдвинут на голову origin, затем отправка `send`."""
    base = box.git("rev-parse", f"HEAD:{DOC_REL}").strip()
    held_text = f"# Роадмап\n\n{words(box, 5)}\n"
    guide_text = f"# Руководство\n\n{words(box, 5)}\n"
    open_window()
    hold_doc_commit(box, DOC_REL, held_text)
    hold_doc_commit(box, GUIDE_REL, guide_text)
    foreign = box.doc_text + "".join(
        f"{words(box, 4)}\n" for _ in range(box.rng.randrange(3, 22)))
    advance_pin_and_origin(box, DOC_REL, foreign)
    blob = origin_blob(box, DOC_REL)
    before = held_origin_head(box)
    close_window()

    out = send()

    assert STALE_PHRASE in out, msg(box, out)
    assert REBUILD_PHRASE in out, msg(box, out)
    assert base[:7] in out, msg(box, f"база {base} не названа: {out}")
    assert blob[:7] in out, msg(box, f"blob origin {blob} не назван: {out}")
    assert held_origin_show(box, DOC_REL) == foreign, msg(box, out)
    assert origin_commits_touching(box, before, DOC_REL) == [], msg(box, out)
    assert DOC_REL in pending_paths(), msg(box, out)
    assert held_origin_show(box, GUIDE_REL) == guide_text, msg(box, out)
    assert GUIDE_REL not in pending_paths(), msg(box, out)


def hold_legacy(box, text: str) -> None:
    """Запись прежнего формата — без поля базы, как до задачи
    01M3Y75X6K2ZMD85971TCWV41E."""
    d = pending_dir()
    d.mkdir(parents=True, exist_ok=True)
    name = f"{int(time.time() * 1000):013d}-{uuid.uuid4().hex[:8]}.json"
    (d / name).write_text(json.dumps(
        {"kind": notes.DOC_COMMIT_KIND, "path": DOC_REL, "content": text,
         "message": words(box, 2)}, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------- помощники `unit_box`

def write_pending(record: dict) -> str:
    d = pending_dir()
    d.mkdir(parents=True, exist_ok=True)
    record_id = f"{int(time.time() * 1000):013d}-abcdef01"
    (d / f"{record_id}.json").write_text(
        json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return record_id


# -------------------------------------------- помощники `knowledge_box`

def name(box) -> str:
    return "".join(box.rng.choice(LATIN)
                   for _ in range(box.rng.randrange(4, 10)))


def valid_text(box) -> str:
    lines = ["cards:"]
    for _ in range(box.rng.randrange(2, 4)):
        lines += [f"  {name(box)}:", f"    where: [{name(box)}/*.py]",
                  f"    rule: правило {name(box)}",
                  f"    why: причина {name(box)}"]
    return "\n".join(lines) + "\n"


def invalid_text(box) -> str:
    key = name(box)
    card = (f"  {key}:\n    where: [a.py]\n    rule: правило\n"
            f"    why: причина\n")
    variants = (
        "cards:\n" + card + card,
        "cards:\n" + card.replace("    why:", "    owner: x\n    why:"),
        "cards:\n" + card.replace("    rule: правило", '    rule: ""'),
        "cards:\n" + card.replace(f"  {key}:", f"  {key.upper()}_x:"),
        f"{name(box)}: x\ncards:\n" + card,
    )
    return box.rng.choice(variants)


def kc_origin_head(box) -> str:
    return box.git("-C", box.origin, "rev-parse", config.MAIN_BRANCH).strip()


def origin_has(box, rel: str) -> bool:
    return bool(box.git("-C", box.origin, "ls-tree", "--name-only",
                        config.MAIN_BRANCH, "--", rel).strip())


def kc_origin_show(box, rel: str) -> str:
    return box.git("-C", box.origin, "show", f"{config.MAIN_BRANCH}:{rel}")


def kc_origin_subject(box) -> str:
    return box.git("-C", box.origin, "log", "-1", "--format=%s",
                   config.MAIN_BRANCH).strip()


def pending_files() -> list:
    d = config.ROOT / ".artel" / "notes-pending"
    return sorted(d.glob("*")) if d.exists() else []


def break_fetch(box) -> None:
    missing = Path(box.source_dir) / f"нет-{name(box)}"
    box.git("-C", str(box.clone), "remote", "set-url", "origin", str(missing))


def via_command(box, rel: str, text: str, message: str) -> tuple:
    source = Path(box.source_dir) / f"{name(box)}.yaml"
    source.write_bytes(text.encode("utf-8"))
    return run_command_exited(notes.cmd_doc_commit,
                              [rel, "--from", str(source), "--message", message])


def via_content(box, rel: str, text: str, message: str) -> tuple:
    return run_command_exited(notes.doc_commit_content, rel, text, message)


def assert_nothing_sent(box, before: str, out: str) -> None:
    assert kc_origin_head(box) == before, msg(box, out)
    assert pending_files() == [], msg(box, out)
    assert notes.pending_notes() == [], msg(box, out)


# ============================================ допустимые пути `doc-commit`

@pytest.mark.parametrize("rel", [
    DOC_REL, "docs/research/x.md", "docs/adr/0001.md",
    "roles.yaml", "gates.yaml", "targets.yaml",
    # Каталог моделей (SPEC 01M3009Y9AGGY6ZCFA7H1HJ1TD,
    # требование 4, AC-4): состав каталога — та же
    # конфигурация Оператора, что roles.yaml рядом.
    "models.yaml"])
def test_docs_paths_and_operator_config_are_allowed(rel):
    """`docs/**` любой глубины и ровно три файла конфигурации Оператора
    проходят без отказа.

    Ловит мутацию: список допустимых путей сведён к `docs/**` (конфиг
    забыт) либо к плоскому `docs/<файл>` без подкаталогов — тест
    красен на непустом отказе для `roles.yaml` или
    `docs/research/x.md`."""
    assert notes._doc_commit_path_refusal(rel) is None, rel
    assert "models.yaml" in notes.DOC_COMMIT_CONFIG_PATHS
    assert notes._doc_commit_prefix("models.yaml") == "config"


def test_backlog_is_refused_naming_note():
    """`docs/backlog.md` — путь `note`, отказ называет `note`.

    Ловит мутацию: проверка смотрит только на префикс `docs/` — тест
    красен на `None` вместо отказа."""
    refusal = notes._doc_commit_path_refusal("docs/backlog.md")
    assert refusal is not None
    assert "note" in refusal


@pytest.mark.parametrize("rel", [
    "orchestrator/notes.py", "tests/test_notes.py",
    "skills/x.md", "templates/SPEC.md",
    "tasks/01M2XMCG167615YS9EZD9TYJWV/SPEC.md", "other.yaml",
    "README.md"])
def test_code_tests_skills_templates_tasks_refused_with_named_text(rel):
    """Код, тесты, скилы, шаблоны, `tasks/`, чужой yaml в корне —
    именованный отказ «код и артефакты меняются задачами».

    Ловит мутацию: допустимость определяется расширением (`.md`/
    `.yaml`), не расположением — тест красен на `skills/x.md` и
    `other.yaml`."""
    refusal = notes._doc_commit_path_refusal(rel)
    assert refusal is not None, rel
    assert notes.DOC_COMMIT_FOREIGN_REFUSAL in refusal, rel


@pytest.mark.parametrize("rel", [
    "/docs/x.md", "docs/../orchestrator/notes.py", "",
    "docs", "docs/", "../docs/x.md"])
def test_absolute_dotdot_empty_and_bare_docs_dir_refused(rel):
    """Абсолютный путь, `..`, пустая строка и голый каталог `docs`
    отказываются раньше сверки со списком.

    Ловит мутацию: `docs/../roles.yaml`-подобный путь пропускается
    как `docs/**` по строковому префиксу — тест красен на `None`."""
    assert notes._doc_commit_path_refusal(rel) is not None, rel


# ===================================================== сообщение коммита

def test_prefix_by_path_kind_without_truncation():
    """`docs:` для `docs/**`, `config:` для конфигурации, текст
    `--message` целиком (не усечён до 80 символов, как у `note`).

    Ловит мутацию: ветка `doc-commit` в `_commit_message` отсутствует
    и сообщение уходит в общий `оператор: …` — тест красен на
    несовпадении строки."""
    long_message = "о" * 120
    docs = notes._commit_message(DOC_REL, {
        "kind": notes.DOC_COMMIT_KIND, "path": DOC_REL,
        "content": "", "message": long_message}, None)
    assert docs == f"docs: {DOC_REL} — {long_message}"
    cfg = notes._commit_message("gates.yaml", {
        "kind": notes.DOC_COMMIT_KIND, "path": "gates.yaml",
        "content": "", "message": "порог"}, None)
    assert cfg == "config: gates.yaml — порог"


def test_target_rel_is_own_path_for_doc_commit_and_backlog_for_note():
    """`_target_rel`: запись `doc-commit` пишет свой путь, любой вид
    `note` — `docs/backlog.md`.

    Ловит мутацию: `_commit_and_push` пишет и добавляет в индекс
    всегда `BACKLOG_REL` — тест красен на пути записи `doc-commit`."""
    assert notes._target_rel(
        {"kind": notes.DOC_COMMIT_KIND, "path": "roles.yaml"}) == "roles.yaml"
    assert notes._target_rel(
        {"kind": "insert", "section": "копилка", "text": "x"}) == notes.BACKLOG_REL


# ================================================== отправка `doc-commit`

def test_content_lands_in_origin_output_names_sha_main_copy_untouched(doc_box):
    """Успешный вызов: содержимое `--from` становится содержимым пути в
    origin, вывод называет sha нового `origin/<MAIN_BRANCH>`, HEAD/
    ветка/рабочее дерево главной копии и файл на её диске прежние.

    Ловит мутацию: команда правит и коммитит файл прямо в
    `config.ROOT` (мимо `.artel/notes-work`) либо печатает только
    путь без sha — тест красен на снимке главной копии или на
    отсутствии sha в выводе."""
    new_text = "# Роадмап\n\nНовый раздел.\n"
    source = source_file(doc_box, new_text)
    before_origin = origin_head(doc_box)
    before_main = main_copy_snapshot(doc_box)

    output = doc_commit(DOC_REL, "--from", str(source),
                        "--message", "перенос раздела")

    head = origin_head(doc_box)
    assert before_origin != head
    assert origin_show(doc_box, DOC_REL) == new_text
    assert head in output
    assert before_main == main_copy_snapshot(doc_box)
    assert (doc_box.root / DOC_REL).read_text(encoding="utf-8") == ROADMAP_TEXT
    assert notes.pending_notes() == []


def test_bytes_preserved_crlf_not_translated(doc_box):
    """Содержимое переносится байт-в-байт: CRLF в `--from` остаётся
    CRLF в origin.

    Ловит мутацию: чтение `--from` через `read_text` (универсальные
    переводы строк) превращает CRLF в LF — тест красен на
    несовпадении байтов."""
    source = Path(doc_box.source_dir) / "crlf.md"
    source.write_bytes(b"# CRLF\r\n\r\nstroka\r\n")

    doc_commit(DOC_REL, "--from", str(source), "--message", "crlf")

    assert origin_show_bytes(doc_box, DOC_REL) == b"# CRLF\r\n\r\nstroka\r\n"


def test_no_journal_row_for_doc_commit(doc_box):
    """Требование 7: журнал пульта `doc-commit` не пишет — таблица
    steps после успешного вызова пуста.

    Ловит мутацию: `_commit_and_push` журналирует оба вида записи
    одинаково — тест красен на непустом журнале."""
    source = source_file(doc_box, "# Роадмап\n\nбез журнала\n")

    doc_commit(DOC_REL, "--from", str(source), "--message", "тихо")

    rows = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
    assert rows == 0


def test_config_path_gets_config_prefix_docs_path_gets_docs_prefix(doc_box):
    """Сообщение коммита в origin: `config: roles.yaml — …` и
    `docs: docs/roadmap.md — …` целиком.

    Ловит мутацию: префикс один на оба вида путей — тест красен на
    одном из двух сравнений."""
    doc_commit("roles.yaml", "--from",
               str(source_file(doc_box, "developer:\n  model: sonnet\n",
                               "roles.yaml")),
               "--message", "модель")
    assert origin_subject(doc_box) == "config: roles.yaml — модель"

    doc_commit(DOC_REL, "--from",
               str(source_file(doc_box, "# Роадмап\n\nещё\n")),
               "--message", "раздел")
    assert origin_subject(doc_box) == f"docs: {DOC_REL} — раздел"


# ==================================================== отказы `doc-commit`

def test_foreign_path_refused_without_commit_or_hold(doc_box):
    """Путь вне допустимых — отказ до git: origin на месте, удержанной
    записи нет.

    Ловит мутацию: проверка пути перенесена после `_run` (запись
    успевает удержаться/закоммититься) — тест красен на непустом
    `pending_notes()` или сдвинувшемся origin."""
    source = source_file(doc_box, "любое\n")
    before = origin_head(doc_box)

    assert_refused(["orchestrator/notes.py", "--from", str(source),
                    "--message", "правка"],
                   notes.DOC_COMMIT_FOREIGN_REFUSAL)

    assert before == origin_head(doc_box)
    assert notes.pending_notes() == []


def test_backlog_path_refused_origin_keeps_backlog(doc_box):
    """`docs/backlog.md` отказывается, бэклог в origin цел.

    Ловит мутацию: `docs/**` принимает и бэклог — тест красен на
    подменённом содержимом бэклога в origin."""
    source = source_file(doc_box, "# затёртый бэклог\n")

    assert_refused([notes.BACKLOG_REL, "--from", str(source),
                    "--message", "правка"], "note")

    assert origin_show(doc_box, notes.BACKLOG_REL) == BACKLOG_TEXT


def test_missing_message_refused_without_commit_or_hold(doc_box):
    """Без `--message` — отказ; пустой/пробельный `--message` — тот же
    отказ; origin и каталог удержания нетронуты.

    Ловит мутацию: `--message` получает дефолт либо пробельная строка
    проходит — тест красен на сдвинувшемся origin."""
    source = source_file(doc_box, "# Роадмап\n\nбез основания\n")
    before = origin_head(doc_box)

    assert_refused([DOC_REL, "--from", str(source)], "--message")
    assert_refused([DOC_REL, "--from", str(source), "--message", "  "],
                   "--message")

    assert before == origin_head(doc_box)
    assert notes.pending_notes() == []


def test_missing_or_absent_source_file_refused(doc_box):
    """Без `--from` и с несуществующим `--from` — отказ, называющий
    `--from`; origin на месте.

    Ловит мутацию: отсутствие файла не проверяется и падает
    `FileNotFoundError` вместо именованного отказа — тест красен на
    типе исключения."""
    before = origin_head(doc_box)

    assert_refused([DOC_REL, "--message", "основание"], "--from")
    assert_refused([DOC_REL, "--from",
                    str(Path(doc_box.source_dir) / "нет.md"),
                    "--message", "основание"], "не найден")

    assert before == origin_head(doc_box)


def test_identical_content_refused_instead_of_hanging_in_pending(doc_box):
    """Содержимое `--from` уже равно содержимому пути в origin —
    именованный отказ, не три провала `git commit` с удержанием.

    Ловит мутацию: проверка «уже совпадает» отсутствует — `_run`
    исчерпывает попытки, удерживает запись и отказывает текстом «не
    удалось отправить»; тест красен на непустом `pending_notes()`."""
    source = source_file(doc_box, ROADMAP_TEXT)

    assert_refused([DOC_REL, "--from", str(source),
                    "--message", "то же"], "уже совпадает")

    assert notes.pending_notes() == []


def test_role_environment_refused_before_work_repo_exists(doc_box):
    """`runner.in_role_environment()` истинна — отказ первым действием:
    `.artel/notes-work` не заводится, origin на месте.

    Прежняя заявка («рубеж стоит после `_ensure_work_repo()` — красен
    на существующем рабочем репозитории») устарела: рабочий
    репозиторий — клон артели, `.artel/notes-work` не заводится вовсе
    (ADR-0021 п.1, этап 2), и такая мутация не убивается (находка PLAN).

    Ловит мутацию: рубеж окружения роли снят с `cmd_doc_commit` — правка
    уезжает в origin из-под роли, тест красен на отсутствии отказа и
    сдвинувшемся origin."""
    source = source_file(doc_box, "# Роадмап\n\nиз-под роли\n")
    before = origin_head(doc_box)

    with mock.patch.object(notes.runner, "in_role_environment",
                           return_value=True):
        assert_refused([DOC_REL, "--from", str(source),
                        "--message", "правка"], "окружения роли")

    assert before == origin_head(doc_box)
    assert not (config.ROOT / ".artel" / "notes-work").exists()


def test_role_environment_markers_from_env_are_honoured(doc_box):
    """Те же маркеры окружения роли, что ставит `runner.role_env`
    (HOME/CLAUDE_CONFIG_DIR на курируемый слой), без патча функции —
    отказ.

    Ловит мутацию: рубеж читает собственный признак (например
    `ARTEL_ROLE`), а не `runner.in_role_environment` — тест красен на
    отсутствии `SystemExit`."""
    source = source_file(doc_box, "# Роадмап\n\nиз-под роли\n")
    role_env = {"HOME": str(config.ROLE_HOME),
                "CLAUDE_CONFIG_DIR": str(config.ROLE_CONFIG_DIR)}

    with mock.patch.dict(os.environ, role_env):
        assert_refused([DOC_REL, "--from", str(source),
                        "--message", "правка"], "окружения роли")


# ======================================================= сверка с пином

def test_origin_diverged_from_pin_refuses_naming_pin_update(doc_box):
    """origin несёт чужую версию пути, пин — старую: отказ «сначала
    pin-update», чужой текст в origin цел, удержанной записи нет.

    Ловит мутацию: сверка сравнивает origin с содержимым `--from` или
    отсутствует — тест красен на подменённом `origin_show`."""
    foreign = "# Роадмап\n\nчужой раздел\n"
    push_foreign_change_past_the_pin(doc_box, DOC_REL, foreign)
    source = source_file(doc_box, "# Роадмап\n\nмоя правка\n")

    with pytest.raises(SystemExit,
                       match=re.escape(notes.DOC_COMMIT_BASE_REFUSAL)):
        notes.cmd_doc_commit([DOC_REL, "--from", str(source),
                              "--message", "моя"])

    assert origin_show(doc_box, DOC_REL) == foreign
    assert notes.pending_notes() == []


def test_new_path_absent_everywhere_is_committed(doc_box):
    """Пути нет ни в origin, ни в пине — новый файл заводится
    коммитом, каталог создаётся по дороге.

    Ловит мутацию: «нет в origin» трактуется как расхождение с пином
    — тест красен на отказе вместо коммита."""
    rel = "docs/research/new-note.md"
    text = "# Заметка\n\nновый файл\n"
    source = source_file(doc_box, text, "new-note.md")

    doc_commit(rel, "--from", str(source), "--message", "новая")

    assert origin_show(doc_box, rel) == text


def test_path_added_in_origin_after_pin_refuses(doc_box):
    """Путь появился в origin после пина (в HEAD главной копии его нет)
    — это тоже чужая правка после пина: отказ, а не затирание.

    Ловит мутацию: сверка пропускает случай «в пине нет» как новый
    файл — тест красен на подменённом содержимом в origin."""
    rel = "docs/research/foreign.md"
    foreign = "# чужой новый файл\n"
    (doc_box.root / rel).parent.mkdir(parents=True, exist_ok=True)
    (doc_box.root / rel).write_text(foreign, encoding="utf-8")
    doc_box.git("add", rel)
    doc_box.git("commit", "-q", "-m", "чужой новый файл")
    doc_box.git("push", "-q", "origin",
                f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    doc_box.git("reset", "-q", "--hard", "HEAD~1")
    source = source_file(doc_box, "# мой файл\n")

    with pytest.raises(SystemExit):
        notes.cmd_doc_commit([rel, "--from", str(source),
                              "--message", "мой"])

    assert origin_show(doc_box, rel) == foreign


# ======================================= окно тишины и общий флаш записей

def test_open_window_holds_json_with_kind_and_flush_after_close_pushes(doc_box):
    """Окно тишины открыто: запись удерживается в общем каталоге как
    JSON с `kind: doc-commit`, origin не сдвигается, вывод называет
    удержание и `doc-commit --flush`; после закрытия окна
    `doc-commit --flush` доводит содержимое до origin.

    Ловит мутацию: `_run` для `doc-commit` не проверяет окно и пушит
    сразу — тест красен на сдвинувшемся origin до закрытия окна."""
    new_text = "# Роадмап\n\nпосле окна\n"
    source = source_file(doc_box, new_text)
    open_silence_window()
    before = origin_head(doc_box)

    output = doc_commit(DOC_REL, "--from", str(source),
                        "--message", "под окном")

    assert before == origin_head(doc_box)
    assert "doc-commit удержан:" in output
    assert "doc-commit --flush" in output
    pending = notes.pending_notes()
    assert len(pending) == 1, pending
    assert pending[0]["kind"] == notes.DOC_COMMIT_KIND
    assert pending[0]["path"] == DOC_REL
    assert pending[0]["content"] == new_text

    close_silence_window()
    doc_commit("--flush")

    assert origin_show(doc_box, DOC_REL) == new_text
    assert notes.pending_notes() == []


def test_flush_does_not_need_source_file_anymore(doc_box):
    """Удержанная запись самодостаточна: `--from`-файл удалён до флаша,
    содержимое всё равно приезжает в origin.

    Ловит мутацию: запись хранит путь к `--from` и перечитывает файл
    при флаше — тест красен на висящей записи и старом origin."""
    new_text = "# Роадмап\n\nисточник исчез\n"
    source = source_file(doc_box, new_text)
    open_silence_window()
    doc_commit(DOC_REL, "--from", str(source), "--message", "х")
    source.unlink()
    close_silence_window()

    doc_commit("--flush")

    assert origin_show(doc_box, DOC_REL) == new_text
    assert notes.pending_notes() == []


def test_note_flush_sends_both_kinds(doc_box):
    """`note --flush` отправляет и запись `note`, и запись `doc-commit`
    из одного каталога.

    Ловит мутацию: `_fetch_and_build` разбирает запись с `kind:
    doc-commit` старым путём `_build_for` и спотыкается — тест красен
    на висящей записи и старом роадмапе в origin."""
    hold_both_kinds(doc_box)
    capture(notes.cmd_note, ["--flush"])
    assert_both_arrived(doc_box)


def test_doc_commit_flush_sends_both_kinds(doc_box):
    """`doc-commit --flush` симметрично отправляет обе записи.

    Ловит мутацию: `doc-commit --flush` фильтрует каталог по своему
    виду — тест красен на висящей записи `note`."""
    hold_both_kinds(doc_box)
    doc_commit("--flush")
    assert_both_arrived(doc_box)


def test_flush_ignores_open_window_but_new_record_is_still_held(doc_box):
    """`doc-commit --flush` обходит окно явно; обычный вызов при
    открытом окне не допушивает ранее удержанную запись (обе висят).

    Ловит мутацию: оппортунистический флаш в `cmd_doc_commit`
    безусловен — тест красен на сдвинувшемся origin при открытом
    окне."""
    notes._hold_pending({"kind": "insert", "section": "копилка",
                         "text": "4 | 09.09 | старая | o.py"})
    open_silence_window()
    before = origin_head(doc_box)

    doc_commit(DOC_REL, "--from",
               str(source_file(doc_box, "# Роадмап\n\nновая\n")),
               "--message", "новая")

    assert before == origin_head(doc_box)
    assert len(notes.pending_notes()) == 2

    doc_commit("--flush")

    assert before != origin_head(doc_box)
    assert notes.pending_notes() == []


def test_note_hold_texts_unchanged(doc_box):
    """Тексты удержания `note` не изменились от параметризации по виду
    записи (требование 9 — совместимость `note`).

    Ловит мутацию: общий текст удержания переписан под оба вида
    («запись удержана») — тест красен на отсутствии «заметка
    удержана:»."""
    open_silence_window()
    output = capture(notes.cmd_note,
                     ["копилка", "--text", "4 | 09.09 | текст | o.py"])
    assert "заметка удержана:" in output
    assert ("отправка — note --flush либо автоматически "
            "следующим note вне окна") in output


# ============================================================ диспетчер

def test_artel_dispatches_doc_commit_with_rest_argv(doc_box):
    """`artel.py doc-commit …` доходит до `notes.cmd_doc_commit` с
    остатком argv.

    Ловит мутацию: команда не заведена в таблице диспетчера — тест
    красен на `SystemExit(«Неизвестная команда»)`."""
    seen = []
    with mock.patch.object(notes, "cmd_doc_commit",
                           side_effect=seen.append), \
            mock.patch.object(sys, "argv",
                              ["artel.py", "doc-commit", "--flush"]):
        artel.main()
    assert seen == [["--flush"]]


def test_help_text_names_doc_commit(doc_box):
    """Справка `artel.py` называет `doc-commit`.

    Ловит мутацию: команда заведена в таблице, но не в справке —
    тест красен на отсутствии слова в docstring."""
    assert "doc-commit" in artel.__doc__


# ======================================== гейт полного набора `tests/`
#
# Прогон набора где нужно настоящий (исход «набор не запустился вовсе»
# субпроцесса вообще не требует), а где предмет проверки — КАКОЕ дерево
# видит прогон, там `acceptance.run_full_suite` подменяется шпионом,
# читающим это дерево: иначе «прогон идёт до применения правки» и
# «прогон идёт после» не различить. Причина гейта — прецедент 27.09:
# правка `roles.yaml` (a6da0abe) сделала главную ветку красной,
# потребовался откат (d910c523) и встали ветки волны.

def test_red_suite_refuses_naming_the_failed_test(doc_box):
    """Настоящий прогон красного набора: `doc-commit` конфигурации
    отказывает, называя упавший тест, коммита в origin нет,
    конфигурация в origin прежняя, удержанной записи не появилось
    (требование 13).

    Ловит мутацию: гейт не заведён вовсе либо стоит ПОСЛЕ `git
    commit`/push — правка уезжает в origin, и тест красен на
    отсутствии `SystemExit`.
    """
    reseed_suite(doc_box, RED_SUITE_TEXT)
    before = origin_head(doc_box)

    message = refuse_config(doc_box)

    assert "test_seed_always_red" in message, message
    assert before == origin_head(doc_box)
    assert origin_show(doc_box, CONFIG_REL) == "developer:\n  model: opus\n"
    assert notes.pending_notes() == []


def test_unrunnable_suite_refuses_the_same_way(doc_box):
    """Дерево без `tests/` вовсе — прогон не стартует: исход тот же,
    что при красном наборе (отказ, коммита нет, удержанной записи
    нет), а не молчаливый пропуск гейта (требование 14).

    Ловит мутацию: «набор не запустился» трактуется как «гонять
    нечего, значит можно коммитить» (`if tests_dir.is_dir()` вокруг
    всего гейта) — правка уезжает в origin.
    """
    reseed_suite(doc_box, None)
    before = origin_head(doc_box)

    message = refuse_config(doc_box)

    assert "tests/" in message, message
    assert before == origin_head(doc_box)
    assert notes.pending_notes() == []


def test_green_suite_lets_the_commit_through(doc_box):
    """Зелёный набор (посеян стендом) — коммит проходит, содержимое
    приезжает в origin: гейт закрыт по умолчанию, но не наглухо.

    Ловит мутацию: гейт отказывает независимо от исхода прогона
    (условие перевёрнуто) — правка конфигурации перестаёт коммититься
    вовсе.
    """
    commit_config(doc_box)

    assert origin_show(doc_box, CONFIG_REL) == NEW_CONFIG_TEXT
    assert notes.pending_notes() == []


def test_suite_runs_on_the_tree_with_the_change_already_applied(doc_box):
    """Прогон видит дерево, в котором правка УЖЕ записана: шпион
    читает конфигурацию в корне прогона и находит там НОВОЕ содержимое
    (требование 13).

    Ловит мутацию: порядок «прогнать набор → записать файл» вместо
    обратного либо прогон не на том дереве (`config.ROOT` вместо
    рабочего репозитория) — шпион видит старую конфигурацию или падает
    на её отсутствии.
    """
    seen = spy_suite(doc_box, green=True)

    commit_config(doc_box)

    assert len(seen) == 1, seen
    root, content = seen[0]
    assert content == NEW_CONFIG_TEXT
    # Рабочий репозиторий — клон артели: `.artel/notes-work` упразднён
    # (ADR-0021 п.1, этап 2; SPEC 01M42PENCS26D0656X8FR7DFA7,
    # требование 5).
    assert root == config.PROJECTS / config.DEFAULT_TARGET / "repo"
    assert origin_show(doc_box, CONFIG_REL) == NEW_CONFIG_TEXT


def test_docs_path_does_not_run_the_suite_at_all(doc_box):
    """Путь `docs/**` прогона не заводит: шпион не позван ни разу, а
    документ доезжает до origin поверх красного набора (требование 16).

    Ловит мутацию: прогон поставлен на ВСЕ пути `doc-commit` (проверка
    `path in DOC_COMMIT_CONFIG_PATHS` забыта либо инвертирована) —
    документный путь отказывает по красному набору.
    """
    reseed_suite(doc_box, RED_SUITE_TEXT)
    seen = spy_suite(doc_box, green=False)
    new_text = "# Роадмап\n\nНовый раздел.\n"

    doc_commit(DOC_REL, "--from", str(source_file(doc_box, new_text)),
               "--message", "перенос раздела")

    assert seen == []
    assert origin_show(doc_box, DOC_REL) == new_text


def test_open_window_holds_the_record_and_the_gate_fires_on_flush(doc_box):
    """Окно тишины открыто: запись удерживается, прогона нет вовсе —
    отправки ещё не было. Прогон случается на `doc-commit --flush`,
    когда отправка действительно идёт; красный набор оставляет запись
    удержанной (тот же исход, что у любой записи, не прошедшей
    собственную валидацию при флаше, — `doctor.check_pending_notes`
    её и покажет), и origin не сдвигается.

    Ловит мутацию: гейт вынесен из `_commit_and_push` выше, к
    построению правки — набор гоняется на каждом удержании, то есть
    минуты прогона тратятся на запись, которая никуда не поедет; либо
    наоборот, флаш обходит гейт, и красная правка уезжает в origin
    мимо требования 13.
    """
    reseed_suite(doc_box, RED_SUITE_TEXT)
    seen = spy_suite(doc_box, green=False)
    open_silence_window()
    before = origin_head(doc_box)

    commit_config(doc_box)

    assert seen == []
    assert len(notes.pending_notes()) == 1, notes.pending_notes()

    doc_commit("--flush")

    assert len(seen) == 1, seen
    assert before == origin_head(doc_box)
    assert len(notes.pending_notes()) == 1, notes.pending_notes()


def test_accept_red_commits_and_journal_carries_path_and_reason(doc_box):
    """`--accept-red "<основание>"` при красном наборе: правка
    приезжает в origin, а журнал пульта несёт и путь, и основание
    обхода (требование 15).

    Ловит мутацию: флаг принят, но основание в журнал не попадает
    (запись пишется без него либо не пишется вовсе) — обход становится
    невидимым.
    """
    reseed_suite(doc_box, RED_SUITE_TEXT)

    commit_config(doc_box, "--accept-red", ACCEPT_REASON)

    assert origin_show(doc_box, CONFIG_REL) == NEW_CONFIG_TEXT
    journal = journal_text()
    assert CONFIG_REL in journal, journal
    assert ACCEPT_REASON in journal, journal


def test_accept_red_skips_the_run_entirely(doc_box):
    """С флагом набор не гоняется вовсе: шпион не позван ни разу.

    Ловит мутацию: флаг учитывается только ПОСЛЕ прогона (исход
    игнорируется, но минуты тратятся) — шпион позван, и тест красен.
    """
    seen = spy_suite(doc_box, green=False)

    commit_config(doc_box, "--accept-red", ACCEPT_REASON)

    assert seen == []
    assert origin_show(doc_box, CONFIG_REL) == NEW_CONFIG_TEXT


def test_accept_red_without_reason_refuses_by_substance_not_argparse(doc_box):
    """Флаг без основания — ИМЕНОВАННЫЙ отказ, называющий флаг, а не
    код выхода 2 самого argparse (требование 15, «без основания флаг
    отказывает»); origin не сдвигается, удержанной записи нет.

    Ловит мутацию: флаг объявлен обычным `add_argument("--accept-red")`
    — голый флаг тогда даёт `SystemExit(2)` без внятного текста, и
    Оператор не знает, чего от него хотят.
    """
    before = origin_head(doc_box)

    message = refuse_config(doc_box, "--accept-red")

    assert message.strip() != "2", message
    assert "--accept-red" in message, message
    assert before == origin_head(doc_box)
    assert notes.pending_notes() == []


def test_green_suite_with_accept_red_still_journals_the_bypass(doc_box):
    """Флаг при ЗЕЛЁНОМ наборе: коммит проходит, и обход всё равно
    записан журналом — Оператор объявил осознанное решение, и оно
    остаётся в истории независимо от того, что показал бы прогон.

    Ловит мутацию: запись журнала привязана к исходу прогона, которого
    при флаге нет вовсе (`if not green and reason`) — обход уходит
    бесследно, а отличить его от обычного коммита потом нечем.
    """
    commit_config(doc_box, "--accept-red", ACCEPT_REASON)

    journal = journal_text()
    assert notes.ACCEPT_RED_JOURNAL_ACTION in journal, journal
    assert ACCEPT_REASON in journal, journal


# Отказ гейта выходит `sys.exit`'ом ПОСЛЕ записи правки в общий рабочий
# репозиторий — оба регресса R1-F1 ревью итерации 1 про то, чем он
# оставляет дерево после себя.

def test_repeat_after_fixing_the_suite_commits_the_same_change(doc_box):
    """Отказ гейта не оставляет записанную правку в дереве рабочего
    репозитория: `git status` по пути пуст, и ТА ЖЕ команда после
    починки набора доводит правку до origin.

    Ловит мутацию: отказ гейта не снимает правку с дерева, а сверка
    «содержимое уже совпадает» читает ФАЙЛ дерева вместо blob'а origin
    — повтор отказывает «содержимое уже совпадает с origin/main» даже
    при зелёном наборе, и правка конфигурации не проходит уже никогда.
    """
    reseed_suite(doc_box, RED_SUITE_TEXT)

    message = refuse_config(doc_box)

    assert "test_seed_always_red" in message, message
    assert work_status(CONFIG_REL) == ""

    reseed_suite(doc_box, GREEN_SUITE_TEXT)
    commit_config(doc_box)

    assert origin_show(doc_box, CONFIG_REL) == NEW_CONFIG_TEXT
    assert notes.pending_notes() == []


def test_note_reaches_origin_after_a_gate_refusal_and_a_foreign_change(doc_box):
    """Второй сценарий R1-F1: после отказа гейта тот же путь изменён в
    origin сторонней правкой — заметка `note` всё равно доезжает до
    origin, удержанной записи не появляется.

    Ловит мутацию: дерево остаётся грязным, а `checkout -B` в
    `_fetch_and_build` идёт без `-f` и без проверки кода возврата —
    сборка молча идёт на дереве прошлого коммита, и КАЖДАЯ заметка
    отказывает «не удалось отправить заметку в origin».
    """
    reseed_suite(doc_box, RED_SUITE_TEXT)
    refuse_config(doc_box)
    push_foreign_config_change(doc_box)

    note_row("ЗАМЕТКАПОСЛЕОТКАЗА")

    assert "ЗАМЕТКАПОСЛЕОТКАЗА" in origin_show(doc_box, notes.BACKLOG_REL)
    assert notes.pending_notes() == []


def test_dirty_work_tree_is_forced_to_origin_before_the_next_record(doc_box):
    """Дерево общего рабочего репозитория, оставшееся с посторонним
    файлом пути, который есть в origin (аварийный выход команды, снятие
    процесса), приводится к origin ПРИНУДИТЕЛЬНО — заметка доезжает.

    Прежняя заявка (`checkout -B` без `-f` и без проверки кода возврата)
    устарела: грязь кладётся в `.artel/notes-work`, а рабочий
    репозиторий — клон артели (ADR-0021 п.1, этап 2), и такая мутация не
    убивается (находка PLAN).

    Ловит мутацию: проверка кода возврата принудительного checkout в
    `_fetch_and_build` перевёрнута — успешное приведение дерева к origin
    читается как отказ, заметка удерживается вместо отправки, тест красен
    на отсутствии заметки в origin.
    """
    work_config = config.ROOT / ".artel" / "notes-work" / CONFIG_REL
    work_config.parent.mkdir(parents=True, exist_ok=True)
    work_config.write_text("developer:\n  model: ГРЯЗЬ\n", encoding="utf-8")

    note_row("ЗАМЕТКАПОВЕРХГРЯЗИ")

    assert "ЗАМЕТКАПОВЕРХГРЯЗИ" in origin_show(doc_box, notes.BACKLOG_REL)
    assert notes.pending_notes() == []


def test_leftover_file_in_the_work_tree_is_not_read_as_origin_content(doc_box):
    """Мусор в дереве общего рабочего репозитория не читается как
    содержимое origin: файл нового пути, оставшийся в
    `.artel/notes-work` и равный тому, что коммитят, ложного отказа
    «содержимое уже совпадает» не даёт — путь доезжает до origin.

    Прежняя заявка (сверка «уже совпадает» читает ФАЙЛ дерева, дерево
    перед сборкой не чистится) устарела: мусор кладётся в
    `.artel/notes-work`, а рабочий репозиторий — клон артели (ADR-0021
    п.1, этап 2), и такая мутация не убивается (находка PLAN).

    Ловит мутацию: `_write_doc` не заводит каталог нового пути
    (`docs/research/` в клоне нет) — запись падает `FileNotFoundError`,
    тест красен на отсутствии файла в origin.
    """
    rel = "docs/research/new.md"
    text = "# новый документ\n"
    leftover = config.ROOT / ".artel" / "notes-work" / rel
    leftover.parent.mkdir(parents=True, exist_ok=True)
    leftover.write_text(text, encoding="utf-8")

    doc_commit(rel, "--from", str(source_file(doc_box, text, "new.md")),
               "--message", "новый документ")

    assert origin_show(doc_box, rel) == text


def test_opportunistic_flush_skips_the_record_and_explicit_flush_speaks(doc_box):
    """Удержанная правка конфигурации не превращает обычную `note` в
    молчаливый прогон полного набора: прогона нет, причина напечатана,
    сама заметка доезжает до origin. Явный `doc-commit --flush` прогон
    заводит и печатает причину отказа (R1-F3 ревью итерации 1).

    Ловит мутацию: попутный флаш отправляет любую удержанную запись —
    прогон позван на обычной `note`; либо `_flush_pending` снова глотает
    `SystemExit` целиком — явный флаш ничего не печатает, и запись висит
    без объяснения.
    """
    seen = spy_suite(doc_box, green=False)
    open_silence_window()
    commit_config(doc_box)
    close_silence_window()
    assert len(notes.pending_notes()) == 1, notes.pending_notes()

    note_output = note_row("ЗАМЕТКАПРИУДЕРЖАНИИ")

    assert seen == []
    assert CONFIG_REL in note_output, note_output
    assert "ЗАМЕТКАПРИУДЕРЖАНИИ" in origin_show(doc_box, notes.BACKLOG_REL)
    assert len(notes.pending_notes()) == 1, notes.pending_notes()

    flush_output = doc_commit("--flush")

    assert len(seen) == 1, seen
    assert "tests/" in flush_output, flush_output
    assert len(notes.pending_notes()) == 1, notes.pending_notes()


def test_accept_red_record_is_sent_by_the_opportunistic_flush(doc_box):
    """Удержанная запись с `--accept-red` прогона не заведёт, поэтому
    попутным флашем отправляется как любая другая: обход Оператор уже
    объявил, ждать явного флаша нечего.

    Ловит мутацию: попутный флаш откладывает ЛЮБУЮ запись пути
    конфигурации (условие пропуска не смотрит на `accept_red`) —
    осознанный обход перестаёт доезжать сам, и тест красен на старой
    конфигурации в origin.
    """
    reseed_suite(doc_box, RED_SUITE_TEXT)
    open_silence_window()
    commit_config(doc_box, "--accept-red", ACCEPT_REASON)
    close_silence_window()

    note_row("ЗАМЕТКАПРИОБХОДЕ")

    assert origin_show(doc_box, CONFIG_REL) == NEW_CONFIG_TEXT
    assert notes.pending_notes() == []


def test_docs_path_accept_red_writes_no_bypass_journal_row(doc_box):
    """`--accept-red` на пути `docs/**`: документ коммитится, а записи
    об обходе в журнале пульта НЕТ — гейта на этом пути не существует
    (требование 16), и запись была бы ложной (R1-F4 ревью итерации 1).

    Ловит мутацию: запись журнала пишется по одному наличию флага, без
    сверки пути — журнал несёт обход, которого не было, и Оператор
    ищет по нему несуществующую правку конфигурации.
    """
    new_text = "# Роадмап\n\nбез обхода\n"

    doc_commit(DOC_REL, "--from", str(source_file(doc_box, new_text)),
               "--message", "раздел", "--accept-red", ACCEPT_REASON)

    assert origin_show(doc_box, DOC_REL) == new_text
    journal = journal_text()
    assert notes.ACCEPT_RED_JOURNAL_ACTION not in journal, journal
    assert ACCEPT_REASON not in journal, journal


# ================================== края пакетного сброса удержанных записей

def test_explicit_flush_warns_about_missing_base_of_config_record(doc_box):
    """Явный флаш (`note --flush` и `doc-commit --flush`) удержанной
    без базы правки конфигурации печатает `<путь>: NO_BASE_WARNING` и
    отправляет её прежним путём — правила правок конфигурации пакетный
    сброс не меняет (требование 3).

    Ловит мутацию: ветка `_suite_gate_applies` в `_flush_pending`
    уходит в `continue` раньше проверки `HELD_BASE_KEY` — правка
    уходит, а предупреждения в выводе нет.
    """
    spy_suite(doc_box, green=True)
    for entry, fn in (("note", notes.cmd_note),
                      ("doc-commit", notes.cmd_doc_commit)):
        text = f"developer:\n  model: {entry}\n"
        hold_config_without_base(doc_box, text)

        out = capture(fn, ["--flush"])

        assert f"{CONFIG_REL}: {notes.NO_BASE_WARNING}" in out, entry
        assert origin_show(doc_box, CONFIG_REL) == text, entry
        assert notes.pending_notes() == [], entry


def test_opportunistic_flush_still_skips_config_record_silently_on_base(doc_box):
    """Попутный сброс правку конфигурации по-прежнему пропускает
    прежней строкой причины и о базе не говорит: запись не
    отправляется, предупреждать не о чем.

    Ловит мутацию: предупреждение о базе вынесено до проверки
    `explicit` — попутный сброс в начале обычной `note` печатает
    `NO_BASE_WARNING` записи, которую не отправляет.
    """
    spy_suite(doc_box, green=True)
    hold_config_without_base(doc_box)

    out = note_row("ЗАМЕТКАБЕЗБАЗЫ")

    assert "попутно не отправляется" in out
    assert notes.NO_BASE_WARNING not in out
    assert len(notes.pending_notes()) == 1


def test_half_written_record_does_not_become_batch_head_for_next(doc_box):
    """`OSError` при записи файла записи пакета после частичной записи
    снимает правку с общего рабочего дерева: следующая запись пакета
    того же пути (`docs/backlog.md`) строится от головы пакета, а не от
    недописанного файла.

    Ловит мутацию: ветка `except OSError` в `_flush_batch` просто
    продолжает цикл — вторая заметка читает `_read_backlog` из грязного
    дерева, и мусор первой записи уезжает в origin (либо вторая запись
    отказывает валидацией разметки).
    """
    open_silence_window()
    note_row("ПЕРВАЯЗАМЕТКА")
    note_row("ВТОРАЯЗАМЕТКА")
    close_silence_window()
    assert len(notes.pending_notes()) == 2
    real_write = notes._write_backlog
    calls = []

    def write_then_fail(work_dir, text):
        calls.append(text)
        if len(calls) == 1:
            (work_dir / notes.BACKLOG_REL).write_text(
                "НЕДОПИСАННЫЙМУСОР", encoding="utf-8")
            raise OSError("диск отказал посреди записи")
        real_write(work_dir, text)

    with mock.patch.object(notes, "_write_backlog", write_then_fail):
        capture(notes.cmd_note, ["--flush"])

    backlog = origin_show(doc_box, notes.BACKLOG_REL)
    assert "ВТОРАЯЗАМЕТКА" in backlog
    assert "НЕДОПИСАННЫЙМУСОР" not in backlog
    assert "ПЕРВАЯЗАМЕТКА" not in backlog
    assert len(notes.pending_notes()) == 1


# ============================== удержанная запись сверяется с базой сборки

def test_ac1_held_record_stores_pin_blob_or_absent_mark(held_box):
    """Удержанная запись несёт blob-sha пути из HEAD главной копии.

    Сценарий: окно тишины открыто, `doc-commit` существующего пути
    удерживается — среди значений записи есть blob-sha `HEAD:<путь>`
    (не sha коммита и не blob содержимого записи); `doc-commit` нового
    пути (в HEAD его нет) удерживается — запись несёт поле сверх
    прежнего формата (`kind`/`path`/`content`/`message`) — отметку
    «файла не было».

    Ловит мутацию: `_hold_pending` пишет прежний словарь без базы либо
    база берётся как sha коммита HEAD/blob нового содержимого — среди
    значений записи нет blob-sha пути в HEAD, у записи нового файла нет
    поля сверх прежних.
    """
    base = held_box.git("rev-parse", f"HEAD:{DOC_REL}").strip()
    new_rel = f"docs/research/{word(held_box).lower()}.md"
    open_window()

    hold_doc_commit(held_box, DOC_REL, f"# Роадмап\n\n{words(held_box, 5)}\n")
    hold_doc_commit(held_box, new_rel, f"# Новое\n\n{words(held_box, 5)}\n")

    records = {r["path"]: r for r in notes.pending_notes()}
    assert base in string_values(records[DOC_REL]), (
        msg(held_box, f"база {base} не сохранена: {records[DOC_REL]}"))
    extra = set(records[new_rel]) - LEGACY_KEYS
    assert extra, msg(held_box,
                      f"у записи нового файла нет отметки «файла не было»: "
                      f"{records[new_rel]}")


def test_ac2_doc_commit_flush_refuses_stale_base_and_sends_others(held_box):
    """`doc-commit --flush` после сдвига пина на изменённый origin.

    Сценарий 02.10 (см. `stale_scenario`): отказ называет «файл
    изменился в origin после сборки записи», базу и blob origin и
    «собери заново от origin»; чужой текст в origin цел, коммитов по
    пути нет, запись осталась удержанной, вторая запись прохода
    (другой документ) отправлена.

    Ловит мутацию: при отправке удержанной записи сверяется только
    origin против пина (как до задачи) — пин совпал с origin, чужие
    строки затёрты коммитом, отказа нет.
    """
    stale_scenario(held_box,
                   lambda: run_command(notes.cmd_doc_commit, ["--flush"]))


def test_ac2_note_flush_refuses_stale_base(held_box):
    """`note --flush` — тот же отказ сценария 02.10.

    Ловит мутацию: сверка базы заведена только в путь
    `cmd_doc_commit`, а не в общую отправку удержанных записей —
    `note --flush` затирает чужие строки.
    """
    stale_scenario(held_box, lambda: run_command(notes.cmd_note, ["--flush"]))


def test_ac2_opportunistic_flush_refuses_stale_base(held_box):
    """Попутная отправка (обычная `note` вне окна) — тот же отказ.

    Ловит мутацию: сверка базы стоит только на явном флаше
    (`explicit=True`), попутная отправка идёт по-старому — ровно
    коммит 28b09389, стёрший чужие строки.
    """
    stale_scenario(held_box, lambda: run_command(
        notes.cmd_note,
        ["копилка", "--text", f"4 | 02.10 | {word(held_box)} | o.py"]))


def test_ac3_base_matching_origin_is_sent(held_box):
    """База совпадает с blob пути в origin — запись отправляется.

    Сценарий: запись удержана; origin уходит вперёд коммитом по
    ДРУГОМУ пути (blob пути прежний, пин отстал от origin); после
    закрытия окна `doc-commit --flush` — содержимое записи в origin,
    `pending_notes()` пуст.

    Ловит мутацию: база сравнивается не с blob'ом пути в origin, а с
    sha головы origin либо с blob'ом нового содержимого — запись
    отказывает «файл изменился» и висит.
    """
    held_text = f"# Роадмап\n\n{words(held_box, 5)}\n"
    open_window()
    hold_doc_commit(held_box, DOC_REL, held_text)
    push_foreign_past_the_pin(held_box, GUIDE_REL,
                              f"# другое\n{words(held_box, 3)}\n")
    close_window()

    out = run_command(notes.cmd_doc_commit, ["--flush"])

    assert held_origin_show(held_box, DOC_REL) == held_text, msg(held_box, out)
    assert notes.pending_notes() == [], msg(held_box, out)
    assert STALE_PHRASE not in out, msg(held_box, out)


def test_ac4_new_file_absent_in_origin_is_sent(held_box):
    """Новый файл: удержан с отметкой «файла не было», в origin файла
    нет — отправляется.

    Сценарий: путь `docs/research/<случайное>.md` нет ни в пине, ни в
    origin; запись удержана; после закрытия окна `doc-commit --flush`
    — файл появился в origin с содержимым записи, запись снята.

    Ловит мутацию: отметка «файла не было» сравнивается с отсутствием
    blob'а как с расхождением (или пишется пустой строкой, не равной
    «нет blob'а») — новый файл отказывает и висит.
    """
    rel = f"docs/research/{word(held_box).lower()}.md"
    text = f"# Новое\n\n{words(held_box, 5)}\n"
    open_window()
    hold_doc_commit(held_box, rel, text)
    close_window()

    out = run_command(notes.cmd_doc_commit, ["--flush"])

    assert held_origin_show(held_box, rel) == text, msg(held_box, out)
    assert notes.pending_notes() == [], msg(held_box, out)


def test_ac4_new_file_appeared_in_origin_is_refused(held_box):
    """Новый файл появился в origin до отправки — отказ AC-2.

    Сценарий: запись нового пути удержана с отметкой «файла не было»;
    затем чужой коммит заводит этот путь, пин сдвинут на голову
    origin (сверка с пином прошла бы); флаш — отказ «файл изменился в
    origin после сборки записи», чужой файл в origin цел, коммитов по
    пути нет, запись удержана.

    Ловит мутацию: отметка «файла не было» трактуется как «базы нет»
    и запись идёт по пиновой сверке — пин совпал с origin, чужой файл
    затёрт.
    """
    rel = f"docs/research/{word(held_box).lower()}.md"
    open_window()
    hold_doc_commit(held_box, rel, f"# Моё\n\n{words(held_box, 5)}\n")
    foreign = f"# Чужое\n\n{words(held_box, 5)}\n"
    advance_pin_and_origin(held_box, rel, foreign)
    blob = origin_blob(held_box, rel)
    before = held_origin_head(held_box)
    close_window()

    out = run_command(notes.cmd_doc_commit, ["--flush"])

    assert STALE_PHRASE in out, msg(held_box, out)
    assert blob[:7] in out, msg(held_box, out)
    assert held_origin_show(held_box, rel) == foreign, msg(held_box, out)
    assert origin_commits_touching(held_box, before, rel) == [], (
        msg(held_box, out))
    assert rel in pending_paths(), msg(held_box, out)


def test_ac5_immediate_send_still_refuses_on_pin(held_box):
    """Немедленная отправка при origin ≠ пин — отказ пиновой сверки.

    Сценарий: чужая правка пути ушла в origin мимо пина (пин прежний);
    окно закрыто; `doc-commit` этого пути — отказ с текстом
    `notes.DOC_COMMIT_BASE_REFUSAL`, чужой текст в origin цел, запись
    не удержана.

    Ловит мутацию: пиновая сверка немедленной отправки заменена новой
    сверкой с базой (или снята) — отказ приходит другим текстом либо
    чужая правка затёрта.
    """
    foreign = held_box.doc_text + f"{words(held_box, 4)}\n"
    push_foreign_past_the_pin(held_box, DOC_REL, foreign)

    out = held_doc_commit(held_box, DOC_REL,
                          f"# Роадмап\n\n{words(held_box, 5)}\n")

    assert notes.DOC_COMMIT_BASE_REFUSAL in out, msg(held_box, out)
    assert held_origin_show(held_box, DOC_REL) == foreign, msg(held_box, out)
    assert notes.pending_notes() == [], msg(held_box, out)


def test_ac6_legacy_record_pin_matches_is_sent_with_warning(held_box):
    """Запись без базы, origin совпадает с пином — отправлена с
    предупреждением «база не сохранена».

    Ловит мутацию: запись без базы молча идёт по пиновой сверке (нет
    предупреждения) либо отсутствие базы читается как отметка «файла
    не было» — отказ вместо отправки.
    """
    text = f"# Роадмап\n\n{words(held_box, 5)}\n"
    hold_legacy(held_box, text)

    out = run_command(notes.cmd_doc_commit, ["--flush"])

    assert NO_BASE_PHRASE in out, msg(held_box, out)
    assert held_origin_show(held_box, DOC_REL) == text, msg(held_box, out)
    assert notes.pending_notes() == [], msg(held_box, out)


def test_ac6_legacy_record_pin_differs_is_refused_with_warning(held_box):
    """Запись без базы, origin ушёл от пина — отказ
    `DOC_COMMIT_BASE_REFUSAL` и предупреждение «база не сохранена».

    Ловит мутацию: запись без базы пропускается без всякой сверки —
    чужая правка в origin затёрта, отказа нет; либо предупреждение
    печатается только на успешной отправке.
    """
    hold_legacy(held_box, f"# Роадмап\n\n{words(held_box, 5)}\n")
    foreign = held_box.doc_text + f"{words(held_box, 4)}\n"
    push_foreign_past_the_pin(held_box, DOC_REL, foreign)

    out = run_command(notes.cmd_doc_commit, ["--flush"])

    assert NO_BASE_PHRASE in out, msg(held_box, out)
    assert notes.DOC_COMMIT_BASE_REFUSAL in out, msg(held_box, out)
    assert held_origin_show(held_box, DOC_REL) == foreign, msg(held_box, out)
    assert DOC_REL in pending_paths(), msg(held_box, out)


def test_network_hold_stores_head_blob(unit_box):
    """Удержание сетевым отказом (origin недоступен) тоже несёт базу.

    Сценарий: origin указывает на несуществующий каталог, `doc-commit`
    отказывает «не удалось отправить» и удерживает запись — в ней поле
    `notes.HELD_BASE_KEY` с blob-sha `HEAD:docs/roadmap.md`.

    Ловит мутацию: база добавляется только на ветке окна тишины в
    `_run`, а не в `_hold_pending` — запись сетевого удержания уходит
    без базы и на флаше идёт по пиновой сверке (сценарий 02.10).
    """
    # С этапа 2 ADR-0021 (п.1) `doc-commit` идёт через клон артели,
    # заведённый `init` из живого origin; недоступным origin становится
    # потом — у клона (SPEC 01M42PENCS26D0656X8FR7DFA7, требование 5).
    origin = Path(unit_box.source_dir) / "origin.git"
    init_bare_origin(origin, unit_box.git)
    unit_box.git("remote", "add", "origin", str(origin))
    unit_box.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
    clone = clone_artel_from_origin(origin)
    subprocess.run(["git", "-C", str(clone), "remote", "set-url", "origin",
                    str(Path(unit_box.source_dir) / "нет-такого")],
                   check=True, capture_output=True)
    source = Path(unit_box.source_dir) / "new.md"
    source.write_text("# Роадмап\n\nновое\n", encoding="utf-8")
    base = unit_box.git("rev-parse", "HEAD:docs/roadmap.md").strip()

    out = run_command(notes.cmd_doc_commit,
                      ["docs/roadmap.md", "--from", str(source),
                       "--message", "правка"])

    records = notes.pending_notes()
    assert len(records) == 1, out
    assert records[0].get(notes.HELD_BASE_KEY) == base, out


# ======================================= `note --pending`/`--drop-pending`

def test_ac7_pending_lists_each_record_with_truncated_content(held_box):
    """`note --pending` — строка на каждую удержанную запись.

    Сценарий: удержаны `doc-commit` документа с однострочным
    содержимым длиннее 80 знаков и заметка копилки с длинным текстом;
    в выводе для каждого id файла записи есть строка с этим id, где
    у `doc-commit` — вид и путь, у заметки — раздел, у обеих — время
    и первые 80 знаков содержимого, но не 81-й знак.

    Ловит мутацию: содержимое не обрезается (или режется по другой
    длине), либо строка записи не несёт id файла/пути/раздела — тест
    красен на строке записи.
    """
    doc_content = word(held_box, held_box.rng.randrange(90, 140))
    note_text = (f"4 | 02.10 | {word(held_box, held_box.rng.randrange(90, 140))} "
                 f"| o.py")
    open_window()
    hold_doc_commit(held_box, DOC_REL, doc_content)
    hold_note(held_box, note_text)
    by_kind = {}
    for path in pending_dir().glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        by_kind[record["kind"]] = path.stem

    out = run_command(notes.cmd_note, ["--pending"])
    lines = out.split("\n")

    def line_of(record_id: str) -> str:
        found = [line for line in lines if record_id in line]
        assert len(found) == 1, msg(held_box, f"строка записи {record_id}: {out}")
        return found[0]

    doc_line = line_of(by_kind[notes.DOC_COMMIT_KIND])
    assert notes.DOC_COMMIT_KIND in doc_line, msg(held_box, doc_line)
    assert DOC_REL in doc_line, msg(held_box, doc_line)
    assert doc_content[:80] in doc_line, msg(held_box, doc_line)
    assert doc_content[:81] not in doc_line, msg(held_box, doc_line)
    note_line = line_of(by_kind["insert"])
    assert "копилка" in note_line, msg(held_box, note_line)
    assert note_text[:80] in note_line, msg(held_box, note_line)
    assert note_text[:81] not in note_line, msg(held_box, note_line)
    for line in (doc_line, note_line):
        stripped = line
        for record_id in by_kind.values():
            stripped = stripped.replace(record_id, "")
        assert TIME_RE.search(stripped), (
            msg(held_box, f"нет времени удержания: {line}"))
    assert len(notes.pending_notes()) == 2, msg(held_box, out)


def test_ac8_drop_pending_removes_exactly_one_and_journals(held_box):
    """`note --drop-pending <id>` снимает ровно эту запись и пишет журнал.

    Сценарий: удержаны три записи (два документа и заметка), снимается
    случайно выбранная; две другие остаются в `pending_notes()`, файла
    снятой нет; в журнале `steps` появилась строка, называющая id
    снятой записи, с непустым актором.

    Ловит мутацию: снимаются все записи (как `--flush` без отправки)
    либо первая по порядку, а не по id; либо журнал не пишется — тест
    красен на составе `pending_notes()` или на пустом журнале.
    """
    open_window()
    hold_doc_commit(held_box, DOC_REL, f"# Роадмап\n\n{words(held_box, 5)}\n")
    hold_doc_commit(held_box, GUIDE_REL,
                    f"# Руководство\n\n{words(held_box, 5)}\n")
    hold_note(held_box, f"4 | 02.10 | {words(held_box, 3)} | o.py")
    ids = pending_ids()
    victim = held_box.rng.choice(ids)
    victim_record = json.loads(
        (pending_dir() / f"{victim}.json").read_text(encoding="utf-8"))
    before_rows = store.db().execute(
        "SELECT COUNT(*) FROM steps").fetchone()[0]

    out = run_command(notes.cmd_note, ["--drop-pending", victim])

    assert pending_ids() == [i for i in ids if i != victim], msg(held_box, out)
    assert victim_record not in notes.pending_notes(), msg(held_box, out)
    assert len(notes.pending_notes()) == 2, msg(held_box, out)
    rows = store.db().execute(
        "SELECT actor, action, detail FROM steps ORDER BY rowid").fetchall()
    new_rows = rows[before_rows:]
    naming = [r for r in new_rows
              if victim in f"{r[1]} {r[2]}" and (r[0] or "").strip()]
    assert naming, msg(held_box, f"журнал не называет {victim}: "
                                 f"{new_rows}; вывод: {out}")


def test_ac9_pending_and_drop_pending_refuse_under_role(held_box):
    """Под признаком шага роли `--pending` и `--drop-pending` отказывают.

    Сценарий: Оператор удержал две записи; затем из окружения роли
    (непустой маркер `ARTEL_ROLE` случайного имени) `note --pending` —
    отказ без id записей в выводе; `note --drop-pending <id>` — отказ,
    обе записи на месте.

    Ловит мутацию: ветки `--pending`/`--drop-pending` разобраны до
    рубежа `runner.in_role_environment()` — роль видит перечень записей
    или снимает запись.
    """
    open_window()
    hold_doc_commit(held_box, DOC_REL, f"# Роадмап\n\n{words(held_box, 5)}\n")
    hold_note(held_box, f"4 | 02.10 | {words(held_box, 3)} | o.py")
    ids = pending_ids()
    role_env = {config.ARTEL_ROLE_ENV: f"role_{word(held_box).lower()}"}

    for argv in (["--pending"], ["--drop-pending", held_box.rng.choice(ids)]):
        with mock.patch.dict(os.environ, role_env):
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(buf):
                with pytest.raises(SystemExit):
                    notes.cmd_note(argv)
        for record_id in ids:
            assert record_id not in buf.getvalue(), (
                msg(held_box, f"{argv[0]}: {buf.getvalue()}"))
        assert pending_ids() == ids, msg(held_box, argv[0])


def test_multiline_content_stays_one_line_and_truncated(unit_box):
    """Многострочное содержимое `doc-commit` даёт ОДНУ строку перечня
    с выдержкой не длиннее 80 знаков содержимого.

    Ловит мутацию: выдержка берётся без замены переводов строк —
    запись `note --pending` рвётся на несколько строк вывода, и id
    стоит только на первой; либо обрезка снята.
    """
    content = "# Заголовок\n" + "строка текста\n" * 20
    record_id = write_pending(
        {"kind": notes.DOC_COMMIT_KIND, "path": "docs/roadmap.md",
         "content": content, "message": "м"})

    out = run_command(notes.cmd_note, ["--pending"])

    lines = [line for line in out.split("\n") if line.strip()]
    assert len(lines) == 1, out
    assert record_id in lines[0]
    assert content[:80].replace("\n", " ") in lines[0]
    assert content[:81].replace("\n", " ") not in lines[0]


def test_empty_pending_says_so(unit_box):
    """Пустой каталог удержанных записей — именованная строка.

    Ловит мутацию: пустой перечень печатает ничего — Оператор не
    отличит «записей нет» от сбоя команды.
    """
    out = run_command(notes.cmd_note, ["--pending"])
    assert "удержанных записей нет" in out


def test_unknown_or_traversal_id_refuses_without_removal(unit_box):
    """Id, которого нет среди файлов каталога (в том числе «../…»),
    отказывает: ни одна запись не снята, файл вне каталога цел,
    журнал не пишется.

    Ловит мутацию: id склеивается в путь `_pending_dir() / f"{id}.json"`
    без сверки с перечнем — «../outside» снимает файл вне каталога.
    """
    record_id = write_pending(
        {"kind": "insert", "section": "копилка", "text": "т"})
    outside = config.ROOT / ".artel" / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    before = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]

    for bad in ("../outside", "нет-такой"):
        out = run_command(notes.cmd_note, ["--drop-pending", bad])
        assert "note --pending" in out

    assert outside.exists()
    assert (pending_dir() / f"{record_id}.json").exists()
    after = store.db().execute("SELECT COUNT(*) FROM steps").fetchone()[0]
    assert after == before


# ============================== `doc-commit` файла карточек `knowledge/`
#
# Связка «команда `doc-commit` / `notes.doc_commit_content` — проверка
# формы `knowledge_cards` — клон артели — bare `origin` — каталог
# удержанных записей»; прогон полного набора `tests/` подменён шпионом
# `acceptance.run_full_suite` (зелёный ответ): предмет — заводится ли
# гейт, а не сам прогон. Имена файлов карточек, ключи и основания
# коммитов — случайные при каждом запуске; зерно печатается и входит в
# текст провала.

def test_ac14_valid_new_file_committed_with_knowledge_prefix_no_suite(knowledge_box):
    """Верный новый файл в отсутствующем ранее каталоге `knowledge/`
    коммитится в origin с префиксом `knowledge`, без запуска полного
    набора `tests/`, без удержанной записи.

    Ловит мутацию: путь `knowledge/<имя>.yaml` добавлен в
    `DOC_COMMIT_CONFIG_PATHS` (заведён гейт полного набора, префикс
    `config`) либо префикс по-прежнему `config` для всего вне `docs/`
    — шпион набора вызван или тема коммита иная.
    """
    box = knowledge_box
    rel = f"knowledge/{name(box)}.yaml"
    text = valid_text(box)
    message = f"карточки {name(box)}"
    assert not origin_has(box, "knowledge")

    out, exited = via_command(box, rel, text, message)

    assert not exited, msg(box, out)
    assert kc_origin_show(box, rel) == text, msg(box, out)
    assert kc_origin_subject(box) == f"knowledge: {rel} — {message}", (
        msg(box, out))
    box.suite.assert_not_called()
    assert pending_files() == [], msg(box, out)


def test_ac14_knowledge_paths_not_in_config_paths(knowledge_box):
    """Ни один путь под `knowledge/` не входит в
    `notes.DOC_COMMIT_CONFIG_PATHS`.

    Ловит мутацию: системный файл карточек внесён в перечень
    конфигурации Оператора — его `doc-commit` гоняет полный набор.
    """
    for path in notes.DOC_COMMIT_CONFIG_PATHS:
        assert not (path == "knowledge" or path.startswith("knowledge/")), path


def test_ac14_invalid_form_refused_without_commit_or_hold(knowledge_box):
    """Файл неверной формы отвергнут с кодом причины и подробностью;
    коммита нет, запись не удержана — при доступном origin, при
    открытом окне тишины и при отказе `fetch`, через команду и через
    публичную `notes.doc_commit_content`.

    Сценарий: случайный дефект (повтор ключа, неизвестное поле, пустой
    `rule`, ключ не по форме, неизвестный раздел); ожидаемые код и
    подробность — ответ `check_text` на тот же текст; каталог
    `.artel/notes-pending/` после каждого отказа пуст.

    Ловит мутацию: форма проверяется в `_build_doc_commit` — на ветке
    отказа `fetch` он не вызывается, и запись удерживается; либо
    проверка стоит только в `cmd_doc_commit` — `doc_commit_content`
    коммитит неверный файл; либо проверка после окна тишины — запись
    удержана.
    """
    box = knowledge_box
    conditions = (("origin доступен", lambda: None),
                  ("окно тишины открыто", open_window),
                  ("отказ fetch", lambda: break_fetch(box)))
    for label, prepare in conditions:
        prepare()
        for entry in (via_command, via_content):
            rel = f"knowledge/{name(box)}.yaml"
            text = invalid_text(box)
            expected = kc.check_text(text, rel, kc.SYSTEM)
            assert isinstance(expected, kc.Refusal), msg(box, text)
            before = kc_origin_head(box)
            where = f"{label}, {entry.__name__}"
            out, exited = entry(box, rel, text, f"основание {name(box)}")
            assert exited, msg(box, f"{where}: {out}")
            assert expected.code in out, msg(box, f"{where}: {out}")
            assert expected.detail in out, msg(box, f"{where}: {out}")
            assert_nothing_sent(box, before, out)


def test_ac14_nested_and_non_yaml_paths_refused(knowledge_box):
    """Пути `knowledge/a/b.yaml` и `knowledge/x.md` отвергнуты — через
    команду и через `doc_commit_content`, без коммита и удержания.

    Ловит мутацию: допуск пути — префикс `knowledge/` без проверки
    уровня и суффикса — вложенный файл или `.md` закоммичен.
    """
    box = knowledge_box
    text = valid_text(box)
    for rel in (f"knowledge/{name(box)}/{name(box)}.yaml",
                f"knowledge/{name(box)}.md"):
        for entry in (via_command, via_content):
            before = kc_origin_head(box)
            out, exited = entry(box, rel, text, "основание")
            assert exited, msg(box, out)
            assert not origin_has(box, rel), msg(box, out)
            assert_nothing_sent(box, before, out)


def test_ac14_role_environment_refused(knowledge_box):
    """Вызов из окружения роли отказывает `DOC_COMMIT_ROLE_REFUSAL` и
    для `knowledge/<имя>.yaml` — команда и `doc_commit_content`.

    Ловит мутацию: ветка `knowledge/` разобрана до рубежа
    `runner.in_role_environment()` — роль коммитит карточки.
    """
    box = knowledge_box
    rel = f"knowledge/{name(box)}.yaml"
    role = {config.ARTEL_ROLE_ENV: f"role_{name(box)}"}
    for entry in (via_command, via_content):
        before = kc_origin_head(box)
        with mock.patch.dict(os.environ, role):
            out, exited = entry(box, rel, valid_text(box), "основание")
            assert exited, msg(box, out)
            assert notes.DOC_COMMIT_ROLE_REFUSAL in out, msg(box, out)
            assert_nothing_sent(box, before, out)


def test_ac14_previous_paths_behave_as_before(knowledge_box):
    """`docs/**` коммитится с префиксом `docs` без полного набора;
    `roles.yaml` из `DOC_COMMIT_CONFIG_PATHS` — с префиксом `config` и
    через гейт полного набора.

    Ловит мутацию: проверка формы карточек применена ко всем путям
    `doc-commit` (документ `docs/` отвергнут как «файл не разобран»)
    либо ветка `knowledge` перехватила префикс `config`.
    """
    box = knowledge_box
    doc_text = f"# Роадмап\n\n{name(box)}\n"
    out, exited = via_command(box, DOC_REL, doc_text, "раздел")
    assert not exited, msg(box, out)
    assert kc_origin_show(box, DOC_REL) == doc_text, msg(box, out)
    assert kc_origin_subject(box) == f"docs: {DOC_REL} — раздел"
    box.suite.assert_not_called()

    roles_text = f"developer:\n  model: {name(box)}\n"
    out, exited = via_command(box, "roles.yaml", roles_text, "модель")
    assert not exited, msg(box, out)
    assert kc_origin_show(box, "roles.yaml") == roles_text, msg(box, out)
    assert kc_origin_subject(box) == "config: roles.yaml — модель"
    assert box.suite.called, msg(box, out)
