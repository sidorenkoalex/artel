"""Общий разбор дублей тестовых хелперов для приёмочных тестов T089.

Не `test_*.py` — `scripts/guard.py::scan_acceptance_tests`/
`scan_redness_markers` читают только `test_*.py` (SPEC T081/T064), тот же
приём, что `_sandbox.py`/`_mutex_sandbox.py` в других задачах: сюда не
нужна ни AC-разметка, ни маркер красноты, это просто общий код для
файлов `test_ac*.py` рядом.
"""
import re
import subprocess
from pathlib import Path

# Сигнатуры хелперов, названных SPEC T089 (требование 1): байт-в-байт
# определение верхнего уровня (без отступа — не вложенный класс/функция).
HELPER_PATTERNS = {
    "_ts_ago": re.compile(r"^def _ts_ago\b", re.MULTILINE),
    "FakeStream": re.compile(r"^class FakeStream\b", re.MULTILINE),
    "SpyRun": re.compile(r"^class SpyRun\b", re.MULTILINE),
    "RealGitSandbox": re.compile(r"^class RealGitSandbox\b", re.MULTILINE),
    "_dead_pid": re.compile(r"^def _dead_pid\b", re.MULTILINE),
}

# Каталоги, которые не входят в кодовую базу репозитория (.gitignore).
_SKIP_PARTS = {".git", ".artel", "__pycache__"}


def repo_root() -> Path:
    """Корень репозитория — воркт-дерево задачи (то же дерево, в котором
    гейт acceptance гоняет `python3 -m unittest discover`,
    `orchestrator/acceptance.py::run` с `cwd=config.ROOT`)."""
    return Path(__file__).resolve().parents[3]


def _walk_py_files(base: Path, recursive: bool):
    """`*.py` под `base`, кроме гитигнорнутых каталогов — по частям пути
    ОТНОСИТЕЛЬНО `base`, не абсолютного пути: воркт-дерево задачи само
    лежит внутри `.artel/worktrees/<id>/`, абсолютный путь несёт `.artel`
    как предок репозитория, а не как гитигнорнутое содержимое внутри
    него — фильтр по абсолютным `p.parts` резал бы вообще все файлы."""
    if not base.is_dir():
        return []
    it = base.rglob("*.py") if recursive else base.glob("*.py")
    return sorted(
        p for p in it
        if not (_SKIP_PARTS & set(p.relative_to(base).parts)))


def all_py_files(root: Path) -> list:
    return _walk_py_files(root, recursive=True)


def tests_dir_py_files(root: Path) -> list:
    return _walk_py_files(root / "tests", recursive=False)


def acceptance_test_dirs(root: Path) -> list:
    """`tasks/*/acceptance_tests` существующих задач, отсортировано."""
    return sorted((root / "tasks").glob("*/acceptance_tests"))


def task_id_of(acceptance_dir: Path) -> str:
    return acceptance_dir.parent.name


def scan_definitions(paths) -> list:
    """[(path, helper_name), ...] — верхнеуровневые определения хелперов
    из HELPER_PATTERNS, найденные в файлах `paths`."""
    hits = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for name, pattern in HELPER_PATTERNS.items():
            if pattern.search(text):
                hits.append((p, name))
    return hits


def _git(root: Path, *args: str) -> str:
    res = subprocess.run(["git", *args], cwd=root,
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} упал: {res.stderr}")
    return res.stdout


def open_task_ids(root: Path) -> set:
    """ID задач с ЛОКАЛЬНОЙ веткой `task/t<id>-...` — задача ещё не
    закрыта (закрытие удаляет только локальную ветку,
    `orchestrator/cleanup.py::drop_merged_task_branch`; ветка на origin
    остаётся, поэтому именно локальные ветки, не `-a`)."""
    out = _git(root, "branch", "--format=%(refname:short)")
    ids = set()
    for line in out.splitlines():
        m = re.match(r"task/t(\d+)-", line.strip(), re.IGNORECASE)
        if m:
            ids.add("T" + m.group(1))
    return ids


def resolve_base_ref(root: Path) -> str:
    """Ветка `main` — база сравнения диффа этой задачи. Локальная `main`
    предпочтительна (гейт acceptance гоняет тесты в полноценном локальном
    дереве пульта/воркт-дерева, не мелком CI-чекауте), `origin/main` —
    запасной вариант."""
    for ref in ("main", "origin/main"):
        res = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref],
                             cwd=root, capture_output=True, text=True)
        if res.returncode == 0:
            return ref
    raise RuntimeError("ни main, ни origin/main не резолвятся")


def changed_files(root: Path, base_ref: str) -> list:
    out = _git(root, "diff", "--name-only", f"{base_ref}...HEAD")
    return [line for line in out.splitlines() if line]
