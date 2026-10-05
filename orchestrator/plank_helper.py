"""Помощник планки `_pult.py`: пульт выкладывает его рядом с планкой задачи.

Исходный текст помощника планки приёмки (SPEC 01M44EP4Q927DJXVX9YMMZ0B7V).
Выкладка планки (`orchestrator/acceptance.py::materialize_from_branch`,
`::materialize_files`) кладёт копию этого файла под именем `_pult.py` в
`tasks/<id>/acceptance_tests/` рабочей копии кода и подставляет в блок
значений выкладки id задачи, корень рабочей копии, репозиторий и ревизию
ссылки документов, базу диффа и её источник. Планка импортирует `_pult` как
соседний модуль и получает:

- `artifact_text(name)` — текст `tasks/<id>/<name>` из ссылки документов
  задачи ровно той ревизии, с которой выложена планка; файла нет — `None`,
  сбой git — `ArtifactReadError`;
- `branch_diff()` — закоммиченный дифф задачи от базы до HEAD рабочей копии;
- `changed_paths()` — пути задачи по правилу гейта зон: пути закоммиченного
  диффа от базы до HEAD плюс неотслеживаемые файлы рабочей копии, кроме
  собственного каталога задачи `tasks/<id>/`; незакоммиченные правки
  отслеживаемых файлов не включаются;
- `apply_check(diff, reverse=False)` — применимость unified-диффа к дереву
  HEAD рабочей копии, без изменения рабочей копии и индекса.

Только стандартная библиотека и ни одного импорта пакета `orchestrator`:
планка исполняется в рабочей копии, код которой и есть предмет задачи, —
её `orchestrator` может быть сломан, а `config.ROOT` планки не знает ни
`state.db`, ни клона проекта. Базу диффа помощник сам не вычисляет: пульт
считает её при выкладке теми же `gitcmd.diff_base`/`diff_base_source`, что
гейт зон.
"""
import os
import subprocess
import tempfile
from pathlib import Path

# --- значения выкладки: подставляет пульт (acceptance._plank_helper_text) ---
TASK_ID = ""
CODE_ROOT = ""
DOCS_REPO = ""
DOCS_REVISION = ""
DIFF_BASE = None
DIFF_BASE_SOURCE = ""
# --- конец значений выкладки ---

# Переменные, которыми git находит репозиторий и индекс в обход `-C`: под
# хуком git или чужой обвязкой они указывали бы не на тот репозиторий.
_REPO_LOCATING_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                      "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
                      "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX")


class GitError(RuntimeError):
    """git не ответил на вопрос помощника (команда, код возврата, stderr)."""


class ArtifactReadError(GitError):
    """Сбой git при чтении артефакта — не то же, что «файла нет» (`None`)."""


def _git(repo, *args: str, index_file: str | None = None,
         error=GitError) -> str:
    """stdout `git -C <repo> <args>`; ненулевой код — `error`.

    Подъём вверх по каталогам запрещён (`GIT_CEILING_DIRECTORIES`): у
    репозитория без `.git` git иначе молча ответил бы из объемлющего."""
    if not repo:
        raise error(f"репозиторий не подставлен при выкладке: git {' '.join(args)}")
    env = {k: v for k, v in os.environ.items() if k not in _REPO_LOCATING_ENV}
    env["GIT_CEILING_DIRECTORIES"] = str(Path(repo).parent)
    if index_file:
        env["GIT_INDEX_FILE"] = index_file
    try:
        res = subprocess.run(["git", "-C", str(repo), *args], env=env,
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
    except OSError as exc:
        raise error(f"git {' '.join(args)}: {exc}") from exc
    if res.returncode != 0:
        raise error(f"git {' '.join(args)} в {repo} вернул {res.returncode}: "
                    f"{res.stderr.strip()}")
    return res.stdout


def _base() -> str:
    if not DIFF_BASE:
        raise GitError("база диффа не определена при выкладке "
                       "(git не ответил на merge-base)")
    return DIFF_BASE


def artifact_text(name: str) -> str | None:
    """Текст `tasks/<TASK_ID>/<name>` ревизии ссылки документов, с которой
    выложена планка (`DOCS_REVISION`), — не головы ссылки: коммит в ссылку
    после выкладки ответ не меняет. Файла в этой ревизии нет — `None`; сбой
    git (репозиторий ссылки недоступен, ревизии нет) — `ArtifactReadError`."""
    if not DOCS_REVISION:
        raise ArtifactReadError("ревизия ссылки документов не определена "
                                "при выкладке")
    rel = f"tasks/{TASK_ID}/{name}"
    listing = _git(DOCS_REPO, "ls-tree", "-z", DOCS_REVISION, "--", rel,
                   error=ArtifactReadError)
    for entry in listing.split("\0"):
        meta, _, path = entry.partition("\t")
        fields = meta.split()
        if path == rel and len(fields) == 3 and fields[1] == "blob":
            return _git(DOCS_REPO, "cat-file", "blob", fields[2],
                        error=ArtifactReadError)
    return None


def branch_diff() -> str:
    """Закоммиченный дифф задачи: от `DIFF_BASE` до HEAD рабочей копии.
    Неотслеживаемые и незакоммиченные правки в него не входят."""
    return _git(CODE_ROOT, "diff", "--no-color", "--no-ext-diff", _base(), "HEAD")


def changed_paths() -> list[str]:
    """Пути задачи по правилу гейта зон: пути закоммиченного диффа от
    `DIFF_BASE` до HEAD плюс неотслеживаемые файлы рабочей копии, кроме
    собственного каталога задачи `tasks/<TASK_ID>/` (там лежит выложенная
    планка); изменённые, но незакоммиченные отслеживаемые файлы не
    включаются."""
    committed = [p for p in _git(CODE_ROOT, "diff", "--name-only", "-z",
                                 _base(), "HEAD").split("\0") if p]
    task_dir = f"tasks/{TASK_ID}/"
    untracked = [p for p in _git(CODE_ROOT, "ls-files", "--others",
                                 "--exclude-standard", "-z").split("\0")
                 if p and not p.startswith(task_dir)]
    return committed + [p for p in untracked if p not in committed]


def apply_check(diff: str, reverse: bool = False) -> str:
    """Применимость unified-диффа `diff` к дереву HEAD рабочей копии.
    Пустая строка — git согласился; иначе его ответ. `reverse=True` —
    обратное наложение: правка уже в дереве HEAD.

    Дифф подаётся git файлом, как в `plan_appendix.git_apply` пульта;
    проверка идёт во временном индексе, собранном из HEAD (`--cached`), —
    файлы рабочей копии и её индекс не трогаются, а грязная правка рабочего
    дерева ответ не меняет."""
    with tempfile.TemporaryDirectory(prefix="pult-apply-check-") as tmp:
        patch = Path(tmp) / "appendix.diff"
        patch.write_text(diff, encoding="utf-8")
        index = str(Path(tmp) / "index")
        flags = ["--reverse"] if reverse else []
        try:
            _git(CODE_ROOT, "read-tree", "HEAD", index_file=index)
            _git(CODE_ROOT, "apply", "--check", "--cached", *flags, str(patch),
                 index_file=index)
        except GitError as exc:
            return str(exc)
    return ""
