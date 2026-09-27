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

from orchestrator import catalog, config, fsm, store, zone_lock  # noqa: E402
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

# Вёрстка ТЗ по ~72 символа рвёт длинный путь по `/` или `-` — как в живых
# ТЗ пульта (`tasks/01M3FQ2Z2PY0E9T5F5WQ207NP5/TZ.md`:
# `orchestrator/⏎schema.py`, `tasks/01M1NSR5M5THYRC0RFWPMVE2DW/TZ.md`:
# `docs/reference/⏎role-home.md`). Здесь разорваны оба вида: путь после
# слэша и путь после дефиса (замечание R2-F1 ревью итерации 2).
TZ_WRAPPED_PATHS = """Требуется:
1. Разобрать очередь.

Зоны: orchestrator/canary.py, orchestrator/
schema.py, docs/operator-
session.md, tests/.
"""

# Перенос в ПРОЗЕ раздела «Зоны:» (так свёрстана половина живых ТЗ):
# идущий за ним путь начинает новую строку, а предыдущая кончается
# латинским идентификатором задачи.
TZ_WRAPPED_PROSE = """Требуется:
1. Разобрать очередь.

Зоны: orchestrator/pull.py, конфликт зон с 01M3FQ2V77QNK95Z599DM124QN
docs/stack.md.
"""


