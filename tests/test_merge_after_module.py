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
"""
import contextlib
import io
import os
import random
import sqlite3
from unittest import mock

import pytest

from orchestrator import (answer, catalog, config, fsm, idgen, merge_after,
                          schema, store)
from orchestrator.advance_gates import mandate
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
