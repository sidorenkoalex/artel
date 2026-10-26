"""Проект с неподдержанным хостингом (`forge: gitlab`) или гейтом мержа людьми проекта (`merge_gate: target-human`): запись читается, а `new`, `run`, `auto`, `approve` отказывают именованной причиной `targets.unsupported_reason`; `doctor` выводит строку `project-support-<проект>`.

Группа: долгоживущий
Красен до реализации: в `orchestrator/targets.py` нет `unsupported_reason`, `SUPPORTED_FORGES`, `SUPPORTED_MERGE_GATES` — обращение падает `AttributeError`; `new`/`run`/`auto`/`approve` проект не проверяют (идут к клону, git, агенту, `fsm.cmd_advance`), строки `project-support-<проект>` у `doctor` нет.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
команда CLI `artel.py` — БД (строки `tasks`/`steps`) — внешние процессы».
Песочница — `initialized_tmp_root` (`tests.sandbox.InitializedTmpRootTest`:
пути `config` во временном каталоге, БД со схемой, `subprocess.run`
подменён шпионом `git_spy`, который записывает КАЖДУЮ команду процесса —
это и есть шпион git: всякий git пульта уходит процессом). Агент —
подменённый `runner.spawn_agent`, переход — подменённый `fsm.cmd_advance`:
оба при вызове поднимают `Halt`, команда на нём обрывается, и тест видит
факт вызова. Позитивный `new` поддержанного проекта — в лёгкой песочнице
переходов `light_transition` (там `new` проходит целиком без настоящего
git). Строки `doctor` — публичный `doctor.all_checks(conn)`, внешние
процессы, кроме локальных, получают отказ запуска (тот же приём, что у
долгоживущего теста строки `targets-local-layer`).

Имена проектов порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.
"""
import ast
import contextlib
import io
import os
import random
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

import orchestrator
from orchestrator import (artel, config, doctor, fsm, idgen, repo_context,
                          runner, store, targets)
from tests.sandbox import artel_target_entry, strip_dash_c

LETTERS = "abcdefghijkmnopqrstuvwxyz"
GITLAB_REASON = "хостинг gitlab не поддержан: адаптера нет (ADR-0029)"
TARGET_HUMAN_REASON = "гейт мержа target-human не исполняется (ADR-0029)"
# (forge, merge_gate, ожидаемая причина) — две неподдержанные записи AC.
UNSUPPORTED = [
    ("gitlab", "operator", GITLAB_REASON),
    ("github", "target-human", TARGET_HUMAN_REASON),
]
UNSUPPORTED_IDS = ["gitlab", "target-human"]
NETWORK_GIT = {"clone", "fetch", "push", "pull", "ls-remote"}


class Halt(Exception):
    """Подменённая зависимость вызвана: команда обрывается здесь."""


# --- окружение сценария ---

def project_name(rng: random.Random) -> str:
    return "p" + "".join(rng.choice(LETTERS) for _ in range(7))


def flat_entry(name: str, forge: str, gate: str) -> str:
    return (f"  {name}:\n    forge: {forge}\n"
            f"    url: https://localhost/team/{name}\n"
            f"    base: {config.MAIN_BRANCH}\n"
            f"    token_slot: {name}-token\n    no_paths: []\n"
            f"    project_skills: []\n    merge_gate: {gate}\n")


def declare(name: str, forge: str, gate: str) -> None:
    """Дописывает плоскую запись проекта в `targets.yaml` песочницы."""
    text = (config.TARGETS.read_text(encoding="utf-8")
            if config.TARGETS.exists() else "targets:\n" + artel_target_entry())
    config.TARGETS.write_text(text.rstrip("\n") + "\n" + flat_entry(name, forge, gate),
                              encoding="utf-8")


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def halted():
    """Агент и переход FSM подменены: вызов поднимает `Halt`."""
    with mock.patch.object(runner, "spawn_agent", side_effect=Halt("spawn_agent")) as spawn, \
            mock.patch.object(fsm, "cmd_advance", side_effect=Halt("cmd_advance")) as advance:
        yield {"spawn": spawn, "advance": advance}


