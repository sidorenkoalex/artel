"""AC-5 (tasks/01M1R5B570KMS26NQ6J2G2WXZB/SPEC.md): тесты из AC-1/AC-2
проходят даже при искусственной задержке между посевом lease и вызовом
проверяемой функции (SPEC приводит пример: `time.sleep` на 1–2 секунды
между `seed_lease` и `busy_other_tasks`/`refusal`) — подтверждает
независимость от скорости машины.

Отдельно от AC-1/AC-2 (которые мгновенно СИМУЛИРУЮТ сдвиг «сейчас» почти
на половину порога патчем `liveness.datetime`, без реального ожидания,
и тем самым строго проверяют именно ТРЕБУЕМУЮ величину запаса): здесь —
буквальное воспроизведение примера из текста AC-5 настоящим `time.sleep`
между посевом и проверкой, той же техникой, что описана в SPEC. Две
разные техники измерения (мгновенная симуляция сдвига часов у AC-1/AC-2
и настоящее ожидание здесь) ловят разные классы дефектов: например, если
бы приём был реализован через `time.monotonic()`/поток-специфичный
таймер вместо `datetime.now()`, симуляция AC-1 могла бы не отличить
исправленный код от старого, а настоящая задержка — отличит.

Инъекция задержки — на входе в `parallel_limit.busy_other_tasks`/
`parallel_limit.refusal` (а не изнутри теста через `seed_lease`):
не зависит от того, как именно разработчик назвал внутренние хелперы
теста, реагирует только на сам факт «между посевом и проверкой прошло
реальное время» — работает независимо от выбранного приёма (заморозка
или увеличенный запас).

Красен до реализации: `test_heartbeat_just_under_the_threshold_still_
counts` сегодня использует запас в 1 секунду и не подменяет источник
времени — при настоящей задержке в 1.2 секунды перед вызовом
`busy_other_tasks` heartbeat реально «протухает» к моменту проверки,
тест падает (проверено эмпирически перед записью этого файла).
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import parallel_limit  # noqa: E402
import tests.test_parallel_limit as parallel_limit_tests  # noqa: E402

DELAY_SEC = 1.2

TARGET_METHOD_NAMES = (
    "test_heartbeat_just_under_the_threshold_still_counts",
    "test_stale_heartbeat_is_excluded",
    "test_foreign_host_with_stale_heartbeat_is_still_excluded",
    "test_refusal_is_none_when_ceiling_only_reached_by_stale_or_dead",
)


def _delayed(real_fn, delay_seconds):
    def wrapper(*args, **kwargs):
        time.sleep(delay_seconds)
        return real_fn(*args, **kwargs)
    return wrapper


def _run_with_real_delay(method_names, delay_seconds):
    real_busy = parallel_limit.busy_other_tasks
    real_refusal = parallel_limit.refusal
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in method_names:
        suite.addTests(loader.loadTestsFromName(
            name, parallel_limit_tests.ParallelLimitTest))
    result = unittest.TestResult()
    with mock.patch.object(parallel_limit, "busy_other_tasks",
                           _delayed(real_busy, delay_seconds)), \
         mock.patch.object(parallel_limit, "refusal",
                           _delayed(real_refusal, delay_seconds)):
        suite.run(result)
    return result


class ArtificialRealDelaySurvivalTest(unittest.TestCase):

    def test_ac5_boundary_tests_survive_real_artificial_delay_before_check(self):
        """Все четыре теста границы свежести heartbeat из AC-1/AC-2
        проходят, даже если между посевом lease и вызовом
        `busy_other_tasks`/`refusal` реально проходит 1.2 секунды —
        буквальное воспроизведение примера из формулировки AC-5.

        Ловит мутацию: любой из четырёх тестов остаётся завязан на
        реальную скорость выполнения (например, запас увеличен
        недостаточно, либо заморозка времени применена частично —
        скажем, только к `busy_other_tasks`, но не к `refusal`) —
        настоящая задержка перед проверяемым вызовом это проявит.
        """
        result = _run_with_real_delay(TARGET_METHOD_NAMES, DELAY_SEC)

        self.assertTrue(
            result.wasSuccessful(),
            f"хотя бы один из тестов границы не пережил реальную "
            f"задержку в {DELAY_SEC} сек между посевом и проверкой: "
            f"errors={result.errors}, failures={result.failures}")


if __name__ == "__main__":
    unittest.main()
