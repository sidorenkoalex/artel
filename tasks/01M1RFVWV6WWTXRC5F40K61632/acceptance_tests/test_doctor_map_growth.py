"""Приёмочные тесты 01M1RFVWV6WWTXRC5F40K61632 — AC-8..AC-16:
`orchestrator/doctor.py::check_map_growth(conn)`.

Источник — только tasks/01M1RFVWV6WWTXRC5F40K61632/SPEC.md, раздел
«Критерии приёмки». Ряд журнала строится напрямую `store.journal(...,
"карта: размер", detail)` — не через `fsm_postmerge` (это отдельная
планка, `test_fsm_map_size_journal.py`): здесь под проверкой только
`check_map_growth`, ряд ему нужен уже готовый.

Схема `detail`, число полей и их имена — та же локальная конкретизация,
что и в `test_map_stats.py`/`_fixtures.py` (`bytes_total`,
`bytes_by_dir`, `top_sections` = `[{"name":..., "bytes":...}]`, плюс
`sha` из `test_fsm_map_size_journal.py`) — `check_map_growth` читает то
же поле `detail`, что пишет `_regenerate_and_commit_map`.

Имя `Check` на target SPEC буквально не называет (AC-8 говорит только
«для каждого target ... строит ряд») — `Check` несёт лишь `name status
detail`, без отдельного поля `target`, так что имя обязано нести
атрибуцию само. Здесь зафиксирована конкретизация `f"map-growth:
{target}"` — единственный способ различить checks двух target в
одном списке `list[Check]`, который возвращает функция.

Статус сработавшего триггера зафиксирован как `"warn"` (не `"fail"`):
`map.growth` — сигнал для решения Оператора (`docs/triggers.md`), не
поломка, блокирующая `doctor` (`LABELS`/`cmd_doctor` завершается
ненулевым кодом только на `"fail"`) — по аналогии с `check_base_branch`
(расхождение — `warn`, не `fail`).

Ловушка «одна и та же запись двигает оба сигнала сразу» снята
конструкцией фикстур: сценарии ползучего роста (AC-11) и скачка
(AC-12) построены так, чтобы шаг между соседними записями оставался
ниже/выше только ОДНОГО из двух порогов — иначе тест AC-12 не отличил
бы «скачок сработал» от «заодно сработал и ползучий рост».

Красен до реализации: `orchestrator/doctor.py` ещё не содержит
`check_map_growth` — каждый тест падает `AttributeError` на первом же
обращении к функции, пока она не написана (требование 3 SPEC).
"""
import inspect
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, config, doctor, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

SIZE_ACTION = "карта: размер"
ZERO_SHA = "0" * 40


def _detail(bytes_total: int, bytes_by_dir: dict | None = None,
           top_sections: list | None = None) -> str:
    payload = {
        "bytes_total": bytes_total,
        "sections_total": 3,
        "bytes_by_dir": bytes_by_dir or {
            "orchestrator": bytes_total, "scripts": 0, "tests": 0},
        "top_sections": top_sections or [
            {"name": "orchestrator/x.py", "bytes": bytes_total}],
        "sha": ZERO_SHA,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class _MapGrowthTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self._next_task_seq = 0

    def make_task(self, target: str = "artel") -> str:
        self._next_task_seq += 1
        task_id = f"01M1MAPGROWTH{self._next_task_seq:012d}"
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}", target, 25.0)
        return task_id

    def add_step(self, task_id: str, bytes_total: int, **kw) -> None:
        store.journal(self.conn, task_id, "orchestrator", SIZE_ACTION,
                      _detail(bytes_total, **kw))

    def checks_by_target(self) -> dict:
        return {c.name: c for c in doctor.check_map_growth(self.conn)}

    def trigger_alerts(self) -> list:
        """Текущие открытые триггеры `map.growth` — ПРОГОНЯЕТ
        `check_map_growth` перед чтением: алерты заводит сама
        проверка, не факт записи в журнал."""
        doctor.check_map_growth(self.conn)
        return [a for a in alerts.open_alerts(self.conn, "trigger")
               if a["source"] == "map.growth"]

    def K(self) -> int:
        return config.MAP_GROWTH_CALIBRATION_MERGES


