"""Приёмочный тест T094 — AC-5 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-5: «Задачи с историческим идентификатором Tnnn проходят команды CLI
и переходы FSM без регресса после введения ULID-генератора.»

Зелёный с рождения: `Tnnn`-задачи уже сегодня проходят `cmd_show` и
`store.set_state` (единственная точка перехода FSM, её докстринг:
«через неё проходит любой переход FSM») — ULID-генератор ещё не введён,
регрессировать нечему. Тест фиксирует это поведение СЕЙЧАС, в СМЕШАННОМ
мире (рядом с `Tnnn`-задачей — задача с id длинного ULID-образного вида,
дословно требование 5 SPEC ADR-0005 п.6: «смешанная нумерация после
перехода... принята»), чтобы наивный рефакторинг под ULID (например,
резолв префикса или сортировка, вслепую предполагающие один формат id)
не остался незамеченным: любое из трёх действий ниже — регресс,
описанный критерием, если он появится.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

LEGACY_ID = "T00042"
# Id-образный сосед формата ULID (26 символов Crockford base32) — не
# настоящий сгенерированный ULID (генератора ещё нет), но той же формы,
# какую резолвер префиксов и остальной код обязаны научиться понимать
# рядом со старыми `Tnnn` id (требование 5).
ULID_SHAPED_SIBLING = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


class Ac5LegacyTnnnRegressionTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        conn = store.db()
        store.insert_task(conn, LEGACY_ID, "Легаси-задача", "spec_writing",
                          f"task/{LEGACY_ID.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.insert_task(conn, ULID_SHAPED_SIBLING, "ULID-соседка",
                          "spec_writing", f"task/{ULID_SHAPED_SIBLING.lower()}-x",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def test_ac5_legacy_task_id_shown_by_cli_alongside_ulid_shaped_sibling(self):
        out = capture(catalog.cmd_show, LEGACY_ID)

        self.assertIn(LEGACY_ID, out)

    def test_ac5_legacy_task_id_unique_prefix_resolves_despite_longer_sibling(self):
        """Резолвер префикса (AC-3) не имеет права предполагать единый
        формат/длину id: короткий префикс `Tnnn`-задачи обязан находить
        именно её, даже когда рядом есть заметно более длинный
        ULID-образный id."""
        out = capture(catalog.cmd_show, LEGACY_ID[:4])

        self.assertIn(LEGACY_ID, out)

    def test_ac5_legacy_task_fsm_transition_still_succeeds(self):
        conn = store.db()

        store.set_state(conn, LEGACY_ID, "spec_gate", "operator",
                        expected_state="spec_writing")

        row = store.get_task(conn, LEGACY_ID)
        self.assertEqual(row["state"], "spec_gate")
        steps = store.task_steps(conn, LEGACY_ID)
        self.assertTrue(any(s["action"] == "state -> spec_gate" for s in steps))


if __name__ == "__main__":
    unittest.main()
