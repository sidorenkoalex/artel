"""Команда `prune`: исполняет retention-политику docs/retention.md для
`.artel/logs/` и `alerts` (tasks/T073/SPEC.md, требование 3).

Не часть уборки `kill`/`done` (`orchestrator/cleanup.py`) и не реагирует
на переход FSM ни одной задачи — отдельная, явно вызываемая Оператором
операция над всем `.artel/logs/`/`alerts` сразу (инвариант 16,
docs/invariants.md, не ослабляется: уборка ОДНОЙ задачи логи по-прежнему
не трогает — уточнение см. tasks/T073/PLAN.md, «Подход», п.5).

dry-run по умолчанию (`execute=False`): план и факт считаются одним и
тем же расчётом кандидатов — различается только то, исполняется ли
действие (удаление файла / `store.archive_alert`), отчёт печатает
конкретные имена в обоих режимах (AC-7).
"""
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config, store


_CLOSE_ACTIONS = ("state -> done", "state -> killed")


def _close_ts(conn, task_id: str) -> str | None:
    """Момент закрытия задачи из журнала (`store.now()`, `%Y-%m-%d
    %H:%M:%SZ` — ширина фиксирована, лексикографическое сравнение строк
    совпадает с хронологическим); `None` — задача ещё не закрыта."""
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] in _CLOSE_ACTIONS:
            return row["ts"]
    return None


def _kept_task_ids(conn) -> set:
    """id последних `config.LOG_RETENTION_KEEP_TASKS` ЗАКРЫТЫХ задач по
    дате закрытия из журнала (SPEC T094, требование 5, AC-6) — не по
    числовому номеру: ULID id не несёт сравнимого по величине номера
    (требование 2), а `Tnnn`-задачи участвуют в этом же датовом отборе,
    не в отдельном отборе «последние N по номеру». Ещё не закрытая
    задача (нет записи `state -> done`/`state -> killed`) не участвует в
    датовом ранжировании вовсе — её логи retention не трогает независимо
    от возраста, тем же принципом, что и раньше для «последних N»."""
    closed: list[tuple[str, str]] = []
    open_ids: set = set()
    for row in store.all_tasks(conn):
        ts = _close_ts(conn, row["id"])
        if ts is None:
            open_ids.add(row["id"])
        else:
            closed.append((ts, row["id"]))
    closed.sort(reverse=True)
    kept_closed = {task_id for _, task_id in closed[:config.LOG_RETENTION_KEEP_TASKS]}
    return open_ids | kept_closed


def _log_candidates(conn) -> list:
    """Файлы `.artel/logs/*.log`, ОДНОВРЕМЕННО старше
    `config.LOG_RETENTION_DAYS` И вне «последних N» (AC-5)."""
    if not config.LOGS.is_dir():
        return []
    kept = _kept_task_ids(conn)
    cutoff = time.time() - config.LOG_RETENTION_DAYS * 86400
    candidates = []
    for path in sorted(config.LOGS.glob("*.log")):
        task_id = path.name.split("-", 1)[0]
        if task_id in kept:
            continue
        if path.stat().st_mtime >= cutoff:
            continue
        candidates.append(path)
    return candidates


def _alert_cutoff_ts() -> str:
    when = datetime.now(timezone.utc) - timedelta(days=config.ALERT_ARCHIVE_DAYS)
    return when.strftime("%Y-%m-%d %H:%M:%SZ")


def _alert_candidates(conn) -> list:
    """Alerts старше `config.ALERT_ARCHIVE_DAYS` — кандидаты архивации,
    любой `kind`, вне зависимости от `ack` (AC-6)."""
    return store.alerts_older_than(conn, _alert_cutoff_ts())


def _print_report(mode: str, logs: list, alert_rows: list) -> None:
    log_verb = "удалён" if mode == "исполнено" else "будет удалён"
    alert_verb = "заархивирован" if mode == "исполнено" else "будет заархивирован"
    print(f"prune ({mode}):")
    if not logs and not alert_rows:
        print("  нечего убирать")
        return
    for path in logs:
        print(f"  лог {path.name} {log_verb}")
    for row in alert_rows:
        print(f"  alert «{row['message']}» {alert_verb}")


def cmd_prune(execute: bool = False) -> None:
    """dry-run по умолчанию (AC-4): без `execute=True` ничего не удаляет
    и не архивирует, только печатает план. С `execute=True` (AC-5, AC-6)
    исполняет retention-политику `docs/retention.md` и печатает отчёт
    о фактически убранном (AC-7)."""
    conn = store.db()
    logs = _log_candidates(conn)
    alert_rows = _alert_candidates(conn)

    if not execute:
        _print_report("план", logs, alert_rows)
        return

    removed: list[Path] = []
    for path in logs:
        try:
            path.unlink()
        except OSError as exc:
            print(f"  лог {path.name} не удалён: {exc}")
            continue
        removed.append(path)

    archived = []
    for row in alert_rows:
        store.archive_alert(conn, row["id"])
        archived.append(row)

    _print_report("исполнено", removed, archived)
