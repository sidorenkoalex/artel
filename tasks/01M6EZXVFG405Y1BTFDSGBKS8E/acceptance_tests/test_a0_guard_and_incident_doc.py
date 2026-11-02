"""Факты задачи: правка сторожа А0 в рамках мандата, документ порядка при инциденте, неизменность прочих тестов `tests/`.

Группа: разовый
Красен до реализации: сторож А0 держит прежние тексты `GITLAB_REASON`/`TARGET_HUMAN_REASON` и не проверяет пару `gitlab` + `target-human` (отказ ей ac1/ac7/ac8 не валит), `targets.SUPPORTED_PAIRS` нет (мутация констант не применяется), документа `docs/incident-external-project.md` нет.

База сравнения — `DIFF_BASE` помощника пульта (точка расхождения ветки с
`origin`), текст файла на базе — `git show <база>:<путь>` в `CODE_ROOT`.
Условия (а)–(в) требования 5 проверяются поведенчески: сторож А0
прогоняется подпроцессом pytest, в котором `orchestrator.targets` испорчен
заданной мутацией (подменён атрибут модуля — его берут все вызывающие);
сторож обязан покраснеть.
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

A0 = "tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py"
DOC = "docs/incident-external-project.md"
AC1 = "test_ac1_entry_loads_and_reason_names_unsupported_value"
AC7 = "test_ac7_doctor_project_support_line"
AC8 = "test_ac8_supported_project_new_is_not_refused"
CHANGED_TESTS = {AC1, AC7, AC8}
REASON_CONSTANTS = {
    "GITLAB_REASON": ("гейт мержа operator не поддержан для хостинга gitlab "
                      "(поддержаны: github + operator, gitlab + target-human)"),
    "TARGET_HUMAN_REASON": ("гейт мержа target-human не поддержан для хостинга github "
                            "(поддержаны: github + operator, gitlab + target-human)"),
}


def base_text(rel: str) -> str:
    assert DIFF_BASE, "база диффа задачи не определена пультом"
    proc = subprocess.run(["git", "-C", str(CODE_ROOT), "show", f"{DIFF_BASE}:{rel}"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def exists_at_base(rel: str) -> bool:
    proc = subprocess.run(["git", "-C", str(CODE_ROOT), "cat-file", "-e", f"{DIFF_BASE}:{rel}"],
                          capture_output=True, text=True)
    return proc.returncode == 0


def head_text(rel: str) -> str:
    return (Path(CODE_ROOT) / rel).read_text(encoding="utf-8")


def top_level(source: str) -> tuple:
    """({имя: (узел, исходник с декораторами)}, [исходники безымянных узлов])."""
    lines = source.splitlines(keepends=True)
    named, unnamed = {}, []
    for node in ast.parse(source).body:
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        text = "".join(lines[start - 1:node.end_lineno])
        name = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name)):
            name = node.targets[0].id
        if name is None:
            unnamed.append(text)
        else:
            named[name] = (node, text)
    return named, unnamed


def asserts(node: ast.AST) -> list:
    return [ast.dump(n) for n in ast.walk(node) if isinstance(n, ast.Assert)]


# --- AC-5 ---

def test_ac5_only_mandated_parts_of_a0_changed():
    """Относительно базы в сторож А0 изменены только две константы причин и три теста мандата.

    Сценарий: файл сторожа на базе ветки и в HEAD разбираются по узлам
    верхнего уровня. Безымянные узлы (докстринг, импорты) совпадают
    побайтно; набор имён тот же; каждый именованный узел, кроме
    `GITLAB_REASON`, `TARGET_HUMAN_REASON`, ac1, ac7, ac8, — побайтно
    прежний вместе с декораторами (в том числе `UNSUPPORTED`,
    `UNSUPPORTED_IDS`, ac2–ac6, ac9, `EXEMPT`). Константы причин — строки,
    точно равные текстам п. 3 (условие (г)).

    Ловит мутацию: правка декоратора или тела ac2–ac6 (например, сужение
    `UNSUPPORTED` до одной пары), правка `EXEMPT`/ac9, добавленный новый
    помощник или константа модуля; константы причин оставлены прежними
    или записаны с префиксом «проект <имя>: ».
    """
    base_named, base_unnamed = top_level(base_text(A0))
    head_named, head_unnamed = top_level(head_text(A0))
    assert head_unnamed == base_unnamed
    assert set(head_named) == set(base_named), \
        f"добавлено: {sorted(set(head_named) - set(base_named))}; " \
        f"убрано: {sorted(set(base_named) - set(head_named))}"
    for name in ("UNSUPPORTED", "UNSUPPORTED_IDS", "EXEMPT",
                 "test_ac9_no_support_literals_outside_targets"):
        assert name in base_named, name
    for name, (_, text) in base_named.items():
        if name in CHANGED_TESTS or name in REASON_CONSTANTS:
            continue
        assert head_named[name][1] == text, f"{name} изменён относительно базы"
    for name, expected in REASON_CONSTANTS.items():
        node = head_named[name][0]
        assert isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant), name
        assert node.value.value == expected, f"{name} = {node.value.value!r}"


@pytest.mark.parametrize("test_name", [AC7, AC8])
def test_ac5_requirement6_asserts_preserved(test_name):
    """Утверждения требования 6 в ac7 и ac8 остались в своём тесте в прежнем виде.

    Сценарий: каждое `assert` теста на базе ветки (сравнение по
    `ast.dump`) находится среди `assert` того же теста в HEAD.

    Ловит мутацию: `assert len(found) == 1` ослаблен до `>= 1`, убрана
    проверка `reason in found[0].detail`, в ac8 убран `"ADR-0029" not in
    out` или условие «ровно одна задача проекта».
    """
    base_named, _ = top_level(base_text(A0))
    head_named, _ = top_level(head_text(A0))
    head_asserts = asserts(head_named[test_name][0])
    missing = [a for a in asserts(base_named[test_name][0]) if a not in head_asserts]
    assert missing == [], "\n".join(missing)


def run_a0(test_name: str | None, mutation: str = "") -> subprocess.CompletedProcess:
    """Прогон сторожа А0 (или одного его теста) подпроцессом pytest после `mutation`."""
    node = A0 if test_name is None else f"{A0}::{test_name}"
    # `sys.argv` — тот же адресный прогон, что и аргументы `pytest.main`:
    # сторож роли корневого `conftest.py` судит о прогоне по нему.
    args = [node, "-q", "-p", "no:cacheprovider"]
    # Мутация, не применившаяся (нет константы), — код 3, а не «провал
    # сторожа»: иначе её сбой сошёл бы за пойманную мутацию.
    script = ("import sys, pytest\n"
              "from orchestrator import targets\n"
              f"try:\n    exec({mutation!r})\n"
              "except Exception as exc:\n"
              "    print(f'мутация не применилась: {exc!r}')\n"
              "    sys.exit(3)\n"
              f"sys.argv = ['pytest', *{args!r}]\n"
              f"sys.exit(pytest.main({args!r}))\n")
    return subprocess.run([sys.executable, "-c", script], cwd=str(CODE_ROOT),
                          capture_output=True, text=True, timeout=110)


def pair_mutation(forge: str, gate: str, value) -> str:
    """Подмена `unsupported_reason`: для пары (`forge`, `gate`) — `value`."""
    return ("_orig = targets.unsupported_reason\n"
            "def _mut(name):\n"
            "    try:\n"
            "        e = targets.target(name)\n"
            "    except targets.TargetsError:\n"
            "        return _orig(name)\n"
            f"    if (e['forge'], e['merge_gate']) == ({forge!r}, {gate!r}):\n"
            f"        return {value!r}\n"
            "    return _orig(name)\n"
            "targets.unsupported_reason = _mut\n")


GL_TH_REFUSED = pair_mutation("gitlab", "target-human",
                              "гейт мержа target-human не поддержан для хостинга gitlab")
GH_OP_REFUSED = pair_mutation("github", "operator",
                              "гейт мержа operator не поддержан для хостинга github")
GH_TH_OPEN = pair_mutation("github", "target-human", None)
GL_OP_OPEN = pair_mutation("gitlab", "operator", None)
SWAPPED = (pair_mutation("gitlab", "operator", REASON_CONSTANTS["TARGET_HUMAN_REASON"])
           .replace("_orig", "_orig1").replace("_mut", "_mut1")
           + pair_mutation("github", "target-human", REASON_CONSTANTS["GITLAB_REASON"]))
SUFFIXED = pair_mutation("gitlab", "operator", REASON_CONSTANTS["GITLAB_REASON"] + " (ADR-0029)")


def test_ac5_a0_guard_green():
    """Сторож А0 целиком зелёный на коде ветки.

    Сценарий: подпроцесс pytest прогоняет файл сторожа без мутаций — код
    выхода 0.

    Ловит мутацию: константы причин сторожа обновлены, а
    `targets.unsupported_reason` по-прежнему отдаёт старые тексты — ac2–ac7
    сторожа покраснеют.
    """
    proc = run_a0(None)
    assert proc.returncode == 0, proc.stdout[-4000:] + proc.stderr[-2000:]


@pytest.mark.parametrize("test_name,mutation", [
    # (а) точное равенство констант поддержки, а не членство
    (AC1, "targets.SUPPORTED_FORGES = tuple(targets.SUPPORTED_FORGES) + ('bitbucket',)"),
    (AC1, "targets.SUPPORTED_MERGE_GATES = tuple(targets.SUPPORTED_MERGE_GATES) + ('nobody',)"),
    (AC1, "targets.SUPPORTED_PAIRS = set(targets.SUPPORTED_PAIRS) | {('github', 'nobody')}"),
    # (б) ac7 видит обе неподдержанные пары
    (AC7, GH_TH_OPEN),
    (AC7, GL_OP_OPEN),
    # (в) ac1, ac7, ac8 — на обеих поддержанных парах
    (AC1, GL_TH_REFUSED),
    (AC7, GL_TH_REFUSED),
    (AC8, GL_TH_REFUSED),
    (AC1, GH_OP_REFUSED),
    (AC7, GH_OP_REFUSED),
    (AC8, GH_OP_REFUSED),
    # (г) тексты двух пар различимы и сверяются точным равенством
    (AC1, SWAPPED),
    (AC1, SUFFIXED),
], ids=["a-forges-extra", "a-gates-extra", "a-pairs-extra",
        "b-ac7-github-target-human-open", "b-ac7-gitlab-operator-open",
        "c-ac1-gitlab-target-human", "c-ac7-gitlab-target-human", "c-ac8-gitlab-target-human",
        "c-ac1-github-operator", "c-ac7-github-operator", "c-ac8-github-operator",
        "d-ac1-swapped", "d-ac1-suffixed"])
def test_ac5_a0_guard_catches_mutation(test_name, mutation):
    """Тест сторожа А0 краснеет на мутации, которую обязан ловить по условиям (а)–(г).

    Сценарий: подпроцесс pytest портит `orchestrator.targets` (лишний
    элемент в константе поддержки; отказ поддержанной паре; открытие
    неподдержанной; перепутанные или удлинённые тексты причин) и гоняет
    названный тест сторожа — код выхода pytest 1 (есть провалы).

    Ловит мутацию: ac1 проверяет константы членством (`"gitlab" in
    SUPPORTED_FORGES`), не дополнен парой `gitlab` + `target-human`,
    сверяет причину вхождением, а не равенством; ac7/ac8 не дополнены
    поддержанной парой `gitlab` + `target-human` — испорченный код пройдёт
    сторож молча.
    """
    proc = run_a0(test_name, mutation)
    assert proc.returncode == 1, (f"код {proc.returncode}\n{mutation}\n"
                                  + proc.stdout[-3000:] + proc.stderr[-2000:])


# --- AC-6 ---

ACTIONS = {
    "отзыв токена": [r"отозв|отзыв", r"токен"],
    "срез журнала задачи": [r"срез", r"журнал"],
    "ссылка на MR": [r"\bMR\b", r"ссылк"],
    "остановка задач проекта": [r"останов", r"задач"],
}
PROJECT_DATA = [
    r"https?://",
    r"\bglpat-[A-Za-z0-9_-]+",
    r"\bgh[pousr]_[A-Za-z0-9]+",
    r"\bgithub_pat_",
    r"\b[a-z0-9][a-z0-9_-]*-token\b",
]


def test_ac6_incident_doc_four_actions_no_project_data():
    """Документ порядка при инциденте называет четыре действия и не несёт данных проектов.

    Сценарий: `docs/incident-external-project.md` в рабочей копии ветки
    существует; для каждого действия (отзыв токена, срез журнала задачи,
    ссылка на MR, остановка задач проекта) в нём есть оба опорных слова; в
    тексте нет адресов (`http(s)://`), токенов вида GitLab/GitHub и имён
    слотов токена вида `<имя>-token`.

    Ловит мутацию: документ не создан; пропущено одно из действий
    (например, остановка задач проекта); в пример вставлен адрес
    репозитория или слот реального проекта.
    """
    path = Path(CODE_ROOT) / DOC
    assert path.is_file(), f"{DOC} нет"
    text = path.read_text(encoding="utf-8")
    missing = [action for action, words in ACTIONS.items()
               if not all(re.search(w, text, re.IGNORECASE) for w in words)]
    assert missing == [], f"не описано: {missing}"
    found = [m.group(0) for p in PROJECT_DATA for m in re.finditer(p, text)]
    assert found == [], f"данные конкретных проектов: {found}"


# --- AC-7 ---

def test_ac7_existing_tests_outside_a0_unchanged():
    """Из существовавших на базе файлов `tests/` задача меняет только сторож А0.

    Сценарий: каждый путь `changed_paths()` под `tests/`, существующий на
    базе ветки, — файл сторожа А0; новые файлы задачи допустимы.

    Ловит мутацию: разработчик поправил тест, подменяющий
    `SUPPORTED_MERGE_GATES` (например,
    `tests/test_awaiting_human_units.py`), под новую проверку пар вместо
    сохранения прежнего поведения.
    """
    touched = [p for p in changed_paths()
               if p.startswith("tests/") and p != A0 and exists_at_base(p)]
    assert touched == []
