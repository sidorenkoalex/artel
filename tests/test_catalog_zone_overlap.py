"""Юнит-тесты предупреждения `new` о пересечении зон и пометки `status`
(SPEC 01M3GKJ84XM5QPC6TK5EE307Q9, требования 1-3): `_tz_zone_paths`,
`_warn_zone_overlap`, `_zone_forecast_suffix` и сквозной путь
`cmd_new`/`cmd_status`.

Сама сверка пересечения — `tests/test_zone_lock_forecast.py`; здесь
предмет — что `new` заводит задачу НЕСМОТРЯ на пересечение (отказом
предупреждение не становится), что запись журнала находится по
фиксированному действию, и что добавка `status` достаётся трём
состояниям ДО `in_dev`, но не самому `in_dev` (его суффикс ожидания зоны
не меняется).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, store, zone_lock  # noqa: E402
from tests.sandbox import (InitializedTmpRootTest,  # noqa: E402
                           SchemaTmpRootTest, capture, capture_new_task_id)

# ТЗ Оператора: пути упомянуты ТОЛЬКО в строке «Зоны:» — существующая
# сверка путей ТЗ (`_tz_path_refusal`) на таком тексте молчит, и предмет
# теста не подменяется её отказом. Строки «Рамка:» нет намеренно: иначе
# `new` печатал бы ещё и подсказку калибровки.
TZ_ZONES = """Источник: копилка.

Требуется:
1. Разобрать очередь.

Зоны: orchestrator/pull.py,
docs/stack.md.
"""

TZ_COMMON_ZONES_ONLY = """Требуется:
1. Разобрать очередь.

