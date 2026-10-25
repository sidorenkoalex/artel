"""Тесты `orchestrator/merge_after.py` и его опор: зависимости мержа
`merge_after` (SPEC 01M44EP0D47F498TEE08MNGBYT), заявленные строкой ТЗ
«Порядок: после …» (SPEC 01M45D29BQJE8FJYJA4JQWSYFZ), переписывание при
делении задачи на гейте SPEC (SPEC 01M4JC58GZFHZ4PZHW254P22M2) и текст
отказа о потере заявленной зависимости с путём reject → эскалация
аналитика → answer в escalated → approve (SPEC 01M5FGHNB29QA254FM07QR55AB)
— волна 3м-2 сведения тестов, SPEC 01M5R0AFX9Z1GA1DG5XV73JRTE; ADR-0027
п. 8.

Свод четырёх прежних файлов:
- `tests/test_merge_after.py` — форма id, узел разрешения префикса,
  повтор после разрешения, пропавшая из БД зависимость на гейте мержа,
  строка мандата «нет» вперемешку с id и повтор строки, совпадающее
  значение PLAN, миграция колонки;
- `tests/test_merge_after_declared.py` — метка не с первой позиции и
  слово, лишь начинающееся с «после», пустой перечень, явный target ещё
  не заведённой задачи, повторный приход на гейт SPEC, обоснование
  коротким префиксом внутри чужого id;
- `tests/test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py` —
  деление родителя заменяет его в `merge_after` зависящих задач последней
  подзадачей, пишет «было → стало» в их журнал, гейт мержа зависящей
  задачи не отказывает по убитому родителю;
- `tests/test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py` — текст отказа
  о потере заявленной зависимости и связка `new --tz` — `answer` в
  `escalated` — сверка гейта SPEC.

Стенды — фикстуры с телами прежних `setUp`: `merge_after_stand` (бывшие
`MergeAfterDbSandbox` и `DeclaredSandbox` — тела равны), `loss_stand`
(бывший `LossRefusalTextTest`), `declared_path_stand` (бывший
`DeclaredPathTest`), `division_stand` поверх `division_sandbox` —
песочницы `DivisionSandbox` с заголовком задачи родителя деления.
Входы деления и подсказки гейта SPEC порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.
Доказательство неослабления — таблицы `mutation-run` «до» и «после» в
PLAN задачи.

Волна 3м-2б (SPEC 01M5RHGRH3YJV8VBFH3QCHD8X0) дописала в конец модуля
свод шести долгоживущих файлов, по разделу на файл:
- `tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py` — мандат
  Оператора «Зависимости мержа: …» в ANSWER-n.md (`escalated`,
  `merge_gate`, отказ до коммита);
- `tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py` — форма
  поля `merge_after` SPEC в guard;
- `tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py` — канал PLAN
  на переходе `in_dev -> verifying`;
- `tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py` —
  проверка значения по БД на `approve` гейта SPEC;
- `tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py` —
  добавка «[ждёт мержа: …]» `status` и строка зависимостей `show`
  (эти пять — SPEC 01M44EP0D47F498TEE08MNGBYT);
- `tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py` —
  заявление зависимостей строкой ТЗ «Порядок: после …» при `new --tz`
  (SPEC 01M45D29BQJE8FJYJA4JQWSYFZ).

Стенды этих разделов — фикстуры с телами прежних `setUp`: `answer_stand`,
`guard_stand`, `plan_stand`, `spec_gate_stand`, `status_show_stand`,
`new_declares_stand`; методы песочниц — функции с префиксом имени
прежнего файла. Подслучаи `subTest` — прежними циклами с ярлыком в тексте
сообщения каждого утверждения.
"""
import contextlib
import io
import os
import random
import re
import sqlite3
import subprocess
from unittest import mock

import pytest

from orchestrator import (answer, catalog, config, fsm, idgen, merge_after,
                          schema, store)
from orchestrator import github_adapter, workspace
from orchestrator.advance_gates import mandate
from scripts import guard
from tests.fixtures import _sandbox
from tests.sandbox import (LightTransitionSandbox, capture_new_task_id,
                           disk_backed_ls_tree_files)

# --- константы и функции прежних модулей (дословно) ---

MARKER = mandate.MERGE_AFTER_MANDATE_MARKER

OTHER_TARGET = "proekt"

# Вымышленный путь зоны: сверка путей SPEC с `zones:` на входе approve
# обязана пройти, иначе до деления дело не дойдёт.
ZONE = "orchestrator/t4jc_zone.py"

DIVIDED_PREFIX = "поделена на:"


def division_spec(task_id: str, parts: int) -> str:
    """SPEC родителя на гейте с секцией «## Деление» из `parts` частей."""
    sections = "\n".join(
        f"### Часть {n} фикстуры\n\n"
        f"Зоны: {ZONE}\n"
        f"Порядок: {'первая, без зависимостей' if n == 1 else f'после части {n - 1}'}\n\n"
        f"Текст ТЗ части {n}.\n"
        for n in range(1, parts + 1))
    return f"""---
task: {task_id}
type: spec
author_role: analyst
status: ready
schema_version: 1
budget_usd: 15
zones: {ZONE}
---

# SPEC: Родитель, поделённый на гейте SPEC

## Контекст
Фикстура деления — короткий безобидный текст.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры.

## Деление

{sections}
## Не входит
- Всё остальное.
"""


FIELD = "merge_after"
MANDATE = "Зависимости мержа:"
LOSS_START = (f"{FIELD} SPEC теряет зависимости, заявленные Оператором строкой "
              f"ТЗ «Порядок: после»: ")
OLD_TAIL = ("снять заявленную может только Оператор: мандат «Зависимости "
            "мержа: …» в ANSWER (artel.py answer {id} <файл>)")
ZONES = "orchestrator/catalog.py"

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
{field_line}---

# SPEC: фикстура подсказки гейта SPEC

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.
"""


def spec_text(task_id: str, value: str | None) -> str:
    field_line = "" if value is None else f"{FIELD}: {value}\n"
    return SPEC_TEXT.format(task=task_id, zones=ZONES, field_line=field_line)


def meta_of(value: str | None) -> dict:
    return {} if value is None else {FIELD: value}


# --- песочница деления и фикстуры стендов ---

class DivisionSandbox(LightTransitionSandbox):
    """Лёгкая песочница переходов с заголовком задачи родителя деления:
    от него деление строит заголовки подзадач."""

    TASK_TITLE = "Родитель, поделённый на гейте SPEC"


@pytest.fixture
def merge_after_stand(light_transition):
    """Стенд бывших `MergeAfterDbSandbox` и `DeclaredSandbox` (тела `setUp`
    равны): лёгкая песочница переходов с подключением `conn`."""
    light_transition.conn = store.db()
    return light_transition


@pytest.fixture
def loss_stand(initialized_tmp_root):
    """Стенд бывшего `LossRefusalTextTest`: инициализированный пульт, зерно
    случайных входов, подключение `conn`, счётчик задач `counter`."""
    initialized_tmp_root.seed = random.randrange(1 << 30)
    print(f"зерно: {initialized_tmp_root.seed}")
    initialized_tmp_root.rng = random.Random(initialized_tmp_root.seed)
    initialized_tmp_root.conn = store.db()
    initialized_tmp_root.counter = 0
    return initialized_tmp_root


@pytest.fixture
def declared_path_stand(light_transition):
    """Стенд бывшего `DeclaredPathTest`: зерно, `conn`, файл зоны SPEC на
    диске, пустой признак роли в окружении до уборки стенда."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.conn = store.db()
    path = light_transition.root / ZONES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# фикстура\n", encoding="utf-8")
    env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
    env.start()
    light_transition.addCleanup(env.stop)
    return light_transition


@pytest.fixture
def division_sandbox():
    """Экземпляр `DivisionSandbox` после `setUp()`."""
    yield from _sandbox(DivisionSandbox)


@pytest.fixture
def division_stand(division_sandbox):
    """Стенд бывшего `DivisionRewritesDependentsTest`: родитель P (задача
    песочницы) на `spec_gate` с секцией «## Деление»; зависящие задачи D
    держат P в `merge_after` в паре с соседями X."""
    division_sandbox.seed = random.randrange(1 << 30)
    print(f"зерно: {division_sandbox.seed}")
    division_sandbox.rnd = random.Random(division_sandbox.seed)
    division_sandbox.parent = division_sandbox.TASK
    division_sandbox.parts = division_sandbox.rnd.randint(2, 4)
    division_sandbox.tdir.mkdir(parents=True, exist_ok=True)
    (division_sandbox.tdir / "SPEC.md").write_text(
        division_spec(division_sandbox.parent, division_sandbox.parts),
        encoding="utf-8")
    division_sandbox.set_state("spec_gate")
    # Зависящие задачи: у каждой P стоит на случайной позиции среди
    # 1..2 соседних зависимостей X (свежих задач, не P).
    division_sandbox.dependents: dict[str, list[str]] = {}
    for n in range(division_sandbox.rnd.randint(2, 3)):
        others = [new_task(division_sandbox, f"Сосед {n}.{k}")
                  for k in range(division_sandbox.rnd.randint(1, 2))]
        deps = list(others)
        deps.insert(division_sandbox.rnd.randint(0, len(deps)),
                    division_sandbox.parent)
        dep_id = new_task(division_sandbox, f"Зависящая задача {n}")
        store.update_task(store.db(), dep_id,
                          merge_after=merge_after.column(deps))
        division_sandbox.dependents[dep_id] = deps
    return division_sandbox


# --- помощники стендов (бывшие методы классов) ---

