"""Деление на гейте SPEC доводится до конца: признак поделённого родителя,
порядок частей в `merge_after`, рамка части — её потолок, отказ деления
до любых записей.

Группа: долгоживущий
Красен до реализации: `approve` деления не пишет `closed_as` (колонки нет — чтение строки падает KeyError), не разрешает «Порядок: после …» в `merge_after` частей, не проверяет порядок и рамку до записей и не ставит рамку потолком части.

Держит связку «команда `approve` — FSM — БД»: каждый сценарий — родитель
в лёгкой песочнице переходов (`light_transition`), SPEC с секцией
«## Деление» на диске песочницы, вызов `fsm.cmd_approve` и сверка строк
`tasks` и журнала. Названия частей, позиция частей с рамкой и форма
ссылки на задачу (полный id или префикс) порождаются модулем `random`
при каждом запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import random
import re

import pytest

from orchestrator import (budget, catalog, cleanup, config, fsm, idgen,
                          merge_after, store)
from orchestrator.advance_gates import spec_audit
from tests.sandbox import capture_new_task_id

FIRST = "первая, без зависимостей"
REFUSED = "approve отклонён"
LEASE_ACTIONS = ("lease взят", "lease снят", "lease перехвачен")
OTHER_TARGET = "proekt"
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук")
ULID = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
LONE_30 = re.compile(r"(?<![\w.,])\$?30(?:[.,]0+)?(?![\w.,]*\d)")


# --- окружение сценария ---

@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов с зерном случайных входов и счётчиком зон."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.zone_counter = 0
    return light_transition


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def run(fn, *args, **kwargs) -> str:
    """Вывод команды вместе с текстом отказа `sys.exit`."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue()


def new_task(title: str) -> str:
    _, task_id = capture_new_task_id(catalog.cmd_new, title)
    return task_id


def titles(stand, count: int) -> list[str]:
    return [f"Узел {w}" for w in stand.rng.sample(WORDS, count)]


def next_zone(stand) -> str:
    stand.zone_counter += 1
    return f"orchestrator/t_division_zone_{stand.zone_counter}.py"


def parent_spec(task_id: str, parts: list, zone: str, *,
                merge_after_value: str | None = None,
                budget_value: str = "15") -> str:
    """SPEC родителя на гейте; `parts` — (название, «Порядок:», «Рамка:»
    или None)."""
    sections = "".join(
        f"### {title}\n\nЗоны: {zone}\nПорядок: {order}\n"
        + (f"Рамка: {frame}\n" if frame is not None else "")
        + f"\nТекст ТЗ части «{title}».\n\n"
        for title, order, frame in parts)
    deps_line = (f"merge_after: {merge_after_value}\n"
                 if merge_after_value else "")
    return f"""---
task: {task_id}
type: spec
author_role: analyst
status: ready
schema_version: 5
budget_usd: {budget_value}
zones: {zone}
{deps_line}---

# SPEC: Родитель деления

## Контекст
Фикстура деления.

## Требования
1. Фикстура.

## Критерии приёмки
AC-1. Фикстура.

## Оценка объёма и деление
Фикстура.

## Деление

{sections}## Не входит
- Всё остальное.
"""


def make_parent(stand) -> str:
    return new_task("Родитель деления")


def put_on_gate(stand, parent: str, parts: list, **spec_kwargs) -> str:
    """Пишет SPEC родителя на диск песочницы и ставит его на `spec_gate`;
    возвращает зону SPEC."""
    zone = next_zone(stand)
    folder = stand.tdir.parent / parent
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SPEC.md").write_text(
        parent_spec(parent, parts, zone, **spec_kwargs), encoding="utf-8")
    conn = store.db()
    conn.execute("UPDATE tasks SET state='spec_gate' WHERE id=?", (parent,))
    conn.commit()
    return zone


def parts_by_title(parent: str) -> dict[str, str]:
    return {r["title"]: r["id"] for r in store.all_tasks(store.db())
            if r["parent_task_id"] == parent}


