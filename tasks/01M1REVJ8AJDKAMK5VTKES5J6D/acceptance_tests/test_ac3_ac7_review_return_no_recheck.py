"""AC-3, AC-7 (01M1REVJ8AJDKAMK5VTKES5J6D) — задача, чьё текущее
пребывание в `in_dev`…`merge_gate` уже несёт признак «код стартовал»
(AC-2) ДО возврата `review -> in_dev`, после этого возврата не проходит
повторную проверку занятости для СЕБЯ САМОЙ — владелец остаётся
владельцем до `done`/`killed`, даже если рядом стоят ждущие соседи по
той же зоне.

Красен до реализации: `_visit_since_id` (zone_lock.py:156-163) берёт
ПОСЛЕДНЮЮ запись `"state -> in_dev"` — после возврата `review -> in_dev`
эта граница сдвигается на новый визит, старая запись `"agent run
started"` (из визита ДО возврата) оказывается ДО новой границы и
перестаёт засчитываться; собственная проверка задачи снова видит
ждущих соседей и ложно возвращает конфликт — оба теста этого файла
падают на `assertIsNone`/непустом отказе там, где ждут `None`. Это
буквально факт (б) из «Контекста» SPEC.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ZoneMechanicsSandbox  # noqa: E402

from orchestrator import store  # noqa: E402


class Ac3Ac7Test(ZoneMechanicsSandbox):

    def test_ac3_return_from_review_does_not_recheck_owner(self):
        """Владелец A стартовал код в `in_dev`, прошёл `in_dev -> review ->
        in_dev` (возврат из ревью). Рядом стоит задача-сосед с той же
        зоной, сама ни разу не стартовавшая код. `blocking_conflict` для A
        после возврата возвращает `None` — повторная проверка не
        выполняется.

        Ловит мутацию: см. докстринг модуля.
        """
        owner = self.seed_task("TOWN", "in_dev", "a/b")
        self.mark_started(owner)
        conn = store.db()
        store.set_state(conn, owner, "review", "system",
                        expected_state="in_dev")
        store.set_state(conn, owner, "in_dev", "system",
                        expected_state="review")
        self.seed_task("TN", "in_dev", "a/b")

        self.assertIsNone(self.conflict_for(owner))

    def test_ac7_owner_run_passes_after_review_return_despite_several_waiting_neighbors(self):
        """Тот же возврат `review -> in_dev`, что и AC-3, но на уровне
        наблюдаемого исхода `run`/`auto` — `zone_lock.refusal` для
        владельца после возврата пуст, даже когда НЕСКОЛЬКО соседей стоят
        в `in_dev` с той же зоной в режиме ожидания.

        Ловит мутацию: см. докстринг модуля — здесь дополнительно
        проверяется, что наличие МНОЖЕСТВА ждущих соседей (не одного) не
        меняет исход: мутация, чинящая границу визита только для случая
        «конфликтов ещё нет», но по-прежнему возвращающая первый найденный
        конфликт, как только соседей больше одного, тоже будет поймана.
        """
        owner = self.seed_task("TOWN", "in_dev", "a/b")
        self.mark_started(owner)
        conn = store.db()
        store.set_state(conn, owner, "review", "system",
                        expected_state="in_dev")
        store.set_state(conn, owner, "in_dev", "system",
                        expected_state="review")
        self.seed_task("TN1", "in_dev", "a/b")
        self.seed_task("TN2", "in_dev", "a/b")

        self.assertIsNone(self.refusal_for(owner))