def merge_after_db_insert(stand, state: str, task_id: str | None = None) -> str:
    task_id = task_id or idgen.new_task_id()
    store.insert_task(stand.conn, task_id, f"Фикстура {task_id}", state,
                      f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def set_deps(stand, task_id: str, deps: list[str]) -> None:
    store.update_task(stand.conn, task_id,
                      merge_after=merge_after.column(deps))


def declared_insert(stand, state: str,
                    target: str = config.DEFAULT_TARGET) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(stand.conn, task_id, f"Фикстура {task_id}", state,
                      f"task/{task_id.lower()}-x", target,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def spec_gate_declared_refusal_spec_text(stand, section: str) -> str:
    return (f"# SPEC\n\n## Обоснование зависимостей мержа\n\n{section}\n\n"
            f"## Критерии приёмки\n")


def new_task(stand, title: str) -> str:
    _, task_id = capture_new_task_id(catalog.cmd_new, title)
    return task_id


def msg(stand, text: str = "") -> str:
    return f"зерно: {stand.seed}; {text}"


def divide(stand) -> list[str]:
    """approve родителя на гейте SPEC; подзадачи деления в порядке
    записи «поделена на: …» журнала родителя."""
    out = stand.capture(fsm.cmd_approve, stand.parent)
    assert "killed" == store.task_state(store.db(), stand.parent), (
        msg(stand, f"деление не состоялось: {out}"))
    details = [r["detail"] or "" for r in
               store.task_steps(store.db(), stand.parent)
               if DIVIDED_PREFIX in (r["detail"] or "")]
    assert details, msg(stand, f"нет записи деления: {out}")
    subtasks = [s.strip() for s in
                details[-1].split(DIVIDED_PREFIX, 1)[1].split(",")]
    assert stand.parts == len(subtasks), msg(stand, details[-1])
    return subtasks


def stored_deps(stand, task_id: str) -> list[str]:
    return merge_after.stored(
        store.get_task(store.db(), task_id)["merge_after"])


def journal(stand, task_id: str) -> list:
    return store.task_steps(store.db(), task_id)


def task(stand) -> str:
    stand.counter += 1
    task_id = f"T6{stand.rng.randrange(1000, 9999)}{stand.counter:02d}"
    store.insert_task(stand.conn, task_id, f"Задача {task_id}", "spec_gate",
                      f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def declared_path_note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def run_cmd(stand, fn, *args) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*args)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue()


def live_task(stand) -> str:
    _, task_id = capture_new_task_id(
        catalog.cmd_new, f"Зависимость {stand.rng.randrange(1 << 20)}")
    return task_id


def declared_task(stand, deps: list[str]) -> str:
    tz = stand.root / f"tz-{stand.rng.randrange(1 << 30)}.md"
    tz.write_text(f"Источник: фикстура {stand.seed}.\n\nТребуется:\n"
                  f"1. Фикстура.\n\nПорядок: после {', '.join(deps)}\n\n"
                  f"Зоны: {ZONES}.\n", encoding="utf-8")
    out, task_id = capture_new_task_id(
        catalog.cmd_new, f"Задача {stand.rng.randrange(1 << 20)}", str(tz))
    assert merge_after.stored(store.get_task(
        stand.conn, task_id)["merge_after"]) == deps, (
        declared_path_note(stand, f"предпосылка: new не заявил {deps}:\n{out}"))
    return task_id


def refusal(stand, task_id: str, value: str | None) -> tuple[list, str | None]:
    return merge_after.spec_gate_declared_refusal(
        stand.conn, task_id, store.get_task(stand.conn, task_id),
        meta_of(value), value, spec_text(task_id, value))


def no_code_tree(branch, rel, *, repo=None):
    if rel == ".":
        return None
    return disk_backed_ls_tree_files(branch, rel, repo=repo)


# --- TaskIdFormTest (бывший test_merge_after.py) ---

def test_form_accepts_ids_prefixes_and_legacy_rejects_rest():
    """Полный id, его префикс и `Tnnn` — годная форма; строчные буквы,
    буквы вне алфавита ULID, пробел и id длиннее полного — нет.

    Ловит мутацию: проверка длины снята (строка длиннее 26 символов
    алфавита проходит) либо алфавит не сверяется (строчный id или `I`
    проходят).
    """
    full = idgen.new_task_id()
    for good in (full, full[:8], "T101"):
        assert idgen.is_task_id_form(good), good
    for bad in ("", full.lower(), full + "0", "01MI", "foo bar"):
        assert not idgen.is_task_id_form(bad), bad


# --- TaskIdMatchesTest (бывший test_merge_after.py) ---

def test_exact_match_wins_over_longer_ids_with_same_prefix(merge_after_stand):
    """Id, который сам является префиксом другого id, разрешается в себя.

    Ловит мутацию: точное совпадение не проверяется первым — `T1` при
    наличии `T10` объявляется неоднозначным.
    """
    merge_after_db_insert(merge_after_stand, "in_dev", "T1")
    merge_after_db_insert(merge_after_stand, "in_dev", "T10")

    assert store.task_id_matches(merge_after_stand.conn, "T1") == ["T1"]
    assert sorted(store.task_id_matches(merge_after_stand.conn, "T1")
                  + store.task_id_matches(merge_after_stand.conn, "T10")) == \
        ["T1", "T10"]


# --- CheckTest (бывший test_merge_after.py) ---

def test_prefix_and_full_id_of_same_task_is_a_repeat(merge_after_stand):
    """Префикс и полный id одной задачи в одном значении — повтор после разрешения.

    Ловит мутацию: повтор сверяется только по буквальному тексту
    элемента — в колонку попала бы одна задача дважды.
    """
    dep = merge_after_db_insert(merge_after_stand, "in_dev")

    ids, reasons = merge_after.check(merge_after_stand.conn,
                                     merge_after_stand.TASK, [dep, dep[:-1]])

    assert ids == []
    assert [r for r in reasons if "повтор" in r], reasons


def test_done_dependency_is_valid(merge_after_stand):
    """Зависимость в `done` годна — её мерж уже состоялся.

    Ловит мутацию: проверка состояния отказывает любой завершённой
    задаче (`done` спутан с `killed`).
    """
    dep = merge_after_db_insert(merge_after_stand, "done")

    assert merge_after.check(merge_after_stand.conn, merge_after_stand.TASK,
                             [dep]) == ([dep], [])


# --- MergeGateMissingDependencyTest (бывший test_merge_after.py) ---

def test_dependency_missing_from_db_refuses_with_answer_channel(
        merge_after_stand):
    """Зависимость, пропавшая из БД, — отказ с каналом снятия, не «повтори approve».

    Ловит мутацию: пропавшая зависимость обрабатывается как
    незавершённая — Оператору советуют повторять `approve`, которая не
    пройдёт никогда.
    """
    ghost = idgen.new_task_id()
    set_deps(merge_after_stand, merge_after_stand.TASK, [ghost])
    t = store.get_task(merge_after_stand.conn, merge_after_stand.TASK)

    out = merge_after_stand.capture(merge_after.merge_gate_refuses,
                                    merge_after_stand.conn,
                                    merge_after_stand.TASK, t)

    assert ghost in out
    assert merge_after.MISSING_STATE in out
    assert "answer" in out
    assert MARKER in out


# --- MandateLineTest (бывший test_merge_after.py) ---

def test_none_word_mixed_with_ids_refused(merge_after_stand):
    """«нет» рядом с id в одной строке — отказ проверки строки мандата.

    Ловит мутацию: «нет» молча отбрасывается из перечня до проверки
    (строка читается как перечень одних id) — неоднозначная строка
    проходит.
    """
    dep = merge_after_db_insert(merge_after_stand, "in_dev")

    found = mandate.refusals(f"{MARKER} {dep}, нет\n", None,
                             conn=merge_after_stand.conn,
                             task_id=merge_after_stand.TASK)

    assert found


def test_two_mandate_lines_refused(merge_after_stand):
    """Две строки «Зависимости мержа:» в одном ответе — отказ.

    Ловит мутацию: берётся первая строка, вторая молча теряется —
    Оператор не узнаёт, какое из двух значений вступило в силу.
    """
    first, second = (merge_after_db_insert(merge_after_stand, "in_dev"),
                     merge_after_db_insert(merge_after_stand, "in_dev"))

    found = mandate.refusals(f"{MARKER} {first}\n{MARKER} {second}\n",
                             None, conn=merge_after_stand.conn,
                             task_id=merge_after_stand.TASK)

    assert [f for f in found if "повторена" in f], found


# --- PlanChannelSameValueTest (бывший test_merge_after.py) ---

def test_plan_value_equal_to_db_after_resolution_is_silent(merge_after_stand):
    """PLAN со значением, совпадающим с БД после разрешения префиксов, журнал не трогает.

    Ловит мутацию: сравнение идёт по сырому тексту PLAN — префикс
    прежней зависимости без обоснования даёт запись «отклонён».
    """
    dep = merge_after_db_insert(merge_after_stand, "in_dev")
    set_deps(merge_after_stand, merge_after_stand.TASK, [dep])
    t = store.get_task(merge_after_stand.conn, merge_after_stand.TASK)
    before = len(store.task_steps(merge_after_stand.conn,
                                  merge_after_stand.TASK))

    merge_after.apply_plan(merge_after_stand.conn, merge_after_stand.TASK, t,
                           {"merge_after": dep[:-2]},
                           "## Влияние на систему\n\nНет.\n")

    assert len(store.task_steps(merge_after_stand.conn,
                                merge_after_stand.TASK)) == before
    assert merge_after.stored(
        store.get_task(merge_after_stand.conn,
                       merge_after_stand.TASK)["merge_after"]) == [dep]


# --- ReplaceDividedTest (бывший test_merge_after.py) ---

def test_task_not_depending_on_parent_is_untouched(merge_after_stand):
    """Деление родителя не трогает задачу, в чьём `merge_after` его нет.

    Ловит мутацию: фильтр «родитель в значении» снят — колонка
    независимой задачи переписывается тем же значением, а в её журнал
    ложится лишняя запись «merge_after изменён».
    """
    parent, other, successor = (merge_after_db_insert(merge_after_stand,
                                                      "in_dev"),
                                merge_after_db_insert(merge_after_stand,
                                                      "in_dev"),
                                merge_after_db_insert(merge_after_stand,
                                                      "spec_writing"))
    set_deps(merge_after_stand, merge_after_stand.TASK, [other])
    before = len(store.task_steps(merge_after_stand.conn,
                                  merge_after_stand.TASK))

    merge_after_stand.capture(merge_after.replace_divided,
                              merge_after_stand.conn, parent, successor)

    assert len(store.task_steps(merge_after_stand.conn,
                                merge_after_stand.TASK)) == before
    assert merge_after.stored(
        store.get_task(merge_after_stand.conn,
                       merge_after_stand.TASK)["merge_after"]) == [other]


# --- MigrationTest (бывший test_merge_after.py) ---

def test_migrate_adds_merge_after_to_old_tasks_table():
    """`migrate` догоняет таблицу `tasks` прошлой версии колонкой `merge_after`.

    Ловит мутацию: колонка добавлена только в DDL — БД, созданная до
    задачи, остаётся без неё, и чтение `t["merge_after"]` падает.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, "
                 "state TEXT, branch TEXT)")
    try:
        schema.migrate(conn)
    except sqlite3.Error:
        pass  # прочие шаги миграции пустой БД здесь не предмет
    assert "merge_after" in schema.table_columns(conn, "tasks")


# --- DeclaredFromTzTest (бывший test_merge_after_declared.py) ---

def test_label_must_start_line_and_word_must_be_whole(merge_after_stand):
    """Метка с отступом и «Порядок: послезавтра» зависимостей не заявляют.

    Ловит мутацию: метка ищется в любом месте строки (без `^`) либо
    слово «после» сверяется префиксом — элемент «завтра …»/строка с
    отступом дают перечень или отказ формы.
    """
    dep = declared_insert(merge_after_stand, "in_dev")
    for tz in (f"  Порядок: после {dep}\n",
               f"Порядок: послезавтра {dep}\n"):
        assert merge_after.declared_from_tz(
            merge_after_stand.conn, tz, config.DEFAULT_TARGET) == ([], []), (
            f"tz={tz!r}")


def test_empty_list_is_refused(merge_after_stand):
    """«Порядок: после» без id до скобки — отказ, а не молчаливое «зависимостей нет».

    Ловит мутацию: пустой перечень возвращается как ([], []) — `new`
    заводит задачу, хотя строка заявляет зависимость.
    """
    ids, reasons = merge_after.declared_from_tz(
        merge_after_stand.conn, "Порядок: после (уточню позже)\n",
        config.DEFAULT_TARGET)

    assert ids == []
    assert reasons


def test_explicit_target_of_new_task_is_used(merge_after_stand):
    """Зависимость того же не-основного target, что у заводимой задачи, проходит.

    Ловит мутацию: `check` берёт target из строки БД несуществующей
    задачи (`store.task_target` — target по умолчанию) — зависимость
    target'а `proekt` отказана как чужая.
    """
    dep = declared_insert(merge_after_stand, "in_dev", target=OTHER_TARGET)

    assert merge_after.declared_from_tz(
        merge_after_stand.conn, f"Порядок: после {dep}.\n",
        OTHER_TARGET) == ([dep], [])


# --- SpecGateDeclaredRefusalTest (бывший test_merge_after_declared.py) ---

def test_no_check_after_spec_gate_was_passed(merge_after_stand):
    """После прохода гейта SPEC колонка — рабочее значение, сверки с ним нет.

    Сценарий: колонка несёт зависимость, журнал задачи — переход
    `state -> tests_writing`; поле SPEC её не несёт.

    Ловит мутацию: признак «гейт SPEC уже пройден» снят — повторный
    approve отказывает как теряющий заявленную.
    """
    dep = declared_insert(merge_after_stand, "in_dev")
    store.update_task(merge_after_stand.conn, merge_after_stand.TASK,
                      merge_after=dep)
    t = store.get_task(merge_after_stand.conn, merge_after_stand.TASK)
    assert merge_after.spec_gate_declared_refusal(
        merge_after_stand.conn, merge_after_stand.TASK, t, {}, None,
        "")[1] is not None

    store.journal(merge_after_stand.conn, merge_after_stand.TASK, "operator",
                  "state -> tests_writing", "гейт SPEC пройден")

    assert merge_after.spec_gate_declared_refusal(
        merge_after_stand.conn, merge_after_stand.TASK, t, {}, None,
        "") == ([], None)


def test_short_prefix_inside_other_id_is_not_justification(merge_after_stand):
    """Префикс добавки, встречающийся только внутри чужого id в разделе, обоснованием не считается.

    Ловит мутацию: обоснование ищется подстрокой, а не словом целиком —
    добавка, не названная в разделе, принимается.
    """
    declared = declared_insert(merge_after_stand, "in_dev")
    added = declared_insert(merge_after_stand, "in_dev")
    shared = 0
    while declared[shared] == added[shared]:
        shared += 1
    prefix = added[:shared + 1]
    store.update_task(merge_after_stand.conn, merge_after_stand.TASK,
                      merge_after=declared)
    t = store.get_task(merge_after_stand.conn, merge_after_stand.TASK)
    meta = {merge_after.FIELD: f"{declared}, {prefix}"}
    # Раздел называет только заявленную, но с хвостом, где префикс
    # добавки стоит внутри слова.
    text = spec_gate_declared_refusal_spec_text(
        merge_after_stand, f"Заявлена {declared}; см. X{prefix}Y.")

    added_ids, reason = merge_after.spec_gate_declared_refusal(
        merge_after_stand.conn, merge_after_stand.TASK, t, meta,
        f"{declared}, {added}", text)

    assert added_ids == []
    assert added in (reason or "")


# --- DivisionRewritesDependentsTest (бывший
# test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py) ---

def test_ac1_parent_replaced_by_last_subtask_in_every_dependent(division_stand):
    """Деление P на S1…Sn: у каждой зависящей задачи D элемент P в
    `merge_after` заменён на Sn на той же позиции, соседи X остались.

    Зависящих задач две-три, у каждой P стоит на случайной позиции
    рядом с одной-двумя другими зависимостями.

    Ловит мутацию: вместо последней подзадачи подставлена первая
    (`new_ids[0]`) — значение D называет S1, а не Sn; элемент P
    удалён вместо замены — значение короче прежнего; переписана только
    первая найденная зависящая задача — у второй D в колонке остаётся
    P; соседи X отброшены (значение — один Sn).
    """
    subtasks = divide(division_stand)
    last = subtasks[-1]
    for dep_id, before in division_stand.dependents.items():
        expected = [last if d == division_stand.parent else d for d in before]
        assert expected == stored_deps(division_stand, dep_id), (
            msg(division_stand, f"merge_after {dep_id}: было {before}, подзадачи "
                f"{subtasks}"))


def test_ac2_dependent_journal_names_old_and_new_value(division_stand):
    """Деление P добавляет в журнал каждой зависящей задачи D запись
    `merge_after` «было → стало»: слева прежнее значение с P, справа
    новое — с Sn вместо P.

    Ловит мутацию: колонка D переписана прямым `store.update_task`
    мимо `merge_after.rewrite` — значение новое, а записи
    «merge_after изменён» в журнале D нет; запись сделана в журнал
    родителя P вместо журнала D.
    """
    subtasks = divide(division_stand)
    last = subtasks[-1]
    for dep_id, before in division_stand.dependents.items():
        after = [last if d == division_stand.parent else d for d in before]
        records = [r["detail"] or "" for r in journal(division_stand, dep_id)
                   if r["action"] == merge_after.CHANGED_ACTION]
        assert records, msg(
            division_stand,
            f"в журнале {dep_id} нет «{merge_after.CHANGED_ACTION}»")
        detail = records[-1]
        assert "→" in detail, msg(division_stand, detail)
        old_part, new_part = detail.split("→", 1)
        assert merge_after.column(before) in old_part, (
            msg(division_stand, f"прежнее значение не названо: {detail}"))
        assert merge_after.column(after) in new_part, (
            msg(division_stand, f"новое значение не названо: {detail}"))
        assert division_stand.parent not in new_part, msg(division_stand,
                                                          detail)


def test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent(division_stand):
    """После деления P approve на `merge_gate` зависящей задачи D не
    пишет отказ «зависимость мержа убита» по P.

    D ставится на `merge_gate`, approve вызывается командой; отказ
    «ждёт мержа зависимостей» по ещё не смерженной Sn законен и
    критерием не запрещён.

    Ловит мутацию: деление не переписывает `merge_after` зависящих
    задач (поведение до задачи) либо переписывает только колонку
    родителя — `merge_gate_refuses` видит P в `killed` и журналирует
    «approve отклонён: зависимость мержа убита» с id P.
    """
    divide(division_stand)
    conn = store.db()
    for dep_id in division_stand.dependents:
        conn.execute("UPDATE tasks SET state='merge_gate' WHERE id=?",
                     (dep_id,))
        conn.commit()
        try:
            out = division_stand.capture(fsm.cmd_approve, dep_id)
        except SystemExit as exc:
            out = f"SystemExit: {exc}"
        refusals = [r["detail"] or "" for r in journal(division_stand, dep_id)
                    if r["action"] == merge_after.MERGE_GATE_KILLED_ACTION
                    and division_stand.parent in (r["detail"] or "")]
        assert [] == refusals, msg(
            division_stand,
            f"approve {dep_id} отказал по убитому {division_stand.parent}: "
            f"{out}")


# --- LossRefusalTextTest (бывший
# test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py) ---

def test_ac8_loss_refusal_leads_through_reject_and_escalated_answer(loss_stand):
    """Отказ о потере заявленной зависимости сохраняет начало и ведёт через reject, эскалацию аналитика, answer в escalated и approve.

    Сценарий: задача на `spec_gate` с одной-тремя заявленными
    зависимостями в колонке `merge_after`; поле SPEC от зерна либо
    отсутствует, либо несёт часть заявленных. Отказ начинается прежним
    текстом «merge_after SPEC теряет зависимости, заявленные Оператором
    строкой ТЗ «Порядок: после»: <полные id потерянных>»; содержит
    «reject», «эскалац», «аналитик», «answer», «Зависимости мержа:»,
    «escalated» и «approve»; первое «answer» стоит после первого
    «reject»; прежнего хвоста «снять заявленную может только Оператор:
    мандат … в ANSWER (artel.py answer <id> <файл>)» нет.

    Ловит мутацию: хвост отказа не заменён (по-прежнему советует answer
    мимо reject) — нет «reject»/«escalated», прежний хвост на месте;
    новый текст называет answer раньше reject — порядок не сходится;
    правка задела начало отказа (поле, фраза или список id) — начало
    расходится.
    """
    for _ in range(3):
        task_id = task(loss_stand)
        declared = [task(loss_stand)
                    for _ in range(loss_stand.rng.randint(1, 3))]
        store.update_task(loss_stand.conn, task_id,
                          merge_after=merge_after.column(declared))
        kept = [d for d in declared if loss_stand.rng.random() < 0.5]
        if len(kept) == len(declared):
            kept.pop(loss_stand.rng.randrange(len(kept)))
        value = merge_after.column(kept) if kept and loss_stand.rng.random() < 0.7 else None
        lost = [d for d in declared if d not in merge_after.stored(value)]
        t = store.get_task(loss_stand.conn, task_id)

        added, reason = merge_after.spec_gate_declared_refusal(
            loss_stand.conn, task_id, t, meta_of(value), value,
            spec_text(task_id, value))

        failure_note = (f"зерно: {loss_stand.seed}; заявлено {declared}, поле SPEC "
                        f"{value!r}; отказ: {reason!r}")
        assert added == [], failure_note
        assert reason is not None, failure_note
        assert reason.startswith(LOSS_START + ", ".join(lost)), failure_note
        for word in ("reject", "эскалац", "аналитик", "answer", MANDATE,
                     "escalated", "approve"):
            assert word in reason, f"нет «{word}»: {failure_note}"
        assert reason.index("reject") < reason.index("answer"), failure_note
        assert OLD_TAIL.format(id=task_id) not in reason, failure_note
        assert "снять заявленную может только Оператор: мандат" not in reason, (
            failure_note)


# --- DeclaredPathTest (бывший
# test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py) ---

def test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged(
        declared_path_stand):
    """`answer` с «Зависимости мержа: …» в escalated меняет колонку, и тот же SPEC проходит сверку; отказ о добавке и отказы гейта мержа — прежние.

    Сценарий: задача заведена `new` с одной-двумя заявленными
    зависимостями; SPEC теряет хотя бы одну (поле — часть заявленных
    либо его нет) — сверка отказывает. Задача уходит в `escalated` из
    `spec_writing`, `answer` со строкой «Зависимости мержа: <значение
    поля SPEC или «нет»>» меняет колонку на это значение; тот же SPEC
    проходит `spec_gate_declared_refusal` без отказа. Затем: SPEC с
    добавкой сверх заявленного без раздела обоснования — отказ прежним
    текстом; `merge_gate_refuses` на убитой и на незавершённой
    зависимости — прежние текст журнала и строка вывода.

    Ловит мутацию: правка текста отказа задела соседние ветки — отказ о
    добавке без обоснования или отказы гейта мержа сменили текст;
    `answer` в escalated перестал менять колонку (мандат не применён) —
    тот же SPEC снова отказан.
    """
    deps = [live_task(declared_path_stand)
            for _ in range(declared_path_stand.rng.randint(1, 2))]
    task_id = declared_task(declared_path_stand, deps)
    kept = deps[:declared_path_stand.rng.randint(0, len(deps) - 1)]
    value = merge_after.column(kept)
    _, before = refusal(declared_path_stand, task_id, value)
    assert before is not None, declared_path_note(
        declared_path_stand, f"предпосылка: SPEC {value!r} "
        f"не отказан при заявленных {deps}")

    declared_path_stand.conn.execute(
        "UPDATE tasks SET state='escalated', "
        "escalated_from='spec_writing' WHERE id=?", (task_id,))
    declared_path_stand.conn.commit()
    line = f"{MANDATE} {', '.join(kept) if kept else 'нет'}"
    source = declared_path_stand.root / (
        f"answer-{declared_path_stand.rng.randrange(1 << 30)}.txt")
    source.write_text(f"{line}\n\nОснование: решение Оператора "
                      f"({declared_path_stand.seed}).\n", encoding="utf-8")
    with mock.patch("orchestrator.gitcmd.ls_tree_files", no_code_tree):
        out = run_cmd(declared_path_stand, answer.cmd_answer, task_id,
                      str(source))
    assert merge_after.stored(store.get_task(
        declared_path_stand.conn, task_id)["merge_after"]) == kept, (
        declared_path_note(declared_path_stand,
                           f"answer «{line}» не сменил колонку:\n{out}"))
    declared_path_stand.conn.execute(
        "UPDATE tasks SET state='spec_gate' WHERE id=?", (task_id,))
    declared_path_stand.conn.commit()
    added, after = refusal(declared_path_stand, task_id, value)
    assert after is None, declared_path_note(
        declared_path_stand, f"тот же SPEC {value!r} отказан после "
        f"answer: {after}")
    assert added == [], declared_path_note(declared_path_stand, "добавки нет")

    other = declared_task(declared_path_stand, [live_task(declared_path_stand)])
    extra = live_task(declared_path_stand)
    declared = merge_after.stored(store.get_task(
        declared_path_stand.conn, other)["merge_after"])
    _, unjustified = refusal(declared_path_stand, other,
                             merge_after.column(declared + [extra]))
    assert unjustified == (
        f"{FIELD} SPEC добавляет зависимости сверх заявленных Оператором без "
        f"обоснования: {extra} — назови каждую в разделе «## Обоснование "
        f"зависимостей мержа» SPEC"), declared_path_note(declared_path_stand,
                                                       "отказ о добавке")

    for dep_state in ("killed", "in_dev"):
        dep = live_task(declared_path_stand)
        gate = live_task(declared_path_stand)
        declared_path_stand.conn.execute(
            "UPDATE tasks SET state=? WHERE id=?", (dep_state, dep))
        declared_path_stand.conn.execute(
            "UPDATE tasks SET state='merge_gate', "
            "merge_after=? WHERE id=?", (dep, gate))
        declared_path_stand.conn.commit()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            refused = merge_after.merge_gate_refuses(
                declared_path_stand.conn, gate,
                store.get_task(declared_path_stand.conn, gate))
        if dep_state == "killed":
            action = "approve отклонён: зависимость мержа убита"
            reason = (f"зависимость мержа не завершится: {dep} (killed) — "
                      f"сними или замени её ответом Оператора: artel.py "
                      f"answer {gate} <файл> со строкой «{MANDATE} <id>, "
                      f"…» (или «{MANDATE} нет»)")
        else:
            action = "approve отклонён: зависимости мержа не в done"
            reason = (f"ждёт мержа зависимостей: {dep} (in_dev) — повтори, "
                      f"когда они будут в done: artel.py approve {gate}")
        rows = store.task_steps(declared_path_stand.conn, gate)
        failure_note = declared_path_note(declared_path_stand,
                                          f"вывод: {buf.getvalue()!r}")
        assert refused, failure_note + "; " + f"dependency={dep_state!r}"
        assert (rows[-1]["action"], rows[-1]["detail"]) == (action, reason), (
            failure_note + "; " + f"dependency={dep_state!r}")
        assert buf.getvalue() == f"[{gate}] {action}: {reason}\n", (
            failure_note + "; " + f"dependency={dep_state!r}")


# --- AnswerMandateSandbox, AnswerMandateAcceptedTest, AnswerMandateRefusedTest (бывший test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py) ---

ANSWER_MARKER = "Зависимости мержа:"
DOCS_REF_PREFIX = "refs/artifacts/"
ARROW = re.compile(r"→|->")
def ids_of(value) -> list[str]:
    """Перечень id в значении колонки `merge_after` (пусто/NULL — пустой)."""
    return re.findall(r"[0-9A-Za-z]+", value or "")



@pytest.fixture
def answer_stand(real_git):
    """Стенд бывшего `AnswerMandateSandbox`: тело его `setUp`."""
    real_git.seed = random.randrange(1 << 30)
    print(f"зерно: {real_git.seed}")
    real_git.rng = random.Random(real_git.seed)
    real_git.add_synced_origin()
    real_git.conn = store.db()
    answer_role_env(real_git, "")
    return real_git


def answer_note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def answer_role_env(stand, value: str) -> None:
    patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: value})
    patcher.start()
    stand.addCleanup(patcher.stop)


def answer_insert(stand, state: str) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(stand.conn, task_id, f"Фикстура {task_id}", state,
                      f"task/{task_id.lower()}-fixture",
                      config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
    return task_id


def answer_unique_prefix(stand, task_id: str) -> str:
    others = [r["id"] for r in store.all_tasks(stand.conn) if r["id"] != task_id]
    shortest = next(n for n in range(1, len(task_id) + 1)
                    if not any(o.startswith(task_id[:n]) for o in others))
    return task_id[:stand.rng.randint(shortest, len(task_id))]


def answer_element(stand, task_id: str) -> str:
    return task_id if stand.rng.random() < 0.5 else answer_unique_prefix(stand, task_id)


def answer_mandate_line(stand, deps) -> str:
    """Строка мандата: `deps` — перечень задач либо `None` («нет»)."""
    if deps is None:
        return f"{ANSWER_MARKER} нет"
    return f"{ANSWER_MARKER} {', '.join(answer_element(stand, d) for d in deps)}"


def answer_set_state(stand, task_id: str, state: str) -> None:
    stand.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    stand.conn.commit()


def answer_deps(stand, task_id: str) -> list[str]:
    return ids_of(store.get_task(stand.conn, task_id)["merge_after"])


def answer_answers(stand, task_id: str) -> list[str]:
    ref = DOCS_REF_PREFIX + task_id
    if not stand.git("for-each-ref", "--format=%(objectname)", ref).strip():
        return []
    return sorted(p.rsplit("/", 1)[-1] for p in stand.git(
        "ls-tree", "-r", "--name-only", ref).splitlines()
        if p.rsplit("/", 1)[-1].startswith("ANSWER-"))


def answer_run_answer(stand, task_id: str, body: str) -> tuple[str, bool]:
    """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
    source = stand.root / ".artel" / f"answer-{stand.rng.randrange(1 << 30)}.txt"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(f"{body}\n\nОснование: решение Оператора "
                      f"({stand.seed}).\n", encoding="utf-8")
    buf = io.StringIO()
    failed = False
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            answer.cmd_answer(task_id, str(source))
        except SystemExit as exc:
            if exc.code not in (None, 0):
                failed = True
                buf.write(f"\n{exc.code}")
    return buf.getvalue(), failed


def answer_last_step_id(stand, task_id: str) -> int:
    rows = store.task_steps(stand.conn, task_id)
    return rows[-1]["id"] if rows else 0


def answer_journal_since(stand, task_id: str, since: int) -> list[str]:
    return [f"{r['action']} | {r['detail'] or ''}"
            for r in store.task_steps(stand.conn, task_id) if r["id"] > since]


def answer_accepted(stand, task_id: str, body: str, case: str = "") -> list[str]:
    """`answer` с `body` принят: ANSWER добавлен в ссылку документов;
    возврат — записи журнала, сделанные командой."""
    before = answer_answers(stand, task_id)
    since = answer_last_step_id(stand, task_id)
    out, failed = answer_run_answer(stand, task_id, body)
    assert not failed, answer_note(stand, f"answer отказала:\n{out}") + case
    assert len(answer_answers(stand, task_id)) == len(before) + 1, (
        answer_note(stand, f"ANSWER не создан:\n{out}") + case)
    return answer_journal_since(stand, task_id, since)


def answer_assert_refused(stand, task_id: str, body: str, note: str, case: str = "") -> None:
    """`answer` с `body` отказала до коммита: ANSWER не появился в
    ссылке документов, колонка `merge_after` прежняя."""
    before_answers = answer_answers(stand, task_id)
    before_deps = answer_deps(stand, task_id)

    out, failed = answer_run_answer(stand, task_id, body)

    context = answer_note(stand, f"{note}\nфайл: {body!r}\nвывод:\n{out}")
    assert failed, context + case
    assert answer_answers(stand, task_id) == before_answers, context + case
    assert answer_deps(stand, task_id) == before_deps, context + case


def test_ac11_escalated_answer_sets_and_clears_value(answer_stand):
    """`answer` в `escalated` пишет значение строки мандата полными id, «нет» очищает.

    Сценарий: задача в `escalated` без зависимостей; ANSWER со строкой
    `Зависимости мержа:` на одну-три живые задачи (префиксами или
    полными id, от зерна) — колонка равна их полным id в порядке
    строки, запись журнала называет новые id со стрелкой «было →
    стало». Второй ANSWER со строкой `Зависимости мержа: нет` —
    колонка пуста, запись журнала называет снятые id со стрелкой.

    Ловит мутацию: значение строки мандата не применяется
    (`merge_after.mandate_value` отдаёт перечень причин `check` вместо
    полных id) либо «нет» читается как id задачи — колонка расходится с
    ожидаемой или ANSWER отказан.
    """
    task_id = answer_insert(answer_stand, "escalated")
    deps = [answer_insert(answer_stand, answer_stand.rng.choice(["in_dev", "acceptance", "done"]))
            for _ in range(answer_stand.rng.randint(1, 3))]

    entries = answer_accepted(answer_stand, task_id, answer_mandate_line(answer_stand, deps))

    assert answer_deps(answer_stand, task_id) == deps, answer_note(answer_stand, f"журнал: {entries}")
    assert ([e for e in entries
         if ARROW.search(e) and all(d in e for d in deps)]), (
        answer_note(answer_stand, f"нет записи «было → стало» с {deps}: {entries}"))

    entries = answer_accepted(answer_stand, task_id, answer_mandate_line(answer_stand, None))

    assert answer_deps(answer_stand, task_id) == [], answer_note(answer_stand, f"журнал: {entries}")
    assert ([e for e in entries
         if ARROW.search(e) and all(d in e for d in deps)]), (
        answer_note(answer_stand, f"нет записи «было → стало» со снятыми "
        f"{deps}: {entries}"))


def test_ac11_merge_gate_answer_outside_role_env_accepted(answer_stand):
    """В `merge_gate` ANSWER со строкой мандата принимается вне окружения роли.

    Сценарий: задача получила зависимости мандатом в `escalated`, затем
    одна из них убита, а задача стоит на `merge_gate`. ANSWER со
    строкой `Зависимости мержа:` — от зерна «нет» либо перечень
    оставшихся живых — принят: ANSWER добавлен в ссылку документов,
    колонка равна новому значению.

    Ловит мутацию: перечень принимающих состояний `answer` не дополнен
    `merge_gate` — команда отказывает «answer доступна только для
    задачи в состоянии escalated», у задачи с убитой зависимостью нет
    штатного выхода.
    """
    task_id = answer_insert(answer_stand, "escalated")
    deps = [answer_insert(answer_stand, "acceptance") for _ in range(answer_stand.rng.randint(1, 3))]
    answer_accepted(answer_stand, task_id, answer_mandate_line(answer_stand, deps))
    killed = answer_stand.rng.choice(deps)
    answer_set_state(answer_stand, killed, "killed")
    answer_set_state(answer_stand, task_id, "merge_gate")
    alive = [d for d in deps if d != killed]
    new = None if not alive or answer_stand.rng.random() < 0.5 else alive

    answer_accepted(answer_stand, task_id, answer_mandate_line(answer_stand, new))

    assert answer_deps(answer_stand, task_id) == list(new or []), (
        answer_note(answer_stand, f"было {deps}, убита {killed}"))


def test_ac12_invalid_mandate_element_refused_before_commit(answer_stand):
    """Строка мандата с негодной зависимостью — отказ `answer` до коммита ANSWER.

    Сценарий: для каждого варианта — своя задача в `escalated`, у части
    (от зерна) уже есть прежнее значение из живой задачи. Строка
    `Зависимости мержа:` называет несуществующий id, убитую задачу, id
    самой задачи либо задачу, чья колонка уже ведёт в эту задачу
    (цикл). `answer` завершается отказом, ANSWER-n.md в ссылке
    документов не появляется, колонка прежняя.

    Ловит мутацию: проверка правил гейта SPEC в узле мандата снята
    (проверяется только форма строки) либо стоит после коммита ANSWER —
    ANSWER появляется в ссылке документов или колонка переписана.
    """
    cases = ["нет такой задачи", "убитая", "собственная", "цикл"]
    answer_stand.rng.shuffle(cases)
    for case in cases:
        task_id = answer_insert(answer_stand, "escalated")
        if answer_stand.rng.random() < 0.5:
            answer_accepted(answer_stand, task_id, answer_mandate_line(answer_stand, [answer_insert(answer_stand, "in_dev")]), "; " + f"case={case!r}")
        if case == "нет такой задачи":
            line = f"{ANSWER_MARKER} {idgen.new_task_id()}"
        elif case == "убитая":
            line = answer_mandate_line(answer_stand, [answer_insert(answer_stand, "killed")])
        elif case == "собственная":
            line = answer_mandate_line(answer_stand, [task_id])
        else:
            other = answer_insert(answer_stand, "escalated")
            answer_accepted(answer_stand, other, answer_mandate_line(answer_stand, [task_id]), "; " + f"case={case!r}")
            line = answer_mandate_line(answer_stand, [other])

        answer_assert_refused(answer_stand, task_id, line, case, "; " + f"case={case!r}")


def test_ac12_merge_gate_without_line_or_from_role_env_refused(answer_stand):
    """В `merge_gate` отказ ANSWER без строки мандата и вызова из окружения роли.

    Сценарий: задача на `merge_gate` с живой зависимостью. Первый вызов
    — файл без строки `Зависимости мержа:` вне окружения роли; второй —
    файл с годной строкой (от зерна «нет» или другая живая задача), но
    процесс в окружении роли. Оба раза `answer` отказывает, ANSWER не
    появляется в ссылке документов, колонка прежняя.

    Ловит мутацию: в `merge_gate` принимается любой ANSWER либо рубеж
    `runner.in_role_environment` для `merge_gate` не стоит — роль сама
    себе снимает зависимость мержа.
    """
    task_id = answer_insert(answer_stand, "escalated")
    answer_accepted(answer_stand, task_id, answer_mandate_line(answer_stand, [answer_insert(answer_stand, "acceptance")]))
    answer_set_state(answer_stand, task_id, "merge_gate")

    answer_assert_refused(answer_stand, task_id, "Ответ: продолжай как решено.",
                        "merge_gate, файл без строки мандата")

    valid = answer_mandate_line(answer_stand, None if answer_stand.rng.random() < 0.5
                              else [answer_insert(answer_stand, "in_dev")])
    answer_role_env(answer_stand, answer_stand.rng.choice(["developer", "reviewer"]))
    answer_assert_refused(answer_stand, task_id, valid, "merge_gate, окружение роли")


# --- GuardMergeAfterFieldTest (бывший test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py) ---

GUARD_SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: {version}
zones: orchestrator/catalog.py
budget_usd: 30
{field_line}---

# SPEC: фикстура поля зависимостей мержа

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.

## Не входит

Ничего.
"""
REPEAT_WORDS = re.compile(r"повтор|дубл|дважды", re.IGNORECASE)

@pytest.fixture
def guard_stand(tmp_dir):
    """Стенд бывшего `GuardMergeAfterFieldTest`: тело его `setUp`."""
    tmp_dir.seed = random.randrange(1 << 30)
    print(f"зерно: {tmp_dir.seed}")
    tmp_dir.rng = random.Random(tmp_dir.seed)
    return tmp_dir


def guard_note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def guard_element(stand, task_id: str) -> str:
    """Полный id либо его префикс (длина — от зерна)."""
    if stand.rng.random() < 0.5:
        return task_id
    return task_id[:stand.rng.randint(8, len(task_id) - 1)]


def guard_field_errors(stand, field_value, *, task: str, version: int = 5) -> list[str]:
    field_line = "" if field_value is None else f"{FIELD}: {field_value}\n"
    path = stand.tdir / f"SPEC-{stand.rng.randrange(1 << 30)}.md"
    path.write_text(GUARD_SPEC_TEXT.format(task=task, version=version,
                                     field_line=field_line),
                    encoding="utf-8")
    return [e for e in guard.check(path) if FIELD in e]


def test_ac1_self_reference_names_field_and_element(guard_stand):
    """SPEC, чей `merge_after` называет id из поля `task:`, получает ошибку guard.

    Сценарий: id задачи свежий; `merge_after` несёт ровно его (версия
    схемы — любая из 1-5, от зерна: проверка формы действует для SPEC
    любой версии). Хотя бы одна строка ошибки называет и поле, и сам
    элемент.

    Ловит мутацию: сверка с полем `task:` пропущена (проверяются только
    формат и повторы) — guard молчит о самоссылке, ни одной строки с
    `merge_after` в выводе нет.
    """
    task_id = idgen.new_task_id()
    version = guard_stand.rng.randint(1, guard.SUPPORTED_SCHEMA_VERSION)

    errors = guard_field_errors(guard_stand, task_id, task=task_id, version=version)

    assert [e for e in errors if task_id in e], (
        guard_note(guard_stand, 
        f"нет ошибки, называющей {FIELD} и {task_id} (schema_version "
        f"{version}): {errors}"))


def test_ac1_repeated_element_is_a_repeat_error(guard_stand):
    """Повтор одного и того же элемента — ошибка guard о повторе.

    Сценарий: другой (чужой) id или его префикс стоит в `merge_after`
    дважды подряд через запятую; вторым входом — образец критерия
    `01M446X1, 01M446X1`. Строка ошибки называет поле, сам элемент и
    говорит о повторе.

    Ловит мутацию: элементы собираются во множество до проверки — повтор
    схлопывается молча, ошибки о нём нет.
    """
    task_id = idgen.new_task_id()
    cases = [guard_element(guard_stand, idgen.new_task_id()), "01M446X1"]
    for repeated in cases:
        errors = guard_field_errors(guard_stand, f"{repeated}, {repeated}", task=task_id)

        assert [e for e in errors if repeated in e and REPEAT_WORDS.search(e)], (
            guard_note(guard_stand, f"нет ошибки о повторе {repeated}: {errors}") + "; " + f"element={repeated!r}")


def test_ac1_element_not_in_task_id_format_is_a_form_error(guard_stand):
    """Элемент не в формате id задачи пульта — ошибка формы по полю.

    Сценарий: `merge_after: foo bar` (образец критерия) и тот же
    элемент рядом с корректным id в начале или в конце списка (от
    зерна). Каждый вход даёт хотя бы одну ошибку по полю.

    Ловит мутацию: проверка формата элемента снята (остаются только
    самоссылка и повтор) — `foo bar` проходит без ошибки.
    """
    task_id = idgen.new_task_id()
    valid = guard_element(guard_stand, idgen.new_task_id())
    mixed = (f"foo bar, {valid}" if guard_stand.rng.random() < 0.5
             else f"{valid}, foo bar")
    for value in ("foo bar", mixed):
        errors = guard_field_errors(guard_stand, value, task=task_id)

        assert errors, (
            guard_note(guard_stand, 
            f"{FIELD}: {value} прошёл guard без ошибки формы") + "; " + f"value={value!r}")


def test_ac1_valid_list_and_missing_field_pass(guard_stand):
    """Корректный список из двух разных id и SPEC без поля проходят без ошибок по полю.

    Сценарий: два свежих чужих id (каждый полностью или префиксом, от
    зерна) через запятую; отдельно — SPEC каждой версии 1-5 без поля
    `merge_after`. Ни одна строка ошибки guard не называет поле;
    `guard.SUPPORTED_SCHEMA_VERSION` остаётся 5.

    Ловит мутацию: поле объявлено обязательным (ошибка «нет
    merge_after» у SPEC без поля) либо разделитель «запятая с пробелом»
    не распознаётся и корректный список читается одним негодным
    элементом — тогда в выводе появляется строка с `merge_after`.
    """
    assert guard.SUPPORTED_SCHEMA_VERSION == 5
    task_id = idgen.new_task_id()
    first, second = idgen.new_task_id(), idgen.new_task_id()
    while second == first:
        second = idgen.new_task_id()
    value = f"{guard_element(guard_stand, first)}, {guard_element(guard_stand, second)}"
    if value.split(", ")[0] == value.split(", ")[1]:
        value = f"{first}, {second}"

    assert guard_field_errors(guard_stand, value, task=task_id) == [], (
        guard_note(guard_stand, f"корректный список {value!r}"))
    for version in range(1, guard.SUPPORTED_SCHEMA_VERSION + 1):
        assert guard_field_errors(guard_stand, None, task=task_id, version=version) == [], (
            guard_note(guard_stand, f"SPEC без поля, schema_version {version}") + "; " + f"schema_version={version!r}")


# --- PlanChannelSandbox, PlanChannelAppliesTest, PlanChannelRejectsTest (бывший test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py) ---

PLAN_SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
{field_line}---

# SPEC: фикстура канала PLAN

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

Фикстура.

## Не входит

Ничего.
"""
PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
{field_line}---

# PLAN: фикстура канала PLAN

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

{impact}
"""
JUSTIFIED = "- merge_after: порядок мержа меняется — {why}."
UNJUSTIFIED = "- Порядок мержа не меняется ({why})."

@pytest.fixture
def plan_stand(light_transition):
    """Стенд бывшего `PlanChannelSandbox`: тело его `setUp`."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.conn = store.db()
    light_transition.in_repo_handlers.append(plan_branch_not_behind)
    patcher = mock.patch.object(github_adapter, "ensure_draft_mr",
                                lambda conn, task_id, t: None)
    patcher.start()
    light_transition.addCleanup(patcher.stop)
    return light_transition


def plan_branch_not_behind(repo, *args):
    """Ответ точки расширения песочницы `in_repo_handlers`: ветка задачи
    не отстала от main (`rev-list --count` -> 0), подтяжки нет."""
    if args[:2] == ("rev-list", "--count"):
        return subprocess.CompletedProcess(list(args), 0, "0\n", "")
    return None


def plan_note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def plan_new_task(stand) -> str:
    _, task_id = capture_new_task_id(catalog.cmd_new,
                                     f"Зависимость {stand.rng.randrange(1 << 20)}")
    return task_id


def plan_unique_prefix(stand, task_id: str) -> str:
    others = [r["id"] for r in store.all_tasks(stand.conn) if r["id"] != task_id]
    shortest = next(n for n in range(1, len(task_id) + 1)
                    if not any(o.startswith(task_id[:n]) for o in others))
    return task_id[:stand.rng.randint(shortest, len(task_id))]


def plan_element(stand, task_id: str) -> str:
    return task_id if stand.rng.random() < 0.5 else plan_unique_prefix(stand, task_id)


def plan_field_line(stand, deps) -> str:
    if deps is None:
        return ""
    return f"merge_after: {', '.join(plan_element(stand, d) for d in deps)}\n"


def plan_write_doc(stand, task_id: str, name: str, text: str) -> None:
    tdir = config.TASKS / task_id
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / name).write_text(text, encoding="utf-8")


def plan_set_task_state(stand, task_id: str, state: str) -> None:
    stand.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    stand.conn.commit()


def plan_deps(stand, task_id: str) -> list[str]:
    return ids_of(store.get_task(stand.conn, task_id)["merge_after"])


def plan_state_of(stand, task_id: str) -> str:
    return store.get_task(stand.conn, task_id)["state"]


def plan_approve_spec(stand, task_id: str, deps, case: str = "") -> str:
    """`approve` гейта SPEC с `merge_after: deps` — штатная запись
    прежнего значения; предпосылка: значение записано."""
    plan_write_doc(stand, task_id, "SPEC.md", PLAN_SPEC_TEXT.format(
        task=task_id, field_line=plan_field_line(stand, deps)))
    plan_set_task_state(stand, task_id, "spec_gate")
    out = stand.capture(fsm.cmd_approve, task_id)
    assert plan_deps(stand, task_id) == list(deps or []), (
        plan_note(stand, 
        f"предпосылка: approve гейта SPEC {task_id} не записал "
        f"merge_after {deps}:\n{out}") + case)
    return out


def plan_advance_with_plan(stand, task_id: str, plan_field_line: str,
                      justified: bool) -> str:
    why = f"фикстура {stand.rng.randrange(1 << 20)}"
    impact = (JUSTIFIED if justified else UNJUSTIFIED).format(why=why)
    plan_write_doc(stand, task_id, "PLAN.md", PLAN_TEXT.format(
        task=task_id, field_line=plan_field_line, impact=impact))
    plan_set_task_state(stand, task_id, "in_dev")
    return stand.capture(fsm.cmd_advance, task_id)


def plan_last_step_id(stand, task_id: str) -> int:
    rows = store.task_steps(stand.conn, task_id)
    return rows[-1]["id"] if rows else 0


def plan_journal_since(stand, task_id: str, since: int) -> list[str]:
    return [f"{r['action']} | {r['detail'] or ''}"
            for r in store.task_steps(stand.conn, task_id) if r["id"] > since]


def plan_prepared_task(stand, case: str = "") -> tuple[str, list[str]]:
    """Задача в `in_dev` с прежним `merge_after` из одной-двух живых
    зависимостей, записанным гейтом SPEC."""
    task_id = plan_new_task(stand)
    old = [plan_new_task(stand) for _ in range(stand.rng.randint(1, 2))]
    plan_approve_spec(stand, task_id, old, case)
    return task_id, old


def plan_rejected_case(stand, case: str, task_id: str, old: list[str], label: str = ""):
    """(строка поля PLAN, обоснован ли PLAN, элемент для журнала или None)."""
    if case == "нет такой задачи":
        missing = idgen.new_task_id()
        return f"merge_after: {missing}\n", True, missing
    if case == "убитая":
        dead = plan_new_task(stand)
        plan_set_task_state(stand, dead, "killed")
        element = plan_element(stand, dead)
        return f"merge_after: {element}\n", True, element
    if case == "собственная":
        return f"merge_after: {task_id}\n", True, task_id
    if case == "цикл":
        other = plan_new_task(stand)
        plan_approve_spec(stand, other, [task_id], label)
        element = plan_element(stand, other)
        return f"merge_after: {element}\n", True, element
    fresh = plan_new_task(stand)
    return f"merge_after: {plan_element(stand, fresh)}\n", False, None


def test_ac9_justified_plan_value_replaces_db_value(plan_stand):
    """Обоснованный `merge_after` PLAN, отличный от БД, переписывает колонку полными id.

    Сценарий: прежнее значение — одна-две живые зависимости; PLAN несёт
    другой перечень (одна-две новые живые задачи, от зерна — с одной из
    прежних или без неё) префиксами или полными id, раздел «Влияние на
    систему» упоминает `merge_after`. После `advance` задача в
    `verifying`, колонка — новые полные id в порядке PLAN, одна запись
    журнала называет и все прежние, и все новые id.

    Ловит мутацию: значение PLAN, отличное от БД, не применяется
    (сравнение с прежним значением перевёрнуто) или запись журнала «было →
    стало» не называет новое значение — колонка расходится с полными id
    либо записи, называющей прежние и новые id, нет.
    """
    task_id, old = plan_prepared_task(plan_stand)
    new = [plan_new_task(plan_stand) for _ in range(plan_stand.rng.randint(1, 2))]
    if plan_stand.rng.random() < 0.5:
        new.append(plan_stand.rng.choice(old))
    plan_stand.rng.shuffle(new)
    since = plan_last_step_id(plan_stand, task_id)

    out = plan_advance_with_plan(plan_stand, task_id, plan_field_line(plan_stand, new), justified=True)

    entries = plan_journal_since(plan_stand, task_id, since)
    context = plan_note(plan_stand, f"было {old}, PLAN {new}\nжурнал: {entries}\n"
                        f"вывод advance:\n{out}")
    assert plan_state_of(plan_stand, task_id) == "verifying", context
    assert plan_deps(plan_stand, task_id) == new, context
    assert ([e for e in entries
         if all(i in e for i in old + new)]), (
        context)


def test_ac9_empty_plan_value_clears_dependencies(plan_stand):
    """Пустое `merge_after:` в обоснованном PLAN снимает все зависимости.

    Сценарий: прежнее значение — одна-две живые зависимости; PLAN несёт
    пустое поле `merge_after:`, раздел «Влияние на систему» упоминает
    `merge_after`. После `advance` задача в `verifying`, колонка пуста,
    одна запись журнала называет все прежние id.

    Ловит мутацию: пустое поле читается как «поля нет» — колонка
    сохраняет прежние зависимости.
    """
    task_id, old = plan_prepared_task(plan_stand)
    since = plan_last_step_id(plan_stand, task_id)

    out = plan_advance_with_plan(plan_stand, task_id, "merge_after:\n", justified=True)

    entries = plan_journal_since(plan_stand, task_id, since)
    context = plan_note(plan_stand, f"было {old}\nжурнал: {entries}\nвывод:\n{out}")
    assert plan_state_of(plan_stand, task_id) == "verifying", context
    assert plan_deps(plan_stand, task_id) == [], context
    assert [e for e in entries if all(i in e for i in old)], context


def test_ac9_plan_without_field_keeps_db_value(plan_stand):
    """PLAN без поля `merge_after` значение в БД не меняет.

    Сценарий: прежнее значение — одна-две живые зависимости; PLAN поля
    не несёт, раздел «Влияние на систему» от зерна упоминает
    `merge_after` или нет. После `advance` задача в `verifying`, колонка
    — прежний перечень.

    Ловит мутацию: отсутствие поля в PLAN снимает зависимости (колонка
    очищается) — колонка не равна прежнему перечню.
    """
    task_id, old = plan_prepared_task(plan_stand)

    out = plan_advance_with_plan(plan_stand, task_id, "",
                                 justified=plan_stand.rng.random() < 0.5)

    context = plan_note(plan_stand, f"было {old}\nвывод:\n{out}")
    assert plan_state_of(plan_stand, task_id) == "verifying", context
    assert plan_deps(plan_stand, task_id) == old, context


def test_ac10_rejected_plan_value_keeps_db_and_transition(plan_stand):
    """Негодный или необоснованный `merge_after` PLAN отклоняется, переход идёт дальше.

    Сценарий: для каждого варианта — своя задача с прежним значением из
    одной-двух живых зависимостей; PLAN несёт отличное от БД значение:
    несуществующий id, убитую задачу, id самой задачи, задачу, чья
    колонка уже ведёт в эту задачу (цикл), либо годную живую задачу без
    упоминания `merge_after` в «Влиянии на систему». После `advance`:
    задача в `verifying`, колонка — прежний перечень, в журнале есть
    запись об отклонении `merge_after` (для негодного элемента —
    называющая его).

    Ловит мутацию: отказ значения останавливает переход (задача
    остаётся в `in_dev`) либо проверка обоснования/элемента снята —
    колонка переписана негодным значением.
    """
    cases = ["нет такой задачи", "убитая", "собственная", "цикл",
             "без обоснования"]
    plan_stand.rng.shuffle(cases)
    for case in cases:
        task_id, old = plan_prepared_task(plan_stand, "; " + f"case={case!r}")
        field_line, justified, named = plan_rejected_case(plan_stand, case, task_id, old, "; " + f"case={case!r}")
        since = plan_last_step_id(plan_stand, task_id)

        out = plan_advance_with_plan(plan_stand, task_id, field_line, justified)

        entries = plan_journal_since(plan_stand, task_id, since)
        context = plan_note(plan_stand, f"{case}: было {old}, PLAN {field_line!r}\n"
                            f"журнал: {entries}\nвывод:\n{out}")
        assert plan_state_of(plan_stand, task_id) == "verifying", (
            context + "; " + f"case={case!r}")
        assert plan_deps(plan_stand, task_id) == old, context + "; " + f"case={case!r}"
        rejected = [e for e in entries
                    if "merge_after" in e and "отклон" in e.lower()]
        assert rejected, context + "; " + f"case={case!r}"
        if named is not None:
            assert [e for e in rejected if named in e], (
                context + "; " + f"case={case!r}")


# --- MergeAfterSpecGateSandbox, SpecGateMissingOrAmbiguousTest, SpecGateKilledForeignSelfTest, SpecGateCycleTest, SpecGateWritesColumnTest (бывший test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py) ---

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
SPEC_GATE_SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
{field_line}---

# SPEC: фикстура гейта зависимостей мержа

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.

## Не входит

Ничего.

## Материалы

Нет.
"""

@pytest.fixture
def spec_gate_stand(light_transition):
    """Стенд бывшего `MergeAfterSpecGateSandbox`: тело его `setUp`."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    path = light_transition.root / ZONES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# фикстура\n", encoding="utf-8")
    light_transition.conn = store.db()
    return light_transition