class AllChecksWiringTest(unittest.TestCase):
    """AC-8: `check_map_growth` подключена в `all_checks(conn)`."""

    def test_ac8_all_checks_calls_check_map_growth(self):
        """`all_checks` обязана звать `check_map_growth` — проверка
        исходника `all_checks`, не полный прогон (тяжёлая обвязка
        `all_checks` — CLI/keychain/gh — не имеет отношения к этой
        проверке).

        Ловит мутацию: `check_map_growth` написана, но забыли добавить
        вызов в `all_checks` — здоровый `doctor` никогда не покажет
        сигнал роста карты.
        """
        source = inspect.getsource(doctor.all_checks)
        self.assertIn("check_map_growth", source)


class OnlyTargetsWithRecordsAppearTest(_MapGrowthTest):
    """AC-8: только target, у которого есть хотя бы одна запись «карта:
    размер», получает Check."""

    def test_ac8_target_without_any_size_record_is_absent(self):
        """Target `artel` — одна запись, `sled` — ни одной (task не
        заведён вовсе). `check_map_growth` возвращает Check только для
        `artel`.

        Ловит мутацию: перебор идёт по ВСЕМ объявленным target
        (`targets.load()`) вместо тех, у кого реально есть ряд —
        появился бы Check и для target без единой записи.
        """
        task = self.make_task("artel")
        self.add_step(task, 100_000)

        checks = self.checks_by_target()

        self.assertIn("map-growth:artel", checks)
        self.assertNotIn("map-growth:sled", checks)


class CalibrationWindowTest(_MapGrowthTest):
    """AC-9: пока записей после точки отсчёта меньше
    `config.MAP_GROWTH_CALIBRATION_MERGES` — тихая калибровка."""

    def test_ac9_single_record_reports_one_of_k_measurements(self):
        """Одна запись — статус `ok`, текст `калибровка: 1/K измерений`
        (K — `config.MAP_GROWTH_CALIBRATION_MERGES`, не литерал).

        Ловит мутацию: счётчик считает записи НЕВЕРНО (например, с
        единицы вместо нуля до первой записи, или использует общее
        число задач вместо числа записей ряда) — текст разойдётся с
        «1/K».
        """
        task = self.make_task()
        self.add_step(task, 100_000)

        check = self.checks_by_target()["map-growth:artel"]

        self.assertEqual(check.status, "ok")
        self.assertEqual(check.detail, f"калибровка: 1/{self.K()} измерений")
        self.assertEqual(self.trigger_alerts(), [])

    def test_ac9_one_short_of_the_window_still_silent(self):
        """K-1 записей — всё ещё калибровка, `K-1/K измерений`, без
        алертов, даже если значения внутри уже сильно различаются
        (калибровка не смотрит на разброс, только считает записи).

        Ловит мутацию: реализация начинает сравнивать с медианой ДО
        того, как накопила полное окно (например, `>=` вместо `>` при
        сравнении с K-1) — алерт мог бы появиться раньше срока.
        """
        task = self.make_task()
        k = self.K()
        for i in range(k - 1):
            self.add_step(task, 100_000 * (i + 1))

        check = self.checks_by_target()["map-growth:artel"]

        self.assertEqual(check.status, "ok")
        self.assertEqual(check.detail, f"калибровка: {k - 1}/{k} измерений")
        self.assertEqual(self.trigger_alerts(), [])


