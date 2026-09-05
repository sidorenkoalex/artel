"""AC-1, AC-2, AC-7 — регрессия 01M1REVJ8AJ (SPEC 01M1RR1PZC926T13NB1JSZ7F8T,
«Контекст»): после мержа 01M1REVJ8AJDKAMK5VTKES5J6D (коммит d617c148)
`zone_lock._occupies` считает признаком занятости зоны запись `"agent run
started"` ЛЮБОГО актора — не только `developer`. Прогон роли test_author в
`tests_writing` журналирует то же действие той же точкой
(`runner.run_agent_once`), поэтому КАЖДАЯ задача с зафиксированной
приёмочной планкой ложно «занимает» зону ещё до первого шага developer, и
`blocking_conflict` для соседа с пересекающейся зоной никогда не
срабатывает.

Красен до реализации: `zone_lock._visit_has_action`/`_occupies`
(orchestrator/zone_lock.py:182-196) не сверяют `actor` записи `"agent run
started"` с ролью `developer` — до фикса `_occupies` возвращает `True` для
задачи, чей журнал после границы пребывания несёт только старт
`test_author`, и тесты ниже падают именно на этом (ожидаемые `False`/`None`
не совпадают с фактическими `True`/непустым конфликтом).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class ZoneActorFilterRegressionTest(TmpRootTest):
    CANDIDATE = "T001"
    NEIGHBOR = "T002"
    ZONE = "orchestrator/zone_lock.py"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        conn = store.db()

        # CANDIDATE: прошла границу текущего пребывания и журналирует
        # старт РОЛИ test_author (симулирует реальный прогон test_author на
        # стадии tests_writing, SPEC AC-7) — без единой записи со стартом
        # developer.
        store.insert_task(conn, self.CANDIDATE, "Кандидат", "in_dev",
                          "task/candidate-fake", config.DEFAULT_TARGET, 10.0)
        store.update_task(conn, self.CANDIDATE, zones=self.ZONE)
        store.journal(conn, self.CANDIDATE, "system",
                     "state -> tests_writing", "")
        store.journal(conn, self.CANDIDATE, "test_author",
                     "agent run started", "прогон test_author (tests_writing)")
        store.journal(conn, self.CANDIDATE, "system", "state -> in_dev", "")

        # NEIGHBOR: реальный сосед в in_dev с пересекающейся зоной, ещё не
        # делавший свой первый шаг — та задача, чей `blocking_conflict`
        # регрессия ложно освобождала бы от ожидания.
        store.insert_task(conn, self.NEIGHBOR, "Сосед", "in_dev",
                          "task/neighbor-fake", config.DEFAULT_TARGET, 10.0)
        store.update_task(conn, self.NEIGHBOR, zones=self.ZONE)

    def test_ac1_occupies_false_when_only_non_developer_actor_started(self):
        """`_occupies` для CANDIDATE (старт только актором `test_author`,
        без старта `developer` и без `RELEASE_ACTION`) обязан вернуть
        `False` — задача только ждёт, зоны не держит.

        Ловит мутацию: фильтр роли реализован через `or`/подмену действия
        вместо сверки `actor`, либо забыт вовсе — `_occupies` продолжит
        засчитывать старт `test_author` как занятость и вернёт `True`.
        """
        self.assertFalse(zone_lock._occupies(store.db(), self.CANDIDATE))

    def test_ac2_candidate_does_not_block_neighbors_first_step(self):
        """CANDIDATE, выступая кандидатом в цикле `blocking_conflict` для
        NEIGHBOR (пересекающаяся зона, `in_dev`), не блокирует его первый
        шаг: `blocking_conflict`/`refusal` NEIGHBOR обязаны вернуть `None`.

        Ловит мутацию: `blocking_conflict` продолжает сканировать CANDIDATE
        как занявшую зону задачу (фильтр роли применён только к
        `_occupies` для СВОЕЙ задачи, не к сканированию кандидатов в
        цикле) — NEIGHBOR остаётся ложно заблокированным.
        """
        conn = store.db()
        neighbor_row = store.get_task(conn, self.NEIGHBOR)

        self.assertIsNone(
            zone_lock.blocking_conflict(conn, self.NEIGHBOR, neighbor_row))
        self.assertIsNone(
            zone_lock.refusal(conn, self.NEIGHBOR, neighbor_row))


class ZoneActorFilterLiteralIncidentReproductionTest(TmpRootTest):
    """AC-7: буквальная реконструкция инцидента 05.09 (01M1RFVWV6/
    01M1R5B33C: общие зоны, developer не стартовал ни у одной, `_occupies`
    — `True` у обеих, `blocking_conflict` — `None` у обеих) — отдельный от
    AC-1/AC-2 самодостаточный сценарий, ровно тем набором журнальных
    записей, что описан AC-7 буквально: граница пребывания пройдена, В ТОМ
    ЖЕ пребывании журналируется старт `test_author`, старт `developer` не
    журналируется вовсе."""

    OWNER = "T501"
    NEIGHBOR = "T502"
    ZONE = "orchestrator/doctor.py"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        conn = store.db()
        store.insert_task(conn, self.OWNER, "Владелец", "in_dev",
                          "task/owner-fake", config.DEFAULT_TARGET, 10.0)
        store.update_task(conn, self.OWNER, zones=self.ZONE)
        store.insert_task(conn, self.NEIGHBOR, "Сосед", "in_dev",
                          "task/neighbor-fake", config.DEFAULT_TARGET, 10.0)
        store.update_task(conn, self.NEIGHBOR, zones=self.ZONE)

    def test_ac7_test_author_start_in_same_stay_does_not_block_a_neighbor(self):
        """Граница текущего пребывания (`"state -> tests_writing"`)
        журналируется, следом в ТОМ ЖЕ пребывании — `"agent run started"`
        актором `test_author`; записи того же действия актором `developer`
        нет вовсе. Сосед с пересекающейся зоной в `in_dev` не блокируется
        этой задачей.

        Ловит мутацию: без сверки актора (дефектное поведение до фикса)
        `_occupies` вернула бы `True` по одному факту наличия записи
        `"agent run started"` — тест обязан покраснеть именно на этом, тем
        же способом, каким регрессия 01M1REVJ8AJ пропустила исходную
        планку (её песочница не журналировала прецедент старта
        test_author в том же пребывании).
        """
        conn = store.db()
        store.journal(conn, self.OWNER, "system",
                     "state -> tests_writing", "")
        store.journal(conn, self.OWNER, "test_author", "agent run started",
                     "прогон test_author (tests_writing)")

        neighbor_row = store.get_task(conn, self.NEIGHBOR)
        conflict = zone_lock.blocking_conflict(conn, self.NEIGHBOR,
                                               neighbor_row)

        self.assertIsNone(conflict, f"сосед ложно заблокирован: {conflict}")
        self.assertIsNone(
            zone_lock.refusal(conn, self.NEIGHBOR, neighbor_row))


if __name__ == "__main__":
    unittest.main()
