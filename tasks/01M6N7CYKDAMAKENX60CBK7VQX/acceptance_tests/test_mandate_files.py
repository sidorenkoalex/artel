"""Факты задачи о существующих тестах: три файла мандата `ANSWER-1.md` правлены только в его объёме (AC-13), сторож литералов и названные прежние тесты зелёные и не правлены (AC-12).

Группа: разовый
Красен до реализации: файлы мандата ещё на тексте main — константы причины несут перечень из двух пар, `UNSUPPORTED` держит `github` + `target-human`, утверждения констант поддержки — старое множество пар; методы AC-12 зелены с рождения — они держат неизменность и зелень прежних тестов.

База сравнения — `DIFF_BASE` помощника пульта `_pult.py` (точка
расхождения ветки задачи с `origin/<основная ветка>`), правленая сторона —
HEAD рабочей копии (то же, что закоммиченный дифф `changed_paths()`).
Тексты файлов обеих сторон читаются `git show <ревизия>:<путь>` в
`CODE_ROOT`. Разбор — модулем `ast`: сверяются вид утверждений и значения
литералов, а не строки файла, — переформатирование под мандатом не
краснит планку.

Провалидировано: все проверки AC-13 прогнаны (временным сценарием вне
репозитория) на текстах трёх файлов с правкой ровно в объёме мандата —
зелёные; на правке, ослабляющей равенство до «содержит», удаляющей случай
`gitlab` + `operator` или добавляющей константу причины в файл эпика —
красные.
"""
# AC-9: escalate — критерий требует, чтобы `kill` задачи `github` + `target-human` ДО отправки удалял заранее заведённую ветку задачи из `origin` и писал «ветка origin <ветка>: удалена». Это недостижимо в зонах задачи: уборка удаляет ветку отправкой `push --delete` через `gitcmd.in_repo` с `-c http.lowSpeedLimit…` (`orchestrator/cleanup.py:253-276`), а белый список отправок любой записи с `merge_gate` не `operator` отказывает и глобальной опции `-c` перед push, и `--delete` чего-либо, кроме `refs/artifacts/<id>` (`orchestrator/gitcmd.py:836-841`, `:866-876`); `orchestrator/gitcmd.py` по SPEC («Не входит») — только для чтения. Прогон на стенде подтверждает: GitLab с `target-human` сегодня пишет «ветка origin <ветка>: оставлено — отказ: отправка отказана (проект …): глобальная опция git -c перед push», ветка в `origin` остаётся. Вопрос Оператору (блокирует AC-9, прочие критерии не блокирует): (A) открыть `orchestrator/gitcmd.py` для правки белого списка — разрешить `push --delete refs/heads/<ветка>` ветки задачи проекта, уходящей в `killed`, без `-c` (зона и инвариант белого списка — решение Оператора); (B) переписать AC-9 «до отправки»: ветка в `origin` остаётся, запись «уборка» несёт прежний исход удаления «ветка origin <ветка>: …» (отказ белого списка) и «PR не тронут: MR вливают люди проекта», `gh pr close` не вызван; (C) до отправки уборка проекта людей ветку origin не трогает вовсе, запись — только «PR не тронут: MR вливают люди проекта». Дефолт при молчании — (B): совпадает с прежним поведением GitLab (AC-10 «записи прежние») и не трогает белый список. Части AC-9 «после отправки» и `github` + `operator` от ответа не зависят; их тесты готовы (записка шага, приложение).
import ast
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