class FixedBaselineNotSlidingTest(_MapGrowthTest):
    """AC-10: медиана окна калибровки — фиксированная база, не
    пересчитывается по новым записям (окно не «скользит»)."""

    def test_ac10_growth_measured_against_the_original_window_median(self):
        """K записей `BASE` (медиана окна = `BASE`), затем K записей,
        растущих ГЛАДКО (шаг каждый раз меньше `MAP_JUMP_RATIO`, чтобы
        не подмешать сигнал скачка) до `FINAL`, кратно превышающего
        `BASE*(1+MAP_GROWTH_RATIO)`.

        Если бы медиана окна пересчитывалась по последним K записям
        («скользящее» окно) — все K последних записей были бы близки к
        `FINAL`, их медиана ~ `FINAL`, и рост последней записи против
        НЕЁ был бы ~0% — алерта не было бы вовсе. Фиксированная база
        (медиана ПЕРВЫХ K записей = `BASE`) даёт рост, кратно
        превышающий порог, — алерт обязан появиться.

        Ловит мутацию: окно калибровки пересчитывается заново на
        каждом прогоне вместо однократной фиксации (нарушение AC-10 -
        «окно не скользит») — эта проверка красна ИМЕННО на такой
        мутации, а не на отсутствии алертов вообще.
        """
        k = self.K()
        growth_ratio = config.MAP_GROWTH_RATIO
        jump_ratio = config.MAP_JUMP_RATIO
        base = 1_000_000
        task = self.make_task()
        for _ in range(k):
            self.add_step(task, base)

        # Шаг каждой из K записей роста: гарантированно ниже порога
        # скачка (без "заодно" срабатывания AC-12), но совокупный рост
        # за K шагов кратно превышает порог ползучего роста.
        step = jump_ratio * 0.8
        required_total_growth = (1 + growth_ratio) * 1.2
        self.assertGreater(
            (1 + step) ** k, required_total_growth,
            "фикстура недостаточно раздута для сконфигурированных "
            "MAP_GROWTH_RATIO/MAP_JUMP_RATIO — поправь step/k")
        value = base
        for _ in range(k):
            value = int(value * (1 + step))
            self.add_step(task, value)

        checks = self.checks_by_target()

        self.assertIn("map-growth:artel", checks)
        self.assertEqual(len(self.trigger_alerts()), 1)

    def test_ac10_ack_moves_the_reference_point_and_recalibrates(self):
        """После срабатывания алерта и его `ack` точка отсчёта
        переносится на момент подтверждения — следующие записи считаются
        заново с нуля, окно калибровки ждёт свежих K измерений.

        `store.now()` — секундная точность; без подмены записи одного
        теста (до и после `ack`) рискуют лечь в одну и ту же секунду и
        сделать сравнение «после точки отсчёта» неразличимым от гонки
        часов, а не от логики самого кода — подменяем строго
        возрастающей последовательностью меток, тем же по духу приёмом,
        что `tests/sandbox.py::_ts_ago` для heartbeat lease.

        Ловит мутацию: `ack` не двигает точку отсчёта — счётчик
        калибровки продолжил бы расти от старой точки, и K-1 новых
        записей ПОСЛЕ ack (при уже накопленных K+1 старых) сразу ушли
        бы в боевой режим сравнения с медианой, а не показали бы
        «K-1/K измерений» настройки заново.
        """
        k = self.K()
        base = 1_000_000
        task = self.make_task()
        ticks = iter(f"2026-01-01 00:00:{i:02d}Z" for i in range(2 * k + 2))
        with mock.patch.object(store, "now", side_effect=lambda: next(ticks)):
            for _ in range(k):
                self.add_step(task, base)
            # Запись, гарантированно поднимающая триггер (см. AC-11 ниже).
            self.add_step(task, int(base * (1 + config.MAP_GROWTH_RATIO) * 1.5))
            self.assertEqual(len(self.trigger_alerts()), 1)
            alert_id = self.trigger_alerts()[0]["id"]
            alerts.ack(self.conn, alert_id, "operator",
                      "отложено: обсудим на ретро")

            for _ in range(k - 1):
                self.add_step(task, base)

        check = self.checks_by_target()["map-growth:artel"]
        self.assertEqual(check.status, "ok")
        self.assertEqual(check.detail, f"калибровка: {k - 1}/{k} измерений")


