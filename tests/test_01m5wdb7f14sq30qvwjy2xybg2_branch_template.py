"""Ветка задачи по шаблону `policy.branch_template`: `new --ref` строит имя по ключу ссылки, занятое или непроверенное имя отказывает `new` и деление до заведения задачи, при шаблоне по умолчанию сетевого вызова нет.

Группа: долгоживущий
Красен до реализации: поля `branch_template`/`ref_pattern` записи локального слоя `targets.py` отвергает («неизвестное поле»), `catalog._new_task_row` строит ветку жёстко `task/{id}-{slug}`, `new` и `_division_check` не сверяют имя ветки ни с сервером, ни с БД — задача с шаблоном не заводится или заводится с прежним именем, отказов деления нет.

Держит связку «команда CLI `artel.py` (`new`, `approve` гейта SPEC) — БД —
ссылки документов — `ls-remote` сервера» в лёгкой песочнице переходов
(`light_transition`). Проект с шаблоном — запись локального слоя
(`targets.local_path()`) в трёх разделах, `forge: github`,
`merge_gate: operator`; его клон — заранее заведённый каталог
`workspace.repo(<проект>)` с `.git`. Сервер подменён: вызов `git ls-remote`
отвечает по набору «занятых» имён и на уровне `in_repo` песочницы (хук
`in_repo_handlers`), и на уровне процессов (`subprocess.run` и
`subprocess.Popen` обёрнуты поверх шпиона песочницы) — каждый такой вызов
записывается. Ссылка документов `refs/artifacts/<id>` пишется `update-ref`
через `in_repo` — его записывает тот же хук. Ключи ссылок, названия и имена
проектов порождаются модулем `random` при каждом запуске; зерно печатается
и входит в текст провала.
"""
import contextlib
import io
import random
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import artel, catalog, config, idgen, store, targets, workspace

LETTERS = "abcdefghijkmnopqrstuvwxyz"
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")
FIRST = "первая, без зависимостей"
REF_POLICY = {"branch_template": '"feature/{ref}"', "ref_required": "tracker",
              "ref_pattern": r"PROJ-\d+"}
SLUG_POLICY = {"branch_template": '"feature/{slug}"'}
ID_POLICY = {"branch_template": '"feature/{id}-{slug}"'}
REF_DIVISION_REASON = "ветка по ключу трекера: делите задачу в трекере"
UNCHECKED_REASON = "имя ветки не проверено"
FAKE_SHA = "a" * 40


# --- окружение сценария ---

def ls_remote_rest(args) -> list | None:
    """Аргументы после `ls-remote` git-вызова; `None` — вызов не `ls-remote`."""
    words = [str(a) for a in args]
    if "ls-remote" not in words:
        return None
    return words[words.index("ls-remote") + 1:]


