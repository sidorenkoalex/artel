"""Факты ветки задачи: удаление тринадцати определений против базы сравнения.

Группа: разовый
Красен до реализации: определения таблицы ещё на месте (AC-9 видит их на ветке), комментарии называют `is_clean`/`external_code_sha` (AC-4), над `VERDICT_RETURN` прежний комментарий (AC-5), карта перечисляет удалённые функции (AC-8); AC-3, AC-6, AC-7 держат неизменность и зелены и до кода.

AC-1 и AC-2 держит долгоживущий файл задачи
`tests/test_01m5mhvakhr82vzrxzr19wj677_dead_definitions.py`.

Сторона «ветка» — файлы рабочей копии кода (`_pult.CODE_ROOT`); сторона
«база» — `git show <DIFF_BASE>:<путь>`: база — точка ответвления ветки,
которую пульт подставляет помощнику планки (`orchestrator/plank_helper.py`),
не литерал `main`.
"""
import ast
import importlib
import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _pult  # noqa: E402

CODE = Path(_pult.CODE_ROOT)
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

# Модуль -> удалённые имена таблицы «Контекст» SPEC.
REMOVED = {
    "orchestrator/advance_gates/spec_audit.py": {"answer_names"},
    "orchestrator/advance_gates/test_integrity.py": {"assertion_observation"},
    "orchestrator/fixation.py": {"external_code_sha"},
    "orchestrator/gitcmd.py": {"is_clean"},
    "orchestrator/merge_after.py": {"has_mandate_line"},
    "orchestrator/pool_seal.py": {"guids_path"},
    "orchestrator/retro.py": {"retro_path", "retro_rel_path"},
    "orchestrator/retro_corpus.py": {"read_cache"},
    "orchestrator/rounds.py": {"task_rounds"},
    "orchestrator/models.py": {"VERDICT_APPROVED"},
    "scripts/core_reference.py": {"SETTING_KEYS", "SHA_HEX"},
}
REMOVED_FUNCTIONS = ("answer_names", "assertion_observation", "external_code_sha",
                     "is_clean", "has_mandate_line", "guids_path", "retro_path",
                     "read_cache", "task_rounds", "retro_rel_path")
FUNCTION_MODULE = {name: path for path, names in REMOVED.items()
                   for name in names if name in REMOVED_FUNCTIONS}


def base_text(rel: str) -> str:
    """Текст `rel` в базе сравнения ветки задачи."""
    res = subprocess.run(["git", "-C", str(CODE), "show", f"{_pult.DIFF_BASE}:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise AssertionError(f"git show {_pult.DIFF_BASE}:{rel}: {res.stderr.strip()}")
    return res.stdout


def branch_text(rel: str) -> str:
    return (CODE / rel).read_text(encoding="utf-8")


def def_name(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    return None


def top_level_names(tree: ast.Module) -> set:
    """Имена определений верхнего уровня: def/async def, классы, цели `=` и
    аннотированных присваиваний (в том числе распакованные кортежи)."""
    names = set()
    for node in tree.body:
        name = def_name(node)
        if name:
            names.add(name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def top_level_deletes(tree: ast.Module) -> list:
    """Строки инструкций `del` вне тел функций и классов."""
    found = []

    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Delete):
                found.append(child.lineno)
            visit(child)
    visit(tree)
    return found


def removed_nodes(tree: ast.Module, names: set) -> list:
    """Узлы верхнего уровня, определяющие удалённые имена модуля."""
    nodes = []
    for node in tree.body:
        name = def_name(node)
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        if name in names:
            nodes.append(node)
    return nodes


def bound_import_names(node) -> list:
    """Имена, которые связывает инструкция импорта."""
    names = []
    for alias in node.names:
        if alias.asname:
            names.append(alias.asname)
        elif isinstance(node, ast.Import):
            names.append(alias.name.split(".")[0])
        else:
            names.append(alias.name)
    return names


def imported_names(tree: ast.AST, skip=()) -> set:
    """Имена, связанные импортами модуля, кроме импортов внутри `skip`."""
    inside = {id(n) for s in skip for n in ast.walk(s)}
    return {name for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom)) and id(node) not in inside
            for name in bound_import_names(node)}


def loads(tree: ast.AST) -> list:
    return [n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)]