class CreepSignalTest(_MapGrowthTest):
    """AC-11: ползучий рост — bytes_total последней записи выше медианы
    окна на долю `config.MAP_GROWTH_RATIO`."""

    def test_ac11_growth_beyond_the_ratio_after_calibration_raises_a_trigger(self):
        """K записей `BASE`, затем ОДНА запись `FINAL` заметно выше
        `BASE*(1+MAP_GROWTH_RATIO)` — алерт `kind=trigger`,
        `source=map.growth`.

        Ловит мутацию: сравнение использует `>=`/неверный знак или
        сравнивает не с медианой, а с последней записью САМОЙ ПО СЕБЕ
        (тождество) — на этой фикстуре алерта либо не будет, либо он
        появится тождественно всегда.
        """
        k = self.K()
        base = 1_000_000
        task = self.make_task()
        for _ in range(k):
            self.add_step(task, base)

        final = int(base * (1 + config.MAP_GROWTH_RATIO) * 1.5)
        self.add_step(task, final)

        self.assertGreaterEqual(len(self.trigger_alerts()), 1)
        check = self.checks_by_target()["map-growth:artel"]
        self.assertEqual(check.status, "warn")

    def test_ac11_growth_below_the_ratio_stays_silent(self):
        """Отрицательный контроль: рост ниже порога (`MAP_GROWTH_RATIO
        * 0.5`) после калибровки — алерта нет.

        Ловит мутацию: порог сравнения занижен (например, взята
        константа `MAP_JUMP_RATIO` вместо `MAP_GROWTH_RATIO`, которая
        меньше по SPEC-ориентиру) — эта заведомо смирная фикстура
        неожиданно подняла бы алерт.

        Прирост последнего шага держится ниже ОБОИХ порогов (не только
        `MAP_GROWTH_RATIO`) — иначе на смежном шаге мог бы вместо
        ползучего роста нечаянно сработать сигнал скачка (AC-12),
        замаскировав то, что здесь на самом деле проверяется.
        """
        k = self.K()
        base = 1_000_000
        task = self.make_task()
        for _ in range(k):
            self.add_step(task, base)

        mild_ratio = min(config.MAP_GROWTH_RATIO, config.MAP_JUMP_RATIO) * 0.5
        self.add_step(task, int(base * (1 + mild_ratio)))

        self.assertEqual(self.trigger_alerts(), [])


class JumpSignalTest(_MapGrowthTest):
    """AC-12: скачок — прирост между двумя соседними записями выше
    `config.MAP_JUMP_RATIO` от значения предыдущей, независимо от AC-11."""

    def test_ac12_jump_between_adjacent_records_raises_a_trigger_without_creep(self):
        """K записей `BASE`, затем ОДНА запись с приростом строго между
        `MAP_JUMP_RATIO` и `MAP_GROWTH_RATIO` (гарантированно требует
        `MAP_JUMP_RATIO*1.5 < MAP_GROWTH_RATIO` — проверено ассертом
        фикстуры) — скачок обязан сработать притом, что ОБЩИЙ рост
        против медианы окна ниже порога ползучего роста (creep сам по
        себе НЕ сработал бы).

        Ловит мутацию: скачок сравнивается с медианой окна вместо
        значения ПРЕДЫДУЩЕЙ записи (перепутан с ползучим сигналом) —
        на этой фикстуре (прирост ниже `MAP_GROWTH_RATIO`) алерта бы не
        было вовсе.
        """
        jump_ratio = config.MAP_JUMP_RATIO
        growth_ratio = config.MAP_GROWTH_RATIO
        self.assertLess(
            jump_ratio * 1.5, growth_ratio,
            "фикстура рассчитана на MAP_JUMP_RATIO*1.5 < MAP_GROWTH_RATIO "
            "— поправь коэффициенты сценария под сконфигурированные ratio")
        k = self.K()
        base = 1_000_000
        task = self.make_task()
        for _ in range(k):
            self.add_step(task, base)

        jumped = int(base * (1 + jump_ratio * 1.5))
        self.add_step(task, jumped)

        self.assertGreaterEqual(len(self.trigger_alerts()), 1)

    def test_ac12_small_step_below_both_ratios_stays_silent(self):
        """Отрицательный контроль: прирост ниже ОБОИХ порогов — ни
        скачок, ни ползучий рост не срабатывают.

        Ловит мутацию: один из порогов сравнивается со знаком,
        допускающим случайное срабатывание на маленьком приросте
        (например, `> 0` вместо `> MAP_JUMP_RATIO`).
        """
        k = self.K()
        base = 1_000_000
        task = self.make_task()
        for _ in range(k):
            self.add_step(task, base)

        tiny_ratio = min(config.MAP_GROWTH_RATIO, config.MAP_JUMP_RATIO) * 0.3
        self.add_step(task, int(base * (1 + tiny_ratio)))

        self.assertEqual(self.trigger_alerts(), [])


