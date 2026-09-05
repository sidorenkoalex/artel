"""Приёмочные тесты 01M1RGQV4DG2FX1B90W4EEETTR — AC-6..AC-12 (кроме
части AC-12, покрытой `test_map_growth_cost_estimate.py`): блок
`artel report` по каждому target — таблица ряда, медиана калибровки,
открытые алерты, «измерений нет», зелёность существующих тестов.

Источник — только tasks/01M1RGQV4DG2FX1B90W4EEETTR/SPEC.md, раздел
«Критерии приёмки». Конкретизации теста (имена функций `report.py`,
имя новой константы `config.MAP_GROWTH_CALLS_ESTIMATE`, зависимость
данных части 1 без её кода) — см. docstring `_fixtures.py`.

Красен до реализации: большинство тестов этого файла зовут функции
`orchestrator.report`, которых ещё нет (`map_size_entries`/`map_size_
table_rows`/`map_growth_calibration_median`/`map_growth_open_alerts`) —
падают `AttributeError` на первом же обращении. Два теста `cmd_report()`
(AC-9/AC-10) падают иначе — САМ `cmd_report` сегодня отрабатывает без
исключений (существующий код), просто ещё не несёт нового блока —
искомая строка/сумма не находится в HTML (`AssertionError`, не
`AttributeError`), пока требования 3-4 SPEC не реализованы.
`ExistingReportTestsStayGreenTest.test_ac11_existing_test_report_module_
passes` — зелёный с рождения: гоняет уже существующий `tests/
test_report.py`, ничего нового не зовёт, обязан проходить и до, и после
реализации этой задачи (тест сохранения существующего поведения,
AC-11).

Тесты `cmd_report()` (AC-9/AC-10) заводят target ТОЛЬКО через
`store.insert_task` (задача с этим target существует) — не через
`targets.yaml`/`targets.load()`: остальной `report.py` (борд, закрытые
задачи, метрики) уже сегодня перечисляет всё через `store.all_tasks`,
без обращения к `targets.yaml`, и это же соблюдает существующий
`CmdReportIntegrationTest` (`tests/test_report.py`) — он тоже не сеет
`targets.yaml`. Блок этой задачи, требующий `targets.load()`, упал бы
`TargetsError` на ТОМ существующем тесте, что прямо нарушило бы AC-11.
"""
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, report, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures  # noqa: E402

NO_MEASUREMENTS_TEXT = ("измерений нет: карта ни разу не регенерировалась "
                        "после мержа этой версией")


class _ReportBlockTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        conn = store.db()
        store.create_schema(conn)
        self.conn = conn

    def make_target(self, task_id: str, target: str) -> None:
        store.insert_task(self.conn, task_id, "Задача-фикстура", "done",
                          f"task/{task_id.lower()}", target, 10.0)


class TableRowsTest(_ReportBlockTest):
    """AC-6: таблица последних 12 записей ряда, хронологически, только
    с полями, которые реально есть у записи."""

    def test_ac6_only_last_twelve_of_fifteen_in_chronological_order(self):
        """15 записей одного target по возрастающему `bytes_total`
        (1000..15000 с шагом 1000) — таблица обязана нести РОВНО 12:
        начиная с четвёртой записи (4000) и заканчивая пятнадцатой
        (15000), в хронологическом порядке (старые из выбранных —
        первыми).

        Ловит мутацию: реализация берёт ПЕРВЫЕ 12 записей ряда вместо
        последних — таблица несла бы 1000..12000 вместо 4000..15000;
        либо порядок обратный (свежие первыми) — первый элемент вышел
        бы 15000 вместо 4000.
        """
        self.make_target("T001", "alpha")
        for i in range(1, 16):
            _fixtures.seed_map_size(self.conn, "T001", f"2026-01-01 00:00:{i:02d}Z",
                         bytes_total=i * 1000)

        rows = report.map_size_table_rows(self.conn, "alpha")

        self.assertEqual(len(rows), 12)
        self.assertEqual([r["bytes_total"] for r in rows],
                         [n * 1000 for n in range(4, 16)])

    def test_ac6_bytes_projection_present_only_when_the_record_has_it(self):
        """Три записи: без `bytes_projection`, с ним, снова без — поле
        обязано отсутствовать в словаре строки ИМЕННО там, где его нет
        у записи (не `None`, не 0 — буквально отсутствующий ключ, как
        того требует AC-6/AC-3 части 1).

        Ловит мутацию: реализация всегда кладёт ключ `bytes_projection`
        (со значением `None`, когда его в записи нет) — `"bytes_
        projection" not in rows[0]` перестало бы выполняться.
        """
        self.make_target("T001", "alpha")
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:01Z",
                     bytes_total=1000)
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:02Z",
                     bytes_total=2000, bytes_projection=1500)
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:03Z",
                     bytes_total=3000)

        rows = report.map_size_table_rows(self.conn, "alpha")

        self.assertNotIn("bytes_projection", rows[0])
        self.assertEqual(rows[1]["bytes_projection"], 1500)
        self.assertNotIn("bytes_projection", rows[2])


