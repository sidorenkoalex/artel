"""AC-12..AC-16 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): новый гейт
ёмкости на переходе `in_dev -> review` — отказывает, если полный diff
снимка (`git diff config.MAIN_BRANCH...<ветка>`) превышает 262144 байт
(AC-12); отказ называет причину дословно и id/название задачи (AC-13) и
журналируется через `store.journal`, тем же способом, что остальные
отказы `advance` (AC-13); отказ не эскалирует и не предпринимает
никакого автоматического действия — задача остаётся в `in_dev` (AC-14);
потолок пересчитывается заново на каждом входе в гейт, не по
инкременту (AC-15); diff не больше потолка проходит гейт (AC-16).

262144 — сам критерий приёмки (AC-4/AC-12), не крутилка, которую можно
случайно обогнать литералом — используется намеренно, тем же доводом,
что и 131072/65536 в test_ac2_oversized_excluded.py/
test_ac3_ac4_config_constants.py.

Красен до реализации: AC-12/AC-13/AC-14/AC-15 (Ac12*/Ac13*/Ac14*/
Ac15*Test ниже) — `in_dev -> review` в `orchestrator/fsm_advance.py`
сегодня не смотрит на размер diff вовсе, большой снимок не отказывает,
переход всегда доходит до `review`.

Зелёный с рождения: AC-16 (Ac16SmallDiffPassesTest ниже) — снимок,
который и так меньше потолка, проходит переход уже сегодня, потому что
гейта нет вовсе, но это то же самое поведение, которое AC-16 требует
сохранить после реализации, только уже через настоящую проверку, а не
по умолчанию.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import GateSandbox  # noqa: E402

GATE_CAP_BYTES = 262144  # AC-4/AC-12


class Ac12OversizedSnapshotRefusesTest(GateSandbox):

    def test_ac12_snapshot_diff_over_the_cap_refuses_the_transition(self):
        diff = "x" * (GATE_CAP_BYTES + 1)

        self.advance_with_snapshot_diff(diff)

        self.assertEqual(
            self.state(), "in_dev",
            "diff снимка больше 262144 байт обязан отказать переходу "
            "in_dev -> review (AC-12)")


class Ac13RefusalNamesReasonAndTaskTest(GateSandbox):

    def test_ac13_refusal_names_the_exact_reason_and_the_task(self):
        diff = "x" * (GATE_CAP_BYTES + 1)

        out = self.advance_with_snapshot_diff(diff)

        combined = out + "\n".join(self.journal_details())
        self.assertIn(
            "снимок не помещается в один контекст ревью — разделить "
            "задачу", combined,
            "причина отказа обязана быть названа дословно (AC-13)")
        self.assertIn(self.TASK, combined,
                     "отказ обязан назвать id задачи (AC-13)")

    def test_ac13_refusal_is_journaled_the_same_way_as_other_advance_refusals(self):
        diff = "x" * (GATE_CAP_BYTES + 1)

        self.advance_with_snapshot_diff(diff)

        details = self.journal_details()
        self.assertTrue(
            any("не помещается в один контекст" in d for d in details),
            f"отказ гейта ёмкости обязан лечь в store.journal, как и "
            f"остальные отказы advance: {details}")


class Ac14NoAutomaticActionTest(GateSandbox):

    def test_ac14_state_stays_in_dev_not_escalated(self):
        diff = "x" * (GATE_CAP_BYTES + 1)

        self.advance_with_snapshot_diff(diff)

        self.assertEqual(
            self.state(), "in_dev",
            "гейт ёмкости не имеет права эскалировать сам — задача "
            "остаётся в in_dev до решения Оператора (AC-14), не уходит "
            "в escalated")


class Ac15RecomputedEachEntryTest(GateSandbox):

    def test_ac15_gate_is_recomputed_fresh_on_every_advance_not_cached(self):
        big = "x" * (GATE_CAP_BYTES + 1)
        self.advance_with_snapshot_diff(big)
        self.assertEqual(self.state(), "in_dev", "первый прогон — снимок "
                         "большой, обязан остаться в in_dev")

        small = "x" * (GATE_CAP_BYTES - 100)
        self.advance_with_snapshot_diff(small)

        self.assertEqual(
            self.state(), "review",
            "снимок ужался ниже потолка — повторный вход в гейт обязан "
            "пересчитать его заново, а не унаследовать прошлый отказ "
            "(AC-15)")


class Ac16SmallDiffPassesTest(GateSandbox):

    def test_ac16_snapshot_diff_under_the_cap_passes_the_gate(self):
        diff = "x" * (GATE_CAP_BYTES - 1)

        self.advance_with_snapshot_diff(diff)

        self.assertEqual(
            self.state(), "review",
            "diff снимка не больше 262144 байт обязан пройти гейт при "
            "прочих выполненных условиях перехода (AC-16)")

    def test_ac16_empty_diff_passes_the_gate(self):
        self.advance_with_snapshot_diff("")

        self.assertEqual(self.state(), "review")


if __name__ == "__main__":
    unittest.main()
