"""AC-10: в функциях таблицы требования 1 нет прямого сравнения с
`config.DEFAULT_TARGET`, оставленные места спрашивают одну функцию признака.

Группа: разовый
Красен до реализации: сегодня `repo_context.resolve`, `_gh_repo_kwargs`, `_repo_kwargs`, `_main_copy_reader`, `observed_max_task_number`, `_tasks_dir`, `_fix_unsent_closed_ref` и функции «удалить» сами сравнивают проект с `config.DEFAULT_TARGET`, функции признака они не зовут.

Перечень функций — таблица требования 1 SPEC этой задачи по пину 6eb98eff
(модуль и имя функции), поэтому файл разовый: после мержа таблица теряет
предмет, свойство дальше держит сторож требования 4 и сами тесты модулей.
Исходники читаются разбором (`ast`) из пакета `orchestrator` рабочей копии,
импортом пакета не исполняются.

«Прямое сравнение» — узел сравнения `==`/`!=`, у которого операнд — сама
ссылка на `DEFAULT_TARGET` (`config.DEFAULT_TARGET`, голое имя) либо вызов с
такой ссылкой аргументом (`workspace.repo(config.DEFAULT_TARGET)` — тот же
вопрос «это артель?», заданный путём клона). Значение по умолчанию
`t["target"] or config.DEFAULT_TARGET` в операнде сравнением с проектом
артели не считается: его SPEC выносит в «Не входит».

Поведение оставленных мест для артели и внешнего проекта держат
существующие тесты их модулей (`tests/`), их прогон — дело пульта; здесь
точечно проверяется только публичный `repo_context.resolve` — опора
оставленного решения п.16.
"""
import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import orchestrator
from orchestrator import config, repo_context

PKG = Path(orchestrator.__file__).resolve().parent

# Решение «удалить» таблицы требования 1: модуль -> функции.
REMOVE = {
    "zone_lock.py": ("forecast_overlaps", "blocking_conflict", "queue_position"),
    "catalog.py": ("_warn_zone_overlap", "_zone_forecast_suffix",
                   "_wave_breaker_suffix", "_artifact_frontmatter"),
    "alerts.py": ("_wave_breaker_task_count", "_raise_wave_breaker_alert"),
    "runner.py": ("wave_breaker_alerts_open", "_refuse_before_start"),
    "fsm.py": ("_dirty_refuses", "_tests_writing_ac_state",
               "_origin_main_source", "_snapshot_split_assessment"),
    "store.py": ("_append_passport_line", "record_fixation"),
    "docs_fetch.py": ("_fetch_all",),
    "advance_gates/review.py": ("_review_rework_gate",),
    "doctor/branch_freshness.py": ("check_branch_freshness",),
}

# Решение «оставить»: модуль -> функции.
KEEP = {
    "repo_context.py": ("resolve",),
    "github_adapter.py": ("_gh_repo_kwargs",),
    "ci.py": ("_repo_kwargs",),
    "docs_fetch.py": ("_main_copy_reader",),
    "coldstart.py": ("observed_max_task_number", "_tasks_dir"),
    "doctor/artifact_branches.py": ("_fix_unsent_closed_ref",),
}


def _is_default_target(node: ast.AST) -> bool:
    return ((isinstance(node, ast.Attribute) and node.attr == "DEFAULT_TARGET")
            or (isinstance(node, ast.Name) and node.id == "DEFAULT_TARGET"))


def _direct_operand(node: ast.AST) -> bool:
    if _is_default_target(node):
        return True
    return isinstance(node, ast.Call) and any(
        _is_default_target(a) for a in list(node.args)
        + [k.value for k in node.keywords])


def direct_comparisons(fn: ast.AST) -> list[int]:
    """Строки прямых сравнений `==`/`!=` с `DEFAULT_TARGET` внутри `fn`."""
    lines = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            continue
        if any(_direct_operand(o) for o in [node.left, *node.comparators]):
            lines.append(node.lineno)
    return lines


def functions_of(rel: str) -> dict[str, ast.AST]:
    """Функции модуля по имени: верхнего уровня и методы классов."""
    tree = ast.parse((PKG / rel).read_text(encoding="utf-8"))
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.setdefault(node.name, node)
    return found


def called_names(fn: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def predicate_functions() -> set[str]:
    """Имена функций пакета вне таблицы, которые сами сравнивают проект с
    `DEFAULT_TARGET`, — кандидаты в функцию признака."""
    table = {name for names in list(REMOVE.values()) + list(KEEP.values())
             for name in names}
    found = set()
    for path in PKG.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name not in table and direct_comparisons(node)):
                found.add(node.name)
    return found


