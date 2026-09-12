"""Общая песочница приёмочных тестов задачи 01M2B6JS2BZNBW9WSHT1RPFXTE
(note: окно тишины — удержание строк копилки во время живых циклов).

`NoteSandbox` расширяет `tests.sandbox.RealGitSandbox` (`self.root` —
пульт, настоящий git-репозиторий с `main`) тем же приёмом, что несли
`_sandbox.py` предыдущих задач `note` (01M1VBEHTDYPK3E4RRFHWYYYW3,
01M290Q1VK21V0X2VKC7WS6K1K, не переиспользованы напрямую — те задачи
не оставили общего модуля вне своего `tasks/<id>/acceptance_tests/`):
локальный bare-репозиторий `self.origin` (роль `origin/main` пульта) и
синтетический `docs/backlog.md` с тремя разделами.

Добавка этой задачи — помощники для заведения «окна тишины» через БД
(`store.create_schema` уже вызван `RealGitSandbox.setUp`, схема пуста):
`insert_task_in_state` заводит строку задачи в заданном состоянии
напрямую (минуя FSM — нужно только значение `state`), `set_live_merge_
lock`/`set_dead_merge_lock` заводят держателя мьютекса merge-окна с
heartbeat/pid, дающими предсказуемый исход `merge_lock._holder_is_dead`.

Ключи строк фикстуры подобраны так, чтобы ни один не был подстрокой
другого (`_iter_matching_rows` ищет по `key in line`).
"""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

# Захвачено ДО того, как любой тест патчит `subprocess.run`.
_REAL_RUN = subprocess.run

SECTION_HEADINGS = {
    "копилка": "## Копилка",
    "бэклог": "## Бэклог",
    "очередь": "## Очередь Оператора",
}

BACKLOG_TEXT = """# Копилка и бэклог

## Копилка

| П | Дата | Наблюдение | Где |
|---|---|---|---|
| 1 | 01.01 | старое наблюдение УНИКАЛЬНЫЙКЛЮЧ | orchestrator/x.py |
| 2 | 01.01 | наблюдение ПОВТОРКЛЮЧ один | orchestrator/y.py |
| 2 | 01.01 | наблюдение ПОВТОРКЛЮЧ два | orchestrator/z.py |
| 1 | 01.01 | наблюдение ДРУГОЙКЛЮЧ | orchestrator/w.py |

## Бэклог

| П | Кандидат | Суть | Рамка | Зоны | Условие старта | Заметка |
|---|---|---|---|---|---|---|
| 1 | Кандидат A | Суть A | $10 | orchestrator/a.py | сразу | — |

## Очередь Оператора

| П | Действие |
|---|---|
| 1 | Действие A |
"""

# Состояния окна тишины из AC-1 SPEC — буквально те же пять, не
# `zone_lock.BLOCKING_STATES` (тот несёт ШЕСТЬ состояний, включая
# `escalated`, который окно тишины сознательно не занимает — см.
# test_ac5).
SILENCE_WINDOW_STATES = ("in_dev", "verifying", "review", "acceptance",
                        "merge_gate")


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


class NoteSandbox(RealGitSandbox):
    """`self.root` — пульт с одним коммитом `docs/backlog.md` поверх
    `init` (`RealGitSandbox`), запушенным в локальный bare `self.origin`,
    и пустой БД (`store.create_schema` без задач и без держателя
    `merge_locks`) — окно тишины закрыто по умолчанию, пока тест сам не
    заведёт задачу нужного состояния/держателя мьютекса."""

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

    def origin_log_subjects_since(self, base: str) -> list:
        """Сообщения коммитов `base..HEAD` от СТАРОГО к НОВОМУ — порядок
        применения, для проверки очерёдности допуша (AC-9)."""
        res = self.origin_run("log", "--reverse", "--format=%s",
                              f"{base}..{config.MAIN_BRANCH}")
        return [ln for ln in res.stdout.splitlines() if ln]

    def insert_task_in_state(self, state: str, task_id: str = "T-WIN") -> None:
        """Задача target'а `self` (участвует в определении окна тишины,
        AC-1) в заданном состоянии — заводится прямо в БД, минуя FSM:
        сценарию нужно только значение `state` строки."""
        store.insert_task(store.db(), task_id, "окно тишины", state,
                          f"task/{task_id}", config.DEFAULT_TARGET, 10.0)

    def set_live_merge_lock(self, task_id: str = "T-LOCK",
                            session_id: str = "s-live") -> None:
        """Живой держатель мьютекса merge-окна: heartbeat только что,
        свой pid, свой хост — тот же признак живости, на который
        `merge_lock._holder_is_dead` отвечает `False`."""
        store.set_merge_lock(store.db(), task_id, session_id, os.getpid(),
                             socket.gethostname(), store.now())