def row(task_id: str):
    return store.get_task(store.db(), task_id)


def deps(task_id: str) -> list[str]:
    return merge_after.stored(row(task_id)["merge_after"])


def journal(task_id: str) -> list:
    return store.task_steps(store.db(), task_id)


def last_refusal(parent: str) -> str | None:
    found = [r["detail"] or "" for r in journal(parent)
             if r["action"] == REFUSED]
    return found[-1] if found else None


def names_part(text: str, number: int, title: str) -> bool:
    return bool(title in text or re.search(
        rf"част\w*\s*№?\s*{number}(?!\d)", text, re.IGNORECASE))


def unique_prefix(stand, task_id: str) -> str:
    others = [r["id"] for r in store.all_tasks(store.db())
              if r["id"] != task_id]
    shortest = next(n for n in range(1, len(task_id) + 1)
                    if not any(o.startswith(task_id[:n]) for o in others))
    return task_id[:stand.rng.randint(shortest, len(task_id))]


def chain_orders(count: int) -> list[str]:
    return [FIRST] + [f"после части {n}" for n in range(1, count)]


def divide(stand, orders: list, frames: list | None = None,
           **spec_kwargs) -> tuple[str, list[str], str, str]:
    """Деление успешно: (родитель, id частей по номерам, вывод approve,
    зона)."""
    parent = make_parent(stand)
    names = titles(stand, len(orders))
    frames = frames or [None] * len(orders)
    zone = put_on_gate(stand, parent, list(zip(names, orders, frames)),
                       **spec_kwargs)
    out = run(fsm.cmd_approve, parent)
    found = parts_by_title(parent)
    assert sorted(found) == sorted(names), note(
        stand, f"деление не завело части {names}: {sorted(found)}\n{out}")
    return parent, [found[n] for n in names], out, zone


# --- сценарии отказа деления (AC-4…AC-9, AC-14) ---

def frame_value(kind: str) -> str:
    cap = config.ROLE_BUDGET_CAP
    if kind == "$150":
        return "$150" if cap < 150 else f"${cap + 50:.2f}"
    if kind == "cap+0.01":
        return f"${cap + 0.01:.2f}"
    return kind


def refusal_scenario(stand, case: str, *, rich: bool = False) -> dict:
    """Родитель на `spec_gate` с делением из трёх частей, на котором
    `approve` обязан отказать. `rich` — SPEC родителя несёт `zones`,
    `merge_after` и `budget_usd`, отличные от строки задачи, а последний
    вердикт аудита — `fail` (AC-10). Возврат — родитель, номер и название
    части, которую отказ обязан назвать (или None), зависящая задача D
    (или None), прочие слова отказа."""
    parent = make_parent(stand)
    names = titles(stand, 3)
    orders = chain_orders(3)
    frames = [None, None, None]
    named, dependent, words = None, None, []
    if case == "ac4_range":
        orders[2], named = "после части 4", 3
    elif case == "ac5_self":
        orders[1], named = "после части 2", 2
    elif case == "ac6_cycle":
        orders[1], orders[2], words = "после части 3", "после части 2", ["цикл"]
    elif case == "ac7_parent":
        orders[1], named = f"после {parent}", 2
    elif case == "ac8_dependent_cycle":
        dependent = new_task("Зависящая от родителя")
        neighbours = [new_task("Сосед зависящей")
                      for _ in range(stand.rng.randint(0, 1))]
        value = list(neighbours)
        value.insert(stand.rng.randint(0, len(value)), parent)
        store.update_task(store.db(), dependent,
                          merge_after=merge_after.column(value))
        orders[2], words = f"после части 2, {dependent}", ["цикл"]
    elif case == "ac9_missing":
        ghost = idgen.new_task_id()
        orders[1], named, words = f"после {ghost}", 2, [ghost]
    elif case == "ac9_other_project":
        other = idgen.new_task_id()
        store.insert_task(store.db(), other, "Задача другого проекта",
                          "in_dev", f"task/{other.lower()}-x", OTHER_TARGET,
                          config.DEFAULT_BUDGET_USD)
        orders[1], named, words = f"после {other}", 2, [other]
    elif case.startswith("ac14_"):
        kind = {"ac14_150": "$150", "ac14_word": "тридцать",
                "ac14_zero": "$0", "ac14_cap_plus": "cap+0.01"}[case]
        position = stand.rng.randrange(3)
        frames[position], named = frame_value(kind), position + 1
    else:
        raise AssertionError(f"неизвестный сценарий {case}")
    spec_kwargs = {}
    if rich:
        spec_kwargs = {"merge_after_value": new_task("Зависимость родителя"),
                       "budget_value": "15"}
    put_on_gate(stand, parent, list(zip(names, orders, frames)),
                **spec_kwargs)
    if rich:
        store.journal(store.db(), parent, "fsm", spec_audit.VERDICT_ACTION,
                      "вердикт fail; сигналы: нет")
    return {"parent": parent, "named": named,
            "title": names[named - 1] if named else None,
            "dependent": dependent, "words": words}


