"""Общие константы/хелперы планки задачи 01M2CN42RV0EBBP7HS4HP2VNY1
(рефакторинг canary.py: вынос запечатанного пула в pool_seal.py).
"""
import ast
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# ГОЛОВА ветки задачи на момент написания этой планки (до правок
# разработчика, `git log -1` на старте шага test_author) — стабильная
# точка отсчёта «тела функций ДО переноса» (требование 1, AC-1):
# разработчик коммитит ПОВЕРХ неё (репозиторий не допускает rebase),
# поэтому `git show BASE_COMMIT:<путь>` остаётся разрешимым сколь
# угодно долго внутри истории этой ветки.
BASE_COMMIT = "812c9064edd802bc64546a209742df550c586892"

# Тринадцать имён требования 1 — единственный источник истины для
# состава переноса во всех тестах планки.
POOL_SEAL_NAMES = (
    "_pool_dir",
    "sealed_path",
    "guids_path",
    "_mac_key",
    "_secret_fd",
    "_hmac_tag_hex",
    "_openssl_encrypt",
    "_openssl_decrypt",
    "_serialize_pool",
    "_deserialize_pool",
    "_authorized_pool_payload",
    "restore_pool_if_missing",
    "pool_drift_warning",
    "cmd_pool_seal",
)


def git_show(rel_path: str, commit: str = BASE_COMMIT) -> str:
    """Текст файла `rel_path` на коммите `commit` — читает объект git
    напрямую (`git show <sha>:<путь>`), без checkout и без сети."""
    proc = subprocess.run(
        ["git", "show", f"{commit}:{rel_path}"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return proc.stdout


def top_level_def_source(source_text: str, name: str):
    """Точный исходный текст функции верхнего уровня `name` (включая
    декораторы, если есть) — построчный срез по номерам строк AST, не
    `ast.get_source_segment`: тот не захватывает декораторы для функций
    (начиная с Python 3.8 `node.lineno` указывает на строку `def`, не
    на первый декоратор) — `_secret_fd` несёт `@contextmanager` и без
    ручного расширения диапазона сравнение тела потеряло бы декоратор.
    Возвращает `None`, если функция с таким именем не найдена верхним
    уровнем модуля.
    """
    tree = ast.parse(source_text)
    lines = source_text.splitlines(keepends=True)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.name == name:
            start = (node.decorator_list[0].lineno
                    if node.decorator_list else node.lineno)
            return "".join(lines[start - 1:node.end_lineno])
    return None


def dotted_call_names(source_text: str) -> set:
    """Множество точечных обращений вида `a.b.c` в позиции вызываемого
    (`a.b.c(...)`) исходника — сравнение по `ast.unparse` самого
    выражения перед скобками вызова, устойчиво к переносам строк и
    форматированию."""
    tree = ast.parse(source_text)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            try:
                names.add(ast.unparse(node.func))
            except Exception:
                continue
    return names


def run_unittest_modules(*module_names: str, timeout: int = 300):
    """Прогон именованных модулей `tests.*` отдельным процессом
    `python -m unittest` — та же техника, что и залоченная планка
    01M1TKP08PKB87K8772H69GCXJ (`test_ac6_existing_suite_still_green.py`)
    для «весь названный SPEC поимённо набор проходит»."""
    return subprocess.run(
        [sys.executable, "-m", "unittest", *module_names],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)
