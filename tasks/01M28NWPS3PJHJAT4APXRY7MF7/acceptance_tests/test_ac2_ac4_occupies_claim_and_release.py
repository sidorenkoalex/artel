"""Приёмочные тесты 01M28NWPS3PJHJAT4APXRY7MF7 — AC-2, AC-4 (SPEC.md).

`zone_lock._occupies`/`zone_lock.blocking_conflict` в изоляции: занятость
зоны записью `zone_lock.CLAIM_ACTION` актора `developer` — БЕЗ единого
`"agent run started"` — и её снятие более поздней `"zone claim
released"`. Журнал занявшей задачи заводится вручную (`self.journal`),
тот же приём, что уже применяют `tests/test_zone_lock.py::ZoneLockTest.
_mark_already_started`/`test_operator_release_after_boundary_lifts_conflict`
к существующим маркерам `"agent run started"`/`zone_lock.RELEASE_ACTION`.

Красен до реализации: `zone_lock.CLAIM_ACTION` не существует в этом
дереве — `AttributeError: module 'orchestrator.zone_lock' has no
attribute 'CLAIM_ACTION'` на первой же строке, журналирующей захват.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneClaimSandbox  # noqa: E402

from orchestrator import store, zone_lock  # noqa: E402

OCCUPIER = "T901"


class Ac2ClaimWithoutAgentStartedOccupiesTest(ZoneClaimSandbox):
    """AC-2: захват (`zone_lock.CLAIM_ACTION`, актор `developer`) после
    границы текущего пребывания делает задачу занявшей зону, даже если
    `"agent run started"` ещё ни разу не журналировалось (роль ещё не
    добралась до фактического спавна агента — только что прошла атомарный
    захват).

    Ловит мутацию: `_occupies` продолжает проверять ИСКЛЮЧИТЕЛЬНО
    `"agent run started"`/`zone_lock.RELEASE_ACTION`, не подключая
    `zone_lock.CLAIM_ACTION` вовсе — задача, только что захватившая зону
    (но ещё не написавшая код), не считалась бы занявшей её, и гонка
    AC-1/AC-6 не закрывалась бы этим маркером."""

    def test_ac2_claim_action_alone_makes_occupies_true(self):
        self.seed_fake_occupant(OCCUPIER, "in_dev", self.ZONE)
        self.journal(OCCUPIER, "developer", zone_lock.CLAIM_ACTION, "")

        self.assertTrue(zone_lock._occupies(store.db(), OCCUPIER))

    def test_ac2_claim_action_blocks_other_candidates_zone_check(self):
        self.seed_fake_occupant(OCCUPIER, "in_dev", self.ZONE)
        self.journal(OCCUPIER, "developer", zone_lock.CLAIM_ACTION, "")

        conflict = zone_lock.blocking_conflict(
            store.db(), self.TASK, store.get_task(store.db(), self.TASK))

        self.assertIsNotNone(conflict)
        self.assertEqual(conflict[0], self.ZONE)
        self.assertEqual(conflict[1], OCCUPIER)
        self.assertEqual(conflict[2], "in_dev")

    def test_ac2_claim_action_by_non_developer_actor_does_not_occupy(self):
        """Регрессия того же класса, что уже закрыт для `"agent run
        started"` (`tests/test_zone_lock.py::
        test_non_developer_agent_start_in_same_stay_does_not_occupy`):
        захват засчитывается ТОЛЬКО актору `developer` (требование 1
        SPEC называет актора буквально), любой другой актор — не занятие.

        Ловит мутацию: `_occupies` не сверяет актора записи
        `zone_lock.CLAIM_ACTION` вовсе — захват, ошибочно записанный не от
        имени `developer` (например тестовой фикстурой другой роли),
        ложно считался бы занятием."""
        self.seed_fake_occupant(OCCUPIER, "in_dev", self.ZONE)
        self.journal(OCCUPIER, "test_author", zone_lock.CLAIM_ACTION, "")

        self.assertFalse(zone_lock._occupies(store.db(), OCCUPIER))


class Ac4ReleaseAfterClaimLiftsOccupancyTest(ZoneClaimSandbox):
    """AC-4: более поздняя (по id записи журнала) `"zone claim released"`
    ПОСЛЕ `zone_lock.CLAIM_ACTION`, без более поздней `"agent run
    started"`, снимает занятость — задача перестаёт считаться занявшей
    зону.

    Ловит мутацию: `_occupies` игнорирует `"zone claim released"` вовсе —
    снятый после неудачного старта захват продолжал бы считаться
    занятием навсегда, следующий кандидат (AC-7) не прошёл бы проверку."""

    def test_ac4_release_after_claim_lifts_occupancy(self):
        self.seed_fake_occupant(OCCUPIER, "in_dev", self.ZONE)
        self.journal(OCCUPIER, "developer", zone_lock.CLAIM_ACTION, "")
        self.journal(OCCUPIER, "fsm", "zone claim released", "")

        self.assertFalse(zone_lock._occupies(store.db(), OCCUPIER))

    def test_ac4_release_after_claim_lifts_blocking_conflict(self):
        self.seed_fake_occupant(OCCUPIER, "in_dev", self.ZONE)
        self.journal(OCCUPIER, "developer", zone_lock.CLAIM_ACTION, "")
        self.journal(OCCUPIER, "fsm", "zone claim released", "")

        conflict = zone_lock.blocking_conflict(
            store.db(), self.TASK, store.get_task(store.db(), self.TASK))

        self.assertIsNone(conflict)

    def test_ac4_reclaim_after_release_occupies_again(self):
        """Ordering, не «есть ли хоть один release где-нибудь»: захват
        ПОСЛЕ старого снятия (например следующая попытка `run` того же
        шага) снова делает задачу занявшей зону.

        Ловит мутацию: `_occupies` проверяет «есть ЛИ ВООБЩЕ запись
        `"zone claim released"` после границы пребывания» вместо сравнения
        id самой последней `zone_lock.CLAIM_ACTION` с id самой последней
        `"zone claim released"` — повторный захват после старого снятия
        ошибочно остался бы «не занимает» навсегда."""
        self.seed_fake_occupant(OCCUPIER, "in_dev", self.ZONE)
        self.journal(OCCUPIER, "developer", zone_lock.CLAIM_ACTION, "")
        self.journal(OCCUPIER, "fsm", "zone claim released", "")
        self.journal(OCCUPIER, "developer", zone_lock.CLAIM_ACTION, "")

        self.assertTrue(zone_lock._occupies(store.db(), OCCUPIER))


if __name__ == "__main__":
    import unittest
    unittest.main()
