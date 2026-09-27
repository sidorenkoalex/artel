"""Юнит-тесты прогноза очереди зон `orchestrator/zone_lock.py`
(SPEC 01M3GKJ84XM5QPC6TK5EE307Q9, требования 1 и 3): `forecast_overlaps`,
`task_zone_paths`, наборы состояний `LATER_STATES`/`FORECAST_STATES`.

Предмет отличается от существующего `tests/test_zone_lock.py` ровно тем,
что прогноз НЕ применяет признак «занимает зону» (`_occupies`, старт шага
разработчика): ни одна задача в этой песочнице не журналирует ни
`CLAIM_ACTION`, ни «agent run started» — и тем не менее попадает в
прогноз. Отказ входа в `in_dev` (`blocking_conflict`/`refusal`) этими
тестами не затрагивается вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, store, zone_lock  # noqa: E402
from tests.sandbox import SchemaTmpRootTest  # noqa: E402


class ForecastOverlapsTest(SchemaTmpRootTest):

    def seed(self, task_id: str, state: str, zones: str, *,
             target: str | None = None, zones_extension: str | None = None):
        conn = store.db()
        store.insert_task(conn, task_id, f"Задача {task_id}", state,
                          f"task/{task_id.lower()}-x",
                          target or config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.update_task(conn, task_id, zones=zones,
                          zones_extension=zones_extension)

    def forecast(self, own, **kwargs):
        return zone_lock.forecast_overlaps(store.db(), set(own), **kwargs)

    # ------------------------------------------------- состав набора

    def test_in_dev_task_without_developer_start_is_still_forecast(self):
        """Задача в `in_dev`, ни разу не стартовавшая шаг разработчика
        (журнал пуст — `_occupies` для неё `False`), в прогноз попадает:
        она зону займёт, как только шаг начнётся.

        Ловит мутацию: прогноз начинает фильтровать кандидатов
        `_occupies`, как отказ входа в `in_dev` — список оказался бы
        пустым, и `new` молчал бы ровно о той очереди, которую задача и
        разбирает."""
        self.seed("01FORECASTINDEVNOSTART", "in_dev", "orchestrator/pull.py")

        self.assertFalse(zone_lock._occupies(store.db(),
                                             "01FORECASTINDEVNOSTART"))
        self.assertEqual(
            self.forecast(["orchestrator/pull.py"]),
            [("orchestrator/pull.py", "01FORECASTINDEVNOSTART", "in_dev")])

    def test_tests_writing_task_is_forecast_as_future_occupier(self):
        """`tests_writing` — состояние, которое займёт зону позже
        (`LATER_STATES`), и в прогноз входит.

        Ловит мутацию: набор прогноза сузили до `BLOCKING_STATES` —
        задача с готовой планкой, которой до зоны остался один гейт, в
        предупреждение `new` не попала бы (ровно случай волны
        26–27.09)."""
        self.seed("01FORECASTTESTSWRITING", "tests_writing",
                  "orchestrator/pull.py")

        self.assertEqual(
            self.forecast(["orchestrator/pull.py"]),
            [("orchestrator/pull.py", "01FORECASTTESTSWRITING",
              "tests_writing")])

    def test_done_and_killed_tasks_are_not_forecast(self):
        """Закрытые задачи зону не займут никогда — ни `done`, ни
        `killed` в прогнозе нет.

        Ловит мутацию: набор состояний заменили на «любое, кроме
        пустого» — каждая закрытая задача с той же зоной давала бы
        ложное предупреждение, и предупреждение перестало бы что-либо
        значить."""
        self.seed("01FORECASTDONETASKXXXX", "done", "orchestrator/pull.py")
        self.seed("01FORECASTKILLEDTASKXX", "killed", "orchestrator/pull.py")

        self.assertEqual(self.forecast(["orchestrator/pull.py"]), [])

    def test_states_parameter_narrows_the_scan_to_blocking_states(self):
        """Добавка `status` спрашивает только про `BLOCKING_STATES`
        (требование 3): кандидат в `tests_writing` при этом наборе не
        возвращается, кандидат в `in_dev` — возвращается.

        Ловит мутацию: `states` игнорируется и сверка всегда идёт по
        `FORECAST_STATES` — строка задачи в `spec_writing` получила бы
        добавку «зона занята» из-за другой задачи, которая сама зону
        только ждёт."""
        self.seed("01FORECASTSTATESLATERX", "tests_writing",
                  "orchestrator/pull.py")
        self.seed("01FORECASTSTATESINDEVX", "in_dev", "orchestrator/pull.py")

        self.assertEqual(
            self.forecast(["orchestrator/pull.py"],
                          states=zone_lock.BLOCKING_STATES),
            [("orchestrator/pull.py", "01FORECASTSTATESINDEVX", "in_dev")])

    def test_forecast_states_covers_blocking_and_later_states(self):
        """`FORECAST_STATES` — объединение занимающих и «займут позже»,
        без `done`/`killed`.

        Ловит мутацию: из набора выпало любое из занимающих состояний
        (например `escalated`, задача которого код уже написала) — её
        зона перестала бы попадать в прогноз."""
        self.assertEqual(set(zone_lock.FORECAST_STATES),
                         set(zone_lock.BLOCKING_STATES)
                         | set(zone_lock.LATER_STATES))
        self.assertNotIn("done", zone_lock.FORECAST_STATES)
        self.assertNotIn("killed", zone_lock.FORECAST_STATES)

    # ------------------------------------------------- способ сверки

    def test_common_zones_are_not_an_overlap(self):
        """Пересечение только по путям `config.COMMON_ZONES` (`tests/`,
        `orchestrator/config.py`) пересечением не считается — с учётом
        вложенности пути внутрь общего каталога.

        Ловит мутацию: прогноз считает пути сам, без `_own_paths` — каждая
        задача пульта пересекалась бы с каждой по `tests/`, и
        предупреждение печаталось бы всегда."""
        self.seed("01FORECASTCOMMONZONESX", "in_dev",
                  "tests/test_pull.py, orchestrator/config.py")

        self.assertEqual(
            self.forecast(["tests/test_zone_lock.py",
                           "orchestrator/config.py"]), [])

    def test_directory_zone_overlaps_a_file_inside_it_reporting_the_narrower(self):
        """Своя зона — файл, чужая — каталог, его содержащий: пересечение
        есть, а называется более узкий путь (конкретное место конфликта).

        Ловит мутацию: сверка сведена к равенству строк (`_paths_overlap`
        заменён на `==`) — задача, заявившая каталог `docs/`, не
        пересекалась бы с задачей, заявившей `docs/stack.md`."""
        self.seed("01FORECASTDIRZONEXXXXX", "review", "docs/")

        self.assertEqual(
            self.forecast(["docs/stack.md"]),
            [("docs/stack.md", "01FORECASTDIRZONEXXXXX", "review")])

    def test_zones_extension_of_the_candidate_counts_as_its_zone(self):
        """Расширение зоны кандидата (`zones_extension`, выданное гейтом
        зон уже в `in_dev`) считается его зоной наравне с `zones`.

        Ловит мутацию: `task_zone_paths` читает только `zones` — задача,
        расширившая зону на `docs/stack.md` по ходу работы, исчезла бы
        из прогноза, хотя файл держит именно она."""
        self.seed("01FORECASTZONEEXTENDED", "in_dev", "orchestrator/pull.py",
                  zones_extension="docs/stack.md")

        self.assertEqual(
            self.forecast(["docs/stack.md"]),
            [("docs/stack.md", "01FORECASTZONEEXTENDED", "in_dev")])

    def test_own_task_and_foreign_target_are_skipped(self):
        """Сама задача (`exclude_task_id`) и задача другого target'а в
        прогноз не попадают.

        Ловит мутацию: `exclude_task_id`/фильтр target'а потеряны — задача
        предупреждала бы о пересечении с самой собой, а механика зон
        основного target'а распространилась бы на внешние проекты, для
        которых её нет."""
        self.seed("01FORECASTSELFEXCLUDED", "in_dev", "orchestrator/pull.py")
        self.seed("01FORECASTFOREIGNTARGT", "in_dev", "orchestrator/pull.py",
                  target="other-project")

        self.assertEqual(
            self.forecast(["orchestrator/pull.py"],
                          exclude_task_id="01FORECASTSELFEXCLUDED"), [])

    def test_empty_own_zones_give_no_overlap(self):
        """Своих зон нет (ТЗ без строки `Зоны:` или только общие пути) —
        прогноз пуст, `store.all_tasks` не спрашивается о невозможном.

        Ловит мутацию: пустое множество своих зон трактуется как «любая
        зона» — каждая задача в полёте попадала бы в предупреждение ТЗ,
        которое зон не заявляет вовсе."""
        self.seed("01FORECASTEMPTYOWNZONE", "in_dev", "orchestrator/pull.py")

        self.assertEqual(self.forecast([]), [])

    def test_several_overlaps_are_sorted_for_determinism(self):
        """Несколько пересечений — отсортированы (путь, id, состояние):
        порядок вывода и записи журнала детерминирован.

        Ловит мутацию: сортировка убрана — порядок строк предупреждения
        зависел бы от порядка задач в БД, и тест/читатель журнала не
        могли бы на него опираться."""
        self.seed("01FORECASTSORTSECONDXX", "in_dev", "docs/stack.md")
        self.seed("01FORECASTSORTFIRSTXXX", "spec_gate", "orchestrator/pull.py")

        self.assertEqual(
            self.forecast(["docs/stack.md", "orchestrator/pull.py"]),
            [("docs/stack.md", "01FORECASTSORTSECONDXX", "in_dev"),
             ("orchestrator/pull.py", "01FORECASTSORTFIRSTXXX", "spec_gate")])


if __name__ == "__main__":
    unittest.main()