class CalibrationMedianTest(_ReportBlockTest):
    """AC-7: медиана окна калибровки — тот же алгоритм, что часть 1
    (`doctor.check_map_growth`): фиксированное окно первых `config.
    MAP_GROWTH_CALIBRATION_MERGES` записей ПОСЛЕ точки отсчёта."""

    def test_ac7_window_not_yet_filled_shows_no_median(self):
        """Записей после точки отсчёта меньше окна калибровки — медиана
        обязана быть `None` (не 0, не медиана неполного окна).

        Ловит мутацию: реализация считает медиану по ЧАСТИЧНОМУ окну
        вместо ожидания его заполнения — результат был бы числом, не
        `None`.
        """
        with mock.patch.object(config, "MAP_GROWTH_CALIBRATION_MERGES", 5,
                              create=True):
            self.make_target("T001", "alpha")
            for i in range(1, 4):
                _fixtures.seed_map_size(self.conn, "T001",
                             f"2026-01-01 00:00:{i:02d}Z", bytes_total=i)

            result = report.map_growth_calibration_median(self.conn, "alpha")

        self.assertIsNone(result)

    def test_ac7_window_is_fixed_not_sliding_once_filled(self):
        """Окно из первых 4 записей ряда (без предшествующего ack —
        точка отсчёта — начало ряда): [1000,3000,2000,4000] — медиана
        2500. Пятая запись (999999) появляется ПОСЛЕ заполнения окна —
        база сравнения обязана остаться прежней (2500), не
        пересчитанной с учётом новой записи.

        Ловит мутацию: окно «скользит» — включает последние 4 записи
        ряда вместо первых 4 после точки отсчёта — медиана после
        появления пятой записи стала бы медианой [3000,2000,4000,999999]
        = 3500, не 2500.
        """
        with mock.patch.object(config, "MAP_GROWTH_CALIBRATION_MERGES", 4,
                              create=True):
            self.make_target("T001", "alpha")
            for i, bt in enumerate([1000, 3000, 2000, 4000], start=1):
                _fixtures.seed_map_size(self.conn, "T001",
                             f"2026-01-01 00:00:{i:02d}Z", bytes_total=bt)

            result_at_fill = report.map_growth_calibration_median(
                self.conn, "alpha")

            _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:05Z",
                         bytes_total=999999)
            result_after_new_record = report.map_growth_calibration_median(
                self.conn, "alpha")

        self.assertEqual(result_at_fill, 2500)
        self.assertEqual(result_after_new_record, 2500)

    def test_ac7_ack_moves_the_reference_point_to_the_latest_ack(self):
        """Два алерта `map.growth` этого target подтверждены в разное
        время; запись между ними (1) обязана быть исключена — точка
        отсчёта — момент ПОСЛЕДНЕГО (не первого) `ack`. Окно — первые 3
        записи ПОСЛЕ второго ack: [10,200,300] — медиана 200.

        Ловит мутацию: реализация берёт ПЕРВЫЙ подтверждённый алерт
        target вместо последнего — окно стало бы первыми 3 записями
        ПОСЛЕ первого ack: [1,10,200] (запись между акками попадает в
        окно) — медиана вышла бы 10, а не 200.
        """
        with mock.patch.object(config, "MAP_GROWTH_CALIBRATION_MERGES", 3,
                              create=True):
            self.make_target("T001", "beta")
            _fixtures.seed_ackd_map_growth_alert(self.conn, "beta",
                                      "2026-01-01 00:00:02Z", "первый ack")
            _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:03Z",
                         bytes_total=1)
            _fixtures.seed_ackd_map_growth_alert(self.conn, "beta",
                                      "2026-01-01 00:00:04Z", "второй ack")
            for i, bt in zip((5, 6, 7), (10, 200, 300)):
                _fixtures.seed_map_size(self.conn, "T001",
                             f"2026-01-01 00:00:{i:02d}Z", bytes_total=bt)

            result = report.map_growth_calibration_median(self.conn, "beta")

        self.assertEqual(result, 200)


