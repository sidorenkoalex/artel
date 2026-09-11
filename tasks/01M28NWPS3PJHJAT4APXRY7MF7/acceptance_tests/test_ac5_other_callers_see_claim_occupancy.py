"""Приёмочные тесты 01M28NWPS3PJHJAT4APXRY7MF7 — AC-5 (SPEC.md).

`_occupies`/`blocking_conflict` для ВЫЗЫВАЮЩИХ, отличных от `runner.
_cmd_run` (`catalog`, `doctor`, `auto._wait_for_zone`), не меняют
семантику: задача с действующим захватом (`zone_lock.CLAIM_ACTION`, без
единого `"agent run started"`) видна занявшей зону так же, как с
`"agent run started"`. Все три вызывающих зовут `zone_lock.
blocking_conflict` целиком, без собственной копии проверки (докстринги
`catalog._zone_wait_suffix`/`doctor.hung_test_watchdog`/`auto.
_wait_for_zone` — «та же проверка... не отдельная копия»); эта задача НЕ
трогает их код вовсе (SPEC, зоны задачи), поэтому свойство «видят так же»
проверяется тем, что они СЕГОДНЯШНИМ, неизменным кодом корректно
отражают НОВОЕ основание занятости — `catalog._zone_wait_suffix` взят
как представитель (чистая функция, без побочных эффектов CLI-вывода).

Красен до реализации: `zone_lock.CLAIM_ACTION` не существует —
`AttributeError` на первой же строке, журналирующей захват.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneClaimSandbox  # noqa: E402

from orchestrator import catalog, store, zone_lock  # noqa: E402

OCCUPIER = "T901"


class Ac5CatalogStatusSuffixSeesClaimBasedOccupantTest(ZoneClaimSandbox):
    """AC-5: `catalog._zone_wait_suffix` (код этой задачей не трогается)
    показывает ожидание зоны для задачи, заблокированной кандидатом,
    держащим зону ТОЛЬКО захватом (`zone_lock.CLAIM_ACTION`) — тот же
    вывод, что и для держателя с `"agent run started"` (уже покрыто
    существующими тестами `tests/test_zone_lock.py`, не этой задачей).

    Ловит мутацию: разработчик заводит захват отдельным, не общим с
    `blocking_conflict` путём (например собственная проверка внутри
    `runner._cmd_run`, не через `_occupies`) — тогда `catalog`/`doctor`/
    `auto._wait_for_zone`, продолжающие звать `blocking_conflict` как
    раньше, не увидели бы новую занятость вовсе, и эта строка осталась бы
    пустой вместо «ждёт зоны»."""

    def test_ac5_catalog_status_suffix_reflects_claim_based_occupant(self):
        self.seed_fake_occupant(OCCUPIER, "in_dev", self.ZONE)
        self.journal(OCCUPIER, "developer", zone_lock.CLAIM_ACTION, "")

        suffix = catalog._zone_wait_suffix(
            store.db(), store.get_task(store.db(), self.TASK))

        self.assertIn("ждёт зоны", suffix)
        self.assertIn(self.ZONE, suffix)
        self.assertIn(OCCUPIER, suffix)
        self.assertIn("in_dev", suffix)

    def test_ac5_catalog_status_suffix_is_empty_without_any_occupant(self):
        """Контроль: без единой записи занятости (ни захвата, ни
        `"agent run started"`) — конкурент в `in_dev` НЕ считается
        занявшим зону (часть 1-3 этой механики, здесь не меняется),
        строка остаётся пустой. Без этого контроля предыдущий тест мог
        бы зеленеть по мутации, вернувшей суффикс безусловно."""
        self.seed_fake_occupant(OCCUPIER, "in_dev", self.ZONE)

        suffix = catalog._zone_wait_suffix(
            store.db(), store.get_task(store.db(), self.TASK))

        self.assertEqual(suffix, "")


if __name__ == "__main__":
    import unittest
    unittest.main()