UNSUPPORTED_FILE = "tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py"
PAIR_FILE = "tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py"
EPIC_FILE = "tests/test_epic_draft_promote_unsupported_project.py"
MANDATE_FILES = (UNSUPPORTED_FILE, PAIR_FILE, EPIC_FILE)
NAMED_FILES = (
    "tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py",
    "tests/test_awaiting_human_units.py",
    "tests/test_gitcmd_push_point.py",
    "tests/test_push_hook_stand.py",
    "tests/test_mr_delivery_units.py",
)
GUARD_TEST = f"{UNSUPPORTED_FILE}::test_ac9_no_support_literals_outside_targets"
NEW_PAIRS = {("github", "operator"), ("github", "target-human"), ("gitlab", "target-human")}
NEW_GLOP = ("гейт мержа operator не поддержан для хостинга gitlab "
            "(поддержаны: github + operator, github + target-human, "
            "gitlab + target-human)")
SKIP_NAMES = {"skip", "skipif", "xfail", "importorskip", "skipTest", "expectedFailure"}
GLOP_CASE = re.compile(r"""["']gitlab["']\s*,\s*["']operator["']""")
PYTEST_LIMIT_SEC = 110


# --- чтение сторон ---------------------------------------------------------

def git_text(revision: str, path: str) -> str | None:
    """Текст `path` ревизии `revision` рабочей копии; файла нет — None."""
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show", f"{revision}:{path}"],
                         capture_output=True, text=True, encoding="utf-8",
                         timeout=60)
    return res.stdout if res.returncode == 0 else None


def sides(path: str) -> tuple[str, str]:
    assert DIFF_BASE, "база диффа не подставлена пультом"
    base, head = git_text(DIFF_BASE, path), git_text("HEAD", path)
    assert base is not None, f"{path}: нет в базе {DIFF_BASE}"
    assert head is not None, f"{path}: нет в HEAD"
    return base, head


# --- разбор ----------------------------------------------------------------

def functions(tree: ast.Module) -> dict:
    return {n.name: n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def assigned(tree: ast.Module, name: str):
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name):
            return node.value
    return None


def literal(node, names: dict | None = None):
    """Значение литерала; имена из `names` подставляются их значениями."""
    names = names or {}
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        values = [literal(e, names) for e in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.Set):
        return {literal(e, names) for e in node.elts}
    return ast.literal_eval(node)


def body_dump(fn) -> str:
    """Тело функции без докстринга — для сверки «не правлено»."""
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return "\n".join(ast.dump(stmt) for stmt in body)


def compares(fn) -> list:
    return [n for n in ast.walk(fn) if isinstance(n, ast.Compare)]


def eq_compares(fn, left: str) -> list:
    """Сравнения `<left> == <правая часть>` в функции: правые части."""
    return [n.comparators[0] for n in compares(fn)
            if ast.unparse(n.left) == left and len(n.ops) == 1
            and isinstance(n.ops[0], ast.Eq)]


def asserts_text(fn) -> list:
    return [ast.unparse(n.test) for n in ast.walk(fn) if isinstance(n, ast.Assert)]


def parametrize_args(fn) -> list:
    """Аргументы декораторов `pytest.mark.parametrize` функции."""
    found = []
    for dec in fn.decorator_list:
        if isinstance(dec, ast.Call) and ast.unparse(dec.func).endswith("mark.parametrize"):
            found.append(dec.args)
    return found


def skip_marks(tree: ast.Module) -> int:
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in SKIP_NAMES:
            count += 1
        elif isinstance(node, ast.Name) and node.id in SKIP_NAMES:
            count += 1
    return count


def glop_cases(text: str) -> int:
    """Случаи `gitlab` + `operator` — пары литералов в тексте кода (без
    докстрингов и комментариев)."""
    tree = ast.parse(text)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Tuple, ast.List, ast.Call)):
            items = node.elts if not isinstance(node, ast.Call) else node.args
            values = [i.value if isinstance(i, ast.Constant) else None for i in items]
            count += sum(1 for a, b in zip(values, values[1:])
                         if (a, b) == ("gitlab", "operator"))
    return count


def string_constants(tree: ast.Module) -> list:
    """Строковые литералы кода, кроме докстрингов модуля и функций."""
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docs.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


# --- проверки AC-13 (чистые функции над текстами сторон) ---------------------

