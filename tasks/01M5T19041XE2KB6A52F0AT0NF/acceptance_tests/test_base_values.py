"""Значения и формула, которые задача обязана сохранить или задать относительно базы ветки: константа маркеров обвязки, перечень пульта, прежняя константа `doctor`, результат формулы на перечне артели, минимум git.

Группа: разовый
Красен до реализации: `config.AGENT_WRAPPER_MARKERS` ещё нет (AC-1 падает на атрибуте), `TARGET_WRAPPER_MARKERS` в `orchestrator/doctor/preflight.py` задан литералом кортежа (AC-2), минимум git в `stack.REQUIRED_TOOLS` — `(2, 30, 0)` (AC-24); AC-4 и AC-5 держат прежний результат формулы на перечне артели и зелены с рождения.

Эталон «как на main» — текст `orchestrator/config.py` базы диффа задачи
(`DIFF_BASE` помощника пульта `_pult.py`), прочитанный `git show` в
рабочей копии (`CODE_ROOT`): из него разбором `ast` берутся `PROTECTED_PATHS`,
`PROTECTED_PATH_ANY_DIR_MASK` и функция `is_protected_path` базы — формула
main исполняется в отдельном пространстве имён, без импорта модуля базы.

Провалидировано временным стабом реализации (удалён, не закоммичен):
константа маркеров, вывод прежней константы из неё, формула `**/<каталог>/`,
минимум git 2.35 — все методы зелёные.
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

from orchestrator import config, stack  # noqa: E402
from orchestrator.doctor import preflight  # noqa: E402
from scripts import ci_protected_paths, guard  # noqa: E402

MARKERS = ("**/.claude/", ".mcp.json", "**/CLAUDE.md", "**/AGENTS.md")

# Фиксированный набор путей AC-4: корневые и вложенные, с компонентами
# `.claude`, `conftest.py`, `CLAUDE.md`, `skills`, `templates`.
PATHS = (
    ".claude", ".claude/x.md", ".claude/rules/x.md", "a/.claude",
    "a/.claude/x.md", "frontend/.claude/rules/x.md", "x.claude/y.md",
    "conftest.py", "tests/conftest.py", "a/b/conftest.py", "conftest.py/x",
    "xconftest.py",
    "CLAUDE.md", "sub/CLAUDE.md", "CLAUDE.md/x", "CLAUDE.mdx", "AGENTS.md",
    "sub/AGENTS.md",
    "skills", "skills/x.md", "a/skills/x.md", "skillsx/y.md",
    "templates", "templates/SPEC.md", "a/templates/x.md", "templatesx",
    "docs/adr/0001.md", "knowledge/x.yaml", ".github/workflows/ci.yml",
)


def base_source(rel: str) -> str:
    """Текст файла `rel` в базе диффа задачи."""
    res = subprocess.run(["git", "-C", CODE_ROOT, "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    if res.returncode != 0:
        raise RuntimeError(f"git show {DIFF_BASE}:{rel}: {res.stderr}")
    return res.stdout


@pytest.fixture(scope="module")
def main_formula():
    """(перечень пульта базы, функция `is_protected_path` базы)."""
    tree = ast.parse(base_source("orchestrator/config.py"))
    wanted = {"PROTECTED_PATHS", "PROTECTED_PATH_ANY_DIR_MASK"}
    nodes = [n for n in tree.body
             if (isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id in wanted
                         for t in n.targets))
             or (isinstance(n, ast.FunctionDef) and n.name == "is_protected_path")]
    namespace: dict = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]),
                 "<config базы>", "exec"), namespace)
    return namespace["PROTECTED_PATHS"], namespace["is_protected_path"]


def plan_with_appendices(paths) -> str:
    sections = "".join(
        f"\n## Приложение {n}: правка\n\n```diff\n"
        f"diff --git a/{p} b/{p}\nnew file mode 100644\n--- /dev/null\n"
        f"+++ b/{p}\n@@ -0,0 +1 @@\n+строка\n```\n"
        for n, p in enumerate(paths, 1))
    return ("---\ntask: T1\ntype: plan\nauthor_role: developer\nstatus: ready\n"
            "schema_version: 5\n---\n\n# PLAN\n\n## Подход\nФикстура.\n"
            + sections)


def test_ac1_markers_constant_and_protected_paths_unchanged(main_formula):
    """Константа маркеров обвязки — ровно четыре записи в заданном порядке, перечень пульта — прежний.

    Сценарий: `config.AGENT_WRAPPER_MARKERS` сравнивается с кортежем
    критерия; ни одна его запись не входит в `config.PROTECTED_PATHS`;
    `config.PROTECTED_PATHS` равен значению базы ветки (19 записей в
    прежнем порядке).

    Ловит мутацию: маркеры записаны в другом порядке или без `**/` у
    `.claude/`; маркеры дописаны в `config.PROTECTED_PATHS` (перечень
    пульта вырос, запись маркера в нём есть).
    """
    base_paths, _fn = main_formula
    assert config.AGENT_WRAPPER_MARKERS == MARKERS
    assert [m for m in config.AGENT_WRAPPER_MARKERS
            if m in config.PROTECTED_PATHS] == []
    assert tuple(config.PROTECTED_PATHS) == tuple(base_paths)
    assert len(config.PROTECTED_PATHS) == 19


def test_ac2_doctor_markers_derived_from_common_constant():
    """`TARGET_WRAPPER_MARKERS` прежнего значения выводится из `config.AGENT_WRAPPER_MARKERS`, а не литералом.

    Сценарий: значение константы модуля `preflight` — прежний кортеж;
    присваивание в исходном тексте модуля — не литерал кортежа строк;
    отдельный интерпретатор подменяет `config.AGENT_WRAPPER_MARKERS`
    кортежем `("**/.zzwrap/", "x.json", "**/Q.md")` ДО импорта
    `orchestrator.doctor.preflight` — константа модуля становится
    `(".zzwrap", "x.json", "Q.md")`.

    Ловит мутацию: константа оставлена литералом
    `(".claude", ".mcp.json", "CLAUDE.md", "AGENTS.md")` — разбор находит
    кортеж строк, подмена единой константы её не меняет; вывод не снимает
    завершающий `/` — значение `(".claude/", …)`.
    """
    assert preflight.TARGET_WRAPPER_MARKERS == (
        ".claude", ".mcp.json", "CLAUDE.md", "AGENTS.md")
    source = (Path(CODE_ROOT) / "orchestrator" / "doctor" / "preflight.py"
              ).read_text(encoding="utf-8")
    assigns = [n for n in ast.walk(ast.parse(source))
               if isinstance(n, (ast.Assign, ast.AnnAssign))
               and any(isinstance(t, ast.Name) and t.id == "TARGET_WRAPPER_MARKERS"
                       for t in (n.targets if isinstance(n, ast.Assign)
                                 else [n.target]))]
    assert assigns, "присваивания TARGET_WRAPPER_MARKERS в preflight.py нет"
    for node in assigns:
        value = node.value
        literal = (isinstance(value, ast.Tuple) and all(
            isinstance(e, ast.Constant) and isinstance(e.value, str)
            for e in value.elts))
        assert not literal, f"литерал кортежа строк: {ast.unparse(node)}"
    code = ("from orchestrator import config\n"
            "config.AGENT_WRAPPER_MARKERS = ('**/.zzwrap/', 'x.json', '**/Q.md')\n"
            "from orchestrator.doctor import preflight\n"
            "print(repr(tuple(preflight.TARGET_WRAPPER_MARKERS)))\n")
    res = subprocess.run([sys.executable, "-c", code], cwd=CODE_ROOT,
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip().splitlines()[-1] == repr((".zzwrap", "x.json", "Q.md"))


def test_ac4_protected_paths_entries_match_main_formula(main_formula):
    """Каждая запись перечня пульта, взятая перечнем из одной записи, и перечень целиком дают на наборе путей результат формулы main.

    Сценарий: для каждой записи `config.PROTECTED_PATHS` и каждого пути
    набора `config.is_protected_path(путь, (запись,))` равен результату
    функции базы; `config.is_protected_path(путь)` без перечня — результату
    функции базы на её перечне.

    Ловит мутацию: формула `**/<имя>` начала сверять маску по любому
    компоненту пути — `**/conftest.py` покрыл `conftest.py/x`; префиксная
    сверка заменена покомпонентной — `CLAUDE.md` перестал покрывать
    `CLAUDE.mdx` и `CLAUDE.md/x`, как покрывает на main.
    """
    _base_paths, main_fn = main_formula
    diffs = []
    for entry in config.PROTECTED_PATHS:
        for path in PATHS:
            got = config.is_protected_path(path, (entry,))
            want = main_fn(path, (entry,))
            if got != want:
                diffs.append(f"{entry!r} × {path!r}: {got}, на main {want}")
    for path in PATHS:
        got, want = config.is_protected_path(path), main_fn(path)
        if got != want:
            diffs.append(f"перечень целиком × {path!r}: {got}, на main {want}")
    assert diffs == []


def test_ac5_ci_and_guard_on_artel_list_match_main(main_formula):
    """Джоб CI и guard (`protected_zones`, допуск приложения PLAN) на перечне артели дают результат main.

    Сценарий: на наборе путей AC-4 — `ci_protected_paths.is_violation(путь,
    перечень артели)` равен формуле базы; `guard.protected_zones` без
    перечня и с перечнем артели отдаёт ровно пути, защищённые формулой
    базы; `guard.plan_appendices` по PLAN с приложением на каждый путь
    (без перечня и с перечнем артели) несёт ошибку «путь … не защищённый»
    ровно для путей, не защищённых формулой базы.

    Ловит мутацию: сверка зон guard получила расширение для каталога
    (`.claude` без `/` под записью-каталогом) и у артели — зона
    `skills` (без `/`) стала защищённой, хотя на main нет; джоб CI сверяет
    перечень с маскировкой `**/` по любому компоненту.
    """
    _base_paths, main_fn = main_formula
    artel = list(config.PROTECTED_PATHS)
    protected_on_main = sorted({p for p in PATHS if main_fn(p)})
    ci_diffs = [p for p in PATHS
                if ci_protected_paths.is_violation(p, artel) != main_fn(p)]
    assert ci_diffs == []
    assert guard.protected_zones(list(PATHS)) == protected_on_main
    assert guard.protected_zones(list(PATHS), tuple(artel)) == protected_on_main
    text = plan_with_appendices(PATHS)
    for protected in (None, tuple(artel)):
        _apps, errors = guard.plan_appendices(text, protected)
        flagged = sorted(p for p in PATHS
                         if guard.appendix_unprotected_path_error(p) in errors)
        want = sorted(p for p in PATHS if not main_fn(p))
        assert flagged == want, f"перечень {protected!r}"


def test_ac24_git_minimum_is_2_35():
    """Объявленный минимум git в стеке пульта — `(2, 35, 0)`.

    Ловит мутацию: минимум оставлен `(2, 30, 0)` — режим sparse-checkout
    без конусов и `git add --sparse` не гарантированы объявленной версией.
    """
    assert tuple(stack.REQUIRED_TOOLS["git"].minimum) == (2, 35, 0)
