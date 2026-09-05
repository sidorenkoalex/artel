"""Общая песочница приёмочных тестов 01M1REVJ8AJDKAMK5VTKES5J6D («механика
зон — ждущая задача зону не держит, возврат из ревью занятость не
перепроверяет»).

## Интерфейс уже существует — эта задача правит его поведение

`orchestrator/zone_lock.py` (части 1-3, SPEC 01M1NKVPD2A79PQ6K0JVV1B2Q1/
01M1P9QAG65GVF69YJEV0V18D9/01M1P9QCHPHSCEA6TK13PV85SP) уже введён и уже
несёт публичные `blocking_conflict`/`refusal`/`queue_order`/
`queue_position`/`cmd_zone_release`/`cmd_zone_reorder` — эта задача НЕ
вводит новый интерфейс, а меняет условие занятости внутри
`blocking_conflict` (SPEC, требования 1-2). Тесты этого каталога бьют по
этим функциям НАПРЯМУЮ, тем же приёмом, что собственный юнит-набор модуля
(`tests/test_zone_lock.py::ZoneLockTest`), а не через `run`/`auto`
верхнего уровня — предмет задачи целиком внутри `zone_lock.py`, CLI не
меняется (SPEC, «Не входит»).

Задачи заводятся напрямую через `store.insert_task` (без git/worktree) —
тот же приём, что `tests/test_zone_lock.py::ZoneLockTest.seed_other`.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

# Диапазон занимающих фаз в порядке прохождения FSM (SPEC, требование 1;
# `zone_lock.BLOCKING_STATES`) — используется тестами AC-2/AC-3, которые
# проводят задачу через несколько визитов подряд настоящим `store.set_state`
# (не прямой правкой колонки), чтобы граница «текущего пребывания»
# считалась от честной цепочки переходов, а не от одной подставленной
# строки состояния.
STATE_ORDER = ("in_dev", "review", "verifying", "acceptance", "merge_gate")


class ZoneMechanicsSandbox(TmpRootTest):
    """`TmpRootTest` + БД, инициализированная `catalog.cmd_init`."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

    def clear_tasks(self) -> None:
        """Чистит таблицы `tasks`/`steps` между итерациями одного теста
        (`subTest`) — каждая итерация заводит задачи заново под теми же
        короткими id, не заботясь об уникальности между итерациями."""
        conn = store.db()
        conn.execute("DELETE FROM steps")
        conn.execute("DELETE FROM tasks")
        conn.commit()

    def seed_task(self, task_id: str, state: str, zones: str | None,
                 target: str = config.DEFAULT_TARGET) -> str:
        """Заводит задачу `task_id` напрямую в состоянии `state` с зонами
        `zones` (строка через запятую, часть 1) — без единой записи
        `"state -> ..."` в журнале (тот же приём, что `seed_other` в
        `tests/test_zone_lock.py`): для задачи, ни разу не прошедшей через
        `store.set_state`, граница «текущий визит» (`zone_lock.
        _visit_since_id`) равна `0` — весь её журнал."""
        store.insert_task(store.db(), task_id, f"Задача {task_id}", state,
                          f"task/{task_id.lower()}-fake", target,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(store.db(), task_id, zones=zones)
        return task_id

    def mark_started(self, task_id: str, detail: str = "") -> None:
        """Журналирует `"agent run started"` роли developer — маркер
        «код стартовал» (SPEC, требование 1), тот же приём, что реальный
        `runner.run_agent_once` использует после спавна агента."""
        store.journal(store.db(), task_id, "developer",
                     "agent run started", detail)

    def mark_approved(self, task_id: str) -> None:
        """Маркер момента approve SPEC (`zone_lock._approve_marker_id`,
        R1-F2 части 2) — `"state -> spec_gate"`, за ним `"state ->
        tests_writing"`; `steps.id` — общий монотонный счётчик по всем
        задачам одной БД, поэтому вызов этого метода раньше для одной
        задачи даёт ей меньший id маркера — раньше в `queue_order`."""
        conn = store.db()
        store.journal(conn, task_id, "system", "state -> spec_gate", "")
        store.journal(conn, task_id, "system", "state -> tests_writing", "")

    def walk_to_state(self, task_id: str, target_state: str) -> None:
        """Проводит `task_id` от `in_dev` до `target_state` честной
        цепочкой `store.set_state` (`STATE_ORDER`) — граница «текущего
        пребывания» после этого учитывает реальные переходы, а не одну
        подставленную строку `tasks.state`."""
        conn = store.db()
        idx = STATE_ORDER.index(target_state)
        prev = "in_dev"
        for state in STATE_ORDER[1:idx + 1]:
            store.set_state(conn, task_id, state, "system",
                            expected_state=prev)
            prev = state

    def conflict_for(self, task_id: str):
        return zone_lock.blocking_conflict(
            store.db(), task_id, store.get_task(store.db(), task_id))

    def refusal_for(self, task_id: str):
        return zone_lock.refusal(
            store.db(), task_id, store.get_task(store.db(), task_id))
