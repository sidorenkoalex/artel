"""Приёмочный тест 01M1VBEAWZW4EBZHKMGNBBK648 — AC-7 (SPEC.md).

Уровень — сам `orchestrator/zone_lock.py` в изоляции, тем же приёмом,
что и `tests/test_zone_lock.py` (`TmpRootTest` + прямые
`store.insert_task`/`store.journal`, без `auto`/`run`): требование 5
буквально говорит о `zone_lock.BLOCKING_STATES`/`_occupies` — внутренние
имена уже существуют и зафиксированы, поэтому здесь не нужно
изобретать интерфейс, как в остальных AC этой задачи (см. `_sandbox.py`
для `--wait-zone`).

Красен до реализации: `test_ac7_escalated_with_developer_start_holds_the_
zone` — `zone_lock.BLOCKING_STATES` сегодня — `("in_dev", "review",
"verifying", "acceptance", "merge_gate")`, без `"escalated"` (SPEC
«Контекст», факт «а») — `blocking_conflict` для держателя в `escalated`
со стартом developer возвращает `None` вместо конфликта, пока
`escalated` не войдёт в диапазон занимающих состояний.

Зелёный с рождения: `test_ac7_escalated_without_developer_start_does_
not_hold_the_zone`/`test_ac7_stay_boundary_unchanged_by_this_task` — оба
уже сегодня корректно возвращают `None` (без старта developer `escalated`
и так не входит ни в один занимающий диапазон; граница пребывания читает
существующую `_stay_since_id` независимо от конечного состояния) — тесты
фиксируют это как регрессионный барьер: расширение `BLOCKING_STATES` на
`escalated` не должно сделать его занимающим БЕЗУСЛОВНО, теряя фильтр
старта developer или границу текущего пребывания.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

TASK = "T001"
OTHER = "T901"
ZONE = "a/b"


class Ac7EscalatedOccupiesZoneTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (ZONE, TASK))
        conn.commit()

    def seed_other(self, state: str) -> None:
        store.insert_task(store.db(), OTHER, "Другая", state,
                          "task/t901-fake", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (ZONE, OTHER))
        conn.commit()

    def mark_started(self, task_id: str) -> None:
        conn = store.db()
        store.journal(conn, task_id, "system", "state -> in_dev", "")
        store.journal(conn, task_id, "developer", "agent run started", "")

    def get_task(self):
        return store.get_task(store.db(), TASK)

    def test_ac7_escalated_with_developer_start_holds_the_zone(self):
        """Задача-кандидат в `escalated`, уже начавшая код в ТЕКУЩЕМ
        пребывании (маркер `"agent run started"` актором `developer`
        ПОСЛЕ последней `"state -> tests_writing"`), держит зону — другая
        задача с пересекающейся зоной получает конфликт `blocking_conflict`
        с состоянием `"escalated"`.

        Ловит мутацию: `BLOCKING_STATES` не дополнен `"escalated"` —
        `blocking_conflict` возвращает `None` вместо конфликта, хотя
        держатель реально начал код и всего лишь временно эскалирован
        (бюджет/вопрос/конфликт подтяжки — SPEC «Контекст», факт «а»).
        """
        self.seed_other("escalated")
        self.mark_started(OTHER)

        conflict = zone_lock.blocking_conflict(
            store.db(), TASK, self.get_task())

        self.assertIsNotNone(
            conflict, "escalated со стартом developer обязана держать зону")
        self.assertEqual(conflict, (ZONE, OTHER, "escalated"))

    def test_ac7_escalated_without_developer_start_does_not_hold_the_zone(self):
        """Задача-кандидат в `escalated`, у которой в ТЕКУЩЕМ пребывании
        НЕ БЫЛО старта developer (например эскалация случилась раньше
        первого шага — вопрос по SPEC/PLAN до разработки, либо синтетика
        теста без единой записи `"agent run started"`), зону не держит —
        другая задача с пересекающейся зоной проходит без конфликта.

        Ловит мутацию: `escalated` добавлен в `BLOCKING_STATES` БЕЗ
        сохранения проверки `_occupies` (например добавили `"escalated"`
        и убрали фильтр по старту developer заодно, или сделали
        `escalated` занимающим безусловно) — `blocking_conflict` ложно
        возвращает конфликт для задачи, ещё не написавшей ни строки кода
        (эскалация на самом первом шаге, до `run`).
        """
        self.seed_other("escalated")

        conflict = zone_lock.blocking_conflict(
            store.db(), TASK, self.get_task())

        self.assertIsNone(
            conflict,
            "escalated БЕЗ старта developer не должна держать зону")

    def test_ac7_stay_boundary_unchanged_by_this_task(self):
        """Граница текущего пребывания (последняя запись `"state ->
        tests_writing"`) не сдвигается этой задачей (SPEC, требование 5,
        буквально): старт developer из ПРЕДЫДУЩЕГО пребывания (до самой
        свежей `"state -> tests_writing"`) не засчитывается «занимает» для
        escalated текущего пребывания — то же правило границы, что уже
        действует для `in_dev`…`merge_gate` (`test_first_step_boundary_
        uses_current_in_dev_visit` в `tests/test_zone_lock.py`), только
        здесь конечное состояние — `escalated`, не `in_dev`.

        Ловит мутацию: `_stay_since_id` для `escalated`-кандидата не
        применяется (например код читает АБСОЛЮТНО первый `"agent run
        started"` за всю историю задачи вместо только текущего
        пребывания) — держатель, чьё пребывание давно переоткрылось без
        нового старта developer, всё ещё ложно считается занявшим.
        """
        self.seed_other("in_dev")
        store.journal(store.db(), OTHER, "system",
                     "state -> tests_writing", "старое пребывание")
        store.journal(store.db(), OTHER, "developer",
                     "agent run started", "визит #1 (прошлое пребывание)")
        # Реалистичный цикл возврата на переделку (старое пребывание
        # закрывается новой `"state -> tests_writing"`), НОВОЕ пребывание
        # эскалируется ДО единого шага developer в нём.
        store.set_state(store.db(), OTHER, "escalated", "system",
                        expected_state="in_dev")
        store.set_state(store.db(), OTHER, "tests_writing", "system",
                        expected_state="escalated")
        store.set_state(store.db(), OTHER, "escalated", "system",
                        expected_state="tests_writing")

        conflict = zone_lock.blocking_conflict(
            store.db(), TASK, self.get_task())

        self.assertIsNone(
            conflict,
            "старт developer ИЗ ПРЕДЫДУЩЕГО пребывания не должен считаться "
            "занятостью текущего")


if __name__ == "__main__":
    unittest.main()
