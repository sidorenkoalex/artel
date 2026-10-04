"""Вызов git-примитивов пульта без явного репозитория — только по перечню.

Группа: долгоживущий

Свойство кода (ADR-0021 п.1, этап 2): работа с проектом идёт в репозитории
проекта, названном явно; по главной копии пульта остаются только вызовы
закрытого перечня — версия пульта, его пин, его хуки и git-идентичность
Оператора. Файл разбирает исходники `orchestrator/` синтаксически (без
импорта модуля примитивов): какие функции модуля `orchestrator/gitcmd.py`
исполняют git и в какой позиции принимают `repo`, берётся из его же
исходника, так что новый примитив или новый параметр учитываются сами.

«Явный репозиторий» у вызова: ключевой аргумент `repo=`, позиционный
аргумент на месте параметра `repo` (`head_sha(path)`), примитивы, у которых
репозиторий — обязательный первый аргумент (`in_repo`, `carpentry`, …), и
`git("-C", <путь>, …)`.

Красен до реализации: сегодня десятки вызовов (`workspace.py`, `cleanup.py`,
`fsm_merge_gate.py`, `notes.py`, `doctor/*`, …) идут в git главной копии без
репозитория — перечень требования 4 их не покрывает.

Детектор провалидирован вторым методом файла: посаженный вызов без
репозитория находится в трёх формах обращения, вызов с репозиторием и
вызов из перечня — нет; он зелёный и до реализации.
"""
import ast
import random
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = REPO_ROOT / "orchestrator"
PRIMITIVES_FILE = CODE_DIR / "gitcmd.py"
PRIMITIVES_MODULE = "gitcmd"

# Перечень требования 4: модуль (путь от корня репозитория) -> какие
# примитивы и в какой функции модуля разрешено звать без репозитория.
# Значение `None` вместо функции — в любой функции модуля; «*» вместо
# примитива — любой примитив.
ALLOWED = {
    # pin-update / pin --to: единственная смена HEAD главной копии.
    "orchestrator/pin.py": {"*": None},
    # Сверка пина с origin/main пульта.
    "orchestrator/doctor/root_pin.py": {"*": None},
    # Проверка и ремонт хуков самого пульта.
    "orchestrator/doctor/git_hooks.py": {"*": None},
    # Версия пульта в предупреждении о расхождении пина.
    "orchestrator/catalog.py": {"head_sha": None},
    # Версия пульта и выбор коммита канарейки.
    "orchestrator/canary.py": {"head_sha": None, "git": None,
                               "is_ancestor": None, "merges_between": None,
                               "fetch_ref_sha": None},
    "orchestrator/canary_drive.py": {"head_sha": None},
    # Версия пульта, закрывшего задачу; git-идентичность Оператора.
    "orchestrator/snapshot.py": {"head_sha": None,
                                 "git": {"_operator_identity"}},
    # git-идентичность Оператора.
    "orchestrator/runner.py": {"git": {"git_identity"}},
}

# Примитивы, у которых репозиторий — обязательный первый позиционный
# аргумент без умолчания (имя параметра — любое: `repo`, `path`, …).
_FIRST_ARG_REPO_NAMES = ("repo", "path", "repo_path", "root", "cwd")


def primitive_table(source: str) -> dict:
    """{имя примитива: (индекс позиционного `repo` или None, репозиторий
    обязателен)} для функций модуля примитивов, исполняющих git.

    «Исполняет git» — тело зовёт `git(`, `in_repo(`, `subprocess.run(` или
    другой такой же примитив (замыкание по вызовам внутри модуля)."""
    tree = ast.parse(source)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def callees(fn):
        names = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    if (isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "subprocess"):
                        names.add("subprocess." + node.func.attr)
        return names

    runs_git = {name for name, fn in funcs.items()
                if callees(fn) & {"subprocess.run", "subprocess.Popen"}}
    changed = True
    while changed:
        changed = False
        for name, fn in funcs.items():
            if name not in runs_git and callees(fn) & runs_git:
                runs_git.add(name)
                changed = True

    table = {}
    for name in runs_git:
        if name.startswith("_"):
            continue
        args = funcs[name].args
        positional = [a.arg for a in args.posonlyargs + args.args]
        kwonly = [a.arg for a in args.kwonlyargs]
        n_defaults = len(args.defaults)
        required = positional[:len(positional) - n_defaults]
        if "repo" in positional:
            table[name] = (positional.index("repo"),
                           "repo" in required)
        elif "repo" in kwonly:
            table[name] = (None, False)
        elif required and required[0] in _FIRST_ARG_REPO_NAMES:
            table[name] = (0, True)
        else:
            table[name] = (None, False)
    return table


def _is_primitives_ref(node: ast.AST) -> bool:
    """`gitcmd` или `<что-то>.gitcmd` (`doctor.gitcmd`)."""
    if isinstance(node, ast.Name):
        return node.id == PRIMITIVES_MODULE
    if isinstance(node, ast.Attribute):
        return node.attr == PRIMITIVES_MODULE
    return False


def calls_without_repo(source: str, table: dict) -> list:
    """[(строка, примитив, объемлющая функция)] вызовов примитивов модуля
    без явного репозитория в тексте `source`."""
    tree = ast.parse(source)
    direct = {}  # локальное имя -> примитив (`from .gitcmd import git`)
    for node in ast.walk(tree):
        if (isinstance(node, ast.ImportFrom) and node.module
                and node.module.split(".")[-1] == PRIMITIVES_MODULE):
            for alias in node.names:
                direct[alias.asname or alias.name] = alias.name

    found = []

    def visit(node, enclosing):
        for child in ast.iter_child_nodes(node):
            scope = enclosing
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope = child.name
            if isinstance(child, ast.Call):
                name = None
                if (isinstance(child.func, ast.Attribute)
                        and _is_primitives_ref(child.func.value)):
                    name = child.func.attr
                elif (isinstance(child.func, ast.Name)
                      and child.func.id in direct):
                    name = direct[child.func.id]
                if name in table and not has_explicit_repo(child, name, table):
                    found.append((child.lineno, name, scope))
            visit(child, scope)

    visit(tree, None)
    return found