def docstring_paragraphs(text: str, func: str) -> list:
    """Абзацы докстринга функции `func` верхнего уровня, пробелы нормализованы."""
    for node in ast.parse(text).body:
        if def_name(node) == func:
            doc = ast.get_docstring(node) or ""
            return [" ".join(p.split()) for p in re.split(r"\n\s*\n", doc) if p.strip()]
    raise AssertionError(f"функции {func} нет на верхнем уровне модуля")


class BranchFactsTest(unittest.TestCase):

    def test_ac3_imports_lose_only_names_of_removed_definitions(self):
        """Импорты каждого изменяемого модуля на ветке — базовые минус имена, нужные только удалённым определениям.

        Для каждого из одиннадцати модулей: в базе берутся имена, связанные
        импортами вне удалённых определений; из них вычитаются имена, чьи
        чтения (`ast.Name`, `ast.Load`) встречаются только внутри удалённых
        определений. Множество имён импортов на ветке обязано совпасть с
        остатком — ни лишнего удаления (например, `config` в
        `orchestrator/fixation.py`, неиспользуемого уже в базе), ни
        оставленного импорта, ставшего ненужным.

        Ловит мутацию: разработчик «заодно» снёс неиспользуемый на базе
        импорт `config` из `fixation.py` — множество на ветке меньше
        ожидаемого; либо, удалив `retro_path`, оставил импорт, нужный
        только ей, — множество больше ожидаемого; тест называет модуль и
        расхождение.
        """
        for rel, names in REMOVED.items():
            with self.subTest(module=rel):
                base = ast.parse(base_text(rel))
                dead = removed_nodes(base, names)
                self.assertEqual(len(dead), len(names),
                                 f"{rel}: в базе нет всех определений {sorted(names)}")
                base_imports = imported_names(base, skip=dead)
                inside = [x for n in dead for x in loads(n)]
                dead_ids = {id(x) for n in dead for x in ast.walk(n)}
                outside = [n.id for n in ast.walk(base)
                           if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
                           and id(n) not in dead_ids]
                only_dead = {name for name in base_imports
                             if name in inside and name not in outside}
                expected = base_imports - only_dead
                actual = imported_names(ast.parse(branch_text(rel)))
                self.assertEqual(
                    actual, expected,
                    f"{rel}: импорты ветки расходятся с базой минус {sorted(only_dead)}; "
                    f"лишние на ветке: {sorted(actual - expected)}, "
                    f"пропали: {sorted(expected - actual)}")

    def test_ac4_comments_drop_removed_names_keep_paragraphs(self):
        """Тексты `gitcmd.py`/`fixation.py` не называют удалённые имена, а три абзаца остаются на месте.

        Сценарий: в `orchestrator/gitcmd.py` нет слова `is_clean`, в
        `orchestrator/fixation.py` — `external_code_sha`. Докстринги
        `commits_behind`, `diff_paths` (`gitcmd.py`) и `default_code_sha`
        (`fixation.py`) сравниваются с базой по абзацам: число абзацев то
        же, все абзацы без удалённого имени совпадают с базой дословно (с
        точностью до переноса строк), а абзац, называвший удалённое имя,
        на той же позиции по-прежнему называет `head_sha` (у `gitcmd.py`)
        или `external_artifact_sha` (у `fixation.py`).

        Ловит мутацию: абзац «вырожденный случай» удалён целиком вместе с
        `is_clean` — число абзацев `commits_behind` меньше базы; ссылка
        заменена, но выпала и `head_sha` — абзац на позиции её не называет;
        `is_clean` оставлен в одном из двух докстрингов — слово найдено.
        """
        cases = (
            ("orchestrator/gitcmd.py", "commits_behind", "is_clean", "head_sha"),
            ("orchestrator/gitcmd.py", "diff_paths", "is_clean", "head_sha"),
            ("orchestrator/fixation.py", "default_code_sha", "external_code_sha",
             "external_artifact_sha"),
        )
        for rel, removed in (("orchestrator/gitcmd.py", "is_clean"),
                             ("orchestrator/fixation.py", "external_code_sha")):
            with self.subTest(file=rel, word=removed):
                self.assertNotIn(removed, branch_text(rel),
                                 f"{rel} всё ещё содержит {removed}")
        for rel, func, removed, kept in cases:
            with self.subTest(function=func):
                before = docstring_paragraphs(base_text(rel), func)
                after = docstring_paragraphs(branch_text(rel), func)
                self.assertEqual(len(after), len(before),
                                 f"{rel}::{func}: число абзацев докстринга изменилось")
                hits = [i for i, p in enumerate(before) if removed in p]
                self.assertEqual(len(hits), 1,
                                 f"{rel}::{func}: в базе нет абзаца с {removed}")
                for i, (old, new) in enumerate(zip(before, after)):
                    if i in hits:
                        self.assertIn(kept, new,
                                      f"{rel}::{func}: абзац {i + 1} не называет {kept}")
                        self.assertNotIn(removed, new)
                    else:
                        self.assertEqual(new, old,
                                         f"{rel}::{func}: абзац {i + 1} изменён")

    def test_ac5_verdict_comment_names_both_verdicts_and_single_constant(self):
        """Комментарий над `VERDICT_RETURN` говорит о двух вердиктах и одной константе, константа цела.

        Сценарий: блок строк-комментариев непосредственно над
        `VERDICT_RETURN = ...` в `orchestrator/models.py` упоминает
        `pair_verdicts`, вердикты `return` и `approved`, константу и её
        читателя — сверку пары; сам модуль по-прежнему даёт
        `VERDICT_RETURN == "return"`.

        Ловит мутацию: комментарий оставлен прежним («Вердикты ревью в
        `pair_verdicts`.») — нет `approved`/константы/сверки; либо вместе с
        `VERDICT_APPROVED` по ошибке удалена `VERDICT_RETURN` — импорт
        атрибута падает.
        """
        lines = branch_text("orchestrator/models.py").splitlines()
        idx = next((i for i, line in enumerate(lines)
                    if re.match(r"VERDICT_RETURN\s*=", line)), None)
        self.assertIsNotNone(idx, "в orchestrator/models.py нет VERDICT_RETURN")
        block = []
        j = idx - 1
        while j >= 0 and lines[j].lstrip().startswith("#"):
            block.insert(0, lines[j])
            j -= 1
        comment = " ".join(block)
        for needle in ("pair_verdicts", "return", "approved", "констант", "свер"):
            with self.subTest(needle=needle):
                self.assertIn(needle, comment,
                              f"комментарий над VERDICT_RETURN не содержит {needle!r}: {comment!r}")
        self.assertRegex(comment, r"свер\w*\s+пар",
                         f"комментарий не называет сверку пары: {comment!r}")
        models = importlib.import_module("orchestrator.models")
        self.assertEqual(models.VERDICT_RETURN, "return")

    def test_ac6_retro_dir_and_answer_mandate_helper_stay(self):
        """`RETRO_DIR_REL` в `retro.py` хранит базовое значение, `_has_mandate_lines` остаётся в `answer.py`.

        Значение `RETRO_DIR_REL` берётся из базы разбором AST и сравнивается
        с атрибутом импортированного модуля ветки; определение
        `_has_mandate_lines` ищется на верхнем уровне `orchestrator/answer.py`
        ветки.

        Ловит мутацию: вместе с `retro_rel_path` удалена или переписана
        константа `RETRO_DIR_REL` — значение расходится с базой или атрибута
        нет; удалена «похожая» `_has_mandate_lines` вместо
        `has_mandate_line` — определения нет.
        """
        base_value = None
        for node in ast.parse(base_text("orchestrator/retro.py")).body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "RETRO_DIR_REL" for t in node.targets):
                base_value = ast.literal_eval(node.value)
        self.assertIsNotNone(base_value, "в базе нет RETRO_DIR_REL")
        retro = importlib.import_module("orchestrator.retro")
        self.assertEqual(getattr(retro, "RETRO_DIR_REL", None), base_value)
        answer_defs = {def_name(n) for n in ast.parse(branch_text("orchestrator/answer.py")).body}
        self.assertIn("_has_mandate_lines", answer_defs,
                      "orchestrator/answer.py потерял _has_mandate_lines")

    def test_ac7_tests_dir_only_gains_files(self):
        """Против базы сравнения в `tests/` нет ни изменённых, ни удалённых файлов — только добавленные.

        Сценарий: `git diff --no-renames --name-status <база> -- tests/`
        по рабочей копии (закоммиченные и незакоммиченные правки); любая
        строка со статусом не `A` — нарушение.

        Ловит мутацию: правка существующего `tests/test_repo_context.py`
        (убрали упоминание `is_clean` в докстринге) или переименование
        чужого теста — строка `M`/`D` в выводе, тест называет файл.
        """
        res = subprocess.run(["git", "-C", str(CODE), "diff", "--no-renames",
                              "--name-status", _pult.DIFF_BASE, "--", "tests/"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, res.stderr)
        touched = [line for line in res.stdout.splitlines()
                   if line.strip() and not line.startswith("A\t")]
        self.assertEqual(touched, [], "ветка меняет или удаляет файлы tests/ базы")

    def test_ac8_codebase_map_fresh_and_without_removed_functions(self):
        """Перегенерированная карта совпадает с картой ветки без `built_at_sha` и не перечисляет удалённые функции.

        Сценарий: функции `build_modules`/`render` сценария
        `scripts/codebase_map.py` ветки строят текст карты по рабочей копии
        (то, что записал бы запуск сценария), не трогая файл; текст
        сравнивается с `docs/codebase-map.md` ветки без строк
        `built_at_sha:` — как сверка CI. Затем в разделе `## <модуль>`
        карты каждой из десяти функций нет строки «- `имя`» среди
        публичных функций.

        Ловит мутацию: определения удалены, а карта не перегенерирована —
        текст расходится с перегенерированным, и в разделе
        `orchestrator/gitcmd.py` по-прежнему стоит `- `is_clean``.
        """
        spec = importlib.util.spec_from_file_location(
            "codebase_map_branch", CODE / "scripts" / "codebase_map.py")
        codebase_map = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(codebase_map)
        modules, resolved, imported_by = codebase_map.build_modules(CODE)
        fresh = codebase_map.render(modules, resolved, imported_by, "0" * 40)
        committed = branch_text("docs/codebase-map.md")

        def strip(text):
            return [line for line in text.splitlines() if not line.startswith("built_at_sha:")]
        self.assertTrue(strip(fresh) == strip(committed),
                        "docs/codebase-map.md расходится с перегенерированной картой "
                        "(без built_at_sha) — запусти python3 scripts/codebase_map.py")
        sections = re.split(r"^## ", committed, flags=re.M)
        by_module = {s.split("\n", 1)[0].strip(): s for s in sections[1:]}
        for name in REMOVED_FUNCTIONS:
            rel = FUNCTION_MODULE[name]
            with self.subTest(function=name):
                self.assertIn(rel, by_module, f"в карте нет раздела {rel}")
                self.assertNotIn(f"- `{name}`", by_module[rel],
                                 f"карта перечисляет {name} среди функций {rel}")

    def test_ac9_top_level_definitions_shrink_by_removed_names_only(self):
        """Определения верхнего уровня каждого модуля на ветке — базовые минус удалённые, без `del`.

        Для каждого из одиннадцати модулей разбор AST базы и ветки: множество
        имён верхнего уровня (def/async def, классы, цели `=` и
        аннотированных присваиваний) на ветке равно базовому минус имена
        таблицы этого модуля; инструкций `del` вне тел функций и классов на
        ветке нет.

        Ловит мутацию: удалённое определение переименовано в закрытое
        `_is_clean` — на ветке лишнее имя; определение оставлено с
        `del is_clean` следом — найден `del`; заодно удалена соседняя
        функция — имени не хватает.
        """
        for rel, names in REMOVED.items():
            with self.subTest(module=rel):
                base = top_level_names(ast.parse(base_text(rel)))
                self.assertTrue(names <= base, f"{rel}: в базе нет {sorted(names - base)}")
                branch_tree = ast.parse(branch_text(rel))
                actual = top_level_names(branch_tree)
                expected = base - names
                self.assertEqual(actual, expected,
                                 f"{rel}: лишние на ветке {sorted(actual - expected)}, "
                                 f"пропали {sorted(expected - actual)}")
                self.assertEqual(top_level_deletes(branch_tree), [],
                                 f"{rel}: на верхнем уровне есть del")


if __name__ == "__main__":
    unittest.main()
