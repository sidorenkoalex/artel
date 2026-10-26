"""Сторож единой точки запуска git: пять модулей пульта, чтения git которых
идут через `orchestrator/gitcmd.py`, не запускают git прямым `subprocess`.

Группа: долгоживущий
Красен до реализации: `acceptance.suite_tree_hash`, `brief._clone_git`, `reference_cache.branch_commit`/`_list_tree`/`_cat_blobs`, `tz_check._git` и `outcome_integrity._added_lines` ещё зовут `subprocess.run`/`subprocess.Popen` с argv `["git", …]` — тест модулей находит эти строки; проверки самого сторожа на образцах зелены с рождения.

Образец — `tests/test_invariants.py::CarpentryGitCallsGoThroughGitcmdTest`
(та же структурная половина инварианта единой точки), но разбором `ast`, а
не подстрокой: запуск НЕ git (`pytest`, `sys.executable`) и сам импорт
`subprocess` сторож не запрещает — `outcome_integrity` импортирует модуль
ради подмены `outcome_integrity.subprocess.run` в существующих тестах, а
`acceptance` запускает через него прогоны тестов.

Запуском git считается вызов `subprocess.run`/`Popen`/`call`/
`check_call`/`check_output` (через имя модуля, его псевдоним или имя,
импортированное из него) либо обёрток `_launch`/`_run_capture`, первый
аргумент которого — список/кортеж с литералом "git" в начале, строка
`"git …"`, либо имя, которому такой список присвоен в той же функции.
"""
import ast
import random
from pathlib import Path

import pytest

from orchestrator import acceptance, brief, reference_cache, tz_check
from orchestrator.advance_gates import outcome_integrity

MODULES = (acceptance, brief, reference_cache, tz_check, outcome_integrity)
LAUNCHERS = ("run", "Popen", "call", "check_call", "check_output")
WRAPPERS = ("_launch", "_run_capture")


def _is_git_argv(node) -> bool:
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        first = node.elts[0]
        return isinstance(first, ast.Constant) and first.value == "git"
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and (node.value == "git" or node.value.startswith("git ")))


def _subprocess_names(tree) -> tuple[set, set]:
    """(имена модуля `subprocess`, имена функций запуска, импортированных из него)."""
    modules, functions = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    modules.add(alias.asname or "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                if alias.name in LAUNCHERS:
                    functions.add(alias.asname or alias.name)
    return modules, functions


def raw_git_launches(source: str) -> list[int]:
    """Номера строк прямых запусков git через `subprocess` в тексте модуля."""
    tree = ast.parse(source)
    modules, functions = _subprocess_names(tree)
    hits = set()
    scopes = [n for n in ast.walk(tree)
              if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef))]
    for scope in scopes:
        git_names = {target.id for node in ast.walk(scope)
                     if isinstance(node, ast.Assign) and _is_git_argv(node.value)
                     for target in node.targets if isinstance(target, ast.Name)}
        for node in ast.walk(scope):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            launch = ((isinstance(func, ast.Attribute) and func.attr in LAUNCHERS
                       and isinstance(func.value, ast.Name)
                       and func.value.id in modules)
                      or (isinstance(func, ast.Name)
                          and (func.id in functions or func.id in WRAPPERS)))
            if not launch:
                continue
            argv = node.args[0] if node.args else next(
                (kw.value for kw in node.keywords if kw.arg == "args"), None)
            if argv is not None and (_is_git_argv(argv) or (
                    isinstance(argv, ast.Name) and argv.id in git_names)):
                hits.add(node.lineno)
    return sorted(hits)


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__)
def test_ac2_modules_launch_git_only_through_gitcmd(module):
    """Текст каждого из пяти модулей не несёт прямого запуска git через `subprocess`.

    Модуль читается с диска и разбирается `ast`; находки — строки вызовов
    `subprocess.run`/`Popen` (и обёрток `_launch`/`_run_capture`) с argv git.

    Ловит мутацию: `tz_check._git` возвращён на
    `subprocess.run(["git", "-C", str(repo), *args], …)` — строка вызова
    попадает в находки модуля `orchestrator.tz_check`.
    """
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert raw_git_launches(source) == [], (
        f"{module.__name__}: прямой запуск git через subprocess, строки "
        f"{raw_git_launches(source)} — запускай git функцией orchestrator/gitcmd.py")


