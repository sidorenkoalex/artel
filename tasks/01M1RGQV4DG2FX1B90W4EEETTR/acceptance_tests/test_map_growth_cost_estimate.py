"""Приёмочные тесты 01M1RGQV4DG2FX1B90W4EEETTR — AC-1..AC-5, часть
AC-12 (константы `config` динамически, независимость двух target).

Источник — только tasks/01M1RGQV4DG2FX1B90W4EEETTR/SPEC.md, раздел
«Критерии приёмки». Схема данных и все конкретизации теста (имена
функций `report.py`, схема словаря оценки, имя новой константы
`config.MAP_GROWTH_CALLS_ESTIMATE`) — см. docstring `_fixtures.py`
этого каталога.

Красен до реализации: `orchestrator.report` ещё не несёт
`map_growth_cost_estimate` (и вспомогательных функций, которых зовёт
эта реализация) — импорт/вызов падает `AttributeError` на первом же
обращении, пока требование 1 SPEC не реализовано.
`NoAlertsOrFsmDependencyTest.test_ac5_no_fsm_module_imports_the_report_
module` — зелёный с рождения: `fsm.py`/`fsm_advance.py`/`fsm_autogate.
py` уже сегодня не импортируют `report` — тест фиксирует существующее
свойство кодовой базы, ловя будущий регресс, а не ждёт кода этой
задачи.
"""
import statistics
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm, fsm_advance, fsm_autogate, report, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures  # noqa: E402

CALLS_FALLBACK = 6  # значение теста для config.MAP_GROWTH_CALLS_ESTIMATE