class TableFunctionsTest(unittest.TestCase):

    def test_ac10_removed_forks_have_no_direct_comparison(self):
        """Функции с решением «удалить» не сравнивают проект с артелью.

        Для каждой функции таблицы с решением «удалить», которая ещё есть в
        своём модуле, разбор исходника не находит ни одного `==`/`!=` с
        `config.DEFAULT_TARGET`. Функция, сведённая к другой (дубль
        `_origin_main_source`), может исчезнуть — её отсутствие не провал.

        Ловит мутацию: в `zone_lock.blocking_conflict` оставили
        `row["target"] != config.DEFAULT_TARGET` при отборе кандидатов —
        тест называет модуль, функцию и строку этого сравнения.
        """
        hits = []
        for rel, names in REMOVE.items():
            funcs = functions_of(rel)
            for name in names:
                if name in funcs:
                    hits += [f"orchestrator/{rel}:{line} {name}"
                             for line in direct_comparisons(funcs[name])]
        self.assertEqual(hits, [], "прямое сравнение с config.DEFAULT_TARGET "
                                   "в функциях «удалить»: " + "; ".join(hits))

    def test_ac10_kept_places_ask_one_predicate(self):
        """Оставленные места не сравнивают сами, а зовут одну функцию признака.

        Каждая из семи функций «оставить» есть в своём модуле, в ней нет
        прямого `==`/`!=` с `config.DEFAULT_TARGET`, и она вызывает функцию
        признака — функцию пакета, которая единственная сама держит
        сравнение с `config.DEFAULT_TARGET`. Хотя бы одна такая функция общая
        для всех семи мест: признак артели проверяет одна функция.

        Ловит мутацию: `ci._repo_kwargs` оставили сравнением
        `repo == workspace.repo(config.DEFAULT_TARGET)` либо
        `coldstart._tasks_dir` спрашивает свою локальную копию признака —
        у места нет вызова общей функции признака, тест называет его.
        """
        predicates = predicate_functions()
        problems = []
        common = None
        for rel, names in KEEP.items():
            funcs = functions_of(rel)
            for name in names:
                where = f"orchestrator/{rel}::{name}"
                if name not in funcs:
                    problems.append(f"{where}: функции нет")
                    continue
                problems += [f"{where}:{line}: прямое сравнение"
                             for line in direct_comparisons(funcs[name])]
                asked = called_names(funcs[name]) & predicates
                if not asked:
                    problems.append(f"{where}: не зовёт функцию признака "
                                    f"(кандидаты: {sorted(predicates)})")
                common = asked if common is None else common & asked
        self.assertEqual(problems, [], "; ".join(problems))
        self.assertTrue(common, "оставленные места зовут разные функции "
                                "признака — нет одной общей")

    def test_ac10_resolve_keeps_artel_and_external_behaviour(self):
        """`repo_context.resolve` для артели и внешнего проекта — прежний.

        Сценарий: `targets.yaml` песочницы несёт только запись внешнего
        проекта `ext` (адрес `file:///srv/ext.git`, база `trunk`). Артель
        разрешается без чтения записи: удалённый источник — `origin`, база —
        `config.MAIN_BRANCH`; внешний проект — адрес и база из его записи;
        неизвестное имя — `None`.

        Ловит мутацию: признак в `resolve` спрашивает не имя проекта, а
        что-то иное (контекст, ещё не построенный) и всегда ложен — артель
        уходит в чтение `targets.yaml`, записи `artel` там нет, `resolve`
        возвращает `None` вместо контекста с `origin`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "targets.yaml"
            path.write_text(
                "targets:\n"
                "  ext:\n"
                "    forge: github\n"
                "    url: file:///srv/ext.git\n"
                "    base: trunk\n"
                "    token_slot: ext-token\n"
                "    no_paths: []\n"
                "    project_skills: []\n"
                "    merge_gate: operator\n", encoding="utf-8")
            with mock.patch.object(config, "TARGETS", path):
                artel = repo_context.resolve(config.DEFAULT_TARGET)
                ext = repo_context.resolve("ext")
                missing = repo_context.resolve("nope")
        self.assertIsNotNone(artel)
        self.assertEqual((artel.remote, artel.base),
                         ("origin", config.MAIN_BRANCH))
        self.assertIsNotNone(ext)
        self.assertEqual((ext.remote, ext.base), ("file:///srv/ext.git", "trunk"))
        self.assertIsNone(missing)


if __name__ == "__main__":
    unittest.main()