def spec_gate_note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def spec_gate_new_task(stand) -> str:
    _, task_id = capture_new_task_id(catalog.cmd_new,
                                     f"Зависимость {stand.rng.randrange(1 << 20)}")
    return task_id


def spec_gate_insert(stand, task_id: str, state: str,
           target: str = config.DEFAULT_TARGET) -> str:
    store.insert_task(stand.conn, task_id, f"Фикстура {task_id}", state,
                      f"task/{task_id.lower()}-fixture", target,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def spec_gate_all_ids(stand) -> list[str]:
    return [r["id"] for r in store.all_tasks(stand.conn)]


def spec_gate_unique_prefix(stand, task_id: str) -> str:
    """Префикс `task_id`, однозначный среди задач БД (длина — от зерна)."""
    others = [i for i in spec_gate_all_ids(stand) if i != task_id]
    shortest = next(n for n in range(1, len(task_id) + 1)
                    if not any(o.startswith(task_id[:n]) for o in others))
    return task_id[:stand.rng.randint(shortest, len(task_id))]


def spec_gate_element(stand, task_id: str) -> str:
    return task_id if stand.rng.random() < 0.5 else spec_gate_unique_prefix(stand, task_id)


def spec_gate_write_spec(stand, task_id: str, field_value) -> None:
    field_line = "" if field_value is None else f"merge_after: {field_value}\n"
    tdir = config.TASKS / task_id
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "SPEC.md").write_text(
        SPEC_GATE_SPEC_TEXT.format(task=task_id, zones=ZONES, field_line=field_line),
        encoding="utf-8")