def assert_refused(stand, scenario: dict, out: str) -> str:
    """Общая часть отказа: частей нет, родитель на гейте с пустым
    `closed_as`, отказ в журнале называет часть и слова сценария."""
    parent = scenario["parent"]
    reason = last_refusal(parent)
    assert reason is not None, note(stand, f"approve не отказал:\n{out}")
    assert parts_by_title(parent) == {}, note(
        stand, f"части заведены при отказе: {reason}")
    assert row(parent)["state"] == "spec_gate", note(stand, reason)
    assert not row(parent)["closed_as"], note(stand, reason)
    if scenario["named"]:
        assert names_part(reason, scenario["named"], scenario["title"]), (
            note(stand, f"отказ не называет часть {scenario['named']} "
                        f"«{scenario['title']}»: {reason}"))
    for word in scenario["words"]:
        assert word in reason, note(stand, f"нет «{word}» в отказе: {reason}")
    return reason


# --- AC-1 ---

def test_ac1_divided_parent_marked_killed_task_not(stand):
    """Деление на 2–4 части цепочкой: родитель `killed` с `closed_as='divided'`; задача, убитая `kill`, — `killed` с пустым `closed_as`.

    Ловит мутацию: деление переводит родителя в `killed`, но не пишет
    `closed_as` (колонка остаётся пустой); либо `closed_as='divided'`
    пишет общий узел перехода в `killed` — и у задачи, убитой `kill`,
    колонка тоже заполнена.
    """
    count = stand.rng.randint(2, 4)
    parent, _, out, _ = divide(stand, chain_orders(count))
    assert row(parent)["state"] == "killed", note(stand, out)
    assert row(parent)["closed_as"] == "divided", note(stand, out)

    victim = new_task("Задача под kill")
    kill_out = run(cleanup.cmd_kill, victim, confirmed=True,
                   reason="ликвидация фикстуры")
    assert row(victim)["state"] == "killed", note(stand, kill_out)
    assert not row(victim)["closed_as"], note(
        stand, f"kill заполнил closed_as: {row(victim)['closed_as']!r}")


# --- AC-3, AC-11: цепочка и предупреждение о нецепочке ---

def normalized(out: str, labels: dict[str, str], zone: str) -> list[str]:
    lines = []
    for line in out.splitlines():
        for task_id, label in labels.items():
            line = line.replace(task_id, label)
        lines.append(ULID.sub("X", line).replace(zone, "ZONE"))
    return lines


def division_lines(parent: str, part_ids: list[str], out: str,
                   zone: str) -> list[str]:
    labels = {parent: "P"}
    labels.update({pid: f"S{n}" for n, pid in enumerate(part_ids, 1)})
    return normalized(out, labels, zone)