@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов: зерно, подменённый сервер `ls-remote`,
    запись ссылок документов, которые пишет `update-ref`."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.taken = set()
    light_transition.taken_match = None
    light_transition.ls_fail = False
    light_transition.ls_calls = []
    light_transition.artifact_refs = []

    def answer(args, text: bool):
        rest = ls_remote_rest(args)
        light_transition.ls_calls.append(rest)
        if light_transition.ls_fail:
            out, err, code = "", "fatal: unable to access origin", 128
        else:
            positional = [a for a in rest if not a.startswith("-")]
            patterns = [p.removeprefix("refs/heads/") for p in positional[1:]]
            names = (sorted(light_transition.taken) if not patterns
                     else [n for n in patterns if taken(light_transition, n)])
            out = "".join(f"{FAKE_SHA}\trefs/heads/{n}\n" for n in names)
            err = ""
            code = 2 if ("--exit-code" in rest and not names) else 0
        if not text:
            out, err = out.encode(), err.encode()
        return subprocess.CompletedProcess(list(args), code, out, err)

    def in_repo_handler(repo, *args):
        if "update-ref" in args:
            light_transition.artifact_refs.extend(
                a for a in args if str(a).startswith("refs/artifacts/"))
        if ls_remote_rest(args) is not None:
            return answer(args, True)
        return None

    light_transition.in_repo_handlers.append(in_repo_handler)
    spy_run, real_popen = subprocess.run, subprocess.Popen

    def run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and ls_remote_rest(cmd) is not None:
            text = bool(kwargs.get("text") or kwargs.get("encoding")
                        or kwargs.get("universal_newlines"))
            return answer(cmd, text)
        return spy_run(cmd, *args, **kwargs)

    def popen(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and ls_remote_rest(cmd) is not None:
            light_transition.ls_calls.append(ls_remote_rest(cmd))
            raise OSError("песочница: ls-remote процессом Popen не исполняется")
        return real_popen(cmd, *args, **kwargs)

    with mock.patch.object(subprocess, "run", run), \
            mock.patch.object(subprocess, "Popen", popen):
        yield light_transition


def taken(stand, name: str) -> bool:
    return name in stand.taken or bool(stand.taken_match and stand.taken_match(name))


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def cli(*args: str) -> tuple[str, int]:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода)."""
    buf = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                buf.write(f"\n{code}")
                code = 1
    return buf.getvalue(), code


def words(stand, count: int = 2) -> str:
    return " ".join(stand.rng.sample(WORDS, count))


def task_ids() -> set:
    return {r["id"] for r in store.all_tasks(store.db())}


def task_row(task_id: str):
    return store.get_task(store.db(), task_id)


def epics() -> set:
    return {r["id"] for r in store.db().execute("SELECT id FROM epics")}


def render(fields: dict) -> str:
    return "".join(f"      {key}: {value}\n" for key, value in fields.items())


def project(stand, policy: dict | None = None) -> str:
    """Внешний проект локального слоя с полями `policy`; клон заведён заранее."""
    name = "p" + "".join(stand.rng.choice(LETTERS) for _ in range(7))
    entry = (f"  {name}:\n"
             f"    description:\n      base: {config.MAIN_BRANCH}\n"
             f"      test_profile:\n        command: [python3, -m, pytest]\n"
             f"        long_lived_dir: tests\n"
             f"        long_lived_name: test_<id>_<name>.py\n"
             f"    policy:\n      no_paths: []\n      project_skills: []\n"
             f"      merge_gate: operator\n"
             f"      weakening_scope: [tests/**/*.py]\n"
             f"      mutation_claim_scope: [tests/test_*.py]\n"
             + render(policy or {})
             + f"    machine:\n      forge: github\n"
             f"      url: https://localhost/team/{name}\n"
             f"      token_slot: {name}-token\n")
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    text = local.read_text(encoding="utf-8") if local.exists() else "targets:\n"
    local.write_text(text + entry, encoding="utf-8")
    (workspace.repo(name) / ".git").mkdir(parents=True, exist_ok=True)
    return name


def insert_task(stand, name: str, state: str, branch: str) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, f"Задача {words(stand)}", state,
                      branch, name, config.DEFAULT_BUDGET_USD)
    return task_id


def new(stand, name: str | None, *flags: str) -> dict:
    """`new "<название>" [--target <проект>] <flags>`: вывод, код, заведённые
    задачи, новые ссылки документов."""
    before_ids, before_refs = task_ids(), len(stand.artifact_refs)
    target = ["--target", name] if name is not None else []
    out, code = cli("new", f"Новая {words(stand)}", *target, *flags)
    return {"out": out, "code": code, "created": task_ids() - before_ids,
            "artifacts": stand.artifact_refs[before_refs:]}


def assert_refused_clean(stand, result: dict, what: str) -> None:
    """Отказ без следов: ни строки `tasks`, ни ссылки документов."""
    assert result["code"] != 0, note(stand, f"{what}: new не отказал:\n{result['out']}")
    assert result["created"] == set(), note(
        stand, f"{what}: заведены {result['created']}:\n{result['out']}")
    assert result["artifacts"] == [], note(
        stand, f"{what}: ссылки документов {result['artifacts']}")


def created_branch(stand, result: dict, what: str) -> str:
    assert result["code"] == 0 and len(result["created"]) == 1, note(
        stand, f"{what}: new ({result['code']}):\n{result['out']}")
    return task_row(next(iter(result["created"])))["branch"]


def key(stand) -> str:
    return f"PROJ-{stand.rng.randrange(10, 10 ** 6)}"


# --- AC-3 ---

def test_ac3_new_ref_builds_branch_by_template(stand):
    """`new --ref tracker:PROJ-<n>` при шаблоне `feature/{ref}` заводит задачу с веткой `feature/PROJ-<n>`.

    Сценарий: проект с `branch_template: feature/{ref}`, `ref_required:
    tracker`, `ref_pattern: PROJ-\\d+`; случайный ключ по образцу. `new`
    выходит с кодом 0, заводит ровно одну задачу, её ветка в строке
    `tasks` — `feature/<ключ>`.

    Ловит мутацию: `_new_task_row` по-прежнему строит `task/{id}-{slug}` —
    ветка будет `task/…`; `{ref}` подставляется в нижнем регистре, как
    `{id}`, — ветка будет `feature/proj-<n>`; подставляется система ссылки
    вместо ключа — `feature/tracker`.
    """
    name = project(stand, REF_POLICY)
    ref = key(stand)
    result = new(stand, name, "--ref", f"tracker:{ref}")
    branch = created_branch(stand, result, f"new --ref tracker:{ref}")
    assert branch == f"feature/{ref}", note(stand, f"ветка {branch!r}\n{result['out']}")


@pytest.mark.parametrize("case", ["pattern-mismatch", "two-refs"])
def test_ac3_new_ref_refused_without_trace(stand, case):
    """Ключ не по `ref_pattern` или две ссылки системы `ref_required` — отказ `new` без задачи и ссылки документов.

    Сценарий: проект с шаблоном `feature/{ref}`. `new --ref
    tracker:PROJ-<n>x` (ключ не полностью совпадает с `PROJ-\\d+`) и `new
    --ref tracker:PROJ-<n> --ref tracker:PROJ-<m>` выходят с ненулевым
    кодом; строк `tasks` и ссылок `refs/artifacts/*` не прибавилось.
    Контрольно тот же проект с одной годной ссылкой задачу заводит — отказ
    вызван ссылкой, а не непрочитанной записью.

    Ловит мутацию: `ref_pattern` сверяется `re.match`, а не полным
    совпадением — `PROJ-<n>x` пройдёт; при двух ссылках берётся первая —
    задача заведётся; проверка стоит после `_new_task_row` — останется
    ссылка документов или строка задачи.
    """
    name = project(stand, REF_POLICY)
    first, second = key(stand), key(stand)
    refs = ([f"tracker:{first}x"] if case == "pattern-mismatch"
            else [f"tracker:{first}", f"tracker:{second}"])
    flags = [part for ref in refs for part in ("--ref", ref)]
    assert_refused_clean(stand, new(stand, name, *flags), f"new {flags}")
    control = key(stand)
    branch = created_branch(stand, new(stand, name, "--ref", f"tracker:{control}"),
                            "контроль: одна годная ссылка")
    assert branch == f"feature/{control}", note(stand, f"контроль: ветка {branch!r}")


# --- AC-4 ---

@pytest.mark.parametrize("conflict", ["server", "done", "killed"])
def test_ac4_taken_branch_name_refuses_new(stand, conflict):
    """Имя `feature/PROJ-<n>` занято на сервере или задачей проекта в `done`/`killed` — отказ `new` без следов.

    Сценарий: проект с шаблоном `feature/{ref}`. Имя занято: подменённый
    `ls-remote` отвечает на него ссылкой — либо в БД есть задача этого
    проекта в `done` или `killed` с этой веткой. `new --ref
    tracker:PROJ-<n>` выходит с ненулевым кодом, строк `tasks` и ссылок
    `refs/artifacts/*` не прибавилось. Контрольно свободный ключ задачу
    заводит.

    Ловит мутацию: занятость в БД ищется только среди задач в полёте
    (без `done`/`killed`) — задача заведётся; ответ `ls-remote` не
    разбирается (сверяется только код выхода) — серверное имя сойдёт за
    свободное; проверка стоит после `_new_task_row` — останется ссылка
    документов.
    """
    name = project(stand, REF_POLICY)
    ref = key(stand)
    if conflict == "server":
        stand.taken.add(f"feature/{ref}")
    else:
        insert_task(stand, name, conflict, f"feature/{ref}")
    assert_refused_clean(stand, new(stand, name, "--ref", f"tracker:{ref}"),
                         f"имя занято ({conflict})")
    control = key(stand)
    while control == ref:
        control = key(stand)
    branch = created_branch(stand, new(stand, name, "--ref", f"tracker:{control}"),
                            "контроль: свободное имя")
    assert branch == f"feature/{control}", note(stand, f"контроль: ветка {branch!r}")


def test_ac4_ls_remote_failure_refuses_new(stand):
    """Сбой `ls-remote` — отказ `new` с причиной «имя ветки не проверено», без следов.

    Сценарий: проект с шаблоном `feature/{ref}`, подменённый `ls-remote`
    выходит с кодом 128. `new --ref tracker:PROJ-<n>` выходит с ненулевым
    кодом, в выводе — «имя ветки не проверено», строк `tasks` и ссылок
    документов не прибавилось. Когда сервер снова отвечает, тот же `new`
    задачу заводит.

    Ловит мутацию: сбой `ls-remote` трактуется как «ветки нет» — задача
    заведётся; отказ печатает общий текст без «имя ветки не проверено».
    """
    name = project(stand, REF_POLICY)
    ref = key(stand)
    stand.ls_fail = True
    result = new(stand, name, "--ref", f"tracker:{ref}")
    assert_refused_clean(stand, result, "сбой ls-remote")
    assert UNCHECKED_REASON in result["out"], note(stand, result["out"])
    stand.ls_fail = False
    branch = created_branch(stand, new(stand, name, "--ref", f"tracker:{ref}"),
                            "контроль: сервер отвечает")
    assert branch == f"feature/{ref}", note(stand, f"контроль: ветка {branch!r}")


@pytest.mark.parametrize("which", ["artel", "default-fields"])
def test_ac4_default_template_new_without_ls_remote(stand, which):
    """При шаблоне по умолчанию `new` заводит задачу без вызова `ls-remote`.

    Сценарий: артель либо внешний проект без поля `branch_template`.
    `new` выходит с кодом 0 и заводит задачу; подменённый сервер не видел
    ни одного вызова `ls-remote` — ни через `in_repo`, ни процессом.

    Ловит мутацию: проверка занятости имени на сервере выполняется при
    любом шаблоне, а не только при шаблоне не по умолчанию, — шпион
    увидит `ls-remote`.
    """
    name = None if which == "artel" else project(stand)
    created_branch(stand, new(stand, name), f"new ({which})")
    assert stand.ls_calls == [], note(stand, f"ls-remote: {stand.ls_calls}")


# --- AC-4 (деление), AC-5 ---

def spec_text(task_id: str, zone: str, parts: list) -> str:
    """SPEC родителя с секцией «## Деление» на части `parts`."""
    orders = [FIRST] + [f"после части {n}" for n in range(1, len(parts))]
    division = "".join(
        f"### {title}\n\nЗоны: {zone}\nПорядок: {order}\n\n"
        f"Текст ТЗ части «{title}».\n\n"
        for title, order in zip(parts, orders))
    return f"""---
task: {task_id}
type: spec
author_role: analyst
status: ready
schema_version: 5
budget_usd: 15
zones: {zone}
---

# SPEC: Родитель деления

## Контекст
Фикстура деления по шаблону ветки.

## Требования
1. Фикстура.

## Критерии приёмки
AC-1. Фикстура.

## Оценка объёма и деление
Фикстура.

## Деление

{division}## Не входит
- Всё остальное.
"""