def spec_gate_set_task_state(stand, task_id: str, state: str) -> None:
    stand.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    stand.conn.commit()


def spec_gate_approve_spec(stand, task_id: str, field_value) -> str:
    """SPEC с `merge_after: field_value` (None — без поля) и `approve`
    на `spec_gate`; вывод вместе с текстом отказа `SystemExit`."""
    spec_gate_write_spec(stand, task_id, field_value)
    spec_gate_set_task_state(stand, task_id, "spec_gate")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fsm.cmd_approve(task_id)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue()


def spec_gate_row(stand, task_id: str):
    return store.get_task(stand.conn, task_id)


def spec_gate_deps(stand, task_id: str) -> list[str]:
    return ids_of(spec_gate_row(stand, task_id)["merge_after"])


def spec_gate_last_step_id(stand, task_id: str) -> int:
    rows = store.task_steps(stand.conn, task_id)
    return rows[-1]["id"] if rows else 0


def spec_gate_journal_since(stand, task_id: str, since: int) -> list[str]:
    return [f"{r['action']} | {r['detail'] or ''}"
            for r in store.task_steps(stand.conn, task_id) if r["id"] > since]


def spec_gate_assert_refused(stand, task_id: str, field_value, named: str,
                   reason: re.Pattern) -> None:
    """`approve` с `merge_after: field_value` отказывает мягко: задача на
    `spec_gate`, колонка пуста, журнал называет `named` и причину."""
    since = spec_gate_last_step_id(stand, task_id)

    out = spec_gate_approve_spec(stand, task_id, field_value)

    entries = spec_gate_journal_since(stand, task_id, since)
    context = spec_gate_note(stand, f"merge_after: {field_value}\nжурнал: {entries}\n"
                        f"вывод approve:\n{out}")
    assert spec_gate_row(stand, task_id)["state"] == "spec_gate", context
    assert spec_gate_deps(stand, task_id) == [], context
    assert [e for e in entries if named in e and reason.search(e)], (
        spec_gate_note(stand, f"журнал не называет {named} и причину "
        f"/{reason.pattern}/: {context}"))


