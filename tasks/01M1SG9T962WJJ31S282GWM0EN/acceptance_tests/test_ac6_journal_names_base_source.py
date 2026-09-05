"""AC-6 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): журнальная запись
отказа гейта зон и журнальная запись отказа гейта ёмкости называют базу
сравнения — sha merge-base и источник (`origin/main` или локальный
`main`).

`JournalSourceFixture` (`_sandbox.py`) держит sha базы ОДИНАКОВЫМ в обоих
подклассах (`refs/remotes/origin/<MAIN_BRANCH>`, если создан, указывает
на тот же commit0, что и локальный main) — единственное, что вправе
отличаться между парами тестов ниже, это заявленный источник в тексте
журнала, не сам sha.

Красен до реализации: сегодняшние отказы гейта зон/ёмкости не называют
источник базы вовсе (сообщения говорят только `main...ветка` литералом
`config.MAIN_BRANCH`, без разбора «locale main vs origin/main») — тесты
`*_names_origin_source` ниже не найдут строку «origin/main» в журнале
ни для одного подкласса, включая тот, где ref заведён специально.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import fsm_advance  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import JournalSourceFixture  # noqa: E402


class ZonesGateJournalNamesOriginSourceTest(JournalSourceFixture):

    CREATE_ORIGIN_REF = True

    def test_ac6_zones_gate_refusal_names_merge_base_sha_and_origin_source(self):
        """Ловит мутацию: журнал отказа гейта зон не называет ни sha, ни
        источник базы (несёт только список путей вне зон, как сегодня) —
        полный sha локального main (равный sha origin/main в этой
        песочнице) не найдётся в тексте журнала."""
        refused = fsm_advance._zones_gate_refuses(
            self.conn, self.TASK_ID, self.t, self.BRANCH, "PLAN\n")

        self.assertTrue(refused)
        details = "\n".join(self.journal_details())
        self.assertIn(self.local_main_sha, details,
                      "журнал обязан называть sha merge-base")
        self.assertIn("origin/main", details,
                      "ref origin/main заведён — журнал обязан назвать "
                      "именно его источником")


class ZonesGateJournalNamesLocalSourceTest(JournalSourceFixture):

    CREATE_ORIGIN_REF = False

    def test_ac6_zones_gate_refusal_names_merge_base_sha_and_local_source(self):
        """Ловит мутацию: источник в журнале всегда захардкожен как
        «origin/main» независимо от того, существует ли реально этот
        ref, — в этой песочнице ref НЕ заведён (AC-8), и такая
        реализация ложно написала бы «origin/main» вместо локального
        main."""
        refused = fsm_advance._zones_gate_refuses(
            self.conn, self.TASK_ID, self.t, self.BRANCH, "PLAN\n")

        self.assertTrue(refused)
        details = "\n".join(self.journal_details())
        self.assertIn(self.local_main_sha, details,
                      "журнал обязан называть sha merge-base")
        self.assertNotIn("origin/main", details,
                         "ref origin/main в этой песочнице не заведён — "
                         "журнал не имеет права называть его источником")


class CapacityGateJournalNamesOriginSourceTest(JournalSourceFixture):

    CREATE_ORIGIN_REF = True

    def test_ac6_capacity_gate_refusal_names_merge_base_sha_and_origin_source(self):
        """Ловит мутацию: журнал отказа гейта ёмкости продолжает называть
        только размеры в байтах (как сегодня), без sha и источника
        базы."""
        refused = fsm_advance._capacity_gate_refuses(
            self.conn, self.TASK_ID, self.t, "in_dev")

        self.assertTrue(refused)
        details = "\n".join(self.journal_details())
        self.assertIn(self.local_main_sha, details,
                      "журнал обязан называть sha merge-base")
        self.assertIn("origin/main", details,
                      "ref origin/main заведён — журнал обязан назвать "
                      "именно его источником")


class CapacityGateJournalNamesLocalSourceTest(JournalSourceFixture):

    CREATE_ORIGIN_REF = False

    def test_ac6_capacity_gate_refusal_names_merge_base_sha_and_local_source(self):
        """Ловит мутацию: источник в журнале гейта ёмкости захардкожен как
        «origin/main» независимо от фактического наличия ref."""
        refused = fsm_advance._capacity_gate_refuses(
            self.conn, self.TASK_ID, self.t, "in_dev")

        self.assertTrue(refused)
        details = "\n".join(self.journal_details())
        self.assertIn(self.local_main_sha, details,
                      "журнал обязан называть sha merge-base")
        self.assertNotIn("origin/main", details,
                         "ref origin/main в этой песочнице не заведён — "
                         "журнал не имеет права называть его источником")


if __name__ == "__main__":
    unittest.main()