def cli(*args: str) -> tuple[str, int]:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода).
    Оборванная на подменённой зависимости команда — код `Halt`."""
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
        except Halt as exc:
            buf.write(f"\nHalt: {exc}")
            code = "Halt"
    return buf.getvalue(), code


def git_calls(spy, start: int) -> list:
    """Команды git, записанные шпионом процессов с индекса `start`."""
    return [list(c) for c in spy.calls[start:]
            if c and Path(os.fsdecode(c[0])).name == "git"]


def table(name: str) -> list:
    return [tuple(r) for r in store.db().execute(f"SELECT * FROM {name} ORDER BY rowid")]


def insert_task(name: str, state: str) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача неподдержанного проекта", state,
                      f"task/{task_id.lower()}-x", name, config.DEFAULT_BUDGET_USD)
    return task_id


def journal_with(task_id: str, reason: str) -> list:
    return [dict(r) for r in store.task_steps(store.db(), task_id)
            if reason in f"{r['action']} {r['detail']}"]


def unsupported_project(seed: int, forge: str, gate: str) -> str:
    name = project_name(random.Random(seed))
    declare(name, forge, gate)
    return name


# --- AC-1 ---

@pytest.mark.parametrize("forge,gate,reason", UNSUPPORTED + [("github", "operator", None)],
                         ids=UNSUPPORTED_IDS + ["supported"])
def test_ac1_entry_loads_and_reason_names_unsupported_value(tmp_root, seed, forge, gate, reason):
    """Запись с неподдержанным значением загружается, а `unsupported_reason` называет причину.

    Сценарий: в `targets.yaml` песочницы дописана запись проекта со
    случайным именем и парой (`forge`, `merge_gate`). `targets.target`
    возвращает запись без исключения с теми же значениями полей;
    `targets.unsupported_reason` — точный текст причины для `gitlab` и для
    `target-human`, `None` — для `github` + `operator`. Константы
    поддержанных значений — ровно `("github",)` и `("operator",)`.

    Ловит мутацию: отказ поставлен в проверку записи (`targets.check`) —
    `targets.target` поднимет `TargetsError`; `unsupported_reason` сверяет
    `forge` с `FORGES` вместо `SUPPORTED_FORGES` — для `gitlab` вернёт
    `None`; перепутаны тексты причин хостинга и гейта; в
    `SUPPORTED_MERGE_GATES` попал `target-human`.
    """
    name = unsupported_project(seed, forge, gate)
    entry = targets.target(name)
    assert entry["forge"] == forge and entry["merge_gate"] == gate, f"зерно: {seed}; {entry}"
    assert targets.unsupported_reason(name) == reason, f"зерно: {seed}; {name}"
    assert targets.SUPPORTED_FORGES == ("github",)
    assert targets.SUPPORTED_MERGE_GATES == ("operator",)


# --- AC-2 ---

@pytest.mark.parametrize("forge,gate,reason", UNSUPPORTED, ids=UNSUPPORTED_IDS)
def test_ac2_new_refuses_without_side_effects(initialized_tmp_root, seed, forge, gate, reason):
    """`new --target` неподдержанного проекта отказывает до клона, git и id.

    Сценарий: запись проекта со случайным именем, клона нет. `artel.py
    new "<название>" --target <проект>` выходит с ненулевым кодом, в
    выводе — причина `unsupported_reason`; каталог клона
    (`repo_context.clone_path`) не появился, шпион процессов не видел ни
    одной команды git, строки `tasks` и `steps` до и после совпадают.

    Ловит мутацию: проверка поставлена после `workspace.ensure_clone` — шпион
    увидит `git clone`, причина отказа будет про клон, а не про проект;
    поставлена после `idgen.new_task_id`/строки БД — изменятся `tasks`/
    `steps`; отказ печатает общий текст без причины `unsupported_reason`.
    """
    name = unsupported_project(seed, forge, gate)
    spy = initialized_tmp_root.git_spy
    before_tasks, before_steps, start = table("tasks"), table("steps"), len(spy.calls)
    out, code = cli("new", "Задача неподдержанного проекта", "--target", name)
    note = f"зерно: {seed}; проект {name}; код {code}\n{out}"
    assert code != 0, note
    assert reason in out, note
    assert not repo_context.clone_path(name).exists(), note
    assert git_calls(spy, start) == [], note
    assert table("tasks") == before_tasks, note
    assert table("steps") == before_steps, note


# --- AC-3 ---

@pytest.mark.parametrize("forge,gate,reason", UNSUPPORTED, ids=UNSUPPORTED_IDS)
def test_ac3_run_refuses_before_agent_and_git(initialized_tmp_root, halted, seed,
                                              forge, gate, reason):
    """`run` задачи неподдержанного проекта отказывает до агента и git.

    Сценарий: задача проекта заведена в БД фикстурой в агентском
    состоянии `in_dev`. `artel.py run <id> --attach` печатает причину
    `unsupported_reason`; подменённый `runner.spawn_agent` не вызван, шпион
    процессов не видел ни одной команды git; в журнале задачи — запись с
    этой причиной.

    Ловит мутацию: проверки в `runner.cmd_run` нет — шаг доходит до
    рабочей копии (git) и до `spawn_agent`; проверка стоит после подтяжки —
    шпион увидит git; отказ печатается, но не журналируется — записи с
    причиной в `steps` нет.
    """
    name = unsupported_project(seed, forge, gate)
    task_id = insert_task(name, "in_dev")
    spy = initialized_tmp_root.git_spy
    start = len(spy.calls)
    out, code = cli("run", task_id, "--attach")
    note = f"зерно: {seed}; проект {name}; код {code}\n{out}"
    assert reason in out, note
    assert halted["spawn"].call_count == 0, note
    assert git_calls(spy, start) == [], note
    assert journal_with(task_id, reason), f"{note}\nжурнал: {table('steps')}"


# --- AC-4 ---

@pytest.mark.parametrize("forge,gate,reason", UNSUPPORTED, ids=UNSUPPORTED_IDS)
def test_ac4_auto_refuses_at_entry(initialized_tmp_root, halted, seed, forge, gate, reason):
    """`auto` задачи неподдержанного проекта отказывает на входе.

    Сценарий: та же задача в `in_dev`. `artel.py auto <id> --attach`
    печатает причину `unsupported_reason`; подменённые `fsm.cmd_advance` и
    `runner.spawn_agent` не вызваны, шпион процессов не видел ни одной
    команды git; в журнале задачи — запись с этой причиной.

    Ловит мутацию: проверка только в `runner.cmd_run` (а не на входе
    `auto`) — цикл раньше зовёт `fsm.cmd_advance` предварительным шагом и
    шпион его увидит; отказ на входе не журналируется — записи с причиной
    нет.
    """
    name = unsupported_project(seed, forge, gate)
    task_id = insert_task(name, "in_dev")
    spy = initialized_tmp_root.git_spy
    start = len(spy.calls)
    out, code = cli("auto", task_id, "--attach")
    note = f"зерно: {seed}; проект {name}; код {code}\n{out}"
    assert reason in out, note
    assert halted["advance"].call_count == 0, note
    assert halted["spawn"].call_count == 0, note
    assert git_calls(spy, start) == [], note
    assert journal_with(task_id, reason), f"{note}\nжурнал: {table('steps')}"


# --- AC-5, AC-6 ---

@pytest.mark.parametrize("forge,gate,reason", UNSUPPORTED, ids=UNSUPPORTED_IDS)
def test_ac5_approve_on_merge_gate_refuses_before_merge(initialized_tmp_root, halted, seed,
                                                        forge, gate, reason):
    """`approve` на `merge_gate` неподдержанного проекта отказывает до слияния.

    Сценарий: задача проекта в состоянии `merge_gate`. `artel.py approve
    <id>` печатает причину `unsupported_reason`; шпион процессов не видел
    ни `git merge`, ни `git push`; состояние осталось `merge_gate`; в
    журнале задачи — запись с этой причиной.

    Ловит мутацию: проверки нет в `fsm.cmd_approve` — гейт мержа идёт
    обычным путём (сверка фиксации, слияние в `base`, отправка) и причины в
    выводе нет; проверка только для состояний, кроме `merge_gate`; отказ не
    журналируется.
    """
    name = unsupported_project(seed, forge, gate)
    task_id = insert_task(name, "merge_gate")
    spy = initialized_tmp_root.git_spy
    start = len(spy.calls)
    out, code = cli("approve", task_id)
    merges = [c for c in git_calls(spy, start)
              if {"merge", "push"} & set(strip_dash_c(c[1:])[:1])]
    note = f"зерно: {seed}; проект {name}; код {code}\n{out}"
    assert reason in out, note
    assert merges == [], note
    assert store.get_task(store.db(), task_id)["state"] == "merge_gate", note
    assert journal_with(task_id, reason), f"{note}\nжурнал: {table('steps')}"


@pytest.mark.parametrize("forge,gate,reason", UNSUPPORTED, ids=UNSUPPORTED_IDS)
def test_ac6_approve_on_spec_gate_refuses(initialized_tmp_root, halted, seed,
                                          forge, gate, reason):
    """`approve` на `spec_gate` неподдержанного проекта отказывает, состояние не меняется.

    Сценарий: задача проекта в состоянии `spec_gate`. `artel.py approve
    <id>` печатает причину `unsupported_reason`; состояние осталось
    `spec_gate`; в журнале задачи — запись с этой причиной.

    Ловит мутацию: проверка поставлена только в обработчик `merge_gate`
    (`_approve_merge_gate`), а не до таблицы состояний `fsm.cmd_approve` —
    гейт SPEC пройдёт обычным путём без причины в выводе и журнале.
    """
    name = unsupported_project(seed, forge, gate)
    task_id = insert_task(name, "spec_gate")
    out, code = cli("approve", task_id)
    note = f"зерно: {seed}; проект {name}; код {code}\n{out}"
    assert reason in out, note
    assert store.get_task(store.db(), task_id)["state"] == "spec_gate", note
    assert journal_with(task_id, reason), f"{note}\nжурнал: {table('steps')}"


# --- AC-7 ---

def local_command(argv) -> bool:
    """Локальный процесс песочницы: `ps`, интерпретатор Python, git без сети."""
    if not isinstance(argv, (list, tuple)) or not argv:
        return False
    words = [os.fsdecode(a) for a in argv]
    name = Path(words[0]).name
    if name == "git":
        return not NETWORK_GIT & set(words[1:])
    return name == "ps" or name.startswith("python") or words[0] == sys.executable


@pytest.fixture
def pult(initialized_tmp_root):
    """Песочница с проинициализированным корнем; внешние процессы не запускаются."""
    real_run, real_popen = subprocess.run, subprocess.Popen

    def run(argv, *args, **kwargs):
        if local_command(argv):
            return real_run(argv, *args, **kwargs)
        empty = b"" if not (kwargs.get("text") or kwargs.get("encoding")
                            or kwargs.get("universal_newlines")) else ""
        return subprocess.CompletedProcess(argv, 127, empty, empty)

    def popen(argv, *args, **kwargs):
        if local_command(argv):
            return real_popen(argv, *args, **kwargs)
        raise FileNotFoundError(f"песочница: внешний процесс {argv!r} не запускается")

    with mock.patch.object(subprocess, "run", run), \
            mock.patch.object(subprocess, "Popen", popen):
        yield initialized_tmp_root


def test_ac7_doctor_project_support_line(pult, seed):
    """`doctor` выводит строку `project-support-<проект>` для каждой записи.

    Сценарий: в `targets.yaml` песочницы — артель и три внешние записи со
    случайными именами: `forge: gitlab`, `merge_gate: target-human` и
    `github` + `operator`. Среди строк `doctor.all_checks` у каждой записи
    ровно одна строка `project-support-<проект>`: `fail` с причиной
    `unsupported_reason` у двух неподдержанных, `ok` у поддержанной и у
    артели.

    Ловит мутацию: строка не добавлена в `all_checks`; статус `warn`/`skip`
    вместо `fail` у неподдержанной записи; в тексте `fail` нет причины;
    строка выводится только для неподдержанных — у артели её нет.
    """
    rng = random.Random(seed)
    names = {}
    for forge, gate, reason in UNSUPPORTED + [("github", "operator", None)]:
        name = project_name(rng)
        while name in names:
            name = project_name(rng)
        names[name] = reason
        declare(name, forge, gate)
    names[config.DEFAULT_TARGET] = None
    checks = doctor.all_checks(store.db())
    shown = "\n".join(f"[{c.status}] {c.name}: {c.detail}" for c in checks)
    for name, reason in names.items():
        found = [c for c in checks if c.name == f"project-support-{name}"]
        note = f"зерно: {seed}; проект {name}\n{shown}"
        assert len(found) == 1, note
        if reason is None:
            assert found[0].status == "ok", note
        else:
            assert found[0].status == "fail", note
            assert reason in found[0].detail, note


# --- AC-8 (поведение поддержанного проекта) ---

def test_ac8_supported_project_new_is_not_refused(light_transition, seed):
    """`new` проекта `github` + `operator` заводит задачу, как раньше.

    Сценарий: в лёгкой песочнице переходов — внешняя запись `github` +
    `operator` со случайным именем и заранее заведённым каталогом клона.
    `artel.py new "<название>" --target <проект>` выходит с кодом 0,
    заводит ровно одну строку `tasks` этого проекта, в выводе нет ссылки
    на ADR-0029.

    Ловит мутацию: условие `unsupported_reason` перевёрнуто (`is None`
    вместо `is not None`) либо в `SUPPORTED_FORGES` вместо `github` попал
    `gitlab` — `new` поддержанного проекта откажет.
    """
    name = project_name(random.Random(seed))
    declare(name, "github", "operator")
    (repo_context.clone_path(name) / ".git").mkdir(parents=True, exist_ok=True)
    before = {r["id"] for r in store.all_tasks(store.db())}
    out, code = cli("new", "Задача поддержанного проекта", "--target", name)
    created = [r for r in store.all_tasks(store.db()) if r["id"] not in before]
    note = f"зерно: {seed}; проект {name}; код {code}\n{out}"
    assert code == 0, note
    assert len(created) == 1 and created[0]["target"] == name, note
    assert "ADR-0029" not in out, note


# --- AC-9 ---

WATCHED_VALUES = {"github", "gitlab", "operator", "target-human"}
WATCHED_FIELDS = ("forge", "merge_gate")
# Исключения сторожа поимённо (SPEC, раздел «Исключения сторожа AC-9»):
# (путь от каталога пакета orchestrator, функция) — сравнения `forge` с
# "github", выбирающие поведение GitHub-адаптера, не проверку поддержки.
EXEMPT = {
    ("github_adapter.py", "_is_github_target"),
    ("doctor/misc_checks.py", "check_base_branch"),
    ("cleanup.py", "cleanup_project_remote"),
    ("cleanup.py", "_forge_of"),
}
SUPPORT_MODULE = "targets.py"


def field_like(node: ast.AST) -> bool:
    """Выражение — значение поля `forge`/`merge_gate`: `x["forge"]`,
    `x.get("merge_gate")`, имя/атрибут/вызов с `forge`/`merge_gate` в имени."""
    if isinstance(node, ast.Subscript):
        key = node.slice
        return isinstance(key, ast.Constant) and key.value in WATCHED_FIELDS
    if isinstance(node, ast.Call):
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "get" and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in WATCHED_FIELDS):
            return True
        node = func
    if isinstance(node, ast.Name):
        return any(f in node.id for f in WATCHED_FIELDS)
    if isinstance(node, ast.Attribute):
        return any(f in node.attr for f in WATCHED_FIELDS)
    return False


def watched_literals(node: ast.AST) -> set:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value} & WATCHED_VALUES
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return set().union(*(watched_literals(e) for e in node.elts)) if node.elts else set()
    return set()


def support_comparisons(source: str, rel: str) -> list[str]:
    """Сравнения значения `forge`/`merge_gate` с литералом поддержанного или
    неподдержанного значения вне исключений: «путь:строка: текст»."""
    found = []

    def visit(node: ast.AST, functions: tuple) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions = functions + (node.name,)
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if (any(field_like(o) for o in operands)
                    and any(watched_literals(o) for o in operands)
                    and not any((rel, f) in EXEMPT for f in functions)):
                found.append(f"{rel}:{node.lineno}: {ast.unparse(node)}")
        for child in ast.iter_child_nodes(node):
            visit(child, functions)

    visit(ast.parse(source), ())
    return found


def test_ac9_no_support_literals_outside_targets():
    """Во всём `orchestrator/`, кроме `targets.py`, нет сравнения `forge`/`merge_gate` с литералом значения.

    Сценарий: сторож сначала проверяет себя на образцах — сравнения
    `e["merge_gate"] != "operator"`, `e.get("forge") not in ("github",)`,
    `forge == "gitlab"` он находит, а `actor == "operator"` (актор журнала)
    и `t["state"] == "merge_gate"` (имя состояния) — нет. Затем разбирает
    каждый `*.py` пакета `orchestrator` и собирает сравнения значения поля
    `forge`/`merge_gate` с литералом `"github"`, `"gitlab"`, `"operator"`,
    `"target-human"`; исключения SPEC названы поимённо (файл, функция) и
    не считаются. Найденное — пустой список.

    Ловит мутацию: точка отказа в `fsm.py`/`runner.py`/`auto.py`/
    `catalog.py`/`doctor/` проверяет поддержку своим сравнением
    (`entry["merge_gate"] != "operator"`, `entry.get("forge") == "gitlab"`)
    вместо вызова `targets.unsupported_reason` — сторож назовёт файл и
    строку.
    """
    samples = {
        "def f(e):\n    return e['merge_gate'] != 'operator'\n": 1,
        "def f(e):\n    return e.get('forge') not in ('github',)\n": 1,
        "def f(forge):\n    return forge == 'gitlab'\n": 1,
        "def f(actor):\n    return actor == 'operator'\n": 0,
        "def f(t):\n    return t['state'] == 'merge_gate'\n": 0,
    }
    for source, expected in samples.items():
        assert len(support_comparisons(source, "образец.py")) == expected, source
    package = Path(orchestrator.__file__).resolve().parent
    found = []
    for path in sorted(package.rglob("*.py")):
        rel = path.relative_to(package).as_posix()
        if rel == SUPPORT_MODULE:
            continue
        found += support_comparisons(path.read_text(encoding="utf-8"), rel)
    assert found == [], "\n".join(found)
