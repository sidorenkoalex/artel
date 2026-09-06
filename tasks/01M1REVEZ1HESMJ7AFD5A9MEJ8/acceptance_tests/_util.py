"""Общая утилита приёмочных тестов задачи 01M1REVEZ1HESMJ7AFD5A9MEJ8 —
НЕ test_*.py: guard (`scripts/guard.py::scan_acceptance_tests`) разбирает
на AC-разметку только `test_*.py` (тот же приём, что `_util.py` в
tasks/01M1RDCAFENSW2VVAPECHCVGMM/acceptance_tests/).

`find_foreign_imports` — БУКВАЛЬНАЯ копия сканера, которым уже пользуется
`tests/test_invariants.py::StdlibOnlyImportsInvariantTest` на ветке S1
(01M1RDCAFENSW2VVAPECHCVGMM, ещё не смержена в момент написания этой
планки) — не переизобретение, а перенос уже одобренной логики: AC-3 этой
задачи испытывает СОСТОЯТЕЛЬНОСТЬ существующего (после мержа S1)
инварианта на КОНКРЕТНЫХ новых записях exceptions (`pytest` и т.п.), а не
общую механику сканирования саму по себе (та уже приёмочно испытана
задачей S1).

`parse_pip_lock` — независимый разбор pip-формата (`name==version`,
комментарии `#`, пустые строки) для файла закреплённых версий; писать
собственный разбор, а не импортировать код задачи, — тот же принцип, что
`find_foreign_imports` выше: планка испытывает СОДЕРЖИМОЕ файла, а не
доверяет разбору, который сама же задача и напишет.
"""
import ast
import re
import sys
from pathlib import Path

LOCAL_PACKAGES = ("orchestrator", "scripts", "tests")

LOCK_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)\s*==\s*([A-Za-z0-9][A-Za-z0-9_.+-]*)\s*$")


def find_foreign_imports(root: Path, local_packages=LOCAL_PACKAGES,
                         exceptions=()) -> list:
    """[(файл, имя_модуля), ...] для импортов вне stdlib/пакетов репо/исключений.

    Только файлы верхнего уровня каждого каталога (`glob("*.py")`, не
    `rglob`) — у orchestrator/scripts/tests сегодня нет вложенных пакетов.
    Относительные импорты (`from . import x`, `level > 0`) всегда
    внутрипакетные — не проверяются.
    """
    stdlib = frozenset(sys.stdlib_module_names)
    allowed = stdlib | frozenset(local_packages) | frozenset(exceptions)
    violations = []
    for directory in local_packages:
        d = root / directory
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"),
                                 filename=str(path))
            except (SyntaxError, OSError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top not in allowed:
                            violations.append((str(path), top))
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        continue
                    if node.module is None:
                        continue
                    top = node.module.split(".")[0]
                    if top not in allowed:
                        violations.append((str(path), top))
    return violations


def parse_pip_lock(path: Path) -> dict:
    """{имя_пакета_в_нижнем_регистре: версия} из файла формата pip.

    Строки без `==` (комментарии, пустые, диапазоны вроде `>=`) молча
    пропускаются — назначение здесь узкое: найти ТОЧНО закреплённые пины,
    ровно то, что требует AC-1 («точные версии»).
    """
    pinned = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LOCK_LINE_RE.match(line)
        if match is None:
            continue
        name, version = match.groups()
        pinned[normalize_name(name)] = version
    return pinned


def normalize_name(name: str) -> str:
    """`PyTest-XDist` -> `pytest-xdist`: сверка имён пакетов по написанию
    pip (регистр и `_`/`-` в PyPI взаимозаменяемы, PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()