def division_parent(stand, name: str, parts: list) -> str:
    """Родитель проекта `name` на гейте SPEC с делением на части `parts`."""
    parent = insert_task(stand, name, "spec_gate", f"task/parent-{stand.rng.randrange(10 ** 6)}")
    write_spec(stand, parent, parts)
    return parent


def write_spec(stand, parent: str, parts: list) -> None:
    folder = stand.tdir.parent / parent
    folder.mkdir(parents=True, exist_ok=True)
    zone = f"src/t_division_{stand.rng.randrange(10 ** 6)}.py"
    (folder / "SPEC.md").write_text(spec_text(parent, zone, parts), encoding="utf-8")


def parts_of(parent: str) -> list:
    return [r for r in store.all_tasks(store.db()) if r["parent_task_id"] == parent]


def part_titles(stand, count: int = 2) -> list:
    return [f"Часть {w}" for w in stand.rng.sample(WORDS, count)]


def approve(parent: str, as_epic: bool) -> tuple[str, int]:
    return cli("approve", parent, *(["--as-epic"] if as_epic else []))


@pytest.mark.parametrize("which", ["artel", "default-fields"])
def test_ac4_default_template_division_without_ls_remote(stand, which):
    """При шаблоне по умолчанию деление заводит части без вызова `ls-remote`.

    Сценарий: родитель артели либо проекта без `branch_template` на гейте
    SPEC с делением на две части. `approve` заводит обе части; подменённый
    сервер не видел ни одного вызова `ls-remote`.

    Ловит мутацию: `_division_check` сверяет имена частей с сервером при
    любом шаблоне — шпион увидит `ls-remote` с именем части.
    """
    name = config.DEFAULT_TARGET if which == "artel" else project(stand)
    titles = part_titles(stand)
    parent = division_parent(stand, name, titles)
    out, code = approve(parent, False)
    assert len(parts_of(parent)) == len(titles), note(stand, f"approve ({code}):\n{out}")
    assert stand.ls_calls == [], note(stand, f"ls-remote: {stand.ls_calls}")