def seed_task(task_id: str, state: str, zones: str,
              target: str = config.DEFAULT_TARGET) -> None:
    """Строка задачи с заданными зонами. Для состояний ДО гейта SPEC это
    не синтетика: `cmd_new` пишет зоны ТЗ в `tasks.zones` сразу при
    заведении (`_record_preliminary_zones`, ответ Оператора ANSWER-1
    п.2) — сквозной путь того же состояния проверяет
    `CmdNewPreliminaryZonesTest` ниже, без прямой правки колонки."""
    conn = store.db()
    store.insert_task(conn, task_id, f"Задача {task_id}", state,
                      f"task/{task_id.lower()}-x", target,
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

    def test_a_path_broken_by_the_tz_wrap_is_collected_whole(self):
        """Путь, разорванный вёрсткой ТЗ по `/` или по `-`, собирается
        целым, и обрывка-каталога (`orchestrator/`) в множестве нет.

        Ловит мутацию: склейка разрыва (`_TZ_WRAPPED_PATH_BREAK`) снята —
        обрывок `orchestrator/` стал бы самостоятельной зоной и накрыл бы
        почти любую задачу пульта (ложное пересечение), а разорванный
        `docs/operator-session.md` потерялся бы целиком (пропуск
        настоящего — прецедент «Контекста» SPEC)."""
        paths = catalog._tz_zone_paths(TZ_WRAPPED_PATHS)

        self.assertEqual(paths, {"orchestrator/canary.py",
                                 "orchestrator/schema.py",
                                 "docs/operator-session.md"})

    def test_a_wrap_in_the_prose_keeps_the_path_that_follows_it(self):
        """Перенос в прозе раздела «Зоны:» не склеивается: путь, стоящий в
        начале следующей строки, остаётся в множестве.

        Ловит мутацию: склейка снимает ВСЕ переносы, а не только разрыв
        внутри пути — `docs/stack.md` прилип бы к идентификатору задачи
        слева (`…124QNdocs/stack.md`), где `guard.PATH_MENTION` запрещает
        букву/цифру перед кандидатом, и зона документа исчезла бы из
        прогноза."""
        paths = catalog._tz_zone_paths(TZ_WRAPPED_PROSE)

        self.assertIn("docs/stack.md", paths)
        self.assertIn("orchestrator/pull.py", paths)


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
        то же предупреждение; то же для `spec_writing` и `spec_gate`.

        Ловит мутацию: `new` спрашивает только про `BLOCKING_STATES` —
        задачи волны, чьи SPEC/планки пишутся прямо сейчас, в
        предупреждение не попали бы, а именно они и выстраиваются в
        очередь (волна 26–27.09)."""
        seed_task("01ZONEOVERLAPTESTSWRIT", "tests_writing",
                  "orchestrator/pull.py")
        seed_task("01ZONEOVERLAPSPECGATEX", "spec_gate", "docs/stack.md")
        seed_task("01ZONEOVERLAPSPECWRITE", "spec_writing",
                  "orchestrator/pull.py")

        out = self.warn(TZ_ZONES)

        self.assertIn("01ZONEOVERLAPTESTSWRIT", out)
        self.assertIn("01ZONEOVERLAPSPECGATEX", out)
        self.assertIn("01ZONEOVERLAPSPECWRITE", out)
        self.assertEqual(len(self.journal_rows()), 1)

    def test_a_task_of_a_foreign_target_gets_no_warning(self):
        """Заводимая задача чужого target'а предупреждения не получает и
        записи журнала не пишет (ответ Оператора ANSWER-1 п.3): замок зон
        — механика только основного target'а, очереди для такой задачи не
        будет никогда.

        Ловит мутацию: фильтр target'а снят (асимметрия с парной добавкой
        `status`, которая его проверяет) — задача внешнего target'а
        уносила бы в журнал обещание очереди, которой нет."""
        seed_task("01ZONEOVERLAPFOREIGNHL", "in_dev", "orchestrator/pull.py")

        out = capture(catalog._warn_zone_overlap, store.db(), self.TASK,
                      TZ_ZONES, "acme")

        self.assertEqual(out, "")
        self.assertEqual(self.journal_rows(), [])
        # Тот же вызов без чужого target'а предупреждение даёт — иначе
        # тест зеленел бы и на сломанной сверке.
        self.assertIn("01ZONEOVERLAPFOREIGNHL", self.warn(TZ_ZONES))

    def test_a_path_broken_by_the_wrap_still_finds_the_real_overlap(self):
        """Сценарий 2 замечания R2-F1: ТЗ с разорванным вёрсткой
        `docs/operator-⏎session.md` против задачи, заявившей этот документ
        целиком, — предупреждение печатается и журналируется.

        Ловит мутацию: разрыв не склеен — единственным элементом стал бы
        `'docs/operator-\\nsession.md'`, `_shared_zone` вернул бы `None`, и
        механика молчала бы ровно в прецеденте, ради которого заведена
        (три задачи волны 26–27.09 правили один раздел этого документа)."""
        seed_task("01ZONEOVERLAPDOCHOLDER", "in_dev",
                  "docs/operator-session.md")

        out = self.warn(TZ_WRAPPED_PATHS)

        self.assertIn("01ZONEOVERLAPDOCHOLDER", out)
        self.assertIn("docs/operator-session.md", out)
        self.assertEqual(len(self.journal_rows()), 1, out)

    def test_a_fragment_of_a_broken_path_invents_no_overlap(self):
        """Сценарий 1 замечания R2-F1: то же ТЗ против задачи с зоной
        `orchestrator/runner.py`, которой в перечне нет, — ни вывода, ни
        записи журнала.

        Ловит мутацию: разрыв не склеен — обрывок `orchestrator/` накрыл бы
        зону-соседа по вложенности, и `new` обещал бы очередь, которой не
        будет: к `in_dev` колонка уже перезаписана зонами SPEC, где
        каталога `orchestrator/` нет."""
        seed_task("01ZONEOVERLAPRUNNERHLD", "in_dev", "orchestrator/runner.py")

        self.assertEqual(self.warn(TZ_WRAPPED_PATHS), "")
        self.assertEqual(self.journal_rows(), [])
        # Заявленный целиком путь того же ТЗ пересечение даёт — иначе тест
        # зеленел бы и на разборе, потерявшем все зоны разом.
        seed_task("01ZONEOVERLAPCANARYHLD", "spec_gate",
                  "orchestrator/canary.py")
        self.assertIn("01ZONEOVERLAPCANARYHLD", self.warn(TZ_WRAPPED_PATHS))

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


class CmdNewPreliminaryZonesTest(InitializedTmpRootTest):
    """Зоны ТЗ в колонке `tasks.zones` сразу при заведении (ответ
    Оператора ANSWER-1 п.2 по замечанию R1-F2): без них прогноз слеп к
    `spec_writing`/`spec_gate`, потому что колонку писал только approve
    на гейте SPEC."""

    def setUp(self):
        super().setUp()
        self.tz_file = self.root / "TZ.md"
        self.tz_file.write_text(TZ_ZONES, encoding="utf-8")
        patcher = mock.patch.object(catalog, "_warn_pin_divergence")
        patcher.start()
        self.addCleanup(patcher.stop)

    def new_task(self) -> str:
        _out, task_id = capture_new_task_id(catalog.cmd_new, "Фикстура",
                                            str(self.tz_file))
        return task_id

    def zones_of(self, task_id: str):
        return store.get_task(store.db(), task_id)["zones"]

    def test_new_writes_the_tz_zones_into_the_task_row(self):
        """`new --tz` пишет пути строки «Зоны:» в колонку `tasks.zones`
        и журналирует это фиксированным действием; задача при этом в
        `spec_writing`.

        Ловит мутацию: запись предварительных зон снята — колонка
        осталась бы `NULL` до approve на гейте SPEC, и требования 1 и 3
        не наблюдались бы ни в одном состоянии до него (ровно замечание
        R1-F2)."""
        task_id = self.new_task()

        row = store.get_task(store.db(), task_id)
        self.assertEqual(row["state"], "spec_writing")
        self.assertEqual(row["zones"], "docs/stack.md, orchestrator/pull.py")
        actions = [r["action"] for r in store.task_steps(store.db(), task_id)]
        self.assertIn(catalog.PRELIMINARY_ZONES_ACTION, actions)

    def test_a_wrapped_tz_writes_whole_paths_into_the_column(self):
        """Продуктовый путь `new --tz` с ТЗ, чью строку «Зоны:» вёрстка
        разорвала по `/` и по `-`: в колонку `tasks.zones` ложатся целые
        пути, обрывка-каталога там нет.

        Ловит мутацию: склейка разрыва снята — колонка кандидата волны
        несла бы `orchestrator/` и `'orchestrator/\\nschema.py'`, и добавка
        `status` («зона занята») срабатывала бы не на ту зону у любой
        задачи пульта (замечание R2-F1, сценарий 1 на продуктовом
        пути)."""
        self.tz_file.write_text(TZ_WRAPPED_PATHS, encoding="utf-8")

        zones = self.zones_of(self.new_task())

        # Колонка несёт зоны КАК ЗАЯВЛЕНЫ, вместе с общей `tests/` (её
        # отбрасывает уже сверка, `zone_lock._own_paths`) — предмет теста
        # ровно в том, что пути в ней целые.
        self.assertEqual(zones, "docs/operator-session.md, "
                                "orchestrator/canary.py, "
                                "orchestrator/schema.py, tests/")

    def test_tz_without_a_zones_line_leaves_the_column_null(self):
        """ТЗ без строки «Зоны:» колонку не трогает: `NULL` остаётся
        признаком «зона не заявлена вовсе», по которому
        `checkpoint._zone_paths` и гейт зон отключают свой фильтр.

        Ловит мутацию: пустой список зон пишется пустой строкой — «зон
        нет» стало бы неотличимо от «зоны заявлены пустыми», и фильтр
        WIP-чекпоинта посчитал бы посторонним любой путь такой задачи."""
        self.tz_file.write_text("Требуется:\n1. Что-то.\n", encoding="utf-8")

        self.assertIsNone(self.zones_of(self.new_task()))

    def test_second_task_of_the_wave_sees_the_first_one_before_the_spec_gate(self):
        """Сквозной сценарий «Контекста» SPEC, без единой правки колонки
        руками: первая задача волны заведена и ещё пишет SPEC
        (`spec_writing`), вторая заводится с пересекающимся ТЗ — и
        получает предупреждение с id первой.

        Ловит мутацию: прогноз читает зоны, которых в БД до гейта SPEC
        нет (или предварительная запись снята) — предупреждение молчало
        бы ровно в той ситуации, ради которой задача заведена, а тесты на
        seed-фикстурах этого не заметили бы."""
        first = self.new_task()

        out, second = capture_new_task_id(catalog.cmd_new, "Вторая",
                                          str(self.tz_file))

        self.assertEqual(store.get_task(store.db(), first)["state"],
                         "spec_writing")
        self.assertIn(first, out)
        # Общий путь — один на задачу (`_shared_zone`, первый по
        # алфавиту), как и у существующего отказа замка зон.
        self.assertIn("docs/stack.md", out)
        actions = [r["action"] for r in store.task_steps(store.db(), second)]
        self.assertIn(catalog.ZONE_OVERLAP_ACTION, actions)

    def test_reject_on_the_spec_gate_keeps_the_preliminary_zones(self):
        """Возврат SPEC аналитику предварительные зоны НЕ стирает (ответ
        Оператора ANSWER-1 п.2): задача возвращается в `spec_writing` с
        тем же значением колонки, и прогноз продолжает её видеть.

        Ловит мутацию: ветка `reject` на `spec_gate` начала писать зоны
        (например, обнулять их «на всякий случай») — задача волны,
        вернувшаяся с гейта, выпала бы из прогноза, и очередь снова
        стала бы невидимой."""
        task_id = self.new_task()
        store.update_task(store.db(), task_id, state="spec_gate")

        with mock.patch.object(fsm.github_adapter, "ensure_draft_mr"):
            capture(fsm._cmd_reject, store.db(), task_id, "SPEC переписать")

        self.assertEqual(store.get_task(store.db(), task_id)["state"],
                         "spec_writing")
        self.assertEqual(self.zones_of(task_id),
                         "docs/stack.md, orchestrator/pull.py")


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
