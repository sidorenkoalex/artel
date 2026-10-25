"""Сторож одного списка окончательных состояний: литерала из ровно
`"done"` и `"killed"` в модулях пакета `orchestrator/` вне `fsm.py` нет.

Группа: долгоживущий
Красен до реализации: перечисления `("done", "killed")` сегодня стоят в `models.py`, `zone_lock.py`, `cleanup.py`, `prune.py`, `watch.py` и четырёх модулях `doctor/` — сторож их находит.

Сторож по образцу `tests/test_invariants.py`: разбор исходников
модулем `ast`, без импорта проверяемых модулей. Литерал — кортеж, список
или множество, все элементы которого — строковые константы, ровно
`"done"` и `"killed"` в любом порядке. Чувствительность сторожа к
добавленному литералу проверяется на копии пакета во временном каталоге:
модуль верхнего уровня и модуль `doctor/`, форма литерала и порядок
элементов порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.
"""
import ast
import random
import shutil
from pathlib import Path

import orchestrator

PACKAGE = Path(orchestrator.__file__).resolve().parent
OWNER = "fsm.py"


def terminal_literals(root: Path) -> list[str]:
    """`<путь>:<строка>` каждого литерала окончательных состояний в модулях
    `root` вне `fsm.py`."""
    found = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel == OWNER or "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
                continue
            values = [e.value for e in node.elts
                      if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(values) == len(node.elts) and sorted(values) == ["done",
                                                                   "killed"]:
                found.append(f"{rel}:{node.lineno}")
    return found


def literal_text(rng: random.Random) -> str:
    items = ['"done"', '"killed"']
    rng.shuffle(items)
    opening, closing = rng.choice([("(", ")"), ("[", "]"), ("{", "}")])
    return f"{opening}{', '.join(items)}{closing}"


def test_ac16_no_terminal_literal_outside_fsm_and_sentinel_catches_one(tmp_path):
    """Сторож зелёный на пакете `orchestrator/`; на копии пакета литерал, дописанный в модуль верхнего уровня и в модуль `doctor/`, находится, а дописанный в `fsm.py` — нет.

    Ловит мутацию: одно из перечислений `("done", "killed")` пакета
    (например, второе из трёх в `doctor/artifact_branches.py` или
    константа `watch.py`) не заменено ссылкой на
    `fsm.TERMINAL_STATES` — сторож называет модуль и строку.
    """
    seed = random.randrange(1 << 30)
    print(f"зерно: {seed}")
    rng = random.Random(seed)

    found = terminal_literals(PACKAGE)
    assert found == [], f"зерно: {seed}; литералы окончательных " \
                        f"состояний вне {OWNER}: {found}"

    copy = tmp_path / "orchestrator"
    shutil.copytree(PACKAGE, copy,
                    ignore=shutil.ignore_patterns("__pycache__"))
    before = set(terminal_literals(copy))
    modules = sorted(p.relative_to(copy).as_posix() for p in copy.rglob("*.py"))
    top = rng.choice([m for m in modules if "/" not in m and m != OWNER])
    doctor = rng.choice([m for m in modules if m.startswith("doctor/")])
    injected = {}
    for rel in (top, doctor, OWNER):
        path = copy / rel
        text = path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            text += "\n"
        line = text.count("\n") + 1
        path.write_text(f"{text}SENTINEL_PROBE = {literal_text(rng)}\n",
                        encoding="utf-8")
        injected[rel] = f"{rel}:{line}"

    new = set(terminal_literals(copy)) - before
    assert new == {injected[top], injected[doctor]}, (
        f"зерно: {seed}; дописано {injected}, сторож нашёл {sorted(new)}")