def snapshot(parent: str) -> dict:
    row = task_row(parent)
    return {"zones": row["zones"], "merge_after": row["merge_after"],
            "budget_usd": row["budget_usd"], "state": row["state"]}


DIVISION_CASES = ["ref-template", "slug-server", "slug-db", "slug-twins", "id-server"]


@pytest.mark.parametrize("as_epic", [False, True], ids=["approve", "as-epic"])
@pytest.mark.parametrize("case", DIVISION_CASES)
def test_ac5_division_refused_before_any_part(stand, case, as_epic):
    """Отказ деления по имени ветки — ни части, ни эпика, ни записей гейта; родитель на `spec_gate`.

    Сценарий: родитель проекта на гейте SPEC с делением на две части.
    Случаи: шаблон `feature/{ref}` (причина «ветка по ключу трекера:
    делите задачу в трекере»); шаблон `feature/{slug}`, имя второй части
    занято на сервере (подменённый `ls-remote`) или задачей проекта в
    `done` (БД); шаблон `feature/{slug}`, у частей одинаковый slug;
    шаблон `feature/{id}-{slug}`, `ls-remote` отвечает на имя
    `feature/<id второй части>-<slug второй части>`. `approve` (и
    `approve --as-epic`) не заводит ни одной части (ни строки с
    `parent_task_id` родителя, ни ссылки документов), эпиков не
    прибавилось, у родителя прежние `zones`, `merge_after`, `budget_usd`,
    состояние — `spec_gate`. Контрольно после снятия конфликта тот же
    `approve` части заводит — отказ вызван именем ветки.

    Ловит мутацию: проверка имён стоит в `_spawn_division_subtasks` после
    заведения первой части — первая часть и её ссылка документов
    останутся; проверка после записи `zones`/`merge_after` гейта — поля
    родителя изменятся; эпик `--as-epic` создаётся до проверки — эпик
    останется; совпадение slug частей между собой не сверяется — части
    заведутся; при `{id}` имена проверяются с временными id, а части
    заводятся с новыми — занятое имя второй части не будет найдено.
    """
    rng = stand.rng
    titles = part_titles(stand)
    if case == "ref-template":
        name = project(stand, REF_POLICY)
    elif case == "id-server":
        name = project(stand, ID_POLICY)
        slug = re.escape(catalog.slugify(titles[1]))
        stand.taken_match = re.compile(rf"feature/[0-9a-z]+-{slug}").fullmatch
    else:
        name = project(stand, SLUG_POLICY)
        if case == "slug-twins":
            titles = [titles[0], titles[0].upper() + "!"]
        second = f"feature/{catalog.slugify(titles[1])}"
        if case == "slug-server":
            stand.taken.add(second)
        if case == "slug-db":
            holder = insert_task(stand, name, "done", second)
    parent = division_parent(stand, name, titles)
    before, before_epics = snapshot(parent), epics()
    before_refs = len(stand.artifact_refs)
    out, code = approve(parent, as_epic)
    what = f"{case}, approve{' --as-epic' if as_epic else ''} ({code})"
    assert parts_of(parent) == [], note(stand, f"{what}: части заведены:\n{out}")
    assert stand.artifact_refs[before_refs:] == [], note(
        stand, f"{what}: ссылки документов {stand.artifact_refs[before_refs:]}")
    assert epics() == before_epics, note(stand, f"{what}: эпик заведён:\n{out}")
    assert snapshot(parent) == before, note(stand, f"{what}: {snapshot(parent)} != {before}")
    if case == "ref-template":
        assert REF_DIVISION_REASON in out, note(stand, f"{what}:\n{out}")
        return
    # Контроль: конфликт снят — тот же approve заводит части.
    stand.taken.clear()
    stand.taken_match = None
    if case == "slug-db":
        store.update_task(store.db(), holder, branch=f"feature/other-{rng.randrange(10 ** 6)}")
    if case == "slug-twins":
        write_spec(stand, parent, part_titles(stand))
    out, code = approve(parent, as_epic)
    assert len(parts_of(parent)) == len(titles), note(
        stand, f"{what}: контроль без конфликта ({code}):\n{out}")