def common_problems(path: str, base: str, head: str) -> list:
    problems = []
    if glop_cases(head) < glop_cases(base):
        problems.append(f"{path}: случаев gitlab + operator {glop_cases(head)} < "
                        f"{glop_cases(base)} на main")
    if skip_marks(ast.parse(head)) > skip_marks(ast.parse(base)):
        problems.append(f"{path}: новые skip/xfail")
    return problems


def unsupported_problems(base: str, head: str) -> list:
    problems = common_problems(UNSUPPORTED_FILE, base, head)
    tree = ast.parse(head)
    names = {}
    for const in ("GITLAB_REASON", "TARGET_HUMAN_REASON"):
        value = assigned(tree, const)
        if value is not None:
            names[const] = literal(value)
    if names.get("GITLAB_REASON") != NEW_GLOP:
        problems.append(f"GITLAB_REASON — не новый текст целиком: {names.get('GITLAB_REASON')!r}")
    cases = literal(assigned(tree, "UNSUPPORTED"), names) if assigned(tree, "UNSUPPORTED") else []
    if ("gitlab", "operator", NEW_GLOP) not in [tuple(c) for c in cases]:
        problems.append(f"UNSUPPORTED без случая gitlab + operator с новым текстом: {cases}")
    if any(tuple(c)[:2] == ("github", "target-human") for c in cases):
        problems.append("UNSUPPORTED держит github + target-human")
    fns = functions(tree)
    ac1 = fns.get("test_ac1_entry_loads_and_reason_names_unsupported_value")
    if ac1 is None:
        problems.append("нет test_ac1_entry_loads_and_reason_names_unsupported_value")
    else:
        if not eq_compares(ac1, "targets.unsupported_reason(name)"):
            problems.append("AC-1 файла: unsupported_reason сравнивается не равенством")
        pairs = [literal(r) for r in eq_compares(ac1, "targets.SUPPORTED_PAIRS")]
        if pairs != [NEW_PAIRS]:
            problems.append(f"AC-1 файла: SUPPORTED_PAIRS == {pairs}, ждётся {NEW_PAIRS}")
        for const in ("targets.SUPPORTED_FORGES", "targets.SUPPORTED_MERGE_GATES"):
            if not eq_compares(ac1, const):
                problems.append(f"AC-1 файла: {const} сравнивается не равенством")
    for fname in ("test_ac2_new_refuses_without_side_effects",
                  "test_ac3_run_refuses_before_agent_and_git",
                  "test_ac4_auto_refuses_at_entry",
                  "test_ac5_approve_on_merge_gate_refuses_before_merge",
                  "test_ac6_approve_on_spec_gate_refuses"):
        fn = fns.get(fname)
        if fn is None:
            problems.append(f"нет {fname}")
            continue
        if "reason in out" not in asserts_text(fn):
            problems.append(f"{fname}: нет assert reason in out")
        if not any(len(a) > 1 and ast.unparse(a[1]) == "UNSUPPORTED"
                   for a in parametrize_args(fn)):
            problems.append(f"{fname}: случаи не из UNSUPPORTED")
    ac7 = fns.get("test_ac7_doctor_project_support_line")
    if ac7 is None or "reason in found[0].detail" not in asserts_text(ac7):
        problems.append("test_ac7_doctor_project_support_line: нет assert reason in found[0].detail")
    elif "UNSUPPORTED" not in ast.unparse(ac7):
        problems.append("test_ac7_doctor_project_support_line: случаи не из UNSUPPORTED")
    return problems