def has_explicit_repo(call: ast.Call, name: str, table: dict) -> bool:
    index, required = table[name]
    if required:
        return True
    if any(kw.arg == "repo" for kw in call.keywords):
        return True
    if index is not None and len(call.args) > index and not any(
            isinstance(a, ast.Starred) for a in call.args[:index + 1]):
        return True
    if call.args and isinstance(call.args[0], ast.Constant) \
            and call.args[0].value == "-C":
        return True
    return False


def allowed(rel: str, name: str, scope) -> bool:
    entry = ALLOWED.get(rel)
    if entry is None:
        return False
    for key in (name, "*"):
        if key in entry:
            funcs = entry[key]
            return funcs is None or scope in funcs
    return False


def violations(code_dir: Path, table: dict) -> list:
    result = []
    for path in sorted(code_dir.rglob("*.py")):
        if path == code_dir / "gitcmd.py":
            continue
        rel = path.relative_to(code_dir.parent).as_posix()
        source = path.read_text(encoding="utf-8")
        for lineno, name, scope in calls_without_repo(source, table):
            if not allowed(rel, name, scope):
                result.append(f"{rel}:{lineno}: {PRIMITIVES_MODULE}.{name} "
                              f"(в {scope or 'модуле'})")
    return result


class GitcmdWithoutRepoOnlyFromAllowListTest(unittest.TestCase):
    """Перечень требования 4 — единственные вызовы без репозитория."""

    def setUp(self):
        self.table = primitive_table(
            PRIMITIVES_FILE.read_text(encoding="utf-8"))

    def test_ac8_every_call_without_repo_is_in_the_allow_list(self):
        """Обход всех модулей `orchestrator/` (кроме самого модуля
        примитивов): каждый вызов git-примитива без явного репозитория
        стоит в модуле и функции перечня требования 4.

        Ловит мутацию: `workspace.ensure` заводит ветку задачи прежним
        `gitcmd.branch_exists(branch)` / `gitcmd.git("worktree", "add", …)`
        без репозитория клона — вызов из `orchestrator/workspace.py`
        попадает в список нарушений, тест красный с адресом строки.
        """
        found = violations(CODE_DIR, self.table)
        self.assertEqual(found, [], "вызовы без репозитория вне перечня "
                         "требования 4:\n" + "\n".join(found))

    def test_ac8_detector_catches_planted_calls_and_spares_explicit_ones(self):
        """Синтетические исходники со случайно выбранными примитивами: вызов
        без репозитория в модуле вне перечня находится, тот же вызов с
        `repo=` / позиционным репозиторием / `-C` — нет, вызов из перечня
        (`runner.git_identity`) не считается нарушением.

        Ловит мутацию: детектор перестаёт видеть форму `doctor.gitcmd.X(…)`
        или `from .gitcmd import X` — посаженный вызов без репозитория не
        находится, первый тест файла зеленел бы на нарушающем коде.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        names = sorted(self.table)
        self.assertIn("git", names, f"зерно {seed}")
        no_repo_names = [n for n in names if not self.table[n][1]]
        for _ in range(8):
            name = rng.choice(no_repo_names)
            index, _required = self.table[name]
            form = rng.choice(["attr", "doctor", "direct"])
            if form == "attr":
                head, call = "from . import gitcmd\n", f"gitcmd.{name}"
            elif form == "doctor":
                head, call = "from .. import doctor\n", f"doctor.gitcmd.{name}"
            else:
                head, call = f"from .gitcmd import {name}\n", name
            # Позиционных аргументов ровно столько, чтобы место `repo` (если
            # оно есть) осталось пустым.
            bare_args = ", ".join(["'a'"] * (1 if index is None else index))
            planted = f"{head}\ndef work(x):\n    return {call}({bare_args})\n"
            with self.subTest(зерно=seed, примитив=name, форма=form):
                hits = calls_without_repo(planted, self.table)
                self.assertEqual([(h[1], h[2]) for h in hits], [(name, "work")],
                                 f"зерно {seed}: {planted}")
                self.assertFalse(allowed("orchestrator/workspace.py", name, "work"))

                with_kw = (f"{head}\ndef work(x):\n"
                           f"    return {call}({bare_args}{', ' if bare_args else ''}"
                           f"repo=x)\n")
                self.assertEqual(calls_without_repo(with_kw, self.table), [],
                                 f"зерно {seed}: {with_kw}")
                if index is not None:
                    args = ", ".join(["'a'"] * index + ["x"])
                    with_pos = f"{head}\ndef work(x):\n    return {call}({args})\n"
                    self.assertEqual(
                        calls_without_repo(with_pos, self.table), [],
                        f"зерно {seed}: {with_pos}")
        dash_c = "from . import gitcmd\n\ndef w(p):\n    gitcmd.git('-C', str(p), 'log')\n"
        self.assertEqual(calls_without_repo(dash_c, self.table), [])
        identity = ("from . import gitcmd\n\ndef git_identity():\n"
                    "    return gitcmd.git('config', '--get', 'user.name')\n")
        hits = calls_without_repo(identity, self.table)
        self.assertEqual(len(hits), 1)
        self.assertTrue(allowed("orchestrator/runner.py", *hits[0][1:]))
        self.assertFalse(allowed("orchestrator/cleanup.py", *hits[0][1:]))


if __name__ == "__main__":
    unittest.main()