class _CostEstimateTest(TmpRootTest):
    """Песочница: БД с одной задачей/target, фолбэк числа вызовов
    (AC-3) пропатчен фиксированным значением теста — тесты, которым
    нужна РЕАЛЬНАЯ медиана логов (AC-2), заводят собственные задачи с
    логами поверх, вытесняя фолбэк из выборки последних 10."""

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.create_schema(conn)
        self.conn = conn
        patcher = mock.patch.object(config, "MAP_GROWTH_CALLS_ESTIMATE",
                                    CALLS_FALLBACK, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_target(self, task_id: str, target: str) -> None:
        store.insert_task(self.conn, task_id, "Задача-фикстура", "done",
                          f"task/{task_id.lower()}", target, 10.0)


class TokensFromLatestProjectionTest(_CostEstimateTest):
    """AC-1: `tokens` — `bytes_projection` ПОСЛЕДНЕЙ записи ряда, если
    ключ присутствует в НЕЙ САМОЙ, делённое на 3."""

    def test_ac1_latest_bytes_projection_wins_over_bytes_total(self):
        """Две записи ряда: старая без `bytes_projection`, новая — с
        ним и другим `bytes_total`. `tokens` обязан взять `bytes_
        projection` НОВОЙ записи, не `bytes_total` ни новой, ни старой.

        Ловит мутацию: реализация берёт `bytes_total` последней записи
        вместо `bytes_projection`, когда он есть, — `tokens` вышел бы
        3000 (9000 // 3) вместо 2000 (6000 // 3).
        """
        self.make_target("T001", "alpha")
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:01Z",
                     bytes_total=5000)
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:02Z",
                     bytes_total=9000, bytes_projection=6000)

        result = report.map_growth_cost_estimate(self.conn, "alpha")

        self.assertEqual(result["tokens"], 6000 // 3)


class TokensFallBackToBytesTotalTest(_CostEstimateTest):
    """AC-1: `bytes_projection` отсутствует в ПОСЛЕДНЕЙ записи —
    `tokens` — её же `bytes_total`, делённое на 3."""

    def test_ac1_missing_projection_in_latest_uses_its_bytes_total(self):
        """Старая запись несёт `bytes_projection`, новая — нет; `tokens`
        обязан считаться от `bytes_total` НОВОЙ записи (12000 // 3), а
        не от чужого (более раннего) `bytes_projection`.

        Ловит мутацию: реализация ищет `bytes_projection` по ВСЕМУ ряду
        (не только в последней записи) — `tokens` вышел бы 4000 // 1
        (4000 // 3 = 1333) вместо честных 12000 // 3 = 4000.
        """
        self.make_target("T001", "alpha")
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:01Z",
                     bytes_total=1000, bytes_projection=4000)
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:02Z",
                     bytes_total=12000)

        result = report.map_growth_cost_estimate(self.conn, "alpha")

        self.assertEqual(result["tokens"], 12000 // 3)


class CallsMedianOfLastTenTasksGloballyTest(_CostEstimateTest):
    """AC-2: `calls` — медиана числа вызовов инструментов `developer`
    по логам шагов ЗА ПОСЛЕДНИЕ 10 ЗАДАЧ ГЛОБАЛЬНО (не по target)."""

    def test_ac2_median_over_last_ten_tasks_ignores_the_eleventh_and_target(self):
        """11 задач по возрастающему id, разные target вперемешку; самая
        старая (`T00`, несущая заодно и запись ряда target `alpha`)
        несёт заведомо экстремальное число вызовов (999) — должна быть
        исключена окном «последние 10». Оставшиеся 10 (`T01`..`T10`)
        несут числа 1..9,100 — медиана асимметричной выборки (5.5)
        отличима и от среднего (14.5), и от значения исключённой
        задачи.

        Ловит мутацию: окно «последние 10» не применяется (берутся ВСЕ
        задачи, включая `T00`) — тогда в выборке 11 значений, медиана
        сдвинулась бы на 7 (средний элемент 1,2,...,7,...,9,100,999);
        либо взято среднее вместо медианы — тогда результат был бы
        14.5, не 5.5; либо роль `developer` не отфильтрована и в счёт
        попали бы логи другой роли (проверяется отдельно ниже).
        """
        config.LOGS.mkdir(parents=True, exist_ok=True)

        counts_by_id = {"T00": 999, "T01": 1, "T02": 2, "T03": 3, "T04": 4,
                        "T05": 5, "T06": 6, "T07": 7, "T08": 8, "T09": 9,
                        "T10": 100}
        targets = {"T00": "alpha", "T01": "alpha", "T02": "beta",
                  "T03": "alpha", "T04": "beta", "T05": "alpha",
                  "T06": "beta", "T07": "alpha", "T08": "beta",
                  "T09": "alpha", "T10": "beta"}
        for task_id, n_calls in counts_by_id.items():
            store.insert_task(self.conn, task_id, "Задача", "done",
                              f"task/{task_id.lower()}", targets[task_id],
                              10.0)
            (config.LOGS / f"{task_id}-developer-1.log").write_text(
                _fixtures.developer_log_text(n_calls), encoding="utf-8")
        _fixtures.seed_map_size(self.conn, "T00", "2026-01-01 00:00:01Z",
                     bytes_total=3000)

        result = report.map_growth_cost_estimate(self.conn, "alpha")

        expected = statistics.median([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
        self.assertEqual(result["calls"], expected)
        self.assertNotEqual(result["calls"], 999)

    def test_ac2_ignores_logs_of_roles_other_than_developer(self):
        """Задачи последних 10 несут ТОЛЬКО логи роли `reviewer`
        (developer вообще не бежал) — выборка вызовов `developer` этой
        задачи пуста; при пустой глобальной выборке `calls` обязан уйти
        на фолбэк AC-3, а не посчитать медиану по чужой роли.

        Ловит мутацию: фильтр по роли в имени файла лога отсутствует —
        `calls` вышел бы медианой чисел вызовов `reviewer`, не фолбэком.
        """
        self.make_target("A0", "alpha")
        config.LOGS.mkdir(parents=True, exist_ok=True)
        for i in range(10):
            task_id = "T" + str(i).zfill(2)
            store.insert_task(self.conn, task_id, "Задача", "done",
                              f"task/{task_id.lower()}", "alpha", 10.0)
            (config.LOGS / f"{task_id}-reviewer-1.log").write_text(
                _fixtures.developer_log_text(50), encoding="utf-8")
        _fixtures.seed_map_size(self.conn, "A0", "2026-01-01 00:00:01Z",
                     bytes_total=3000)

        result = report.map_growth_cost_estimate(self.conn, "alpha")

        self.assertEqual(result["calls"], CALLS_FALLBACK)
        self.assertTrue(result["is_estimate"])


class CallsFallbackConstantTest(_CostEstimateTest):
    """AC-3: логов `developer` в выборке последних 10 задач нет вовсе —
    `calls` берётся из `config.MAP_GROWTH_CALLS_ESTIMATE`, оценка
    помечена как «оценка»."""

    def test_ac3_no_developer_logs_at_all_uses_named_config_constant(self):
        """Единственная задача в БД (меньше 10, логов `developer` нет
        вовсе — ни один файл `*-developer-*.log` не существует) — тот
        же случай, что «ни одна из последних 10 задач не дошла до шага
        developer» (SPEC AC-3). `calls` обязан прийти РОВНО из
        пропатченной константы, не быть нулём/нейтральным дефолтом
        реализации.

        Ловит мутацию: реализация возвращает 0 (или любую другую
        зашитую константу) вместо чтения `config.MAP_GROWTH_CALLS_
        ESTIMATE` — смена значения константы (см. `CALLS_FALLBACK` в
        этом файле против дефолта, который в итоге впишет разработчик)
        не изменила бы результат теста.
        """
        self.make_target("T001", "alpha")
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:01Z",
                     bytes_total=3000)

        result = report.map_growth_cost_estimate(self.conn, "alpha")

        self.assertEqual(result["calls"], CALLS_FALLBACK)
        self.assertTrue(result["is_estimate"],
                        "оценка на константе обязана нести пометку «оценка»")

    def test_ac3_real_median_is_not_marked_as_estimate(self):
        """Когда медиана посчитана по реальным логам (не фолбэк) —
        пометка «оценка» обязана быть снята, иначе Оператор не отличит
        приблизительный ориентир от посчитанного по факту числа.

        Ловит мутацию: `is_estimate` всегда `True` независимо от
        источника `calls` — Оператор всегда видел бы «оценка», даже
        когда есть настоящие логи.
        """
        self.make_target("A0", "alpha")
        config.LOGS.mkdir(parents=True, exist_ok=True)
        for i in range(10):
            task_id = "T" + str(i).zfill(2)
            store.insert_task(self.conn, task_id, "Задача", "done",
                              f"task/{task_id.lower()}", "alpha", 10.0)
            (config.LOGS / f"{task_id}-developer-1.log").write_text(
                _fixtures.developer_log_text(10 + i), encoding="utf-8")
        _fixtures.seed_map_size(self.conn, "A0", "2026-01-01 00:00:01Z",
                     bytes_total=3000)

        result = report.map_growth_cost_estimate(self.conn, "alpha")

        self.assertFalse(result["is_estimate"])


class CostUsdFormulaTest(_CostEstimateTest):
    """AC-4: `cost_usd` = `tokens × calls × cache_read_usd_per_token` +
    `tokens × cache_creation_usd_per_token`, курс роли `developer`."""

    def test_ac4_cost_combines_read_and_creation_rate_of_developer_role(self):
        """Единственная задача в БД (нет логов → `calls` = пропатченный
        фолбэк `CALLS_FALLBACK`, известное число), одна запись ряда без
        `bytes_projection` (`tokens` = `bytes_total // 3`, тоже
        известное число) — `cost_usd` обязан РОВНО совпасть с формулой
        AC-4, посчитанной здесь теми же курсами `config.TOKEN_RATES
        ["developer"]` (не литералом — курс может быть перекалиброван).

        Ловит мутацию: реализация не прибавляет вторую половину формулы
        (`tokens × cache_creation_usd_per_token`) — результат совпал бы
        только с первым слагаемым, разойдясь с ожиданием на величину
        `tokens × cache_creation_usd_per_token` (не 0 — курс не нулевой).
        """
        self.make_target("T001", "alpha")
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:01Z",
                     bytes_total=3000)
        rates = config.TOKEN_RATES["developer"]
        tokens = 3000 // 3
        expected = (tokens * CALLS_FALLBACK * rates["cache_read_usd_per_token"]
                   + tokens * rates["cache_creation_usd_per_token"])

        result = report.map_growth_cost_estimate(self.conn, "alpha")

        self.assertAlmostEqual(result["cost_usd"], expected, places=9)


class NoAlertsOrFsmDependencyTest(_CostEstimateTest):
    """AC-5: оценка не заводит алертов и не читается ни одним
    переходом FSM — единственный потребитель — вывод `report`."""

    def test_ac5_computing_the_estimate_calls_no_alerts_function(self):
        """Подмена всего модуля `alerts`, каким его видит `report.py`,
        шпионом: после вызова `map_growth_cost_estimate` ни один его
        метод не должен быть тронут — оценка только читает данные.

        Ловит мутацию: реализация «на всякий случай» заводит алерт при
        отсутствии логов (например, `alerts.raise_alert(..., "оценка
        по фолбэку")`) — шпион зафиксировал бы вызов.
        """
        self.make_target("T001", "alpha")
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:01Z",
                     bytes_total=3000)

        with mock.patch.object(report, "alerts", mock.Mock()) as spy_alerts:
            report.map_growth_cost_estimate(self.conn, "alpha")

        self.assertEqual(spy_alerts.method_calls, [])

    def test_ac5_no_fsm_module_imports_the_report_module(self):
        """Ни один из трёх модулей перехода FSM (`fsm.py`/`fsm_advance.
        py`/`fsm_autogate.py`) не импортирует `report` — единственное
        место, что читает оценку (SPEC требование 2), это сам вывод
        `artel report`, не переход состояния. Зона этой задачи (SPEC,
        frontmatter `zones`) и так не включает файлы FSM — этот тест
        ловит РЕГРЕСС будущей задачи, которая решит связать их напрямую.

        Ловит мутацию: будущая правка добавляет `from . import report`
        (или `from orchestrator import report`) в один из трёх модулей
        FSM, чтобы прочитать оценку внутри перехода, — тест перестанет
        проходить, ловя нарушение AC-5 буквально по тексту критерия.
        """
        for module in (fsm, fsm_advance, fsm_autogate):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertNotIn("import report", source,
                            f"{module.__name__} не должен импортировать report")


