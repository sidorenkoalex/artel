"""AC-2 (01M1REVJ8AJDKAMK5VTKES5J6D) — задача, в текущем пребывании
которой уже был `"agent run started"` роли developer, продолжает
считаться занимающей свои зоны на всём диапазоне `BLOCKING_STATES`
(`in_dev`…`merge_gate`), не только буквально в `in_dev`.

Зелёный с рождения: `blocking_conflict` части 1-3 УЖЕ сравнивает
кандидата по `row["state"] in BLOCKING_STATES` независимо от того,
стартовал ли у него код (zone_lock.py:201-205) — для окупанта, который
ДЕЙСТВИТЕЛЬНО стартовал (условие AC-2 выполнено с запасом), результат уже
верен и до правки AC-1/AC-3. Тест зафиксирован здесь явно как приёмочная
планка, чтобы правка AC-1 (добавление проверки «стартовал ли код» для
каждого кандидата) не сузила её по ошибке до одного буквального `in_dev`
— см. докстринг мутации ниже.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import STATE_ORDER, ZoneMechanicsSandbox  # noqa: E402


class Ac2Test(ZoneMechanicsSandbox):

    def test_ac2_started_occupier_conflicts_in_every_blocking_state(self):
        """Окупант A стартовал код в `in_dev`, затем честной цепочкой
        `store.set_state` последовательно проходит `review`, `verifying`,
        `acceptance`, `merge_gate` — на каждом шаге третья задача с той же
        зоной по-прежнему видит его конфликтом, называющим именно его id
        и текущее состояние.

        Ловит мутацию: правка AC-1 определяет границу «стартовал ли
        кандидат» через `_visit_since_id(conn, row["id"], row["state"])`
        (маркер `"state -> {текущее состояние кандидата}"`) вместо
        буквально `"state -> in_dev"` — для окупанта, ушедшего в `review`/
        `verifying`/`acceptance`/`merge_gate`, такого маркера нет вовсе
        (`_visit_since_id` вернёт `0`, что случайно совпадает с верным
        результатом здесь) ИЛИ мутация связывает признак «стартовал» с
        буквальным `row["state"] == "in_dev"` — тогда окупант вне `in_dev`
        перестаёт распознаваться как занявший, хотя его код стартовал в
        том же непрерывном пребывании.
        """
        for state in STATE_ORDER:
            with self.subTest(state=state):
                self.clear_tasks()
                owner = self.seed_task("TOWN", "in_dev", "a/b")
                self.mark_started(owner)
                self.walk_to_state(owner, state)
                checked = self.seed_task("TC", "in_dev", "a/b")

                conflict = self.conflict_for(checked)

                self.assertEqual(conflict, ("a/b", owner, state))
