"""Пакет orchestrator/doctor -- авто-ack снятых incident-условий (tasks/T035).

Коллаборанты читаются лениво через фасад doctor (см. докстринг
orchestrator/doctor/__init__.py) -- не импортируются напрямую.
"""
from pathlib import Path
import re

from orchestrator import doctor


# --- авто-ack (tasks/T035/SPEC.md, требования 1-7) -----------------------

# Разбор сущности обратно из `message`, который сами же под-проверки ниже
# и составляют (формат стабилен, т.к. это единственный писатель) — `alerts`
# не хранит структурированный идентификатор сущности отдельным полем
# (SPEC этого не просит, заводить миграцию схемы вне зоны задачи).
_BRANCH_ALERT_RE = re.compile(r"ветка (\S+) не убрана$")
_DIR_ALERT_RE = re.compile(r"^(.+) без строки БД$")
_WORKTREE_ALERT_RE = re.compile(r"^worktree (.+) без задачи$")


def _auto_ack_gone(conn, source: str, is_live, target: str | None = None) -> None:
    """Подтверждает открытые алерты `source`, чьё условие `is_live` больше
    не подтверждает (требование 7: пока условие в силе — не трогать).

    Сообщение, не распознанное `is_live` (дрейф формата) — безопасный
    отказ: считается, что условие ещё в силе, ack не проставляется.

    `target`, если задан, дополнительно фильтрует по колонке `target`
    строки алерта (SPEC T088, требование 6): источники, у которых
    несколько target одновременно держат свой открытый алерт того же
    `source` (`doctor.recovery.*`, `doctor.task_counter`), не должны
    получать ack одного target по состоянию другого. По умолчанию
    `None` — прежнее поведение (не фильтровать), которое сохраняют все
    вызовы, где сущность и так уникальна внутри `message`
    (сироты/leases/merge_lock/backup_age).
    """
    for row in doctor.alerts.open_alerts(conn, "incident"):
        if row["source"] != source:
            continue
        if target is not None and row["target"] != target:
            continue
        if not is_live(row["message"]):
            doctor.alerts.auto_ack(conn, row["id"])


def _branch_alert_live(message: str) -> bool:
    match = doctor._BRANCH_ALERT_RE.search(message)
    return match is None or doctor.gitcmd.branch_exists(match.group(1))


def _dir_alert_live(message: str, known_ids: set) -> bool:
    match = doctor._DIR_ALERT_RE.match(message)
    return match is None or Path(match.group(1)).name not in known_ids


def _worktree_alert_live(message: str, current_paths: set) -> bool:
    match = doctor._WORKTREE_ALERT_RE.match(message)
    return match is None or match.group(1) in current_paths