def divide_with_titles(stand, names: list[str], orders: list[str]):
    parent = make_parent(stand)
    zone = put_on_gate(stand, parent,
                       [(t, o, None) for t, o in zip(names, orders)])
    out = run(fsm.cmd_approve, parent)
    found = parts_by_title(parent)
    assert sorted(found) == sorted(names), note(
        stand, f"деление не завело части {names}: {sorted(found)}\n{out}")
    part_ids = [found[n] for n in names]
    return parent, part_ids, division_lines(parent, part_ids, out, zone)


def warning_template(line: str, names: list[str]) -> re.Pattern:
    tokens = [f"S{n}" for n in range(1, len(names) + 1)] + list(names)
    pattern = "|".join(sorted(map(re.escape, tokens), key=len,
                              reverse=True)) + r"|\d+"
    pieces = re.split(pattern, line)
    return re.compile(".+?".join(re.escape(p) for p in pieces))


def test_ac3_chain_resolves_order_into_merge_after(stand):
    """Цепочка из трёх частей: `merge_after` части 2 — часть 1, части 3 — часть 2, у части 1 пусто; у частей 2 и 3 запись «заявлено»; предупреждения о нецепочке нет.

    Предупреждение распознаётся сравнением: та же тройка частей, где у
    части 3 «Порядок:» без «после», печатает строки, которых нет в выводе
    цепочки; ни одна строка вывода цепочки не совпадает с ними с точностью
    до номера, id и названия части.

    Ловит мутацию: «после части N» разрешается в N+1-ю часть или в
    часть с номером от нуля — `merge_after` частей называет не тот id;
    значение пишется прямым `update_task` мимо канала `new` — записи
    «merge_after заявлен Оператором» в журнале части нет; предупреждение
    печатается безусловно — его строка есть и в выводе цепочки.
    """
    names = titles(stand, 3)
    _, _, loose = divide_with_titles(
        stand, names, [FIRST, "после части 1", "первая"])
    parent, (s1, s2, s3), chain = divide_with_titles(
        stand, names, chain_orders(3))

    assert deps(s1) == [], note(stand, f"часть 1: {deps(s1)}")
    assert deps(s2) == [s1], note(stand, f"часть 2: {deps(s2)} ≠ [{s1}]")
    assert deps(s3) == [s2], note(stand, f"часть 3: {deps(s3)} ≠ [{s2}]")
    for part in (s2, s3):
        actions = [r["action"] for r in journal(part)]
        assert merge_after.DECLARED_ACTION in actions, note(
            stand, f"нет «{merge_after.DECLARED_ACTION}» у {part}: {actions}")

    warnings = [line for line in loose if line not in chain]
    assert warnings, note(stand, "нецепочка не напечатала ничего сверх "
                                 "вывода цепочки — предупреждения нет")
    templates = [warning_template(line, names) for line in warnings]
    leaked = [line for line in chain
              if any(t.fullmatch(line) for t in templates)]
    assert leaked == [], note(stand, f"предупреждение в цепочке: {leaked}")


def test_ac11_part_without_after_gets_warning_naming_it(stand):
    """Три части, у части 3 «Порядок:» без «после»: деление выполнено, и вывод сверх вывода цепочки называет часть 3.

    Ловит мутацию: проверка нецепочки смотрит только на часть 2 (или на
    все, кроме последней) — строки предупреждения нет; предупреждение
    называет не ту часть (часть 1, у которой зависимостей и не должно
    быть).
    """
    names = titles(stand, 3)
    parent, ids, loose = divide_with_titles(
        stand, names, [FIRST, "после части 1",
                       stand.rng.choice(["первая", "без зависимостей",
                                         "параллельно частям 1 и 2"])])
    assert row(parent)["state"] == "killed", note(stand, "\n".join(loose))
    _, _, chain = divide_with_titles(stand, names, chain_orders(3))

    warnings = [line for line in loose if line not in chain]
    assert any("S3" in line or names[2] in line
               or re.search(r"част\w*\s*№?\s*3(?!\d)", line, re.I)
               for line in warnings), note(
        stand, f"строки сверх цепочки не называют часть 3: {warnings}")


