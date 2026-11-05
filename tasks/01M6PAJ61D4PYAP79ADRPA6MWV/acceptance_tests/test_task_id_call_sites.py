"""Места гейтов и команд доводят id задачи до прогона `compose`: вызовы в коде задачи.

Группа: разовый

Факт этой задачи (SPEC, требование 3, решения четвёртого–седьмого кругов;
AC-9): в названных модулях вызовы мест прогона несут id задачи — гейт
исходов (`outcome_integrity`: оба вызова `acceptance.report_run` и оба
вызова `_rerun`, сам `_rerun` — с параметром `task_id`), двусторонний
прогон (`two_sided`: вызов `acceptance.report_run`), повтор файла с зерном
(`advance_gates/acceptance.py::_seed_repeats_escalate` → `run_repeat`),
фоновый `suite-run` (`suite_run.py`: оба вызова `run_full_suite`) и
`plank-run` (`plank_run.py`: вызов долгоживущего файла — с
`compose_task_id` и без `task_id`, вызов планки — с `task_id` и без
`compose_task_id`). Поведение самих мест с подменённым `docker` держат
долгоживущие файлы задачи; здесь — что вызывающие места гейтов и команд,
которых те не исполняют, передают id. Исходный текст — файлы рабочей копии
кода (`CODE_ROOT` помощника пульта), разбор — `ast`.

Красен до реализации: вызовы `report_run`/`run_repeat`/`run_full_suite`/`run_plank` и `_rerun` в названных модулях ещё не несут `task_id`/`compose_task_id`.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT  # noqa: E402


def module(rel: str) -> ast.Module:
    return ast.parse((Path(CODE_ROOT) / rel).read_text(encoding="utf-8"))


def calls(tree: ast.AST, attr: str) -> list:
    """Вызовы `<что-то>.<attr>(…)` и `<attr>(…)` в узле."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else \
            func.id if isinstance(func, ast.Name) else ""
        if name == attr:
            found.append(node)
    return found


def keyword(call: ast.Call, name: str):
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def is_name(node, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"функции {name} нет")


def test_ac9_outcome_integrity_passes_task_id():
    """Гейт исходов: оба вызова `acceptance.report_run` и оба вызова `_rerun` несут `task_id`; `_rerun` принимает `task_id`.

    Ловит мутацию: перепрогон стороны (`_rerun`) или прогон прежних
    версий зовёт `report_run` без id — у компонента `compose` отказ «нет id
    задачи» вместо прогона.
    """
    tree = module("orchestrator/advance_gates/outcome_integrity.py")
    runs = calls(tree, "report_run")
    assert len(runs) >= 2, f"вызовов report_run: {len(runs)}"
    for call in runs:
        assert keyword(call, "task_id") is not None, \
            f"строка {call.lineno}: report_run без task_id"
    rerun = function(tree, "_rerun")
    params = [a.arg for a in rerun.args.args + rerun.args.kwonlyargs]
    assert "task_id" in params, f"_rerun: параметры {params}"
    reruns = calls(tree, "_rerun")
    assert len(reruns) >= 2, f"вызовов _rerun: {len(reruns)}"
    for call in reruns:
        assert keyword(call, "task_id") is not None, \
            f"строка {call.lineno}: _rerun без task_id"


def test_ac9_two_sided_passes_task_id():
    """Двусторонний прогон: вызов `acceptance.report_run` стороны несёт `task_id`.

    Ловит мутацию: сторона двустороннего прогона зовёт `report_run` без id
    — у профиля `compose` обе стороны отказаны.
    """
    tree = module("orchestrator/advance_gates/two_sided.py")
    runs = calls(tree, "report_run")
    assert runs, "вызова report_run нет"
    for call in runs:
        assert keyword(call, "task_id") is not None, \
            f"строка {call.lineno}: report_run без task_id"


def test_ac9_seed_repeats_pass_task_id():
    """Повтор файла с зерном: `run_repeat` в `_seed_repeats_escalate` получает `task_id=task_id`.

    Ловит мутацию: повтор долгоживущих файлов с зерном зовёт `run_repeat`
    без id — у `compose` каждый повтор красный отказом, задача уходит в
    эскалацию «зависит от зерна».
    """
    tree = function(module("orchestrator/advance_gates/acceptance.py"),
                    "_seed_repeats_escalate")
    repeats = calls(tree, "run_repeat")
    assert repeats, "вызова run_repeat нет"
    for call in repeats:
        assert is_name(keyword(call, "task_id"), "task_id"), \
            f"строка {call.lineno}: run_repeat без task_id=task_id"


def test_ac9_suite_run_passes_task_id():
    """Фоновый `suite-run`: оба вызова `acceptance.run_full_suite` получают `task_id=task_id`.

    Ловит мутацию: прогон базы или головы `suite-run` зовёт
    `run_full_suite` без id — у `compose` «прогон не начат».
    """
    tree = module("orchestrator/suite_run.py")
    runs = calls(tree, "run_full_suite")
    assert len(runs) >= 2, f"вызовов run_full_suite: {len(runs)}"
    for call in runs:
        assert is_name(keyword(call, "task_id"), "task_id"), \
            f"строка {call.lineno}: run_full_suite без task_id=task_id"


def test_ac9_plank_run_passes_compose_task_id_to_long_lived_call():
    """`plank-run`: вызов долгоживущего файла с профилем — `compose_task_id=task_id` без `task_id`; вызов планки с профилем — `task_id` без `compose_task_id`.

    Ловит мутацию: долгоживущему файлу передан `task_id` (включает
    раскладку планки — прогон ищет каталог планки) или id не передан вовсе
    (отказ «нет id задачи»); планке передан `compose_task_id` вместо
    `task_id`.
    """
    tree = module("orchestrator/plank_run.py")
    runs = [c for c in calls(tree, "run_plank")
            if keyword(c, "profile") is not None]
    long_lived = [c for c in runs if keyword(c, "compose_task_id") is not None]
    plank = [c for c in runs if keyword(c, "task_id") is not None]
    assert long_lived, "вызова run_plank с compose_task_id нет"
    for call in long_lived:
        assert is_name(keyword(call, "compose_task_id"), "task_id"), \
            f"строка {call.lineno}"
        assert keyword(call, "task_id") is None, f"строка {call.lineno}"
    assert plank, "вызова run_plank планки с task_id нет"
    for call in plank:
        assert keyword(call, "compose_task_id") is None, f"строка {call.lineno}"