Зоны: tests/, orchestrator/config.py.
"""


def seed_task(task_id: str, state: str, zones: str) -> None:
    conn = store.db()
    store.insert_task(conn, task_id, f"Задача {task_id}", state,
                      f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                      config.DEFAULT_BUDGET_USD)
    store.update_task(conn, task_id, zones=zones)


class TzZonePathsTest(unittest.TestCase):

    def test_wrapped_zones_line_is_parsed_and_common_zones_dropped(self):
        """Строка «Зоны:» с переносом даёт оба пути; общие зоны
        (`config.COMMON_ZONES`) из множества выпадают.

        Ловит мутацию: разбор зон ТЗ заведён вторым регэкспом вместо
        общего `_tz_sections` — перенесённая строка потеряла бы
        `docs/stack.md`, и предупреждение молчало бы о половине зон; либо
        `_own_paths` не применён — `tests/` считался бы пересечением."""
        self.assertEqual(catalog._tz_zone_paths(TZ_ZONES),
                         {"orchestrator/pull.py", "docs/stack.md"})
        self.assertEqual(catalog._tz_zone_paths(TZ_COMMON_ZONES_ONLY), set())


class WarnZoneOverlapTest(SchemaTmpRootTest):

    TASK = "01ZONEOVERLAPNEWTASKXX"

    def setUp(self):
        super().setUp()
        seed_task(self.TASK, "spec_writing", "")

    def warn(self, tz_raw: str) -> str:
        return capture(catalog._warn_zone_overlap, store.db(), self.TASK,
                       tz_raw)

    def journal_rows(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
                if r["action"] == catalog.ZONE_OVERLAP_ACTION]

    def test_warning_names_id_state_and_shared_path(self):
        """Пересечение с задачей в `in_dev`: напечатанный текст несёт id
        задачи, её состояние и общий путь, а журнал — запись с
        фиксированным действием.

        Ловит мутацию: из текста предупреждения выпало любое из трёх
        (id, состояние, путь) — Оператор не смог бы понять, кого именно
        ждать; либо действие журнала стало вариативным — читатель журнала
        и этот тест перестали бы находить запись."""
        seed_task("01ZONEOVERLAPHOLDERXXX", "in_dev", "orchestrator/pull.py")

        out = self.warn(TZ_ZONES)

        self.assertIn("01ZONEOVERLAPHOLDERXXX", out)
        self.assertIn("in_dev", out)
        self.assertIn("orchestrator/pull.py", out)
        rows = self.journal_rows()
        self.assertEqual(len(rows), 1, out)
        self.assertIn("01ZONEOVERLAPHOLDERXXX", rows[0]["detail"])
        self.assertIn("orchestrator/pull.py", rows[0]["detail"])

    def test_warning_fires_for_a_task_that_will_occupy_the_zone_later(self):
        """Пересечение с задачей в `tests_writing` (займёт зону позже) —
        то же предупреждение; то же для `spec_writing`/`spec_gate`.

        Ловит мутацию: `new` спрашивает только про `BLOCKING_STATES` —
        задачи волны, чьи SPEC/планки пишутся прямо сейчас, в
        предупреждение не попали бы, а именно они и выстраиваются в
        очередь (волна 26–27.09)."""
        seed_task("01ZONEOVERLAPTESTSWRIT", "tests_writing",
                  "orchestrator/pull.py")
        seed_task("01ZONEOVERLAPSPECGATEX", "spec_gate", "docs/stack.md")

        out = self.warn(TZ_ZONES)

        self.assertIn("01ZONEOVERLAPTESTSWRIT", out)
        self.assertIn("01ZONEOVERLAPSPECGATEX", out)
        self.assertEqual(len(self.journal_rows()), 1)

    def test_no_overlap_prints_nothing_and_journals_nothing(self):
        """Пересечения нет, а также пересечение ТОЛЬКО по общим зонам —
        ни вывода, ни записи журнала; задача в `done` с той же зоной
        предупреждения не даёт.

        Ловит мутацию: предупреждение печатается безусловно (например,
        проверка пустого списка потеряна) — каждое `new` печатало бы
        пустой заголовок, и сигнал обесценился бы."""
        seed_task("01ZONEOVERLAPDONEHOLDR", "done", "orchestrator/pull.py")
        seed_task("01ZONEOVERLAPCOMMONZON", "in_dev",
                  "tests/test_pull.py, orchestrator/config.py")

        self.assertEqual(self.warn(TZ_ZONES), "")
        self.assertEqual(self.warn(TZ_COMMON_ZONES_ONLY), "")
        self.assertEqual(self.journal_rows(), [])


class CmdNewZoneOverlapTest(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.tz_file = self.root / "TZ.md"
        self.tz_file.write_text(TZ_ZONES, encoding="utf-8")
        patcher = mock.patch.object(catalog, "_warn_pin_divergence")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_new_creates_the_task_and_warns_after_the_row_exists(self):
        """`new --tz` с пересекающимся ТЗ: задача заведена (строка в БД,
        id возвращён), предупреждение напечатано, запись журнала лежит в
        журнале ЗАВЕДЁННОЙ задачи.

        Ловит мутацию: предупреждение превращено в отказ (`sys.exit`) или
        перенесено ДО `_new_task_row` — `cmd_new` либо не вернул бы id,
        либо `store.journal` писала бы в несуществующую задачу, и записи
        в её журнале не оказалось бы."""
        seed_task("01ZONEOVERLAPCMDNEWHLD", "in_dev", "docs/stack.md")

        out, task_id = capture_new_task_id(catalog.cmd_new, "Фикстура",
                                           str(self.tz_file))

        self.assertTrue(store.task_exists(store.db(), task_id))
        self.assertIn("docs/stack.md", out)
        self.assertIn("01ZONEOVERLAPCMDNEWHLD", out)
        actions = [r["action"] for r in store.task_steps(store.db(), task_id)]
        self.assertIn(catalog.ZONE_OVERLAP_ACTION, actions)

    def test_new_without_overlap_journals_no_zone_overlap_record(self):
        """Пересечения нет — записи «пересечение зон при заведении» в
        журнале заведённой задачи нет вовсе.

        Ловит мутацию: запись пишется на каждом `new` независимо от
        пересечения — журнал любой задачи нёс бы ложное указание на
        очередь, которой не было."""
        out, task_id = capture_new_task_id(catalog.cmd_new, "Фикстура",
                                           str(self.tz_file))

        actions = [r["action"] for r in store.task_steps(store.db(), task_id)]
        self.assertNotIn(catalog.ZONE_OVERLAP_ACTION, actions)
        self.assertNotIn("пересечение зон", out)


class ZoneForecastSuffixTest(SchemaTmpRootTest):

    def setUp(self):
        super().setUp()
        seed_task("01ZONESUFFIXHOLDERXXXX", "in_dev", "orchestrator/pull.py")

    def row(self, task_id: str):
        return store.get_task(store.db(), task_id)

    def suffix(self, task_id: str) -> str:
        return catalog._zone_forecast_suffix(store.db(), self.row(task_id))

    def test_pre_dev_states_get_the_zone_taken_suffix(self):
        """Задача в `spec_writing`/`spec_gate`/`tests_writing`, чья зона
        пересекается с зоной задачи из `BLOCKING_STATES`, получает добавку
        «зона занята: <id>».

        Ловит мутацию: добавка выдаётся только одному из трёх состояний —
        Оператор видел бы будущую очередь не на всех задачах волны, что и
        есть предмет требования 3."""
        for number, state in enumerate(zone_lock.LATER_STATES):
            task_id = f"01ZONESUFFIXWAITER{number}XXX"
            seed_task(task_id, state, "orchestrator/pull.py")

            self.assertEqual(
                self.suffix(task_id),
                "  [зона занята: 01ZONESUFFIXHOLDERXXXX]", state)

    def test_in_dev_task_gets_no_zone_taken_suffix(self):
        """Строка задачи в `in_dev` добавки «зона занята» НЕ получает:
        её ожидание печатает существующий суффикс по
        `zone_lock.blocking_conflict`.

        Ловит мутацию: состояние `in_dev` попало в набор — строка задачи
        в `in_dev` несла бы обе добавки сразу, и существующий суффикс
        ожидания зоны (держатель, очередь, минуты) перестал бы быть
        единственным сообщением о зоне в этом состоянии."""
        seed_task("01ZONESUFFIXINDEVWAITR", "in_dev", "orchestrator/pull.py")

        self.assertEqual(self.suffix("01ZONESUFFIXINDEVWAITR"), "")

    def test_common_zone_overlap_gives_no_suffix(self):
        """Пересечение только по общим зонам добавки не даёт.

        Ловит мутацию: добавка считает пути без `_own_paths` — каждая
        задача пульта получала бы «зона занята» по `tests/`."""
        seed_task("01ZONESUFFIXCOMMONONLY", "tests_writing",
                  "tests/test_pull.py")

        self.assertEqual(self.suffix("01ZONESUFFIXCOMMONONLY"), "")

    def test_status_line_carries_the_suffix(self):
        """Добавка доходит до вывода `status` — в строке ждущей задачи,
        не в чужой.

        Ловит мутацию: `_zone_forecast_suffix` посчитан, но не подклеен к
        строке `cmd_status` — механика была бы невидимой Оператору,
        ради которого она и сделана."""
        seed_task("01ZONESUFFIXSTATUSWAIT", "spec_writing",
                  "orchestrator/pull.py")

        out = capture(catalog.cmd_status)

        waiter = [ln for ln in out.splitlines()
                  if "01ZONESUFFIXSTATUSWAIT" in ln]
        # Строка держателя выбирается по НАЧАЛУ строки: его id встречается
        # и в добавке ждущей задачи, поиском подстроки их не различить.
        holder = [ln for ln in out.splitlines()
                  if ln.startswith("01ZONESUFFIXHOLDERXXXX")]
        self.assertEqual(len(waiter), 1, out)
        self.assertIn("зона занята: 01ZONESUFFIXHOLDERXXXX", waiter[0])
        self.assertEqual(len(holder), 1, out)
        self.assertNotIn("зона занята", holder[0])


if __name__ == "__main__":
    unittest.main()