def pair_problems(base: str, head: str) -> list:
    problems = common_problems(PAIR_FILE, base, head)
    tree, base_tree = ast.parse(head), ast.parse(base)
    glop = assigned(tree, "GLOP_REASON")
    if glop is None or literal(glop) != NEW_GLOP:
        problems.append(f"GLOP_REASON — не новый текст целиком: "
                        f"{literal(glop) if glop is not None else None!r}")
    fns, base_fns = functions(tree), functions(base_tree)
    exact = fns.get("test_ac3_gitlab_operator_reason_exact")
    if exact is None or [ast.unparse(r) for r in
                         eq_compares(exact, "targets.unsupported_reason(name)")] != ["GLOP_REASON"]:
        problems.append("test_ac3_gitlab_operator_reason_exact: нет unsupported_reason == GLOP_REASON")
    actions = fns.get("test_ac3_gitlab_operator_actions_refuse")
    if actions is None:
        problems.append("нет test_ac3_gitlab_operator_actions_refuse")
    else:
        calls = [ast.unparse(n) for n in ast.walk(actions) if isinstance(n, ast.Call)
                 and ast.unparse(n.func) == "check_refusal"]
        if not any("'gitlab', 'operator', GLOP_REASON" in c for c in calls):
            problems.append(f"test_ac3_gitlab_operator_actions_refuse: вызов {calls}")
        params = [literal(a[1]) for a in parametrize_args(actions) if len(a) > 1]
        if not params or not {"new", "run", "auto", "approve"} <= set(params[0]):
            problems.append(f"test_ac3_gitlab_operator_actions_refuse: действия {params}")
    if "check_refusal" not in fns or body_dump(fns["check_refusal"]) != body_dump(
            base_fns["check_refusal"]):
        problems.append("check_refusal правлена (вид утверждения вхождения)")
    constants = fns.get("test_ac4_support_constants_exact")
    if constants is None or [literal(r) for r in
                             eq_compares(constants, "targets.SUPPORTED_PAIRS")] != [NEW_PAIRS]:
        problems.append("test_ac4_support_constants_exact: SUPPORTED_PAIRS не равенством с новым составом")
    elif not (eq_compares(constants, "targets.SUPPORTED_FORGES")
              and eq_compares(constants, "targets.SUPPORTED_MERGE_GATES")):
        problems.append("test_ac4_support_constants_exact: константы хостингов/гейтов не равенством")
    text = fns.get("test_ac4_reason_text_names_pair_and_supported_list")
    if text is None:
        problems.append("нет test_ac4_reason_text_names_pair_and_supported_list")
    else:
        cases = [tuple(c) for a in parametrize_args(text) if len(a) > 1
                 for c in literal(a[1])]
        if ("gitlab", "operator", NEW_GLOP) not in cases:
            problems.append(f"test_ac4_reason_text…: нет случая gitlab-operator с новым текстом: {cases}")
        if any(c[:2] == ("github", "target-human") for c in cases):
            problems.append("test_ac4_reason_text…: github-target-human остался отказным")
        if "reason == expected" not in asserts_text(text):
            problems.append("test_ac4_reason_text…: нет assert reason == expected")
    return problems


def epic_problems(base: str, head: str) -> list:
    problems = common_problems(EPIC_FILE, base, head)
    tree, base_tree = ast.parse(head), ast.parse(base)
    cases = literal(assigned(tree, "UNSUPPORTED")) if assigned(tree, "UNSUPPORTED") else []
    if ("gitlab", "operator") not in [tuple(c) for c in cases]:
        problems.append(f"UNSUPPORTED без gitlab + operator: {cases}")
    if any(tuple(c) == ("github", "target-human") for c in cases):
        problems.append("UNSUPPORTED держит github + target-human")
    name = "test_draft_promote_of_unsupported_project_refuses"
    fns, base_fns = functions(tree), functions(base_tree)
    if name not in fns or body_dump(fns[name]) != body_dump(base_fns[name]):
        problems.append(f"{name}: тело правлено (вид проверки причины не как на main)")
    else:
        texts = asserts_text(fns[name])
        if "reason" not in texts or "reason in out" not in texts:
            problems.append(f"{name}: нет assert reason / assert reason in out")
        if "targets.unsupported_reason(name)" not in ast.unparse(fns[name]):
            problems.append(f"{name}: причина не из targets.unsupported_reason(name)")
    if [s for s in string_constants(tree) if "не поддержан" in s]:
        problems.append("в файл эпика введена константа текста причины")
    other = [ast.dump(n) for n in tree.body
             if not (isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "UNSUPPORTED")
             and not isinstance(n, (ast.FunctionDef, ast.Expr))]
    base_other = [ast.dump(n) for n in base_tree.body
                  if not (isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "UNSUPPORTED")
                  and not isinstance(n, (ast.FunctionDef, ast.Expr))]
    if other != base_other:
        problems.append("правка файла эпика вне переноса параметра target-human")
    for fname, fn in fns.items():
        if fname != name and (fname not in base_fns
                              or body_dump(fn) != body_dump(base_fns[fname])):
            problems.append(f"{fname}: правка вне переноса параметра")
    return problems