class OpenAlertsTest(_ReportBlockTest):
    """AC-8: список открытых (`ack_ts IS NULL`) алертов `map.growth`
    ИМЕННО этого target."""

    def test_ac8_excludes_acked_other_source_and_other_target(self):
        """Четыре алерта-приманки: подтверждённый map.growth того же
        target, открытый другого источника того же target, открытый
        map.growth ДРУГОГО target, и единственный подходящий — открытый
        map.growth ЭТОГО target. Результат обязан нести только его.

        Ловит мутацию: фильтр забывает `ack_ts IS NULL` (уже
        подтверждённый алерт остаётся в списке) или забывает сверить
        `target` (алерт соседнего target просачивается) — `len(result)`
        разошёлся бы с 1.
        """
        from orchestrator import alerts

        self.make_target("T001", "alpha")
        self.make_target("T002", "beta")
        _fixtures.seed_ackd_map_growth_alert(self.conn, "alpha",
                                  "2026-01-01 00:00:01Z", "уже решено")
        alerts.raise_alert(self.conn, "alpha", "warning", "review-diff",
                          "alpha: diff не собран")
        alerts.raise_alert(self.conn, "beta", "trigger", "map.growth",
                          "beta: чужой target")
        alerts.raise_alert(self.conn, "alpha", "trigger", "map.growth",
                          "alpha: единственный подходящий")

        result = report.map_growth_open_alerts(self.conn, "alpha")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["message"], "alpha: единственный подходящий")


class NoMeasurementsTest(_ReportBlockTest):
    """AC-10: target без единой записи «карта: размер» — данные пусты
    БЕЗ ошибки; вместо таблицы/оценки в отчёте — фиксированная строка."""

    def test_ac10_no_records_gives_empty_data_without_raising(self):
        """Target без единой записи «карта: размер»: таблица — пустой
        список, медиана и оценка — `None`, ни одна из функций не
        бросает исключение (`json.JSONDecodeError`/`IndexError` на
        пустом ряде — типичный симптом отсутствия этой ветки).

        Ловит мутацию: реализация обращается к последней записи ряда
        без проверки на пустоту (`entries[-1]`) — тест упал бы
        `IndexError` вместо получения пустых значений.
        """
        self.make_target("T001", "ghost")

        rows = report.map_size_table_rows(self.conn, "ghost")
        median = report.map_growth_calibration_median(self.conn, "ghost")
        estimate = report.map_growth_cost_estimate(self.conn, "ghost")

        self.assertEqual(rows, [])
        self.assertIsNone(median)
        self.assertIsNone(estimate)

    def test_ac10_cmd_report_shows_the_fixed_message_for_a_target_without_data(self):
        """Сквозной путь: задача с target `ghost` есть (target «известен»
        пульту через `store.all_tasks`, без отдельного `targets.yaml` —
        тот же источник, что уже использует остальной `report.py`
        (борд/закрытые задачи), не новая зависимость этой задачи),
        записей «карта: размер» нет вовсе — сгенерированный `artel
        report` несёт РОВНО заданную SPEC строку (без изменений текста,
        без traceback вместо неё).

        Ловит мутацию: `cmd_report` падает на target без данных
        (например, `KeyError` при обращении к последней записи ряда
        внутри рендера) — этот тест ловит именно ЭТУ ветку, отдельно
        от прямых тестов функций выше (там нет прохода через `cmd_
        report`/рендер целиком).
        """
        self.make_target("T001", "ghost")

        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            report.cmd_report()

        html = (config.ROOT / ".artel" / "report.html").read_text(
            encoding="utf-8")
        self.assertIn(NO_MEASUREMENTS_TEXT, html)


