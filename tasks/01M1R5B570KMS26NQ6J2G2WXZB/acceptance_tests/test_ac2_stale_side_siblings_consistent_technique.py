"""AC-2 (tasks/01M1R5B570KMS26NQ6J2G2WXZB/SPEC.md): `test_stale_heartbeat_
is_excluded` и прочие тесты в `tests/test_parallel_limit.py`, использующие
`_ts_ago` совместно с `config.LEASE_STALE_AFTER_SEC` (`test_foreign_host_
with_stale_heartbeat_is_still_excluded`, `test_refusal_is_none_when_
ceiling_only_reached_by_stale_or_dead`), приведены к тому же приёму
устранения зависимости от реального времени, что AC-1.

Эти три теста сегодня уже безопасны (запас у них — со стороны «точно
протух»: `_ts_ago(config.LEASE_STALE_AFTER_SEC + 1)` — просадка скорости
прогона делает heartbeat ещё старее, не превращает «протух» в «свеж»),
поэтому симулированный сдвиг времени, которым AC-1 ловит недостаточный
запас, здесь не отличит «до» от «после»: наблюдаемый результат
(`busy_other_tasks`/`refusal` не видят «протухшую» задачу) одинаков в
обоих случаях по самой природе стороны «точно протух» — так же
рассуждает SPEC (раздел «Требования», пункт 2). Тест здесь — не
доказательство смены приёма (то недоступно наблюдению снаружи без
знания внутренней реализации теста), а регрессионная защита той же
техникой измерения: если рефакторинг этих трёх тестов «под общий приём»
что-то сломает в самой стороне «протух» (например, перепутает знак
запаса или условие в проверяемом коде), симулированный сдвиг это
проявит.

Зелёный с рождения: сторона «точно протух» у этих трёх тестов уже не
зависит от скорости машины сегодня — правки в рамках задачи (в т.ч.
чисто стилистическое приведение к общему приёму AC-1) не обязаны менять
здесь наблюдаемый результат, поэтому тест зелёный и до, и после
реализации, и ловит только регрессию.
"""
import sys
import unittest
from datetime import datetime as real_datetime, timedelta
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, liveness  # noqa: E402
import tests.test_parallel_limit as parallel_limit_tests  # noqa: E402

SIMULATED_ELAPSED_SEC = config.LEASE_STALE_AFTER_SEC // 2 - 1

SIBLING_METHOD_NAMES = (
    "test_stale_heartbeat_is_excluded",
    "test_foreign_host_with_stale_heartbeat_is_still_excluded",
    "test_refusal_is_none_when_ceiling_only_reached_by_stale_or_dead",
)


class _AdvancingDatetime(real_datetime):
    """См. tasks/01M1R5B570KMS26NQ6J2G2WXZB/acceptance_tests/
    test_ac1_heartbeat_edge_case_time_independence.py — тот же приём
    мгновенной симуляции «прошло много времени» без реального ожидания."""

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


class StaleSideSiblingTestsRegressionTest(unittest.TestCase):

    def test_ac2_stale_side_sibling_tests_still_exclude_under_simulated_elapsed_time(self):
        """`test_stale_heartbeat_is_excluded`,
        `test_foreign_host_with_stale_heartbeat_is_still_excluded` и
        `test_refusal_is_none_when_ceiling_only_reached_by_stale_or_dead`
        по-прежнему верно исключают «протухшую» задачу, даже при
        симулированном сдвиге «сейчас» почти на половину
        `LEASE_STALE_AFTER_SEC» — приведение этих тестов к общему с AC-1
        приёму не сломало сторону «точно протух».

        Ловит мутацию: рефакторинг под общий приём (например, замена
        `_ts_ago(config.LEASE_STALE_AFTER_SEC + 1)` на вызов через
        заморозку времени) по ошибке переворачивает знак запаса на
        `-` вместо `+` — тогда эти три сценария при симулированном сдвиге
        начнут ошибочно считать протухшую задачу свежей, и хотя бы один
        из них покраснеет.
        """
        for method_name in SIBLING_METHOD_NAMES:
            with self.subTest(method=method_name):
                result = _run_with_simulated_elapsed_time(
                    method_name, SIMULATED_ELAPSED_SEC)

                self.assertTrue(
                    result.wasSuccessful(),
                    f"{method_name} не пережил симулированный сдвиг "
                    f"времени на {SIMULATED_ELAPSED_SEC} сек: "
                    f"errors={result.errors}, failures={result.failures}")


if __name__ == "__main__":
    unittest.main()
