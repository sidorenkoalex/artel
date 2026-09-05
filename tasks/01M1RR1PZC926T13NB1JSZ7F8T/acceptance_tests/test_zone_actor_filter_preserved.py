"""AC-3, AC-4, AC-5 — то, что фикс регрессии 01M1REVJ8AJ (SPEC
01M1RR1PZC926T13NB1JSZ7F8T) ОБЯЗАН оставить без изменений: требование 1
сужает признак занятости ролью `developer` только для записи `"agent run
started"`; `RELEASE_ACTION` остаётся признаком занятости независимо от
актора (требование 1, буквально: «фильтр по роли developer применяется
только к "agent run started"»), а форма сообщения `refusal` не меняется
вовсе (требование 2/AC-5) — меняется только состав кандидатов, которых
учитывает фильтр занятости.

Зелёный с рождения: сегодняшний (ещё не исправленный) `zone_lock._occupies`
не сверяет актора вовсе, поэтому уже сейчас засчитывает старт `developer` и
`RELEASE_ACTION` признаком занятости независимо от актора — ровно то
поведение, что требования 1/AC-3/AC-4/AC-5 требуют сохранить. Тесты этого
файла охраняют РЕГРЕССИЮ будущей правки (сужение фильтра, случайно
задевающее эти случаи), а не описывают новую функциональность — тот же
приём, что `tasks/01M1KVG3KSCY47HWXWF5HM0E76/acceptance_tests/
test_ac6_existing_plankas_stay_green.py` применил для соседней пары
планок.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class ZoneActorFilterPreservedTest(TmpRootTest):
    OWNER = "T601"
    NEIGHBOR = "T602"
    ZONE = "orchestrator/zone_lock.py"

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
        self.conn = conn

    def _cross_boundary(self, task_id: str) -> None:
        store.journal(self.conn, task_id, "system",
                     "state -> tests_writing", "")

    def test_ac3_developer_start_still_occupies_and_blocks_neighbor(self):
        """Запись `"agent run started"` актором `developer` после границы
        пребывания — OWNER по-прежнему занимает зону: `_occupies`
        возвращает `True`, и она по-прежнему блокирует первый шаг соседа
        через `blocking_conflict`/`refusal`.

        Ловит мутацию: фильтр роли реализован инвертированно (например
        `actor != "developer"` вместо `actor == "developer"`, либо
        сравнение регистрозависимо ломается на реальном значении
        `"developer"`) — старт настоящего разработчика перестал бы
        засчитываться занятостью, и сосед с пересекающейся зоной перестал
        бы ждать реального владельца.
        """
        self._cross_boundary(self.OWNER)
        store.journal(self.conn, self.OWNER, "developer",
                     "agent run started", "визит developer")

        self.assertTrue(zone_lock._occupies(self.conn, self.OWNER))

        neighbor_row = store.get_task(self.conn, self.NEIGHBOR)
        conflict = zone_lock.blocking_conflict(self.conn, self.NEIGHBOR,
                                               neighbor_row)
        self.assertIsNotNone(conflict)
        self.assertEqual(conflict, (self.ZONE, self.OWNER, "in_dev"))
        self.assertIsNotNone(
            zone_lock.refusal(self.conn, self.NEIGHBOR, neighbor_row))

    def test_ac4_release_action_by_any_actor_still_occupies(self):
        """`RELEASE_ACTION` после границы пребывания — признак занятости
        НЕЗАВИСИМО от актора записи (требование 1: фильтр роли `developer`
        применяется только к `"agent run started"`, не к `RELEASE_ACTION`).
        Журналируется здесь актором `test_author` намеренно (не через
        `cmd_zone_release`, который всегда пишет `"operator"`) — чтобы
        проверить именно независимость от актора, а не штатный путь
        Оператора.

        Ловит мутацию: фильтр роли `developer` требования 1 по ошибке
        применён и к `RELEASE_ACTION` (не только к `"agent run started"`)
        — снятие ожидания актором, отличным от `developer`/`operator`,
        перестало бы считаться занятостью.
        """
        self._cross_boundary(self.OWNER)
        store.journal(self.conn, self.OWNER, "test_author",
                     zone_lock.RELEASE_ACTION, "снятие ожидания (тест)")

        self.assertTrue(zone_lock._occupies(self.conn, self.OWNER))

    def test_ac5_refusal_message_format_unchanged_for_real_owners(self):
        """Форма сообщения `refusal` для соседа, заблокированного РЕАЛЬНЫМ
        владельцем (актор `developer` либо `RELEASE_ACTION`), не меняется:
        называет путь зоны, id и состояние владельца — в обоих случаях.

        Ловит мутацию: ветвление, добавленное фильтром роли, меняет
        аргументы `blocking_conflict`/`refusal` (например путает местами
        путь/id при добавлении проверки актора) — сообщение перестаёт
        называть путь, id или состояние занявшей задачи.
        """
        for label, journal_owner in (
            ("developer", lambda: store.journal(
                self.conn, self.OWNER, "developer",
                "agent run started", "визит developer")),
            ("release", lambda: store.journal(
                self.conn, self.OWNER, "operator",
                zone_lock.RELEASE_ACTION, "снятие ожидания (тест)")),
        ):
            with self.subTest(owner=label):
                # Свежая пара задач на каждый подслучай (setUp() второй раз,
                # тот же приём, что tasks/T043/acceptance_tests/
                # test_retro_done.py::test_ac4) — предыдущий подслучай не
                # должен влиять на границу пребывания OWNER.
                self.setUp()
                self._cross_boundary(self.OWNER)
                journal_owner()

                neighbor_row = store.get_task(self.conn, self.NEIGHBOR)
                text = zone_lock.refusal(self.conn, self.NEIGHBOR,
                                         neighbor_row)

                self.assertIsNotNone(text)
                self.assertIn(self.ZONE, text)
                self.assertIn(self.OWNER, text)
                self.assertIn("in_dev", text)


if __name__ == "__main__":
    unittest.main()