class AttributionTextTest(_MapGrowthTest):
    """AC-13: текст алерта называет каталог с наибольшим приростом и
    три самые крупные секции текущей карты."""

    def test_ac13_message_names_the_grown_directory_and_top_three_sections(self):
        """Сценарий скачка (AC-12, сравниваемые записи однозначны — два
        конкретных соседних ряда, без синтетической медианы): каталоги
        `orchestrator`/`tests` держатся РОВНО константными во всех
        записях, растёт только `scripts` — при любом разумном способе
        выбрать «прирост между сравниваемыми записями» имя каталога
        однозначно `scripts`. Пять секций последней записи с заведомо
        разными размерами — в тексте обязаны быть три самые крупные (по
        имени и байтам), но не 4-я/5-я по размеру.

        Ловит мутацию: атрибуция называет каталог, который не рос
        (например, всегда `orchestrator` как первый в списке) — имя
        `scripts` не попадёт в текст; либо в тексте названы не 3, а
        другое число секций.
        """
        jump_ratio = config.MAP_JUMP_RATIO
        growth_ratio = config.MAP_GROWTH_RATIO
        self.assertLess(
            jump_ratio * 1.5, growth_ratio,
            "фикстура рассчитана на MAP_JUMP_RATIO*1.5 < MAP_GROWTH_RATIO "
            "— поправь коэффициенты сценария под сконфигурированные ratio")
        k = self.K()
        task = self.make_task()
        constant_dirs = {"orchestrator": 500_000, "tests": 500_000}
        base_scripts = 500_000
        base_total = constant_dirs["orchestrator"] + constant_dirs["tests"] + base_scripts
        for _ in range(k):
            self.add_step(task, base_total,
                          bytes_by_dir={**constant_dirs, "scripts": base_scripts})

        sections = [
            {"name": "scripts/biggest.py", "bytes": 90_000},
            {"name": "scripts/second.py", "bytes": 80_000},
            {"name": "orchestrator/third.py", "bytes": 70_000},
            {"name": "tests/fourth.py", "bytes": 60_000},
            {"name": "orchestrator/fifth.py", "bytes": 50_000},
        ]
        # Весь прирост ИТОГО (не только доли scripts) обязан превысить
        # порог скачка — рост ТОЛЬКО каталога scripts на ту же долю
        # дал бы прирост ИТОГО втрое меньше (scripts — треть от целого),
        # ниже порога.
        grown_scripts = base_scripts + int(base_total * jump_ratio * 1.5)
        total = constant_dirs["orchestrator"] + constant_dirs["tests"] + grown_scripts
        self.add_step(task, total,
                      bytes_by_dir={**constant_dirs, "scripts": grown_scripts},
                      top_sections=sections)

        alert = self.trigger_alerts()[0]
        message = alert["message"]
        self.assertIn("scripts", message)
        for entry in sections[:3]:
            self.assertIn(entry["name"], message)
            self.assertIn(str(entry["bytes"]), message)
        for entry in sections[3:]:
            self.assertNotIn(entry["name"], message)


class DedupAndDeterminismTest(_MapGrowthTest):
    """AC-14: повторный прогон без нового измерения не дублирует
    алерт; текст детерминирован (без времени/меняющихся величин)."""

    def setUp(self):
        super().setUp()
        self.k = self.K()
        self.base = 1_000_000
        self.task = self.make_task()
        for _ in range(self.k):
            self.add_step(self.task, self.base)
        self.jumped = int(self.base * (1 + config.MAP_JUMP_RATIO * 1.5))
        self.add_step(self.task, self.jumped)

    def test_ac14_repeated_run_without_a_new_record_does_not_duplicate(self):
        """Второй прогон `check_map_growth` на неизменном ряду — то же
        число открытых алертов, не удвоенное.

        Ловит мутацию: алерт заводится напрямую `store.insert_alert`
        (в обход дедупа `alerts.raise_alert`) — второй прогон завёл бы
        вторую копию.
        """
        first_count = len(self.trigger_alerts())

        self.checks_by_target()  # второй прогон check_map_growth

        self.assertEqual(len(self.trigger_alerts()), first_count)

    def test_ac14_message_is_deterministic_across_independent_targets(self):
        """Второй target с БУКВАЛЬНО тем же рядом значений (та же
        последовательность `bytes_total`/`bytes_by_dir`/`top_sections`,
        только записанная позже во времени, для другого target) —
        текст алерта совпадает с первым побайтово.

        Дедуп `raise_alert` (уже покрыт соседним тестом) не даёт
        сравнить «текст повторного прогона» на ОДНОМ ряду — повтор той
        же записи под ДРУГИМ target обходит дедуп (разный `target` —
        разный ключ дедупа) и остаётся единственным способом увидеть
        два вычисления одного и того же условия по-настоящему заново.

        Ловит мутацию: текст несёт `store.now()`/id алерта/иную
        меняющуюся между вычислениями величину — сообщение второго
        target разошлось бы с первым, хотя ряд данных идентичен.
        """
        other_task = self.make_task("sled")
        for _ in range(self.k):
            self.add_step(other_task, self.base)
        self.add_step(other_task, self.jumped)

        by_target = {}
        for a in self.trigger_alerts():
            by_target[a["target"]] = a["message"]

        self.assertEqual(by_target["artel"], by_target["sled"])