def test_ac2_missing_task_keeps_spec_gate_and_column_empty(spec_gate_stand):
    """Id отсутствующей задачи в `merge_after` — мягкий отказ approve с причиной «нет такой задачи».

    Сценарий: в `merge_after` — свежий id, которого нет в БД; от зерна
    рядом с ним (до или после) стоит годная существующая зависимость.
    Задача остаётся на `spec_gate`, колонка `merge_after` пуста (годный
    элемент тоже не записан), журнал задачи называет отсутствующий id и
    причину.

    Ловит мутацию: отсутствующий элемент молча отбрасывается и в
    колонку пишутся только найденные — задача уходит с гейта, колонка
    непуста, отказа в журнале нет.
    """
    task_id = spec_gate_stand.TASK
    missing = idgen.new_task_id()
    while missing in spec_gate_all_ids(spec_gate_stand):
        missing = idgen.new_task_id()
    items = [missing]
    if spec_gate_stand.rng.random() < 0.5:
        items.append(spec_gate_element(spec_gate_stand, spec_gate_new_task(spec_gate_stand)))
        spec_gate_stand.rng.shuffle(items)

    spec_gate_assert_refused(spec_gate_stand, task_id, ", ".join(items), missing,
                        re.compile(r"нет такой задачи", re.IGNORECASE))


