"""Общие хелперы приёмочных тестов задачи 01M2CN465WEDCF6D77V37FJ82E
(фикс утечки тестов в настоящий пульт: WORKTREES в песочнице
test_git_fixation).

Git-хелперы читают состояние РЕАЛЬНОГО репозитория этого рабочего
каталога (worktree задачи) — тот же приём, что `tests/test_git_fixation.
py::RealPultGitTest` применяет к настоящему `config.ROOT`: критерии
AC-4/AC-5 говорят буквально о дифе КОДОВОЙ ветки задачи относительно
`main`, это не воспроизвести песочницей с фейковым git.
"""
import importlib
import pkgutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def merge_base(ref: str = "main") -> str:
    """sha точки расхождения ветки задачи с `ref` (по умолчанию `main`)."""
    res = subprocess.run(["git", "merge-base", ref, "HEAD"], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True)
    return res.stdout.strip()


def diff_since_main(*pathspecs: str, unified: int = None,
                    diff_filter: str = None) -> str:
    """`git diff <merge-base>..рабочее дерево` — включает и закоммиченные,
    и незакоммиченные правки ветки задачи (единая точка сверки для AC-4/5)."""
    args = ["git", "diff"]
    if unified is not None:
        args.append(f"--unified={unified}")
    if diff_filter:
        args.append(f"--diff-filter={diff_filter}")
    args.append(merge_base())
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    res = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True,
                         check=True)
    return res.stdout


def changed_paths_since_main(*pathspecs: str, diff_filter: str = None) -> list:
    args = ["git", "diff", "--name-only"]
    if diff_filter:
        args.append(f"--diff-filter={diff_filter}")
    args.append(merge_base())
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    res = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True,
                         check=True)
    return [line for line in res.stdout.splitlines() if line]


def discover_custom_patched_attrs_classes():
    """Все TestCase-подклассы во всех модулях `tests/`, задающие
    СОБСТВЕННЫЙ (не унаследованный) `PATCHED_ATTRS` — дедуп по identity
    класса (алиасы вида `TmpRootTest = _FooTmpRootTest` в одном модуле не
    должны считаться дважды). Имя класса — `cls.__name__` (имя из
    `class`-инструкции), НЕ имя переменной, под которым класс найден в
    `vars(module)`: модуль часто СНАЧАЛА импортирует `TmpRootTest` из
    `tests.sandbox`, а ПОТОМ переопределяет то же имя алиасом на свой
    класс (`TmpRootTest = _FooTmpRootTest`) — такое переприсваивание
    существующего ключа не двигает его позицию в словаре модуля, и при
    обходе `vars(module)` алиас `TmpRootTest` находится РАНЬШЕ
    `_FooTmpRootTest`, хотя оба — один и тот же объект класса.
    Возвращает список (имя_модуля, cls.__name__, класс)."""
    import tests as tests_pkg

    seen_ids = set()
    result = []
    for modinfo in pkgutil.iter_modules(tests_pkg.__path__,
                                        tests_pkg.__name__ + "."):
        module = importlib.import_module(modinfo.name)
        for obj in vars(module).values():
            if not (isinstance(obj, type) and issubclass(obj, unittest.TestCase)
                    and "PATCHED_ATTRS" in obj.__dict__):
                continue
            if id(obj) in seen_ids:
                continue
            seen_ids.add(id(obj))
            result.append((modinfo.name, obj.__name__, obj))
    return result