class TargetIndependenceTest(_CostEstimateTest):
    """AC-12 (инвариант 22): оценка одного target не путает свои
    `bytes_total`/`bytes_projection` с данными другого target; `calls`
    — намеренно ОБЩИЙ курс на все target (требование 1 SPEC), поэтому
    совпадение `calls` двух target — не утечка, а корректность."""

    def test_ac12_two_targets_keep_their_own_tokens_but_share_calls(self):
        """Два target с разными по размеру записями ряда — `tokens`
        каждого обязан отражать ИМЕННО его собственную запись, не
        соседнюю; `calls` у обоих одинаков (фолбэк, глобальный на все
        target — требование 1: «курс роли один на все target»).

        Ловит мутацию: `tokens` для `alpha` посчитан по записи `beta`
        (перепутан фильтр по target при выборе последней записи ряда)
        — `result_alpha["tokens"]` совпал бы с `result_beta["tokens"]`
        вместо собственного значения 1000 (3000 // 3).
        """
        self.make_target("TA", "alpha")
        self.make_target("TB", "beta")
        _fixtures.seed_map_size(self.conn, "TA", "2026-01-01 00:00:01Z",
                     bytes_total=3000)
        _fixtures.seed_map_size(self.conn, "TB", "2026-01-01 00:00:01Z",
                     bytes_total=30000)

        result_alpha = report.map_growth_cost_estimate(self.conn, "alpha")
        result_beta = report.map_growth_cost_estimate(self.conn, "beta")

        self.assertEqual(result_alpha["tokens"], 3000 // 3)
        self.assertEqual(result_beta["tokens"], 30000 // 3)
        self.assertNotEqual(result_alpha["tokens"], result_beta["tokens"])
        self.assertEqual(result_alpha["calls"], result_beta["calls"])


if __name__ == "__main__":
    unittest.main()