# ------------------------------------------------------------------ AC-13


def test_ac13_unsupported_project_file_within_mandate():
    """`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` против main: случаи `gitlab` + `operator` не убыли, константа причины — новый текст целиком, вид утверждений прежний, константы поддержки — равенство с новым составом.

    Сценарий: тексты файла в базе диффа и в HEAD разбираются `ast`.
    Сверяются: пары литералов `gitlab`, `operator` не реже, чем на main;
    `skip`/`xfail` не прибавилось; `GITLAB_REASON` равен новому тексту
    целиком; `UNSUPPORTED` несёт (`gitlab`, `operator`, новый текст) и не
    несёт `github` + `target-human`; в `test_ac1_…` — равенство
    `unsupported_reason(name) == reason`, равенства трёх констант
    поддержки, `SUPPORTED_PAIRS` — новый состав; `test_ac2_…`…`test_ac6_…`
    — `assert reason in out` по случаям `UNSUPPORTED`; `test_ac7_…` —
    `assert reason in found[0].detail`.

    Ловит мутацию: случай `gitlab` + `operator` удалён вместе с
    `github` + `target-human`; утверждение равенства ослаблено до
    вхождения; константа причины не дописана новой парой; добавлен
    `skip`.
    """
    base, head = sides(UNSUPPORTED_FILE)
    problems = unsupported_problems(base, head)
    assert problems == [], "\n".join(problems)


def test_ac13_pair_support_file_within_mandate():
    """`tests/test_01m6ezxvfg405y1btfdsgbks8e_pair_support.py` против main: `GLOP_REASON` — новый текст, `test_ac3_*` и `test_ac4_*` сравнивают равенством с новым составом и текстом, `check_refusal` не правлена.

    Сценарий: тексты базы и HEAD разбираются `ast`. Сверяются: случаи
    `gitlab` + `operator` не убыли, `skip`/`xfail` не прибавилось;
    `GLOP_REASON` равен новому тексту; `test_ac3_gitlab_operator_reason_exact`
    — `unsupported_reason(name) == GLOP_REASON`;
    `test_ac3_gitlab_operator_actions_refuse` — `check_refusal(…, "gitlab",
    "operator", GLOP_REASON, …)` по действиям `new`, `run`, `auto`,
    `approve`; тело `check_refusal` как на main; в
    `test_ac4_support_constants_exact` — равенства констант,
    `SUPPORTED_PAIRS` — новый состав; в
    `test_ac4_reason_text_names_pair_and_supported_list` — случай
    `gitlab-operator` с новым текстом, `github-target-human` в отказных
    нет, `assert reason == expected`.

    Ловит мутацию: `reason == expected` заменено на вхождение; случай
    `gitlab-operator` убран из параметров; `check_refusal` ослаблена;
    `SUPPORTED_PAIRS` сверяется вхождением пары.
    """
    base, head = sides(PAIR_FILE)
    problems = pair_problems(base, head)
    assert problems == [], "\n".join(problems)