def test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty(spec_gate_stand):
    """Префикс, подходящий к двум задачам, — мягкий отказ approve с причиной «неоднозначен».

    Сценарий: две задачи с id, отличающимися только хвостом, заведены
    прямой строкой БД; в `merge_after` — их общий префикс (длина — от
    зерна). Задача на `spec_gate`, колонка пуста, журнал называет
    префикс и неоднозначность.

    Ловит мутацию: префикс разрешается первым совпадением (`LIMIT 1`)
    вместо узла `store.resolve_task_id` — задача уходит с гейта с
    одной из двух задач в колонке.
    """
    base = idgen.new_task_id()
    length = spec_gate_stand.rng.randint(12, 20)
    prefix = base[:length]
    tails = spec_gate_stand.rng.sample(CROCKFORD, 2)
    for tail in tails:
        spec_gate_insert(spec_gate_stand, prefix + tail + base[length + 1:], "in_dev")

    spec_gate_assert_refused(spec_gate_stand, spec_gate_stand.TASK, prefix, prefix,
                        re.compile(r"неоднознач", re.IGNORECASE))


def test_ac3_killed_dependency_refused(spec_gate_stand):
    """Зависимость в состоянии `killed` — мягкий отказ approve.

    Сценарий: зависимость заведена прямой строкой БД в `killed`; в
    `merge_after` — её id или однозначный префикс. Задача на
    `spec_gate`, колонка пуста, журнал называет элемент и причину
    (убитая задача).

    Ловит мутацию: проверка состояния зависимости снята — убитая задача
    записывается в колонку, задача уходит с гейта.
    """
    dep = spec_gate_insert(spec_gate_stand, idgen.new_task_id(), "killed")
    element = spec_gate_element(spec_gate_stand, dep)

    spec_gate_assert_refused(spec_gate_stand, spec_gate_stand.TASK, element, element,
                        re.compile(r"killed|убит", re.IGNORECASE))


def test_ac3_dependency_of_other_target_refused(spec_gate_stand):
    """Зависимость другого target — мягкий отказ approve.

    Сценарий: зависимость заведена прямой строкой БД с target, отличным
    от target задачи (имя — от зерна), в живом состоянии. Задача на
    `spec_gate`, колонка пуста, журнал называет элемент и причину
    (другой target/проект).

    Ловит мутацию: сверка target снята — зависимость чужого проекта
    записывается в колонку, задача уходит с гейта.
    """
    other = f"proekt{spec_gate_stand.rng.randrange(1 << 20)}"
    dep = spec_gate_insert(spec_gate_stand, idgen.new_task_id(),
                      spec_gate_stand.rng.choice(["in_dev", "acceptance", "done"]),
                      target=other)
    element = spec_gate_element(spec_gate_stand, dep)

    spec_gate_assert_refused(spec_gate_stand, spec_gate_stand.TASK, element, element,
                        re.compile(r"target|проект", re.IGNORECASE))


def test_ac3_prefix_resolving_to_own_id_refused(spec_gate_stand):
    """Префикс, разрешающийся в id самой задачи, — мягкий отказ approve.

    Сценарий: в `merge_after` — однозначный префикс собственного id
    задачи (не полный id; длина — от зерна), в БД есть и другие
    задачи. Задача на `spec_gate`, колонка пуста, журнал называет
    префикс и причину (ссылка на саму себя).

    Ловит мутацию: самоссылка сверяется только по буквальному
    совпадению элемента с id задачи, до разрешения префикса, — префикс
    собственного id проходит и пишется в колонку.
    """
    spec_gate_new_task(spec_gate_stand)
    own = spec_gate_stand.TASK
    prefix = spec_gate_unique_prefix(spec_gate_stand, own)
    if prefix == own:
        prefix = own[:-1]
    assert store.resolve_task_id(spec_gate_stand.conn, prefix) == own, (
        spec_gate_note(spec_gate_stand, f"предпосылка: {prefix} однозначен"))

    spec_gate_assert_refused(spec_gate_stand, own, prefix, prefix,
                        re.compile(r"сам|собствен", re.IGNORECASE))


def test_ac4_cycle_through_existing_values_refused(spec_gate_stand):
    """`merge_after: B` у задачи A, когда цепочка БД от B уже ведёт в A, — отказ «цикл».

    Сценарий: длина цепочки — от зерна: либо у B в БД уже записано
    `merge_after = A`, либо B -> C и C -> A (третья задача). Значения
    цепочки записаны штатным `approve` гейта SPEC самих B и C. Затем
    `approve` A с `merge_after: B`: A на `spec_gate`, колонка A пуста,
    журнал A называет элемент B и причину «цикл».

    Ловит мутацию: проверка цикла снята — значение с циклом записывается
    в колонку, задача уходит с гейта.
    """
    a = spec_gate_stand.TASK
    chain = [spec_gate_new_task(spec_gate_stand) for _ in range(spec_gate_stand.rng.randint(1, 2))]
    # Последний в цепочке ссылается на A, каждый предыдущий — на
    # следующего; утверждаются с конца, чтобы каждый шаг был годен.
    targets = chain[1:] + [a]
    for task_id, dep in reversed(list(zip(chain, targets))):
        out = spec_gate_approve_spec(spec_gate_stand, task_id, spec_gate_element(spec_gate_stand, dep))
        assert spec_gate_deps(spec_gate_stand, task_id) == [dep], (
            spec_gate_note(spec_gate_stand, 
            f"предпосылка: approve {task_id} с merge_after {dep} не "
            f"записал колонку:\n{out}"))
    b_element = spec_gate_element(spec_gate_stand, chain[0])

    spec_gate_assert_refused(spec_gate_stand, a, b_element, b_element,
                        re.compile(r"цикл", re.IGNORECASE))


def test_ac5_prefixes_written_as_full_ids_in_spec_order(spec_gate_stand):
    """Годный `merge_after` префиксами — approve проходит и пишет полные id в порядке SPEC.

    Сценарий: от одной до трёх живых зависимостей (`new`), в
    `merge_after` каждая — однозначным префиксом или полным id, порядок
    перемешан от зерна. После `approve` задача ушла со `spec_gate`,
    колонка `merge_after` — полные id ровно в порядке SPEC, колонка
    `zones` записана тем же approve.

    Ловит мутацию: `approve` гейта SPEC не пишет проверенное значение в
    колонку — перечень колонки пуст вместо полных id в порядке SPEC.
    """
    deps = [spec_gate_new_task(spec_gate_stand) for _ in range(spec_gate_stand.rng.randint(1, 3))]
    spec_gate_stand.rng.shuffle(deps)
    value = ", ".join(spec_gate_element(spec_gate_stand, d) for d in deps)

    out = spec_gate_approve_spec(spec_gate_stand, spec_gate_stand.TASK, value)

    context = spec_gate_note(spec_gate_stand, f"merge_after: {value}\nвывод approve:\n{out}")
    row = spec_gate_row(spec_gate_stand, spec_gate_stand.TASK)
    assert row["state"] != "spec_gate", context
    assert ids_of(row["merge_after"]) == deps, context
    assert row["zones"] == ZONES, context


def test_ac5_spec_without_field_leaves_column_empty(spec_gate_stand):
    """SPEC без `merge_after` — колонка пуста, переход идёт как раньше.

    Сценарий: в БД есть другие задачи (от зерна — одна или две), SPEC
    задачи поля не несёт. `approve` уводит задачу со `spec_gate`,
    колонка `merge_after` пуста, `zones` записана.

    Ловит мутацию: отсутствие поля читается как ошибка проверки (approve
    отказывает) либо в колонку попадает мусор (например, строка
    «None»).
    """
    for _ in range(spec_gate_stand.rng.randint(1, 2)):
        spec_gate_new_task(spec_gate_stand)

    out = spec_gate_approve_spec(spec_gate_stand, spec_gate_stand.TASK, None)

    context = spec_gate_note(spec_gate_stand, f"вывод approve:\n{out}")
    row = spec_gate_row(spec_gate_stand, spec_gate_stand.TASK)
    assert row["state"] != "spec_gate", context
    assert ids_of(row["merge_after"]) == [], context
    assert row["zones"] == ZONES, context


# --- DependencyOutputSandbox, StatusSuffixTest, ShowDependenciesTest (бывший test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py) ---

STATUS_SHOW_SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/catalog.py
budget_usd: 30
{field_line}---

# SPEC: фикстура вывода зависимостей

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.

## Не входит

Ничего.
"""
WAIT_PREFIX = "[ждёт мержа:"
SHOW_PREFIX = "зависимости мержа:"
STATUS_SHOW_UNFINISHED_STATES = ("spec_gate", "tests_writing", "in_dev", "verifying",
                     "review", "acceptance", "merge_gate", "escalated")
WAITING_STATES = ("acceptance", "merge_gate")
OTHER_STATES = ("spec_writing", "tests_writing", "in_dev", "verifying",
                "review", "escalated")

@pytest.fixture
def status_show_stand(light_transition):
    """Стенд бывшего `DependencyOutputSandbox`: тело его `setUp`."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    path = light_transition.root / "orchestrator" / "catalog.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# фикстура\n", encoding="utf-8")
    light_transition.conn = store.db()
    return light_transition


def status_show_note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def status_show_new_task(stand) -> str:
    _, task_id = capture_new_task_id(catalog.cmd_new,
                                     f"Задача {stand.rng.randrange(1 << 20)}")
    return task_id


def status_show_set_state(stand, task_id: str, state: str) -> None:
    stand.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    stand.conn.commit()


def status_show_element(stand, task_id: str) -> str:
    others = [r["id"] for r in store.all_tasks(stand.conn) if r["id"] != task_id]
    shortest = next(n for n in range(1, len(task_id) + 1)
                    if not any(o.startswith(task_id[:n]) for o in others))
    return task_id[:stand.rng.randint(shortest, len(task_id))]


def status_show_with_dependencies(stand, task_id: str, deps) -> None:
    """`approve` гейта SPEC с `merge_after: deps` (`None` — без поля)."""
    field_line = ("" if deps is None else
                  f"merge_after: {', '.join(status_show_element(stand, d) for d in deps)}\n")
    tdir = config.TASKS / task_id
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "SPEC.md").write_text(
        STATUS_SHOW_SPEC_TEXT.format(task=task_id, field_line=field_line), encoding="utf-8")
    status_show_set_state(stand, task_id, "spec_gate")
    out = stand.capture(fsm.cmd_approve, task_id)
    assert store.get_task(stand.conn, task_id)["state"] != "spec_gate", (
        status_show_note(stand, f"предпосылка:\n{out}"))
    if deps is None:
        return
    assert ids_of(store.get_task(stand.conn, task_id)["merge_after"]) == deps, (
        status_show_note(stand, 
        f"предпосылка: approve гейта SPEC не записал "
        f"merge_after {deps}:\n{out}"))


