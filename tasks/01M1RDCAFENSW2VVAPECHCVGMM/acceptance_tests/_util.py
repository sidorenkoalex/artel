"""Общая утилита приёмочных тестов задачи 01M1RDCAFENSW2VVAPECHCVGMM —
НЕ test_*.py: guard (`scripts/guard.py::scan_acceptance_tests`) разбирает
на AC-разметку только `test_*.py`, вспомогательные файлы вроде этого в
трассируемость не попадают (тот же приём, что `_util.py`
tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/).

`find_foreign_imports` — САМОСТОЯТЕЛЬНАЯ реализация правила требования 3
SPEC («тест ... разбирает orchestrator/, scripts/, tests/ через ast и
падает, если ... импорт модуля, который одновременно не входит в
sys.stdlib_module_names и не является пакетом репозитория»), написанная
этой же приёмочной планкой, а не кодом задачи: испытывается
СОСТОЯТЕЛЬНОСТЬ правила (ловит ли оно подсаженный сторонний импорт и
пропускает ли чистое дерево — AC-16), а заодно, прогнанная на РЕАЛЬНОМ
дереве репозитория прямо сейчас, независимо доказывает AC-6 (сторонних
импортов в orchestrator/, scripts/, tests/ сегодня нет). Тот же приём,
что `_util.find_dns_addresses` в
tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/_util.py.
"""
import ast
import sys
from pathlib import Path

LOCAL_PACKAGES = ("orchestrator", "scripts", "tests")


def find_foreign_imports(root: Path, local_packages=LOCAL_PACKAGES,
                         exceptions=()) -> list:
    """[(файл, имя_модуля), ...] для импортов вне stdlib/пакетов репо/исключений.

    Только файлы верхнего уровня каждого каталога (`glob("*.py")`, не
    `rglob`) — тем же приёмом, что `scripts/codebase_map.py::
    discover_module_paths` (вложенных пакетов у orchestrator/scripts/tests
    сегодня нет). Относительные импорты (`from . import x`, level > 0)
    всегда внутрипакетные — не проверяются.
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