# Прежний вид семи мест — так их вернула бы регрессия.
ORIGINAL_PLACES = [
    # место 1: acceptance.suite_tree_hash, вложенная git()
    "import subprocess\n"
    "def git(*args):\n"
    "    process = subprocess.Popen([\"git\", \"-C\", str(root), *args],\n"
    "                               cwd=config.ROOT, env=env,\n"
    "                               stdout=subprocess.PIPE, text=True)\n"
    "    return process.communicate(timeout=15)\n",
    # место 2: brief._clone_git
    "import subprocess\n"
    "def _clone_git(clone, *args):\n"
    "    res = subprocess.run([\"git\", \"-C\", str(clone), *opts, *args],\n"
    "                         capture_output=True, timeout=60)\n",
    # место 3: reference_cache.branch_commit
    "import subprocess\n"
    "def branch_commit(clone, branch):\n"
    "    res = subprocess.run(\n"
    "        [\"git\", \"-C\", str(clone), \"rev-parse\", \"--verify\", \"--quiet\",\n"
    "         f\"refs/heads/{branch}\"], capture_output=True, text=True)\n",
    # место 4: reference_cache._list_tree
    "import subprocess\n"
    "def _list_tree(clone, sha, deadline):\n"
    "    proc = subprocess.Popen(\n"
    "        [\"git\", \"-C\", str(clone), \"ls-tree\", \"-r\", \"-l\", \"-z\", sha],\n"
    "        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)\n",
    # место 5: reference_cache._cat_blobs
    "import subprocess\n"
    "def _cat_blobs(clone, objects, deadline):\n"
    "    res = subprocess.run([\"git\", \"-C\", str(clone), \"cat-file\", \"--batch\"],\n"
    "                         input=b\"\", capture_output=True, timeout=1)\n",
    # место 6: tz_check._git
    "import subprocess\n"
    "def _git(repo, *args):\n"
    "    return subprocess.run([\"git\", \"-C\", str(repo), *args],\n"
    "                          capture_output=True)\n",
    # место 7: outcome_integrity._added_lines, argv через имя
    "import subprocess\n"
    "def _added_lines(repo, base_sha, head_sha):\n"
    "    argv = [\"git\", \"-C\", str(repo), \"diff\", \"-M\", \"-U0\", base_sha, head_sha]\n"
    "    res = subprocess.run(argv, capture_output=True)\n",
]


@pytest.mark.parametrize("snippet", ORIGINAL_PLACES,
                         ids=[f"место-{n}" for n in range(1, 8)])
def test_ac2_guard_turns_red_on_each_original_place(snippet):
    """Прежний вид каждого из семи мест сторож находит.

    Текст места в том виде, в каком он был до переноса в `gitcmd`, —
    вход детектора; находка обязана быть ровно одна.

    Ловит мутацию: место 7 возвращено на `subprocess.run(argv, …)` с
    `argv = ["git", …]` в отдельной строке — без разбора имени сторож
    остался бы зелёным, тест показывает, что строка вызова находится.
    """
    assert len(raw_git_launches(snippet)) == 1


def _random_launch(rng: random.Random) -> str:
    alias = rng.choice(["subprocess", "sp", "_subprocess"])
    func = rng.choice(LAUNCHERS)
    sub = rng.choice(["ls-tree", "show", "rev-parse", "cat-file", "diff",
                      "write-tree", "read-tree", "grep"])
    argv = (f"[\"git\", \"-C\", str(repo), \"{sub}\", "
            f"\"--{rng.choice(['quiet', 'verify', 'z'])}\"]")
    if rng.random() < 0.5:
        argv = argv[:-1] + ")"
        argv = "(" + argv[1:]
    style = rng.choice(["module", "from", "name"])
    var = rng.choice(["argv", "cmd", "command", "git_argv"])
    if style == "from":
        head = f"from subprocess import {func} as launch_{func}\n"
        call = f"launch_{func}({argv}, capture_output=True)"
        body = f"    return {call}\n"
    else:
        head = (f"import subprocess as {alias}\n" if alias != "subprocess"
                else "import subprocess\n")
        if style == "name":
            body = (f"    {var} = {argv}\n"
                    f"    return {alias}.{func}({var}, capture_output=True)\n")
        else:
            body = f"    return {alias}.{func}(args={argv}, text=True)\n"
    return head + f"def place_{rng.randrange(1000)}(repo):\n" + body


def test_ac2_guard_turns_red_on_random_raw_git_launch():
    """Случайно собранный прямой запуск git через `subprocess` сторож находит.

    Каждый запуск порождает новые входы (зерно печатается): псевдоним
    модуля, функция запуска, импорт `from subprocess import …`, argv
    списком/кортежем, напрямую, ключом `args=` или через имя переменной,
    подкоманда git.

    Ловит мутацию: в функции `gitcmd` места оставлен
    `from subprocess import Popen` и в модуль места возвращён прямой
    `Popen(["git", …])` — вид запуска без имени модуля; вход такого вида
    сторож обязан найти.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)
    for _ in range(200):
        snippet = _random_launch(rng)
        assert len(raw_git_launches(snippet)) == 1, f"зерно: {seed}\n{snippet}"


BENIGN = [
    "import subprocess\n",
    "import subprocess\n"
    "def run_suite():\n"
    "    return subprocess.run([sys.executable, \"-m\", \"pytest\"], timeout=5)\n",
    "import subprocess\n"
    "def launch(argv, cwd):\n"
    "    return subprocess.Popen(argv, cwd=cwd)\n",
    "import subprocess\n"
    "def wait(proc):\n"
    "    try:\n"
    "        proc.communicate(timeout=1)\n"
    "    except subprocess.TimeoutExpired:\n"
    "        proc.kill()\n",
    "from orchestrator import gitcmd\n"
    "def read(clone):\n"
    "    return gitcmd.in_repo(clone, \"rev-parse\", \"HEAD\")\n",
]


@pytest.mark.parametrize("snippet", BENIGN, ids=[
    "импорт", "pytest", "argv-параметр", "TimeoutExpired", "gitcmd"])
def test_ac2_guard_allows_subprocess_import_and_non_git_launch(snippet):
    """Импорт `subprocess`, запуск не git и запуск git функцией `gitcmd` сторож не находит.

    Ловит мутацию: сторож упрощён до подстроки `import subprocess`/
    `subprocess.` — модуль `outcome_integrity`, сохраняющий импорт ради
    подмены `outcome_integrity.subprocess.run`, стал бы находкой.
    """
    assert raw_git_launches(snippet) == []
