"""Общая песочница приёмочных тестов задачи 01M1VBEHTDYPK3E4RRFHWYYYW3
(команда `note`): `NoteSandbox` расширяет `tests.sandbox.RealGitSandbox`
(`self.root` — пульт, настоящий git-репозиторий с `main`) добавкой
локального bare-репозитория `self.origin`, играющего роль `origin/main`
пульта, и синтетического `docs/backlog.md` с тремя разделами.

Числа колонок разделов синтетического файла (4/7/2) НАМЕРЕННО не
совпадают с боевыми (5/6/3 — `docs/backlog.md` реального пульта,
SPEC.md «Материалы»): требование 2 SPEC явно требует читать число ячеек
шапки таблицы РАЗДЕЛА из фактического файла, а не жёстко закодированным
списком {"копилка": 5, ...} — с боевыми числами такая жёсткая
подстановка прошла бы тесты незамеченной, с намеренно другими числами
она их проваливает.

`PushSpy` — перехватчик `subprocess.run` (патчится глобально атрибутом
модуля `subprocess`, не только `gitcmd.subprocess.run`: код `notes.py`
не обязан звать git ИМЕННО через `gitcmd`, а тесты retry/hold обязаны
перехватывать push независимо от точки вызова) — считает попытки push
и, если задан `on_before_push`, зовёт колбэк ПЕРЕД каждой настоящей
попыткой push. Колбэки используют `_inject_foreign_commit`, которая
пушит посторонний коммит в `self.origin` В ОБХОД пульта, имитируя гонку
non-fast-forward (внешний коммит уходит в origin строго между fetch и
push команды `note`) — тот же приём, что `tests/test_artifact_branch_
push.py::PushNonFastForwardTest`, только воспроизводимый ПОСЛЕ каждого
push-вызова самой команды, а не один раз до неё.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

# Захвачено ДО того, как любой тест патчит `subprocess.run` — используется
# `PushSpy`/`_inject_foreign_commit` для настоящих git-вызовов, минуя
# собственный перехват (иначе колбэк `on_before_push`, сам зовущий git
# push постороннего коммита, ушёл бы в бесконечную рекурсию через
# патченный `subprocess.run`).
_REAL_RUN = subprocess.run

SECTION_HEADINGS = {
    "копилка": "## Копилка",
    "бэклог": "## Бэклог",
    "очередь": "## Очередь Оператора",
}

# Число ячеек шапки КАЖДОГО раздела синтетического backlog ниже — для
# читаемости тестов, само число нигде не подставляется в код `notes.py`.
HEADER_COLUMNS = {"копилка": 4, "бэклог": 7, "очередь": 2}

BACKLOG_TEXT = """# Копилка и бэклог

## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое наблюдение УНИКАЛЬНЫЙКЛЮЧ | orchestrator/x.py |
| 2 | 01.01 | наблюдение ПОВТОРКЛЮЧ один | orchestrator/y.py |
| 2 | 01.01 | наблюдение ПОВТОРКЛЮЧ два | orchestrator/z.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |

## Очередь Оператора