# --- AC-4…AC-9, AC-14: отказы деления ---

def test_ac4_part_number_out_of_range_refused(stand):
    """У части 3 «Порядок: после части 4» при трёх частях: отказ, частей нет, родитель на гейте, отказ называет часть 3.

    Ловит мутацию: граница номера проверяется как `N <= M + 1` или не
    проверяется вовсе — ссылка на несуществующую часть молча
    отбрасывается, и части заводятся.
    """
    scenario = refusal_scenario(stand, "ac4_range")
    assert_refused(stand, scenario, run(fsm.cmd_approve, scenario["parent"]))


def test_ac5_self_reference_refused(stand):
    """Часть 2 «Порядок: после части 2»: отказ, частей нет, отказ называет часть 2.

    Ловит мутацию: ссылка на саму себя не отсеивается — цикл длины один
    не находится поиском цикла по рёбрам между разными узлами, части
    заводятся с `merge_after` на себя.
    """
    scenario = refusal_scenario(stand, "ac5_self")
    assert_refused(stand, scenario, run(fsm.cmd_approve, scenario["parent"]))


def test_ac6_cycle_between_parts_refused(stand):
    """Часть 2 «после части 3», часть 3 «после части 2»: отказ, частей нет, отказ называет цикл.

    Ловит мутацию: граф проверяется по строкам БД (`merge_after.check`
    до заведения частей), а не по виртуальным узлам — цикла между ещё
    не заведёнными частями не видно, части заводятся.
    """
    scenario = refusal_scenario(stand, "ac6_cycle")
    assert_refused(stand, scenario, run(fsm.cmd_approve, scenario["parent"]))


def test_ac7_parent_as_dependency_refused(stand):
    """Часть 2 «Порядок: после <id родителя>»: отказ как на мёртвой зависимости, частей нет, отказ называет часть 2.

    Ловит мутацию: элемент-id проверяется правилами `check` до перехода
    родителя в `killed` — родитель ещё жив, проверка проходит, и часть
    заводится с зависимостью от задачи, которая этим же approve умирает.
    """
    scenario = refusal_scenario(stand, "ac7_parent")
    reason = assert_refused(stand, scenario,
                            run(fsm.cmd_approve, scenario["parent"]))
    assert re.search(r"мёртв|мертв|убит|killed", reason, re.I), note(
        stand, f"отказ не называет зависимость мёртвой: {reason}")


def test_ac8_cycle_through_dependent_of_parent_refused(stand):
    """D зависит от родителя; цепочка, у части 3 «после части 2, <D>»: отказ по циклу, частей нет, `merge_after` у D прежний.

    Ловит мутацию: виртуальный граф строится без поправки
    `replace_divided` (у D ребро остаётся на родителя, а не на
    преемника) — цикла часть 3 → D → часть 3 не видно, деление проходит
    и переписывает D.
    """
    scenario = refusal_scenario(stand, "ac8_dependent_cycle")
    dependent = scenario["dependent"]
    before = row(dependent)["merge_after"]
    assert_refused(stand, scenario, run(fsm.cmd_approve, scenario["parent"]))
    assert row(dependent)["merge_after"] == before, note(
        stand, f"merge_after D изменён: {before!r} → "
               f"{row(dependent)['merge_after']!r}")


def test_ac9_task_id_element_resolved_or_refused(stand):
    """Часть 2 «после <id>» живой задачи того же проекта (полный id или префикс) — `merge_after` части 2 равен полному id; несуществующий id и id другого проекта — отказ, частей нет, отказ называет часть и элемент.

    Ловит мутацию: префикс пишется в `merge_after` как есть, без
    разрешения в полный id; элемент-id не проходит `merge_after.check`
    по задаче — несуществующая задача или задача другого проекта
    принимаются, части заводятся.
    """
    dependency = new_task("Живая зависимость")
    ref = stand.rng.choice([dependency, unique_prefix(stand, dependency)])
    _, (s1, s2, s3), out, _ = divide(
        stand, [FIRST, f"после {ref}", "после части 2"])
    assert deps(s2) == [dependency], note(
        stand, f"элемент {ref!r}: merge_after части 2 {deps(s2)}\n{out}")

    for case in ("ac9_missing", "ac9_other_project"):
        scenario = refusal_scenario(stand, case)
        assert_refused(stand, scenario,
                       run(fsm.cmd_approve, scenario["parent"]))