def status_show_status_line(stand, task_id: str) -> str:
    out = stand.capture(catalog.cmd_status)
    lines = [line for line in out.splitlines() if line.startswith(task_id)]
    assert len(lines) == 1, status_show_note(stand, f"строка {task_id} в status:\n{out}")
    return lines[0]


def status_show_wait_suffix(stand, line: str) -> str | None:
    start = line.find(WAIT_PREFIX)
    if start < 0:
        return None
    end = line.find("]", start)
    return line[start:] if end < 0 else line[start:end + 1]


def status_show_dependency_scenario(stand) -> tuple[str, dict, list[str]]:
    """Задача с одной-тремя зависимостями: {незавершённая: состояние}
    (хотя бы одна) и перечень завершённых (`done`)."""
    task_id = stand.TASK
    unfinished = {status_show_new_task(stand): stand.rng.choice(STATUS_SHOW_UNFINISHED_STATES)
                  for _ in range(stand.rng.randint(1, 2))}
    done = [status_show_new_task(stand) for _ in range(stand.rng.randint(0, 1))]
    deps = list(unfinished) + done
    stand.rng.shuffle(deps)
    status_show_with_dependencies(stand, task_id, deps)
    for dep, state in unfinished.items():
        status_show_set_state(stand, dep, state)
    for dep in done:
        status_show_set_state(stand, dep, "done")
    return task_id, unfinished, done


def test_ac13_status_suffix_lists_unfinished_and_disappears_after_done(status_show_stand):
    """Задача в `acceptance`/`merge_gate` с незавершёнными зависимостями несёт добавку `[ждёт мержа: …]`.

    Сценарий: одна-две незавершённые зависимости (состояния от зерна) и
    от нуля до одной в `done`; задача в `acceptance` или `merge_gate`.
    Строка задачи в `status` заканчивается добавкой, в которой каждая
    незавершённая названа как `<id> (<состояние>)`, а завершённой нет.
    Затем все зависимости переводятся в `done` правкой БД — следующий
    `status` печатает строку без добавки.

    Ловит мутацию: состояния зависимостей кэшируются (не читаются из БД
    на каждый вызов) либо добавка включает и завершённые зависимости —
    после перевода в `done` добавка остаётся.
    """
    task_id, unfinished, done = status_show_dependency_scenario(status_show_stand)
    status_show_set_state(status_show_stand, task_id, status_show_stand.rng.choice(WAITING_STATES))

    line = status_show_status_line(status_show_stand, task_id)

    suffix = status_show_wait_suffix(status_show_stand, line)
    assert suffix is not None, status_show_note(status_show_stand, f"нет добавки: {line}")
    assert line.rstrip().endswith(suffix), (
        status_show_note(status_show_stand, 
        f"добавка не в конце строки: {line}"))
    for dep, state in unfinished.items():
        assert f"{dep} ({state})" in suffix, status_show_note(status_show_stand, line)
    for dep in done:
        assert dep not in suffix, status_show_note(status_show_stand, line)

    for dep in unfinished:
        status_show_set_state(status_show_stand, dep, "done")
    line = status_show_status_line(status_show_stand, task_id)

    assert status_show_wait_suffix(status_show_stand, line) is None, (
        status_show_note(status_show_stand, 
        f"добавка осталась после перевода зависимостей в done: {line}"))


def test_ac13_no_suffix_in_other_state(status_show_stand):
    """Задача вне `acceptance`/`merge_gate` добавки не несёт даже с незавершёнными зависимостями.

    Сценарий: одна-две незавершённые зависимости; задача в одном из
    прочих рабочих состояний (от зерна, например `in_dev`). Строка
    задачи в `status` без `[ждёт мержа:`.

    Ловит мутацию: фильтр состояния задачи снят — добавка печатается в
    любом состоянии.
    """
    task_id, _, _ = status_show_dependency_scenario(status_show_stand)
    status_show_set_state(status_show_stand, task_id, status_show_stand.rng.choice(OTHER_STATES))

    line = status_show_status_line(status_show_stand, task_id)

    assert status_show_wait_suffix(status_show_stand, line) is None, status_show_note(status_show_stand, line)


def test_ac13_no_suffix_without_field_or_all_done(status_show_stand):
    """Без поля `merge_after` и со всеми зависимостями в `done` добавки нет.

    Сценарий: задача в `acceptance`/`merge_gate` (от зерна) — от зерна
    либо SPEC без поля (в БД при этом есть незавершённые посторонние
    задачи), либо одна-две зависимости, все в `done`. Строка задачи в
    `status` без `[ждёт мержа:`.

    Ловит мутацию: условие «есть зависимости не в done» снято — добавка
    печатается и с пустым перечнем незавершённых.
    """
    task_id = status_show_stand.TASK
    if status_show_stand.rng.random() < 0.5:
        for _ in range(status_show_stand.rng.randint(1, 2)):
            status_show_set_state(status_show_stand, status_show_new_task(status_show_stand), status_show_stand.rng.choice(STATUS_SHOW_UNFINISHED_STATES))
        status_show_with_dependencies(status_show_stand, task_id, None)
    else:
        deps = [status_show_new_task(status_show_stand) for _ in range(status_show_stand.rng.randint(1, 2))]
        status_show_with_dependencies(status_show_stand, task_id, deps)
        for dep in deps:
            status_show_set_state(status_show_stand, dep, "done")
    status_show_set_state(status_show_stand, task_id, status_show_stand.rng.choice(WAITING_STATES))

    line = status_show_status_line(status_show_stand, task_id)

    assert status_show_wait_suffix(status_show_stand, line) is None, status_show_note(status_show_stand, line)


def test_ac14_show_lists_all_dependencies_with_states(status_show_stand):
    """`show` задачи с непустым `merge_after` печатает строку со всеми зависимостями и их состояниями.

    Сценарий: незавершённые и завершённые (`done`) зависимости, задача в
    любом состоянии (от зерна). Вывод `show` несёт строку
    `зависимости мержа:`, в которой каждая зависимость названа как
    `<id> (<состояние>)`, включая `done`.

    Ловит мутацию: `show` переиспользует фильтр добавки `status` —
    зависимости в `done` в строке нет.
    """
    task_id, unfinished, done = status_show_dependency_scenario(status_show_stand)
    if not done:
        extra = status_show_new_task(status_show_stand)
        status_show_with_dependencies(status_show_stand, task_id, list(unfinished) + [extra])
        status_show_set_state(status_show_stand, extra, "done")
        done = [extra]
    status_show_set_state(status_show_stand, task_id, status_show_stand.rng.choice(WAITING_STATES + OTHER_STATES))

    out = status_show_stand.capture(catalog.cmd_show, task_id)

    lines = [line for line in out.splitlines() if SHOW_PREFIX in line]
    assert len(lines) == 1, status_show_note(status_show_stand, out)
    for dep, state in list(unfinished.items()) + [(d, "done") for d in done]:
        assert f"{dep} ({state})" in lines[0], status_show_note(status_show_stand, out)


def test_ac14_show_without_dependencies_has_no_line(status_show_stand):
    """У задачи без зависимостей строки `зависимости мержа:` в `show` нет.

    Сценарий: SPEC без поля; в БД есть посторонние задачи; задача в
    любом состоянии (от зерна). В выводе `show` строки нет.

    Ловит мутацию: строка печатается безусловно (с пустым перечнем
    или «—»).
    """
    for _ in range(status_show_stand.rng.randint(1, 2)):
        status_show_new_task(status_show_stand)
    status_show_with_dependencies(status_show_stand, status_show_stand.TASK, None)
    status_show_set_state(status_show_stand, status_show_stand.TASK, status_show_stand.rng.choice(WAITING_STATES + OTHER_STATES))

    out = status_show_stand.capture(catalog.cmd_show, status_show_stand.TASK)

    assert SHOW_PREFIX not in out.lower(), status_show_note(status_show_stand, out)


# --- DeclaredMergeAfterSandbox, NewDeclaresTest, NewRefusesTest, DeclaredStatusShowTest (бывший test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py) ---

DECLARED_ACTION = "merge_after заявлен Оператором"
NOT_CREATED = "задача не заведена"
SUFFIX_PREFIX = "[мерж после:"
SHOW_MARK = "зависимости мержа"
GIT_WRITES = ("commit-tree", "update-ref")
NEW_DECLARES_UNFINISHED_STATES = ("spec_writing", "spec_gate", "tests_writing", "in_dev",
                     "verifying", "review", "acceptance", "merge_gate",
                     "escalated")
BAD_ELEMENTS = ("мержа «CI до ревью»", "части 1", "мержа соседней задачи",
                "волны 2")

