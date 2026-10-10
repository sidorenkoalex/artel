"""Сторож: в коде пульта нет дочерних вызовов голого `python3`.

Группа: долгоживущий
Красен до реализации: три регенерации карты (`orchestrator/pull.py`, `orchestrator/fsm_postmerge.py`, `orchestrator/brief.py`) зовут `subprocess.run(["python3", "scripts/codebase_map.py"], …)` — сторож называет их файл:строку.

Свойство — статическое, проверяется разбором исходников модулей пульта
(`orchestrator/`, `scripts/`) без исполнения: дочерний вызов модуля
`subprocess` (`run`/`Popen`/`call`/`check_call`/`check_output`, через
`subprocess.` или импортом имени), первый аргумент которого (или
`args=`) — список/кортеж, начинающийся литералом `"python3"`; список,
сложенный с хвостом (`["python3"] + rest`), и имя, которому такой список
присвоен в той же функции, — тот же вызов.

Перечень исключений `ALLOWED` пуст: SPEC оставляет его на PLAN.md, а
сверка по main (раздел «Материалы» SPEC) называет ровно три таких вызова,
и все три требование 1 переводит на интерпретатор пульта.

Чувствительность самого разбора проверяется до сверки дерева: в текст
случайного модуля пульта дописывается вызов голого `python3` случайной
формы — сторож обязан его найти, а вызов под `sys.executable` той же
формы — нет. Модуль, форма и аргументы — от зерна; зерно печатается и
входит в текст провала.

Валидировано временным стабом реализации (три регенерации под
`sys.executable`): тест зелёный, стаб удалён.
"""
import ast
import random
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PULT_DIRS = ("orchestrator", "scripts")
# Исключения — пути относительно корня репозитория вида «файл:функция».
ALLOWED: frozenset = frozenset()
SPAWNERS = ("run", "Popen", "call", "check_call", "check_output")


def _starts_with_python3(node, assigned: dict) -> bool:
    if isinstance(node, (ast.List, ast.Tuple)):
        return bool(node.elts) and isinstance(node.elts[0], ast.Constant) \
            and node.elts[0].value == "python3"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _starts_with_python3(node.left, assigned)
    if isinstance(node, ast.Name):
        return any(_starts_with_python3(value, {})
                   for value in assigned.get(node.id, []))
    return False


def _is_spawner(func) -> bool:
    if isinstance(func, ast.Attribute):
        owner = func.value
        owner_name = owner.attr if isinstance(owner, ast.Attribute) else (
            owner.id if isinstance(owner, ast.Name) else "")
        return func.attr in SPAWNERS and owner_name == "subprocess"
    return isinstance(func, ast.Name) and func.id in SPAWNERS


def bare_python3_calls(source: str) -> list:
    """(строка, имя функции) каждого дочернего вызова голого `python3`."""
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree)
               for child in ast.iter_child_nodes(node)}

    def scope_of(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return node
        return tree

    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _is_spawner(node.func)):
            continue
        argv = node.args[0] if node.args else next(
            (kw.value for kw in node.keywords if kw.arg == "args"), None)
        if argv is None:
            continue
        scope = scope_of(node)
        assigned: dict = {}
        for inner in ast.walk(scope):
            if isinstance(inner, ast.Assign):
                for target in inner.targets:
                    if isinstance(target, ast.Name):
                        assigned.setdefault(target.id, []).append(inner.value)
        if _starts_with_python3(argv, assigned):
            hits.append((node.lineno, getattr(scope, "name", "<модуль>")))
    return hits


def pult_modules() -> list:
    return sorted(path for directory in PULT_DIRS
                  for path in (ROOT / directory).rglob("*.py"))


def injected_call(rng: random.Random, interpreter: str) -> str:
    """Функция с дочерним вызовом `interpreter` случайной формы."""
    script = f"scripts/s{rng.randrange(10**6)}.py"
    spawner = rng.choice(SPAWNERS)
    head = f"[{interpreter}, {script!r}]"
    form = rng.choice(["literal", "tuple", "keyword", "concat", "variable",
                       "imported"])
    if form == "tuple":
        head = f"({interpreter}, {script!r})"
    call = f"subprocess.{spawner}"
    prelude = ""
    if form == "keyword":
        argv = f"args={head}"
    elif form == "concat":
        argv = f"{head} + ['--x']"
    elif form == "variable":
        prelude = f"    cmd = {head}\n"
        argv = "cmd"
    elif form == "imported":
        prelude = f"    from subprocess import {spawner}\n"
        call = spawner
        argv = head
    else:
        argv = head
    return (f"\n\ndef injected_{rng.randrange(10**6)}():\n"
            f"    import subprocess, sys\n{prelude}"
            f"    return {call}({argv}, capture_output=True, text=True)\n")


class BarePython3GuardTest(unittest.TestCase):

    def test_ac6_no_bare_python3_subprocess_calls_in_pult_code(self):
        """В модулях пульта нет дочерних вызовов голого `python3` вне перечня исключений.

        Сценарий: сначала сторож проверяет сам себя — в текст случайного
        модуля пульта дописан вызов голого `python3` случайной формы
        (литерал, кортеж, `args=`, сложение, переменная, импортированное
        имя): разбор находит его на дописанных строках; тот же вызов под
        `sys.executable` не находит. Затем разбор проходит все `*.py`
        `orchestrator/` и `scripts/`: находок вне `ALLOWED` нет.

        Ловит мутацию: регенерация карты в `pull`, `fsm_postmerge` или
        `brief` снова зовёт `subprocess.run(["python3", …])`, либо в любой
        модуль пульта добавлен новый такой вызов — сторож называет
        файл:строку.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        modules = pult_modules()
        self.assertTrue(modules, f"не найдено модулей пульта (зерно {seed})")

        for _ in range(5):
            module = rng.choice(modules)
            source = module.read_text(encoding="utf-8")
            base_lines = source.count("\n") + 1
            state = rng.getstate()
            bare = source + injected_call(rng, '"python3"')
            rng.setstate(state)
            safe = source + injected_call(rng, "sys.executable")
            before = {line for line, _ in bare_python3_calls(source)}
            found = [line for line, _ in bare_python3_calls(bare)
                     if line not in before]
            context = (f"{module.relative_to(ROOT)}, дописано:\n"
                       f"{bare[len(source):]}(зерно {seed})")
            self.assertTrue(found and all(line > base_lines - 1 for line in found),
                            f"сторож не нашёл дописанный вызов; {context}")
            self.assertEqual(
                [line for line, _ in bare_python3_calls(safe)
                 if line not in before], [],
                f"сторож поймал вызов под sys.executable; {context}")

        offenders = []
        for module in modules:
            rel = module.relative_to(ROOT).as_posix()
            for line, function in bare_python3_calls(
                    module.read_text(encoding="utf-8")):
                if f"{rel}:{function}" not in ALLOWED:
                    offenders.append(f"{rel}:{line} ({function})")
        self.assertEqual(offenders, [],
                         f"дочерние вызовы голого python3 в коде пульта: "
                         f"{offenders} (зерно {seed})")


if __name__ == "__main__":
    unittest.main()
