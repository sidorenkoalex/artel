"""Приёмочный тест 01M1VBEAWZW4EBZHKMGNBBK648 — AC-8(в) (SPEC.md).

Дополняет `test_ac7_escalated_occupies.py` (тот кроет `zone_lock.
blocking_conflict` напрямую) проверкой через `zone_lock.refusal` —
функцию, которую реально зовёт `runner.cmd_run` перед первым шагом
developer (AC-8: «...держит зону ДЛЯ ДРУГИХ КАНДИДАТОВ» — наблюдаемо
именно через отказ, который получил бы этот другой кандидат, не только
через внутренний кортеж `blocking_conflict`).

Уровень — `zone_lock`/`TmpRootTest`, тот же приём, что и `tests/
test_zone_lock.py::test_refusal_names_path_task_and_state` (тест этого
файла — по образцу того теста, только держатель — задача в `escalated`).

Красен до реализации: `test_ac8_c_refusal_names_escalated_holder_for_
another_candidate` — `zone_lock.BLOCKING_STATES` не несёт `"escalated"`,
`refusal` для кандидата с пересекающейся зоной возвращает `None` вместо
текста, называющего эскалированного держателя.

Зелёный с рождения: `test_ac8_c_no_refusal_when_escalated_holder_never_
started_developer` — держатель в `escalated` БЕЗ старта developer уже
сегодня не порождает отказ (не входит ни в один занимающий диапазон
независимо от расширения `BLOCKING_STATES`) — тест фиксирует это как
регрессионный барьер тем же приёмом, что вторая половина `test_ac7_
escalated_occupies.py`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

TASK = "T001"
HOLDER = "T902"
ZONE = "shared/module.py"


class Ac8cEscalatedHolderBlocksOtherCandidatesTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), TASK, "Другой кандидат", "in_dev",
                          "task/t001-fake", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (ZONE, TASK))
        conn.commit()

    def seed_holder(self, state: str) -> None:
        store.insert_task(store.db(), HOLDER, "Держатель", state,
                          "task/t902-fake", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        conn = store.db()
        conn.execute("UPDATE tasks SET zones=? WHERE id=?", (ZONE, HOLDER))
        conn.commit()

    def mark_started(self, task_id: str) -> None:
        conn = store.db()
        store.journal(conn, task_id, "system", "state -> in_dev", "")
        store.journal(conn, task_id, "developer", "agent run started", "")

    def test_ac8_c_refusal_names_escalated_holder_for_another_candidate(self):
        """Другой кандидат (`TASK`, тоже в `in_dev`, та же зона) получает
        от `zone_lock.refusal` именованный отказ, называющий держателя в
        `escalated` — тот же наблюдаемый путь, которым реально
        пользуется `runner.cmd_run` перед первым шагом developer.

        Ловит мутацию: `refusal`/`blocking_conflict` не считают
        `escalated` (со стартом developer) занимающим состоянием для
        СКАНИРУЕМЫХ кандидатов — `refusal` вернул бы `None`, и первый шаг
        соседней задачи по той же зоне запустился бы одновременно с
        временно эскалированным держателем (тот самый конфликт подтяжки
        main из SPEC «Контекст», 06.09).
        """
        self.seed_holder("escalated")
        self.mark_started(HOLDER)

        text = zone_lock.refusal(
            store.db(), TASK, store.get_task(store.db(), TASK))

        self.assertIsNotNone(
            text, "escalated со стартом developer обязана порождать отказ "
                 "для другого кандидата той же зоны")
        self.assertIn(ZONE, text)
        self.assertIn(HOLDER, text)
        self.assertIn("escalated", text)

    def test_ac8_c_no_refusal_when_escalated_holder_never_started_developer(self):
        """Симметрично: держатель в `escalated`, ещё не начавший код
        (нет `"agent run started"` в текущем пребывании) — другой
        кандидат отказа не получает, первый шаг проходит.

        Ловит мутацию: `escalated` безусловно добавлен в занимающие
        состояния БЕЗ сохранения фильтра `_occupies` — сосед ложно
        заблокирован задачей, эскалированной ещё до первого шага
        developer (например эскалация из-за неоднозначности SPEC на
        самом старте `in_dev`).
        """
        self.seed_holder("escalated")

        text = zone_lock.refusal(
            store.db(), TASK, store.get_task(store.db(), TASK))

        self.assertIsNone(text)


if __name__ == "__main__":
    unittest.main()