class ContextFileMaxBytesUntouchedTest(_MapGrowthTest):
    """AC-15: `check_map_growth` не трогает `config.CONTEXT_FILE_MAX_
    BYTES` и не влияет на алерт-инцидент брифа."""

    def test_ac15_source_does_not_reference_context_file_max_bytes(self):
        """Исходник `check_map_growth` не упоминает
        `CONTEXT_FILE_MAX_BYTES` — единственный абсолютный потолок карты
        остаётся заботой `brief._handle_map_size_alert`, не этой
        проверки.

        Ловит мутацию: реализация «заодно» сверяет `bytes_total` с
        потолком брифа (смешение относительного и абсолютного порога,
        прямо запрещённое SPEC, «Не входит») — упоминание константы в
        исходнике тест поймает текстовым поиском.
        """
        source = inspect.getsource(doctor.check_map_growth)
        self.assertNotIn("CONTEXT_FILE_MAX_BYTES", source)

    def test_ac15_growth_alert_does_not_raise_brief_incident_source(self):
        """Прогон с гарантированным срабатыванием роста не заводит ни
        одного алерта источника `fsm.map_regen`/иного incident,
        связанного с потолком брифа — только `kind=trigger,
        source=map.growth`.

        Ловит мутацию: реализация подмешивает к сигналу роста ещё и
        incident-алерт «карта не влезла в бриф» — несвязанный incident
        появился бы в списке открытых алертов.
        """
        k = self.K()
        base = 1_000_000
        task = self.make_task()
        for _ in range(k):
            self.add_step(task, base)
        self.add_step(task, int(base * (1 + config.MAP_GROWTH_RATIO) * 1.5))

        self.checks_by_target()

        incidents = alerts.open_alerts(self.conn, "incident")
        self.assertEqual(incidents, [])


class CrossTargetIndependenceTest(_MapGrowthTest):
    """AC-16: ряды двух target независимы (инвариант 22)."""

    def test_ac16_one_target_triggering_does_not_affect_the_other(self):
        """Target `artel` растёт за порог, target `sled` держит ряд
        плоским — калибровка/алерт `sled` не задеты ростом `artel`, и
        наоборот алерт `artel` не несёт данных `sled`.

        Ловит мутацию: ряд строится общим SQL-запросом без фильтрации
        по target (например, `SELECT * FROM steps WHERE action=...`
        без `AND target=?`) — медиана `artel` подмешала бы записи
        `sled` (или наоборот), поменяв оба исхода непредсказуемо.
        """
        k = self.K()
        base = 1_000_000
        task_a = self.make_task("artel")
        task_b = self.make_task("sled")
        for _ in range(k):
            self.add_step(task_a, base)
            self.add_step(task_b, base)
        self.add_step(task_a, int(base * (1 + config.MAP_GROWTH_RATIO) * 1.5))
        self.add_step(task_b, base)  # sled остаётся плоским

        checks = self.checks_by_target()
        by_target_alerts = {}
        for a in self.trigger_alerts():
            by_target_alerts.setdefault(a["target"], []).append(a)

        self.assertEqual(checks["map-growth:artel"].status, "warn")
        self.assertEqual(checks["map-growth:sled"].status, "ok")
        self.assertIn("artel", by_target_alerts)
        self.assertNotIn("sled", by_target_alerts)


if __name__ == "__main__":
    unittest.main()