@pytest.mark.parametrize("case", ["ac14_150", "ac14_word", "ac14_zero",
                                  "ac14_cap_plus"])
def test_ac14_bad_frame_refused_on_approve(stand, case):
    """Рамка части $150, «тридцать», $0 или на $0.01 выше `ROLE_BUDGET_CAP` в SPEC на гейте: отказ approve, частей нет, родитель на гейте, отказ называет часть.

    Часть с плохой рамкой выбирается случайно из трёх.

    Ловит мутацию: approve полагается на проверку guard при переходе на
    гейт и рамку не перепроверяет — части заводятся с непригодной рамкой;
    граница сравнивается `>=` вместо `>` наоборот (`$cap+0.01` проходит);
    `$` не снимается до разбора и любое «$N» считается нечисловым — в
    этом случае отказ получит и допустимая рамка (ловит соседний тест).
    """
    scenario = refusal_scenario(stand, case)
    assert_refused(stand, scenario, run(fsm.cmd_approve, scenario["parent"]))


def test_ac14_frame_equal_to_cap_accepted(stand):
    """Рамка, равная `ROLE_BUDGET_CAP`, у случайной части: деление выполнено, потолок части равен потолку ролей.

    Ловит мутацию: граница рамки проверяется `>=` — рамка, равная
    потолку ролей, отказана; `$` не снимается до разбора — «$N»
    отказано как нечисловое.
    """
    cap = config.ROLE_BUDGET_CAP
    position = stand.rng.randrange(3)
    frames = [None, None, None]
    frames[position] = f"${cap:.2f}"
    _, ids, out, _ = divide(stand, chain_orders(3), frames)
    assert row(ids[position])["budget_usd"] == pytest.approx(cap), note(
        stand, f"потолок части {position + 1}: "
               f"{row(ids[position])['budget_usd']}\n{out}")


# --- AC-10: отказ ничего не пишет ---

def tasks_snapshot() -> list[tuple]:
    return [tuple(r) for r in store.db().execute(
        "SELECT * FROM tasks ORDER BY id")]


def last_step_id() -> int:
    return store.db().execute(
        "SELECT COALESCE(MAX(id), 0) FROM steps").fetchone()[0]


@pytest.mark.parametrize("case", [
    "ac4_range", "ac5_self", "ac6_cycle", "ac7_parent",
    "ac8_dependent_cycle", "ac9_missing", "ac9_other_project",
    "ac14_150", "ac14_word", "ac14_zero", "ac14_cap_plus"])
def test_ac10_refused_division_writes_nothing(stand, case):
    """Отказ деления при approve с принятием `fail` аудита: строки `tasks` до и после равны, из новых записей журнала (без записей lease) — одна «approve отклонён».

    SPEC родителя задаёт `zones`, `merge_after` (живая задача) и
    `budget_usd` 15, отличные от строки задачи (зон нет, зависимостей
    нет, потолок по умолчанию); последний вердикт аудита — `fail`.

    Ловит мутацию: проверки порядка и рамки поставлены в ветку деления
    после записи `zones`/`merge_after` и `apply_spec_budget` (как ветка
    деления стоит сегодня) — строка родителя меняется, в журнале
    появляются «бюджет из SPEC», запись о принятии `fail` аудита;
    проверка идёт по частям по ходу заведения — первая часть успевает
    появиться строкой `tasks`.
    """
    scenario = refusal_scenario(stand, case, rich=True)
    before_rows = tasks_snapshot()
    since = last_step_id()

    out = run(fsm.cmd_approve, scenario["parent"], accept_audit_fail=True)

    assert_refused(stand, scenario, out)
    after_rows = tasks_snapshot()
    assert after_rows == before_rows, note(
        stand, f"строки tasks изменены: было {before_rows}, "
               f"стало {after_rows}")
    added = [(r["task_id"], r["action"], r["detail"])
             for r in store.db().execute(
                 "SELECT * FROM steps WHERE id > ? ORDER BY id", (since,))
             if r["action"] not in LEASE_ACTIONS]
    assert [(t, a) for t, a, _ in added] == [(scenario["parent"], REFUSED)], (
        note(stand, f"записи журнала за approve: {added}"))


