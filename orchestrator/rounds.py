"""Метрика «круги до кода»: аудиты SPEC, возвраты и эскалации задачи по
журналу `steps` (SPEC 01M59DP2GV3SAN54M562CQY42R, требование 1).

Один подсчёт на двух читателей: блок «Круги до кода» команды `report` и
однократное оповещение `rounds` цикла `auto`. Подсчёт — чистая функция над
уже прочитанными строками журнала задачи: `report` отдаёт ей свою единую
выборку журнала (ни одного нового запроса к `steps`), `auto` — журнал
задачи через `store.task_steps`. Стоимость шага читает существующий разбор
`spend.known_cost_breakdown` — своего разбора здесь нет.
"""
from dataclasses import dataclass

from . import alerts, brief, config, spend, store
from .advance_gates import spec_audit

AUDIT_ACTION = "state -> spec_audit"
ESCALATED_ACTION = "state -> escalated"
SPEC_WRITING_ACTION = "state -> spec_writing"
KNOWN_COST_ACTION = "agent cost KNOWN"
# Шаги до планки — роли, пишущие и проверяющие SPEC (требование 1).
BEFORE_PLANK_ACTORS = ("analyst", "spec_auditor")

ALERT_KIND = "warning"
ALERT_SOURCE = "rounds"
# Признак однократности оповещения (требование 7): запись журнала задачи,
# а не открытое оповещение — `ack` и закрытие оповещений внимания переходом
# её не снимают.
ALERT_MARK_ACTION = "круги до кода: оповещение"


@dataclass(frozen=True)
class Rounds:
    audits: int
    audit_returns: int
    gate_returns: int
    escalations: int
    review_iters: int
    cost_before_plank: float
    cost_total: float


def count(steps, review_iters: int | None) -> Rounds:
    """Подсчёт по строкам журнала ОДНОЙ задачи (`action`, `actor`,
    `detail`). Возврат с гейта SPEC — только `state -> spec_writing` с
    detail «возврат из spec_gate:»: снятие эскалации и возврат по вердикту
    аудита тем же действием возвратом с гейта не считаются."""
    audits = audit_returns = gate_returns = escalations = 0
    before = total = 0.0
    for row in steps:
        action = row["action"]
        detail = row["detail"] or ""
        if action == AUDIT_ACTION:
            audits += 1
        elif action == spec_audit.RETURN_ACTION:
            audit_returns += 1
        elif (action == SPEC_WRITING_ACTION
              and detail.startswith(brief.SPEC_GATE_RETURN_PREFIX)):
            gate_returns += 1
        elif action == ESCALATED_ACTION:
            escalations += 1
        elif action == KNOWN_COST_ACTION:
            usd = spend.known_cost_breakdown(detail)[0]
            if usd is None:
                continue
            total += usd
            if row["actor"] in BEFORE_PLANK_ACTORS:
                before += usd
    return Rounds(audits, audit_returns, gate_returns, escalations,
                  review_iters or 0, before, total)


def over_threshold(rounds: Rounds) -> bool:
    return (rounds.audits >= config.ROUNDS_ALERT_SPEC_AUDITS
            or rounds.escalations >= config.ROUNDS_ALERT_ESCALATIONS)


def alert_text(task_id: str, rounds: Rounds) -> str:
    return (f"задача {task_id}: {rounds.audits} аудитов SPEC, "
            f"{rounds.escalations} эскалаций до кода — ТЗ недоопределено?")


def raise_once(conn, task_id: str) -> bool:
    """Сверка задачи с порогом (требования 6-7): при достижении порога и
    без прежней записи «круги до кода: оповещение» поднимает оповещение
    `rounds` на проект задачи и пишет эту запись. True — поднято сейчас."""
    steps = store.task_steps(conn, task_id)
    if any(row["action"] == ALERT_MARK_ACTION for row in steps):
        return False
    rounds = count(steps, store.get_task(conn, task_id)["review_iters"])
    if not over_threshold(rounds):
        return False
    text = alert_text(task_id, rounds)
    alerts.raise_alert(conn, store.task_target(conn, task_id), ALERT_KIND,
                       ALERT_SOURCE, text)
    store.journal(conn, task_id, "fsm", ALERT_MARK_ACTION, text)
    return True