def test_ac13_epic_promote_file_only_moves_parameter():
    """`tests/test_epic_draft_promote_unsupported_project.py` против main: правка — только перенос параметра `target-human`; вид проверки причины — как на main, новой константы текста нет.

    Сценарий: тексты базы и HEAD разбираются `ast`. Сверяются: случай
    (`gitlab`, `operator`) в `UNSUPPORTED` есть, (`github`,
    `target-human`) нет; тело теста (без докстринга) равно телу на main —
    `reason = targets.unsupported_reason(name)`, `assert reason`, `assert
    reason in out`; строковых литералов с «не поддержан» в коде нет; прочие
    инструкции модуля и функции не правлены; `skip`/`xfail` не
    прибавилось.

    Ловит мутацию: в файл эпика введена константа точного текста причины
    (сравнение равенством вместо `unsupported_reason`); случай `gitlab` +
    `operator` удалён; тело теста переписано.
    """
    base, head = sides(EPIC_FILE)
    problems = epic_problems(base, head)
    assert problems == [], "\n".join(problems)


# ------------------------------------------------------------------ AC-12


def test_ac12_prior_tests_not_edited():
    """Ни один прежний файл `tests/`, кроме трёх файлов мандата, не правлен задачей; пять названных файлов и раздел сторожа литералов — как на main.

    Сценарий: пути задачи `changed_paths()` помощника пульта; каждый путь
    под `tests/`, существующий в базе диффа, — один из трёх файлов
    мандата. Пять файлов, названных критерием, равны тексту базы. В файле
    `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` раздел
    сторожа (от `WATCHED_VALUES =` до конца файла) равен тексту базы.

    Ловит мутацию: разработчик подогнал прежний тест под код (правка
    файла `tests/` вне мандата, в том числе одного из пяти названных) или
    ослабил сторож литералов (дописал исключение в `EXEMPT`) — путь в
    списке правленых, текст файла или раздела сторожа отличен от базы.
    """
    changed = changed_paths()
    edited = [p for p in changed if p.startswith("tests/") and p not in MANDATE_FILES
              and git_text(DIFF_BASE, p) is not None]
    assert edited == [], f"правлены прежние тесты: {edited}"
    for path in NAMED_FILES:
        base, head = sides(path)
        assert head == base, f"{path} правлен"
    base, head = sides(UNSUPPORTED_FILE)
    marker = "WATCHED_VALUES ="
    assert marker in base and marker in head, "раздел сторожа не найден"
    assert head[head.index(marker):] == base[base.index(marker):], "раздел сторожа правлен"


def run_pytest(target: str) -> tuple[int | str, str]:
    """pytest одного файла/узла в своей группе процессов с пределом."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", target, "-q", "-p", "no:cacheprovider"],
        cwd=str(CODE_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=PYTEST_LIMIT_SEC)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return "предел", out
    return proc.returncode, out


@pytest.mark.parametrize("target", [GUARD_TEST, *NAMED_FILES])
def test_ac12_guard_and_named_tests_green(target):
    """Сторож литералов `forge`/`merge_gate` и пять названных файлов прежних тестов зелёные.

    Сценарий: pytest узла сторожа
    `test_ac9_no_support_literals_outside_targets` и каждого из пяти
    названных файлов запускается в рабочей копии отдельным процессом в
    своей группе (предел — страховка от зависания); код выхода 0.

    Ловит мутацию: литерал хостинга вне `targets.py` (например
    `_forge_of(target) == "github"` заменён сравнением `forge` в новой
    функции `cleanup.py`) — сторож называет файл и строку; правка отправки,
    хука или доставки MR ломает прежний сценарий `github` + `operator` или
    `gitlab` + `target-human` — код выхода не 0.
    """
    code, out = run_pytest(target)
    assert code == 0, f"{target}: код {code}\n{out[-4000:]}"