# --- AC-12, AC-18: рамка — потолок части ---

def baseline_part(stand) -> str:
    """Часть, заведённая тем же `catalog.spawn_subtask`, что и деление, без
    рамки: эталон потолка и журнала части без рамки."""
    holder = new_task("Эталонный родитель")
    return catalog.spawn_subtask(holder, "Эталонный родитель",
                                 "Эталонная часть",
                                 "Зоны: orchestrator/t_baseline.py\n"
                                 f"Порядок: {FIRST}\n\nТекст ТЗ.",
                                 target=config.DEFAULT_TARGET)


def frame_records(part: str, baseline: str) -> list:
    """Записи журнала части, которых нет у эталонной части по действию и
    которые называют сумму 30."""
    known = {r["action"] for r in journal(baseline)}
    return [r for r in journal(part) if r["action"] not in known
            and LONE_30.search(f"{r['action']} {r['detail'] or ''}")]


def apply_part_spec_budget(part: str, value: str) -> None:
    conn = store.db()
    budget.apply_spec_budget(conn, store.get_task(conn, part),
                             {"budget_usd": value})


def test_ac12_frame_becomes_operator_ceiling_of_part(stand):
    """Часть с «Рамка: $30» (позиция случайна): потолок 30, источник `operator`, в журнале части запись о потолке 30; SPEC части с `budget_usd: 50` потолок не меняет.

    Ловит мутацию: рамка пишется потолком с источником `spec` (или без
    источника) — `apply_spec_budget` перебивает её значением 50; потолок
    ставится прямым `update_task` без записи журнала части; рамка
    вовсе не применяется — потолок части по умолчанию.
    """
    count = stand.rng.randint(2, 3)
    position = stand.rng.randrange(count)
    frames = [None] * count
    frames[position] = "$30"
    _, ids, out, _ = divide(stand, chain_orders(count), frames)
    part = ids[position]
    assert row(part)["budget_usd"] == pytest.approx(30), note(stand, out)
    assert row(part)["budget_source"] == config.BUDGET_SOURCE_OPERATOR, (
        note(stand, f"источник {row(part)['budget_source']!r}"))
    records = frame_records(part, baseline_part(stand))
    assert records, note(stand, "в журнале части нет записи о потолке 30: "
                         + repr([(r["action"], r["detail"])
                                 for r in journal(part)]))

    apply_part_spec_budget(part, "50")
    assert row(part)["budget_usd"] == pytest.approx(30), note(
        stand, f"SPEC части перебил рамку: {row(part)['budget_usd']}")