def test_ac5_id_template_parts_get_checked_names(stand):
    """При шаблоне `feature/{id}-{slug}` без конфликта ветка каждой части — ровно проверенное имя.

    Сценарий: родитель проекта с `branch_template: feature/{id}-{slug}` на
    гейте SPEC с делением на 2–3 части, сервер имён не знает. `approve`
    заводит все части; ветка каждой — `feature/<id части в нижнем
    регистре>-<slug её названия>`, и подменённый `ls-remote` был вызван
    именно с этим именем.

    Ловит мутацию: id частей для проверки выдаются отдельно от id, с
    которыми части заводятся (`spawn_subtask` зовёт `idgen.new_task_id`
    заново), — ветка части не совпадёт ни с одним проверенным именем;
    ветка части строится по шаблону по умолчанию — будет `task/…`.
    """
    name = project(stand, ID_POLICY)
    titles = part_titles(stand, stand.rng.randint(2, 3))
    parent = division_parent(stand, name, titles)
    out, code = approve(parent, False)
    parts = parts_of(parent)
    assert len(parts) == len(titles), note(stand, f"approve ({code}):\n{out}")
    asked = {a.removeprefix("refs/heads/") for call in stand.ls_calls for a in call}
    for part in parts:
        expected = f"feature/{part['id'].lower()}-{catalog.slugify(part['title'])}"
        assert part["branch"] == expected, note(stand, f"часть {part['id']}: {part['branch']!r}")
        assert part["branch"] in asked, note(
            stand, f"часть {part['id']}: {part['branch']} не проверялась; ls-remote: {stand.ls_calls}")