@pytest.fixture
def new_declares_stand(light_transition):
    """Стенд бывшего `DeclaredMergeAfterSandbox`: тело его `setUp`."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    for rel in (ZONES, "orchestrator/fsm.py"):
        path = light_transition.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# фикстура\n", encoding="utf-8")
    light_transition.conn = store.db()
    light_transition.ensure_calls: list = []

    def ensure(task_id, branch):
        light_transition.ensure_calls.append((task_id, branch))
        return light_transition.wt_path, None

    patcher = mock.patch.object(workspace, "ensure", ensure)
    patcher.start()
    light_transition.addCleanup(patcher.stop)
    return light_transition


def new_declares_note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def new_declares_live_task(stand) -> str:
    _, task_id = capture_new_task_id(
        catalog.cmd_new, f"Зависимость {stand.rng.randrange(1 << 20)}")
    return task_id


def new_declares_insert(stand, task_id: str, state: str,
           target: str = config.DEFAULT_TARGET) -> str:
    store.insert_task(stand.conn, task_id, f"Фикстура {task_id}", state,
                      f"task/{task_id.lower()}-fixture", target,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def new_declares_all_ids(stand) -> list[str]:
    return [r["id"] for r in store.all_tasks(stand.conn)]


def new_declares_unique_prefix(stand, task_id: str) -> str:
    """Префикс `task_id`, однозначный среди задач БД (длина — от зерна)."""
    others = [i for i in new_declares_all_ids(stand) if i != task_id]
    shortest = next(n for n in range(1, len(task_id) + 1)
                    if not any(o.startswith(task_id[:n]) for o in others))
    return task_id[:stand.rng.randint(shortest, len(task_id))]


def new_declares_element(stand, task_id: str) -> str:
    return task_id if stand.rng.random() < 0.5 else new_declares_unique_prefix(stand, task_id)


def new_declares_missing_id(stand) -> str:
    missing = idgen.new_task_id()
    while missing in new_declares_all_ids(stand):
        missing = idgen.new_task_id()
    return missing


def new_declares_tz(stand, *order_lines: str, requirement: str = "Фикстура.") -> str:
    """Текст ТЗ: строки `order_lines` — перед «Зоны:» либо после неё (от
    зерна), каждая отдельным абзацем."""
    head = (f"Источник: фикстура {stand.seed}.\n\nТребуется:\n"
            f"1. {requirement}\n\n")
    zones = f"Зоны: {ZONES}.\n\n"
    order = "".join(f"{line}\n\n" for line in order_lines)
    body = (head + order + zones if stand.rng.random() < 0.5
            else head + zones + order)
    return body + "Не входит: прочее.\n"


def new_declares_run_new(stand, tz_text: str) -> tuple[str, str | None]:
    """(вывод вместе с текстом отказа, id заведённой задачи либо `None` —
    `new` завершилась ненулевым `SystemExit`)."""
    path = stand.root / f"tz-{stand.rng.randrange(1 << 30)}.md"
    path.write_text(tz_text, encoding="utf-8")
    buf = io.StringIO()
    task_id = None
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            task_id = catalog.cmd_new(
                f"Задача {stand.rng.randrange(1 << 20)}", str(path))
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
                task_id = None
    return buf.getvalue(), task_id


def new_declares_deps(stand, task_id: str) -> list[str]:
    return ids_of(store.get_task(stand.conn, task_id)["merge_after"])


def new_declares_journal(stand, task_id: str) -> list[str]:
    return [f"{r['action']} | {r['detail'] or ''}"
            for r in store.task_steps(stand.conn, task_id)]


def new_declares_declared(stand, tz_text: str, case: str = "") -> str:
    """`new` с `tz_text` заводит задачу; её id."""
    out, task_id = new_declares_run_new(stand, tz_text)
    assert task_id is not None, (
        new_declares_note(stand, 
        f"new отказала:\n{out}\nТЗ:\n{tz_text}") + case)
    return task_id


def new_declares_assert_refused_without_traces(stand, tz_text: str,
                                  named: list[str], case: str = "") -> str:
    """`new` с `tz_text` отказывает: вывод называет каждую строку
    `named` и «задача не заведена»; новой строки задачи в БД нет, ссылка
    документов не писалась, ветка и рабочая копия не заводились."""
    rows_before = set(new_declares_all_ids(stand))
    git_before = len(stand.git_spy.calls)
    ensure_before = len(stand.ensure_calls)

    out, task_id = new_declares_run_new(stand, tz_text)

    context = new_declares_note(stand, f"ТЗ:\n{tz_text}\nвывод new:\n{out}")
    assert task_id is None, context + case
    assert NOT_CREATED in out, context + case
    for text in named:
        assert text in out, context + case
    assert set(new_declares_all_ids(stand)) == rows_before, context + case
    git_writes = [c for c in stand.git_spy.calls[git_before:]
                  if any(w in map(str, c) for w in GIT_WRITES)]
    assert git_writes == [], context + case
    assert stand.ensure_calls[ensure_before:] == [], context + case
    return out


def new_declares_set_state(stand, task_id: str, state: str) -> None:
    stand.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    stand.conn.commit()


def new_declares_status_line(stand, task_id: str) -> str:
    out = stand.capture(catalog.cmd_status)
    lines = [line for line in out.splitlines() if line.startswith(task_id)]
    assert len(lines) == 1, new_declares_note(stand, f"строка {task_id} в status:\n{out}")
    return lines[0]


def new_declares_suffix(stand, line: str, prefix: str) -> str | None:
    start = line.find(prefix)
    if start < 0:
        return None
    end = line.find("]", start)
    return line[start:] if end < 0 else line[start:end + 1]


def test_ac1_order_line_declares_full_ids_in_line_order(new_declares_stand):
    """Строка «Порядок: после <e1>, …» — `new` пишет в колонку полные id в порядке строки и журнал.

    Сценарий: дважды — одна живая зависимость и две-три (от зерна);
    элементы — полные id или однозначные префиксы, порядок перемешан.
    `new --tz` заводит задачу; колонка `merge_after` — полные id ровно в
    порядке строки; в журнале задачи есть запись «merge_after заявлен
    Оператором», называющая каждый полный id.

    Ловит мутацию: заявленное значение не пишется в колонку либо порядок
    id обращён — перечень колонки расходится с ожидаемым; либо запись
    журнала не делается — записи с действием нет.
    """
    for count in (1, new_declares_stand.rng.randint(2, 3)):
        deps = [new_declares_live_task(new_declares_stand) for _ in range(count)]
        new_declares_stand.rng.shuffle(deps)
        line = f"Порядок: после {', '.join(new_declares_element(new_declares_stand, d) for d in deps)}"

        task_id = new_declares_declared(new_declares_stand, new_declares_tz(new_declares_stand, line), "; " + f"count={count!r}")

        entries = new_declares_journal(new_declares_stand, task_id)
        context = new_declares_note(new_declares_stand, f"строка: {line}\nжурнал: {entries}")
        assert new_declares_deps(new_declares_stand, task_id) == deps, (
            context + "; " + f"count={count!r}")
        assert ([e for e in entries if DECLARED_ACTION in e
             and all(d in e for d in deps)]), (
            new_declares_note(new_declares_stand, f"нет записи «{DECLARED_ACTION}» с {deps}: {context}") + "; " + f"count={count!r}")


def test_ac2_list_ends_at_parenthesis_or_dot(new_declares_stand):
    """Перечень кончается на «(» или «.»; текст после и следующая строка в него не входят.

    Сценарий: две живые зависимости в строке; за ними от зерна либо
    пояснение в скобках с точкой, либо точка без скобок и продолжение
    фразы. И пояснение, и следующая строка ТЗ называют ещё одну живую
    задачу — она не заявлена. Колонка — ровно две зависимости строки.

    Ловит мутацию: перечень берётся до конца строки (ни скобка, ни точка
    не режут хвост) — `new` отказывает элементом «(пояснение …».
    """
    deps = [new_declares_live_task(new_declares_stand) for _ in range(2)]
    other = new_declares_live_task(new_declares_stand)
    listed = ", ".join(new_declares_element(new_declares_stand, d) for d in deps)
    if new_declares_stand.rng.random() < 0.5:
        line = (f"Порядок: после {listed} (зона {ZONES}, рядом {other}, "
                f"ждать его).\nпродолжение: {other}, затем прочее")
    else:
        line = (f"Порядок: после {listed}. Потом {other}, если успеем\n"
                f"{other}, ещё строка")

    task_id = new_declares_declared(new_declares_stand, new_declares_tz(new_declares_stand, line))

    assert new_declares_deps(new_declares_stand, task_id) == deps, new_declares_note(new_declares_stand, f"строка:\n{line}")


def test_ac3_order_line_without_after_declares_nothing(new_declares_stand):
    """«Порядок: без зависимостей», «Порядок: первая, без зависимостей» и ТЗ без строки — без зависимостей.

    Сценарий: три варианта ТЗ; в каждом пункт «Требуется» упоминает
    «после <id живой задачи>» обычным текстом. Задача заводится,
    колонка `merge_after` пуста, записи «merge_after заявлен
    Оператором» в журнале нет.

    Ловит мутацию: хвост «Порядок:» разбирается перечнем и без слова
    «после» (отказ «без зависимостей» не id) либо «после <id>» ищется
    по всему ТЗ, а не в строке с меткой с первой позиции — колонка
    непуста.
    """
    live = new_declares_live_task(new_declares_stand)
    variants = [("Порядок: без зависимостей",),
                ("Порядок: первая, без зависимостей",), ()]
    new_declares_stand.rng.shuffle(variants)
    for lines in variants:
        tz_text = new_declares_tz(new_declares_stand, *lines, requirement=f"Сделать после {live}.")

        task_id = new_declares_declared(new_declares_stand, tz_text, "; " + f"lines={lines!r}")

        entries = new_declares_journal(new_declares_stand, task_id)
        context = new_declares_note(new_declares_stand, f"ТЗ:\n{tz_text}\nжурнал: {entries}")
        assert new_declares_deps(new_declares_stand, task_id) == [], (
            context + "; " + f"lines={lines!r}")
        assert not [e for e in entries if DECLARED_ACTION in e], (
            context + "; " + f"lines={lines!r}")


def test_ac4_unparsed_element_refused_without_traces(new_declares_stand):
    """Элемент хвоста, не являющийся id по форме, — отказ `new` с его названием и без следов.

    Сценарий: хвост строки — неразобранный элемент (от зерна, например
    «мержа «CI до ревью»»), от зерна рядом с годной живой
    зависимостью. Вывод `new` называет элемент и «задача не заведена»;
    строки задачи в БД нет, ссылка документов не писалась, ветка не
    заводилась.

    Ловит мутацию: негодный элемент молча отбрасывается и задача
    заводится с остальными (или без зависимостей) либо проверка стоит
    после заведения строки — в БД появляется задача.
    """
    bad = new_declares_stand.rng.choice(BAD_ELEMENTS)
    items = [bad]
    if new_declares_stand.rng.random() < 0.5:
        items.append(new_declares_element(new_declares_stand, new_declares_live_task(new_declares_stand)))
        new_declares_stand.rng.shuffle(items)

    new_declares_assert_refused_without_traces(new_declares_stand, 
        new_declares_tz(new_declares_stand, f"Порядок: после {', '.join(items)}"), [bad])


def test_ac5_repeated_order_line_refused_without_traces(new_declares_stand):
    """Две строки «Порядок: после …» в одном ТЗ — отказ `new` с причиной повтора.

    Сценарий: обе строки годны (по живой зависимости, от зерна — одной и
    той же или разным). `new` отказывает, вывод называет повтор строки
    и «задача не заведена»; следов в БД и git нет.

    Ловит мутацию: повтор строки не сверяется и берётся первая либо
    последняя строка — задача заводится.
    """
    first = new_declares_live_task(new_declares_stand)
    second = first if new_declares_stand.rng.random() < 0.5 else new_declares_live_task(new_declares_stand)
    tz_text = new_declares_tz(new_declares_stand, f"Порядок: после {new_declares_element(new_declares_stand, first)}",
                      f"Порядок: после {new_declares_element(new_declares_stand, second)}")

    out = new_declares_assert_refused_without_traces(new_declares_stand, tz_text, [])

    assert re.search(re.compile(r"повтор", re.IGNORECASE), out), new_declares_note(new_declares_stand, out)


def test_ac6_invalid_dependency_refused_without_traces(new_declares_stand):
    """Несуществующий, неоднозначный, убитый, чужого target или повторённый элемент — отказ `new`.

    Сценарий: для каждого варианта (порядок — от зерна) строка
    «Порядок: после …» несёт негодный элемент. Вывод `new` называет
    элемент, причину и «задача не заведена»; новой строки задачи в БД
    нет, ссылка документов не писалась, ветка не заводилась.

    Ловит мутацию: строка разбирается только по форме, без
    `merge_after.check` по БД (задача заводится), либо target заводимой
    задачи берётся из несуществующей строки БД/не сверяется — чужой
    target проходит, либо проверка стоит после заведения строки.
    """
    cases = ["нет такой задачи", "неоднозначный префикс", "убитая",
             "чужой target", "повтор"]
    new_declares_stand.rng.shuffle(cases)
    for case in cases:
        if case == "нет такой задачи":
            element = new_declares_missing_id(new_declares_stand)
            items, reason = [element], r"нет такой задачи"
        elif case == "неоднозначный префикс":
            base = idgen.new_task_id()
            element = base[:new_declares_stand.rng.randint(12, 20)]
            for tail in new_declares_stand.rng.sample(CROCKFORD, 2):
                new_declares_insert(new_declares_stand, element + tail
                            + base[len(element) + 1:], "in_dev")
            items, reason = [element], r"неоднознач"
        elif case == "убитая":
            dep = new_declares_insert(new_declares_stand, idgen.new_task_id(), "killed")
            element = new_declares_element(new_declares_stand, dep)
            items, reason = [element], r"killed|убит"
        elif case == "чужой target":
            dep = new_declares_insert(new_declares_stand, idgen.new_task_id(),
                              new_declares_stand.rng.choice(["in_dev", "done"]),
                              target=f"proekt{new_declares_stand.rng.randrange(1 << 20)}")
            element = new_declares_element(new_declares_stand, dep)
            items, reason = [element], r"target|проект"
        else:
            dep = new_declares_live_task(new_declares_stand)
            element = new_declares_unique_prefix(new_declares_stand, dep)
            items, reason = [dep, element], r"повтор"
            new_declares_stand.rng.shuffle(items)

        out = new_declares_assert_refused_without_traces(new_declares_stand, 
            new_declares_tz(new_declares_stand, f"Порядок: после {', '.join(items)}"), [element], "; " + f"case={case!r}")

        assert re.search(re.compile(reason, re.IGNORECASE), out), (
            new_declares_note(new_declares_stand, out) + "; " + f"case={case!r}")


def test_ac7_path_refusal_and_order_refusal_printed_together(new_declares_stand):
    """ТЗ с путём вне зон и негодной строкой «Порядок: после …» — обе причины одним вызовом `new`.

    Сценарий: пункт «Требуется» называет существующий путь вне «Зоны:»;
    строка «Порядок: после …» несёт (от зерна) элемент не в форме id
    либо id несуществующей задачи. Вывод одного вызова `new` называет
    и путь с подсказкой сверки путей, и негодный элемент; задача не
    заведена.

    Ловит мутацию: отказ сверки путей выходит раньше разбора строки
    «Порядок:» (или наоборот) — Оператор видит одну причину из двух.
    """
    element = (new_declares_stand.rng.choice(BAD_ELEMENTS) if new_declares_stand.rng.random() < 0.5
               else new_declares_missing_id(new_declares_stand))
    tz_text = new_declares_tz(new_declares_stand, f"Порядок: после {element}",
                      requirement="Починить orchestrator/fsm.py.")

    new_declares_assert_refused_without_traces(new_declares_stand, 
        tz_text, ["orchestrator/fsm.py", guard.UNCLASSIFIED_PATH_HINT,
                  element])


def test_ac8_status_and_show_carry_declared_dependencies(new_declares_stand):
    """Сразу после `new` `status` в `spec_writing`/`spec_gate` несёт «[мерж после: …]», `show` — строку зависимостей.

    Сценарий: одна-две заявленные зависимости в незавершённых
    состояниях (от зерна). `show` сразу после `new` печатает строку
    зависимостей мержа с каждым id. `status` в `spec_writing` и затем в
    `spec_gate` печатает в строке задачи добавку `[мерж после: …]`, где
    каждая зависимость названа как `<id> (<состояние>)`, и не печатает
    `[ждёт мержа:`. После перевода всех зависимостей в `done` добавки
    нет.

    Ловит мутацию: добавка печатается только в `acceptance`/`merge_gate`
    (нет в ранних состояниях) либо вместо неё расширено
    `[ждёт мержа:`; либо состояние зависимости кэшируется и не читается
    из БД на каждый вызов — добавка остаётся после `done`.
    """
    deps = {new_declares_live_task(new_declares_stand): new_declares_stand.rng.choice(NEW_DECLARES_UNFINISHED_STATES)
            for _ in range(new_declares_stand.rng.randint(1, 2))}
    for dep, state in deps.items():
        new_declares_set_state(new_declares_stand, dep, state)
    line = f"Порядок: после {', '.join(new_declares_element(new_declares_stand, d) for d in deps)}"
    task_id = new_declares_declared(new_declares_stand, new_declares_tz(new_declares_stand, line))

    out = new_declares_stand.capture(catalog.cmd_show, task_id)
    shown = [s for s in out.splitlines() if SHOW_MARK in s.lower()]
    assert shown and all(d in shown[0] for d in deps), (
        new_declares_note(new_declares_stand, f"show:\n{out}"))

    for task_state in ("spec_writing", "spec_gate"):
        new_declares_set_state(new_declares_stand, task_id, task_state)
        row = new_declares_status_line(new_declares_stand, task_id)
        suffix = new_declares_suffix(new_declares_stand, row, SUFFIX_PREFIX)
        context = new_declares_note(new_declares_stand, f"{task_state}: {row}")
        assert suffix is not None, context
        for dep, state in deps.items():
            assert f"{dep} ({state})" in suffix, context
        assert new_declares_suffix(new_declares_stand, row, WAIT_PREFIX) is None, context

    for dep in deps:
        new_declares_set_state(new_declares_stand, dep, "done")
    row = new_declares_status_line(new_declares_stand, task_id)

    assert new_declares_suffix(new_declares_stand, row, SUFFIX_PREFIX) is None, (
        new_declares_note(new_declares_stand, 
        f"добавка осталась после перевода зависимостей в done: {row}"))