| П | Действие |
|---|---|
| 1 | Действие A |
"""


def row_cells(line: str) -> list:
    """Ячейки строки таблицы markdown (без внешних `|`), с обрезкой
    пробелов — тот же формат, что и `--text` команды `note`."""
    stripped = line.strip()
    assert stripped.startswith("|") and stripped.endswith("|"), stripped
    return [c.strip() for c in stripped[1:-1].split("|")]


def section_rows(text: str, heading: str) -> list:
    """Строки таблицы раздела `heading` по порядку: `[0]` — шапка,
    `[1]` — разделитель, `[2:]` — строки данных сверху вниз."""
    lines = text.splitlines()
    start = lines.index(heading)
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        if line.strip().startswith("|"):
            rows.append(line)
    return rows


def _is_push_cmd(cmd) -> bool:
    """`True` — `cmd` это `git [-C <path>] push ...`, сквозь ведущие `-C`
    (тот же пропуск, что `tests.sandbox.SpyRun.git_subcommands`)."""
    if not isinstance(cmd, (list, tuple)) or not cmd or cmd[0] != "git":
        return False
    i = 1
    while i + 1 < len(cmd) and cmd[i] == "-C":
        i += 2
    return i < len(cmd) and cmd[i] == "push"


class PushSpy:
    """Подмена `subprocess.run`: считает попытки `git push`, делегируя
    исполнение настоящему `subprocess.run` (`_REAL_RUN`) всегда — в
    отличие от плотницких заглушек `tests/sandbox.py`, здесь нужен РЕАЛЬНЫЙ
    git на каждом вызове, перехват только считает и, опционально, вызывает
    `on_before_push(номер_попытки)` до настоящего push."""

    def __init__(self, on_before_push=None):
        self.push_calls = 0
        self.on_before_push = on_before_push

    def __call__(self, cmd, *args, **kwargs):
        if _is_push_cmd(cmd):
            self.push_calls += 1
            if self.on_before_push is not None:
                self.on_before_push(self.push_calls)
        return _REAL_RUN(cmd, *args, **kwargs)


def _inject_foreign_commit(bare_origin: str, filename: str) -> None:
    """Пушит посторонний коммит (новый файл `filename`, не
    `docs/backlog.md`) прямо в `bare_origin` из отдельного scratch-клона —
    в обход `self.root`/команды `note`, имитируя Оператора/другую сессию,
    коммитящую в origin в момент между fetch и push команды `note`."""
    scratch = tempfile.mkdtemp()
    try:
        _REAL_RUN(["git", "clone", "-q", bare_origin, scratch], check=True)
        _REAL_RUN(["git", "-C", scratch, "config", "user.email",
                  "operator@example.invalid"], check=True)
        _REAL_RUN(["git", "-C", scratch, "config", "user.name", "operator"],
                 check=True)
        (Path(scratch) / filename).write_text("внешний коммит\n", encoding="utf-8")
        _REAL_RUN(["git", "-C", scratch, "add", "-A"], check=True)
        _REAL_RUN(["git", "-C", scratch, "commit", "-q", "-m",
                  f"внешний коммит {filename}"], check=True)
        _REAL_RUN(["git", "-C", scratch, "push", "-q", "origin",
                  config.MAIN_BRANCH], check=True)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


class NoteSandbox(RealGitSandbox):
    """`self.root` — пульт с одним коммитом `docs/backlog.md` поверх
    `init` (`RealGitSandbox`), запушенным в локальный bare `self.origin`."""

    def setUp(self):
        super().setUp()
        self.origin = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.origin, ignore_errors=True)
        self.git("init", "-q", "--bare", self.origin)
        self.git("remote", "add", "origin", self.origin)
        docs = self.root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "backlog.md").write_text(BACKLOG_TEXT, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "backlog")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def origin_run(self, *args) -> subprocess.CompletedProcess:
        return _REAL_RUN(["git", "-C", self.origin, *args],
                         capture_output=True, text=True)

    def origin_head(self) -> str:
        res = self.origin_run("rev-parse", config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_backlog(self) -> str:
        res = self.origin_run("show", f"{config.MAIN_BRANCH}:docs/backlog.md")
        assert res.returncode == 0, res.stderr
        return res.stdout

    def origin_commit_message(self, sha: str) -> str:
        res = self.origin_run("log", "-1", "--format=%s", sha)
        return res.stdout.strip()

    def origin_changed_files(self, a: str, b: str) -> list:
        res = self.origin_run("diff", "--name-only", a, b)
        return [ln for ln in res.stdout.splitlines() if ln]

    def origin_commit_count(self, a: str, b: str) -> int:
        res = self.origin_run("rev-list", "--count", f"{a}..{b}")
        return int(res.stdout.strip())

    def break_origin_remote(self) -> None:
        """Подменяет `origin` несуществующим локальным путём — тот же
        класс отказа push (git не может достучаться до `origin`), что и
        недоступный по сети хост, детерминированно и без реальной сети."""
        self.git("remote", "set-url", "origin",
                 str(Path(self.origin) / "does-not-exist"))

    def restore_origin_remote(self) -> None:
        self.git("remote", "set-url", "origin", self.origin)
