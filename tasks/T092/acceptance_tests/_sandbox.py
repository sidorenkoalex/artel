"""Общая песочница приёмочных тестов T092 (не test_*.py — не подхватывается
unittest discover напрямую, только импортом из test_ac*.py).

`report` — read-only команда (SPEC требование 9, 11): читает `state.db`
и журнал ТОЛЬКО через `orchestrator/store.py`, git не трогает. Поэтому
фикстуры здесь заводят задачи и журнальные записи напрямую через
`store.insert_task`/`store.update_task`/`store.journal` (тот же приём,
что `tasks/T073/acceptance_tests/test_ac4_prune_dry_run_default.py`
использует для alerts) — без настоящего git-репозитория и без
`catalog.cmd_new` (которая заводит worktree/ветку, ненужные команде
`report`).

Интерфейс команды нигде не зафиксирован SPEC буквально (только «новый
модуль, например `orchestrator/report.py`», требование 1) — тесты здесь
предполагают `orchestrator.report.cmd_report()` без аргументов (сама
команда `report` в CLI зовётся без id задачи, AC-1), по образцу уже
существующих одноимённых команд-модулей (`prune.cmd_prune`,
`doctor.cmd_doctor`).

Числовые фикстуры (бюджеты, суммы, счётчики) намеренно используют
нетипичные для остального вывода значения (не 0/1/10/50 — совпадающие
с `config.DEFAULT_BUDGET_USD`, лимитами и т.п.), чтобы подстрочный поиск
в HTML не ловил случайное совпадение с посторонним числом на странице.
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class ReportSandboxTest(TmpRootTest):
    """`config.DB` во временном каталоге, схема заведена `cmd_init`."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        from orchestrator import report  # noqa: E402 — красное до реализации
        self.report = report

    # ------------------------------------------------------------ фикстуры

    def mk_task(self, task_id: str, title: str, state: str, *,
               budget_usd: float = 1.0, spent_usd: float = 0.0,
               review_iters: int = 0, escalated_from: str | None = None,
               accept_rejects: int = 0) -> str:
        conn = store.db()
        store.insert_task(conn, task_id, title, state,
                          branch=f"task/{task_id}-fixture",
                          target=config.DEFAULT_TARGET, budget_usd=budget_usd)
        fields = {}
        if spent_usd:
            fields["spent_usd"] = spent_usd
        if review_iters:
            fields["review_iters"] = review_iters
        if escalated_from is not None:
            fields["escalated_from"] = escalated_from
        if accept_rejects:
            fields["accept_rejects"] = accept_rejects
        if fields:
            store.update_task(conn, task_id, **fields)
        return task_id

    def mk_step(self, task_id: str, actor: str, action: str,
               detail: str = "", days_ago: float | None = None) -> None:
        conn = store.db()
        store.journal(conn, task_id, actor, action, detail)
        if days_ago is not None:
            ts = time.strftime("%Y-%m-%d %H:%M:%SZ",
                               time.gmtime(time.time() - days_ago * 86400))
            row = conn.execute(
                "SELECT id FROM steps WHERE task_id=? ORDER BY id DESC "
                "LIMIT 1", (task_id,)).fetchone()
            conn.execute("UPDATE steps SET ts=? WHERE id=?", (ts, row["id"]))
            conn.commit()

    def mk_alert(self, kind: str, source: str, message: str,
                target: str | None = None):
        conn = store.db()
        alerts.raise_alert(conn, target, kind, source, message)
        return conn.execute(
            "SELECT id FROM alerts WHERE message=?", (message,)).fetchone()["id"]

    # ------------------------------------------------------------ запуск

    def run_report(self):
        """Прогоняет `report.cmd_report()`, возвращает (stdout, путь,
        текст сгенерированного файла); путь — из множества *.html,
        появившихся под `self.root` за вызов (см. докстринг модуля)."""
        before = set(self.root.rglob("*.html"))
        out = self.capture(self.report.cmd_report)
        after = set(self.root.rglob("*.html"))
        new_files = sorted(after - before)
        return out, new_files, before, after

    def html_files(self):
        return set(self.root.rglob("*.html"))

    def all_files(self):
        return set(self.root.rglob("*")) - {p for p in self.root.rglob("*")
                                            if p.is_dir()}


# ------------------------------------------------------------ текстовые утилиты

def scope(html: str, needle: str, before_chars: int = 500,
         after_chars: int = 2000) -> str | None:
    """Окно текста вокруг ПЕРВОГО вхождения `needle` — не привязывается
    к конкретной разметке (классам/тегам), только к самому факту, что
    нужное поле расположено где-то рядом с искомым текстом на странице."""
    idx = html.find(needle)
    if idx == -1:
        return None
    start = max(0, idx - before_chars)
    end = min(len(html), idx + len(needle) + after_chars)
    return html[start:end]


def all_scopes(html: str, needle: str, before_chars: int = 500,
              after_chars: int = 2000) -> list:
    """Как `scope`, но для КАЖДОГО вхождения `needle` (задача может быть
    упомянута не один раз — борд, карточка, очередь гейтов)."""
    out = []
    pos = 0
    while True:
        idx = html.find(needle, pos)
        if idx == -1:
            return out
        start = max(0, idx - before_chars)
        end = min(len(html), idx + len(needle) + after_chars)
        out.append(html[start:end])
        pos = idx + len(needle)


def count_occurrences(html: str, needle: str) -> int:
    return html.count(needle)


def label_chunks(html: str, labels) -> list:
    """Разбивает `html` по вхождениям любой строки из `labels` (сохраняя
    метку), возвращая список (метка, текст_до_следующей_метки).

    Используется, чтобы проверить, что рядом с меткой состояния X в
    документе не всплывает идентификатор задачи, которая на самом деле
    в состоянии Y — то есть что борд действительно группирует, а не
    просто перечисляет всё подряд (AC-3), независимо от конкретной
    HTML-разметки (классов/тегов), которую SPEC не фиксирует.
    """
    pattern = re.compile("(" + "|".join(re.escape(lbl) for lbl in labels) + ")")
    parts = pattern.split(html)
    chunks = []
    for i in range(1, len(parts), 2):
        label = parts[i]
        text = parts[i + 1] if i + 1 < len(parts) else ""
        chunks.append((label, text))
    return chunks
