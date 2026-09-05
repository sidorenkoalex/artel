"""AC-1 (tasks/01M1R5B570KMS26NQ6J2G2WXZB/SPEC.md):
`tests/test_parallel_limit.py::ParallelLimitTest::
test_heartbeat_just_under_the_threshold_still_counts` переписан так,
чтобы не зависеть от запаса в 1 секунду до реального «сейчас»: время
фиксировано подменой источника времени, либо запас увеличен до
половины `config.LEASE_STALE_AFTER_SEC`.

Проверка через реальный `time.sleep` невозможна: приём «запас — половина
двухчасового порога» по определению требует прогона теста дольше часа,
чтобы отличить исправленный вариант от старого (запас в 1 секунду) —
непрактично для юнит-теста. Вместо этого «сейчас», которое читает
`orchestrator/liveness.py::_age_seconds`, мгновенно сдвигается вперёд
патчем `liveness.datetime` (тот же приём, что уже применяет
`tests/test_report.py::_frozen_today` для `report.datetime`) — это
детерминированно и без ожидания воспроизводит эффект «между посевом
lease и проверкой утекло почти `LEASE_STALE_AFTER_SEC / 2` секунд
реального времени», не трогая при этом `datetime`, которым сам
`tests/sandbox.py::_ts_ago` вычисляет метку heartbeat в момент посева
(разные модули — разные импортированные имена `datetime`, патч одного
не подменяет другой). Если разработчик выбрал заморозку «сейчас»
(например, тем же приёмом `mock.patch.object(liveness, "datetime", ...)`
изнутри теста) — сдвиг снаружи не проникает внутрь их `with`-блока
(внутренний `mock.patch` временно перекрывает внешний на время своего
действия), и тест проходит независимо от величины сдвига. Если
разработчик выбрал увеличение запаса — тест проходит только если запас
действительно не меньше половины порога. Проверено вручную перед
записью на трёх вариантах реализации (запас 10 секунд — недостаточно,
падает; запас `LEASE_STALE_AFTER_SEC // 2` — проходит; заморозка «сейчас»
через `mock.patch.object(liveness, "datetime", ...)` — проходит).

Красен до реализации: сегодняшний тест сеет heartbeat с запасом ровно в
1 секунду (`_ts_ago(config.LEASE_STALE_AFTER_SEC - 1)`,
tests/test_parallel_limit.py:68) и не подменяет источник времени —
симулированный сдвиг «сейчас» почти на половину порога делает heartbeat
старше порога, `busy_other_tasks` перестаёт возвращать `T901`, тест
падает.
"""
import sys
import unittest
from datetime import datetime as real_datetime, timedelta
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, liveness, parallel_limit  # noqa: E402
import tests.test_parallel_limit as parallel_limit_tests  # noqa: E402

# Симулированный сдвиг «сейчас» — чуть меньше половины порога (SPEC,
# AC-1: «запас увеличен до половины LEASE_STALE_AFTER_SEC»). Приём
# именно проходит впритык к минимально допустимому запасу: сдвиг
# БОЛЬШЕ этого запас в 10 секунд из ручной проверки не выдержал бы, а
# запас ровно в половину порога — выдерживает (см. докстринг модуля).
SIMULATED_ELAPSED_SEC = config.LEASE_STALE_AFTER_SEC // 2 - 1


class _AdvancingDatetime(real_datetime):
    """Заменитель `datetime` внутри `orchestrator.liveness`: `.now()`
    возвращает реальное «сейчас» со сдвигом на `_offset_seconds» вперёд —
    мгновенная симуляция «прошло много времени», без настоящего
    ожидания."""

    _offset_seconds = 0

    @classmethod
    def now(cls, tz=None):
        return real_datetime.now(tz) + timedelta(seconds=cls._offset_seconds)


def _run_with_simulated_elapsed_time(method_name, offset_seconds):
    _AdvancingDatetime._offset_seconds = offset_seconds
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(
        method_name, parallel_limit_tests.ParallelLimitTest)
    result = unittest.TestResult()
    with mock.patch.object(liveness, "datetime", _AdvancingDatetime):
        suite.run(result)
    return result


class HeartbeatJustUnderThresholdTimeIndependenceTest(unittest.TestCase):

    def test_ac1_heartbeat_just_under_threshold_survives_near_half_threshold_elapsed_time(self):
        """`test_heartbeat_just_under_the_threshold_still_counts` по-прежнему
        считает задачу занятой, даже если между посевом lease и вызовом
        `busy_other_tasks` симулированно «прошло» почти
        `LEASE_STALE_AFTER_SEC / 2` секунд — доказательство, что тест
        больше не держится на запасе в 1 секунду до реального «сейчас».

        Ловит мутацию: разработчик правит запас на любое небольшое число
        (например, с 1 до 5 или 10 секунд) вместо доведения его до
        половины `LEASE_STALE_AFTER_SEC`, либо оставляет заморозку
        времени неполной (подменяет не то место чтения) — при
        симулированном сдвиге почти на половину порога тест снова
        покраснеет.
        """
        result = _run_with_simulated_elapsed_time(
            "test_heartbeat_just_under_the_threshold_still_counts",
            SIMULATED_ELAPSED_SEC)

        self.assertTrue(
            result.wasSuccessful(),
            f"тест AC-1 не пережил симулированный сдвиг времени на "
            f"{SIMULATED_ELAPSED_SEC} сек: errors={result.errors}, "
            f"failures={result.failures}")


if __name__ == "__main__":
    unittest.main()