class CmdReportShowsEstimateTest(_ReportBlockTest):
    """AC-9: тот же блок показывает оценку AC-1..AC-4 для этого target
    — сквозная проверка, что оценка действительно дошла до вывода
    `artel report`, не только до прямого вызова функции."""

    def test_ac9_cost_estimate_of_the_target_appears_in_the_report(self):
        """Единственная задача/target с одной записью ряда (без
        `bytes_projection`, без логов `developer` — оценка идёт по
        фолбэку AC-3, значение известно из пропатченной константы) —
        сформированный `$X.XX` этой оценки обязан быть виден в HTML
        отчёта.

        Ловит мутацию: блок `report` для target с данными не подключает
        `map_growth_cost_estimate` вовсе (показывает только таблицу и
        медиану) — искомая денежная строка не появилась бы в HTML.
        """
        self.make_target("T001", "alpha")
        _fixtures.seed_map_size(self.conn, "T001", "2026-01-01 00:00:01Z",
                     bytes_total=3000)

        with mock.patch.object(config, "MAP_GROWTH_CALLS_ESTIMATE", 6,
                              create=True), \
                mock.patch.object(config, "MAP_GROWTH_CALIBRATION_MERGES", 4,
                                  create=True):
            estimate = report.map_growth_cost_estimate(self.conn, "alpha")
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                report.cmd_report()

        html = (config.ROOT / ".artel" / "report.html").read_text(
            encoding="utf-8")
        self.assertIn(f"{estimate['cost_usd']:.2f}", html)


class ExistingReportTestsStayGreenTest(unittest.TestCase):
    """AC-11: существующие `tests/test_report.py` остаются зелёными.

    Зелёный с рождения: тест сохранения существующего поведения — код
    `tests/test_report.py` уже сегодня проходит без правки, до и после
    реализации требования этой задачи (мета-тест, не проверка НОВОГО
    кода)."""

    def test_ac11_existing_test_report_module_passes(self):
        """Загружает и прогоняет `tests/test_report.py` целиком —
        регресс любого из его СУЩЕСТВУЮЩИХ ассертов ловится здесь же,
        не только отдельным прогоном CI.

        Ловит мутацию: будущая правка `report.py` меняет поведение уже
        существующей функции (например, `_ratio`/`_gate_ratio`) —
        `result.wasSuccessful()` стал бы `False`.
        """
        suite = unittest.TestLoader().loadTestsFromName("tests.test_report")
        result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)

        self.assertTrue(result.wasSuccessful())


class CrossTargetIndependenceTest(_ReportBlockTest):
    """AC-12 (инвариант 22): таблица, медиана и алерты одного target не
    читают и не путают данные другого."""

    def test_ac12_table_and_alerts_of_two_targets_do_not_leak(self):
        """Два target с непересекающимися рядами записей и алертами —
        таблица/алерты `alpha` не несут ни одного элемента `beta` и
        наоборот.

        Ловит мутацию: фильтр по target в выборке записей/алертов
        отсутствует (берутся ВСЕ записи/алерты программы) — `len(rows_
        alpha)` вышел бы 2 (сумма обоих рядов) вместо 1.
        """
        from orchestrator import alerts

        self.make_target("TA", "alpha")
        self.make_target("TB", "beta")
        _fixtures.seed_map_size(self.conn, "TA", "2026-01-01 00:00:01Z",
                     bytes_total=1111)
        _fixtures.seed_map_size(self.conn, "TB", "2026-01-01 00:00:01Z",
                     bytes_total=2222)
        alerts.raise_alert(self.conn, "alpha", "trigger", "map.growth",
                          "alpha: сигнал")
        alerts.raise_alert(self.conn, "beta", "trigger", "map.growth",
                          "beta: сигнал")

        rows_alpha = report.map_size_table_rows(self.conn, "alpha")
        rows_beta = report.map_size_table_rows(self.conn, "beta")
        alerts_alpha = report.map_growth_open_alerts(self.conn, "alpha")
        alerts_beta = report.map_growth_open_alerts(self.conn, "beta")

        self.assertEqual([r["bytes_total"] for r in rows_alpha], [1111])
        self.assertEqual([r["bytes_total"] for r in rows_beta], [2222])
        self.assertEqual(len(alerts_alpha), 1)
        self.assertEqual(len(alerts_beta), 1)
        self.assertNotEqual(alerts_alpha[0]["message"],
                           alerts_beta[0]["message"])


if __name__ == "__main__":
    unittest.main()