def test_ac18_part_without_frame_keeps_todays_ceiling(stand):
    """Часть 1 «Рамка: $30», у части 2 рамки нет: потолок и источник части 2 — как у части, заведённой без рамки; источник не `operator`; записи о потолке из рамки нет; SPEC части 2 задаёт потолок.

    Ловит мутацию: рамка первой части применяется ко всем частям (или
    источник `operator` ставится всем частям деления) — у части 2
    источник `operator`, SPEC части её потолок не задаёт; запись о
    рамке пишется в журнал каждой части.
    """
    _, (s1, s2), out, _ = divide(stand, chain_orders(2), ["$30", None])
    baseline = baseline_part(stand)
    assert (row(s2)["budget_usd"], row(s2)["budget_source"]) == (
        row(baseline)["budget_usd"], row(baseline)["budget_source"]), note(
        stand, f"часть 2: {row(s2)['budget_usd']}/{row(s2)['budget_source']}"
               f", эталон: {row(baseline)['budget_usd']}/"
               f"{row(baseline)['budget_source']}\n{out}")
    assert row(s2)["budget_source"] != config.BUDGET_SOURCE_OPERATOR
    frame_actions = {r["action"] for r in frame_records(s1, baseline)}
    assert frame_actions, note(stand, "у части 1 нет записи о рамке")
    leaked = [(r["action"], r["detail"]) for r in journal(s2)
              if r["action"] in frame_actions]
    assert leaked == [], note(stand, f"запись о рамке у части 2: {leaked}")

    apply_part_spec_budget(s2, "50")
    assert row(s2)["budget_usd"] == pytest.approx(50), note(
        stand, f"SPEC части 2 не задал потолок: {row(s2)['budget_usd']}")
    other = stand.rng.choice([20, 35, 70])
    apply_part_spec_budget(s2, str(other))
    assert row(s2)["budget_usd"] == pytest.approx(other), note(
        stand, f"SPEC части 2 {other} не задал потолок: "
               f"{row(s2)['budget_usd']}")


# --- AC-19: преемник родителя — последняя по графу часть ---

def dependent_of(stand, parent: str) -> tuple[str, list[str]]:
    dependent = new_task("Зависящая от родителя")
    value = [new_task("Сосед зависящей")
             for _ in range(stand.rng.randint(0, 1))]
    value.insert(stand.rng.randint(0, len(value)), parent)
    store.update_task(store.db(), dependent,
                      merge_after=merge_after.column(value))
    return dependent, value


def divide_parent(stand, parent: str, orders: list[str]):
    names = titles(stand, len(orders))
    put_on_gate(stand, parent, [(t, o, None) for t, o in zip(names, orders)])
    out = run(fsm.cmd_approve, parent)
    found = parts_by_title(parent)
    assert sorted(found) == sorted(names), note(
        stand, f"деление не завело части {names}: {sorted(found)}\n{out}")
    return [found[n] for n in names], out


def test_ac19_successor_is_last_part_by_graph(stand):
    """Часть 1 «после части 3», часть 2 «после части 1», часть 3 без зависимостей: `merge_after` 1→3, 2→1, у 3 пусто; у D родитель заменён частью 2. В цепочке — частью 3.

    Ловит мутацию: преемником остаётся часть с последним номером
    (`new_ids[-1]`, как сегодня) — у D стоит часть 3, которая мержится
    первой; преемник берётся первым узлом без зависимостей — в цепочке
    у D окажется часть 1.
    """
    parent = make_parent(stand)
    dependent, before = dependent_of(stand, parent)
    (s1, s2, s3), out = divide_parent(
        stand, parent, ["после части 3", "после части 1", FIRST])
    assert (deps(s1), deps(s2), deps(s3)) == ([s3], [s1], []), note(
        stand, f"merge_after частей: {deps(s1)}, {deps(s2)}, {deps(s3)}\n"
               f"{out}")
    expected = [s2 if d == parent else d for d in before]
    assert deps(dependent) == expected, note(
        stand, f"D: было {before}, стало {deps(dependent)}, ждали "
               f"{expected} (часть 2 = {s2}, часть 3 = {s3})")

    chain_parent = make_parent(stand)
    chain_dependent, chain_before = dependent_of(stand, chain_parent)
    (_, _, c3), out = divide_parent(stand, chain_parent, chain_orders(3))
    expected = [c3 if d == chain_parent else d for d in chain_before]
    assert deps(chain_dependent) == expected, note(
        stand, f"D цепочки: было {chain_before}, стало "
               f"{deps(chain_dependent)}, ждали {expected}\n{out}")
