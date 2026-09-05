"""Приёмочный тест AC-4 (tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/SPEC.md): ни
одна публичная сигнатура функции `store.py` (имя, порядок и имена
параметров) не изменилась относительно версии ДО рефакторинга.

Золотой снимок `_SIGNATURES_BEFORE_REFACTOR` собран `inspect.signature`
по сегодняшнему (дорефакторинговому) `orchestrator/store.py` — ровно
тем состоянием, с которым сравнивает сам критерий. Тест намеренно НЕ
требует, чтобы каждое имя осталось АТРИБУТОМ `store` (часть функций по
AC-5 может законно переехать к единственному потребителю и исчезнуть
из `store.py` целиком — это регулирует AC-5, не AC-4): для каждого
имени, которое `orchestrator.store` продолжает публиковать после
рефакторинга, сигнатура обязана остаться байт-в-байт той же, что и до
него.

Зелёный с рождения: тест сверяет сегодняшний `store.py` сам с собой —
на сегодняшнем коде и обязан проходить, красным станет только после
рефакторинга, если тот действительно поменяет чью-то сигнатуру
(мутация, которую и требуется ловить).
"""
import inspect
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Снято `inspect.signature` с orchestrator/store.py ДО начала переноса
# схемы/миграций в schema.py (SPEC 01M1SD5NZ79MWCEJDJ9JP6EPWS) — золотой
# снимок: имя публичной функции -> кортеж имён параметров по порядку.
_SIGNATURES_BEFORE_REFACTOR = {
    "ack_alert": ("conn", "alert_id", "actor", "resolution"),
    "add_column": ("conn", "table", "column", "decl"),
    "alerts_older_than": ("conn", "cutoff_ts"),
    "all_leases": ("conn",),
    "all_tasks": ("conn",),
    "archive_alert": ("conn", "alert_id"),
    "canary_baseline": ("conn", "title"),
    "charge": ("conn", "task_id", "usd"),
    "charge_estimate": ("conn", "task_id", "usd"),
    "closed_external_tasks": ("conn",),
    "counter_targets": ("conn",),
    "create_schema": ("conn",),
    "db": (),
    "enable_wal": ("conn",),
    "get_alert": ("conn", "alert_id"),
    "get_task": ("conn", "task_id"),
    "insert_alert": ("conn", "target", "kind", "source", "message"),
    "insert_canary_run": (
        "conn", "run_stamp", "title", "task_id", "steps", "cost_usd",
        "review_iterations", "escalations", "outcome",
        "expected_escalation", "actual_escalation", "marker_mismatch"),
    "insert_lease": (
        "conn", "task_id", "session_id", "pid", "hostname", "heartbeat_ts"),
    "insert_task": (
        "conn", "task_id", "title", "state", "branch", "target",
        "budget_usd", "is_canary"),
    "journal": ("conn", "task_id", "actor", "action", "detail", "session_id"),
    "latest_fixed_sha": ("conn", "target"),
    "lease_row": ("conn", "task_id"),
    "merge_lock_row": ("conn",),
    "migrate": ("conn",),
    "next_task_number": ("conn", "target"),
    "now": (),
    "open_alert_exists": ("conn", "target", "kind", "source", "message"),
    "open_alerts": ("conn", "kind"),
    "peek_task_number": ("conn", "target"),
    "record_fixation": ("conn", "task_id"),
    "refusal_history": ("conn", "task_id", "state", "limit"),
    "release_lease": ("conn", "task_id", "session_id"),
    "release_merge_lock": ("conn", "session_id"),
    "resolve_task_id": ("conn", "task_id"),
    "seed_task_counters": ("conn",),
    "set_canary_baseline": (
        "conn", "title", "steps", "cost_usd", "review_iterations"),
    "set_merge_lock": (
        "conn", "task_id", "session_id", "pid", "hostname", "heartbeat_ts"),
    "set_state": (
        "conn", "task_id", "state", "actor", "expected_state", "detail"),
    "table_columns": ("conn", "table"),
    "task_branch": ("conn", "task_id"),
    "task_exists": ("conn", "task_id"),
    "task_number": ("task_id",),
    "task_steps": ("conn", "task_id"),
    "task_target": ("conn", "task_id"),
    "total_estimate": ("conn",),
    "total_spent": ("conn",),
    "update_lease": (
        "conn", "task_id", "session_id", "pid", "hostname", "heartbeat_ts"),
    "update_lease_pgid": ("conn", "task_id", "pgid"),
    "update_task": ("conn", "task_id", "fields"),
}


class PublicSignaturesUnchangedTest(unittest.TestCase):

    def test_ac4_signatures_of_functions_still_on_store_are_unchanged(self):
        """Для каждого имени золотого снимка, которое `orchestrator.store`
        продолжает публиковать (как собственную функцию либо как
        реэкспорт из `schema.py`/модуля-потребителя), порядок и имена
        параметров совпадают байт-в-байт с дорефакторинговым снимком.

        Ловит мутацию: при переносе запросов по областям (AC-3) или
        схемы в `schema.py` (AC-1) случайно переставлены параметры
        функции (например, `insert_task(conn, task_id, title, state,
        target, branch, ...)` вместо `..., branch, target, ...`) —
        `inspect.signature` зафиксирует новый порядок, и сравнение с
        золотым снимком для этого имени упадёт.
        """
        from orchestrator import store

        mismatches = []
        for name, expected_params in _SIGNATURES_BEFORE_REFACTOR.items():
            obj = getattr(store, name, None)
            if obj is None:
                continue  # AC-5 мог законно унести функцию к потребителю
            actual_params = tuple(inspect.signature(obj).parameters.keys())
            if actual_params != expected_params:
                mismatches.append((name, expected_params, actual_params))

        self.assertEqual(
            mismatches, [],
            "сигнатура изменилась у: " +
            "; ".join(f"{n}: было {exp}, стало {act}"
                     for n, exp, act in mismatches))


if __name__ == "__main__":
    unittest.main()
