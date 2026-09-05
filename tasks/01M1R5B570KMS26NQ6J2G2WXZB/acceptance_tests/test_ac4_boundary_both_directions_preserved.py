"""AC-4 (tasks/01M1R5B570KMS26NQ6J2G2WXZB/SPEC.md): после правки тесты из
AC-1/AC-2 по-прежнему проверяют ОБЕ стороны порога — heartbeat моложе
`LEASE_STALE_AFTER_SEC` считается занятой задачей, heartbeat старше не
считается.

Отдельно от AC-1/AC-5 (которые проверяют устойчивость к искусственному
сдвигу времени): здесь — без какой-либо подмены времени, только факт,
что оба сценария (`test_heartbeat_just_under_the_threshold_still_counts`
и `test_stale_heartbeat_is_excluded`) существуют как разные тестовые
методы и по-прежнему приводят к противоположным наблюдаемым результатам.
Переписывая тест под приём AC-1 (заморозка времени или увеличенный
запас), разработчик мог случайно свернуть оба направления в одно (или
потерять одно из них) — этого AC-1/AC-2/AC-5 сами по себе не ловят,
потому что каждый проверяет свой метод по отдельности и не сверяет их
результаты друг с другом.

Зелёный с рождения: сегодня оба метода существуют и корректно проверяют
противоположные исходы (это и есть исходный, ещё не переписанный код) —
тест ловит не появление нового поведения, а его исчезновение при
рефакторинге под приём AC-1.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

import tests.test_parallel_limit as parallel_limit_tests  # noqa: E402

BUSY_SIDE_METHOD = "test_heartbeat_just_under_the_threshold_still_counts"
EXCLUDED_SIDE_METHOD = "test_stale_heartbeat_is_excluded"


def _run(method_name):
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(
        method_name, parallel_limit_tests.ParallelLimitTest)
    result = unittest.TestResult()
    suite.run(result)
    return result


class BoundaryBothDirectionsStillAssertedTest(unittest.TestCase):

    def test_ac4_both_boundary_directions_still_exist_and_pass(self):
        """`ParallelLimitTest` по-прежнему несёт ОБА тестовых метода границы
        свежести heartbeat, и оба проходят под обычным (без подмены
        времени) исполнением: «моложе порога» — задача занята, «старше
        порога» — задача не занята.

        Ловит мутацию: рефакторинг теста под приём AC-1 (заморозка
        времени/увеличенный запас) случайно удаляет или переименовывает
        один из двух методов (`loadTestsFromName` тогда бросит
        `AttributeError`, тест здесь упадёт), либо копирует тело одного
        метода поверх другого, из-за чего оба начинают проверять один и
        тот же исход.
        """
        for method_name in (BUSY_SIDE_METHOD, EXCLUDED_SIDE_METHOD):
            self.assertTrue(
                hasattr(parallel_limit_tests.ParallelLimitTest, method_name),
                f"метод {method_name} исчез из ParallelLimitTest — AC-4 "
                f"требует сохранить проверку обеих сторон порога")

        busy_result = _run(BUSY_SIDE_METHOD)
        excluded_result = _run(EXCLUDED_SIDE_METHOD)

        self.assertTrue(
            busy_result.wasSuccessful(),
            f"{BUSY_SIDE_METHOD} упал без подмены времени: "
            f"errors={busy_result.errors}, failures={busy_result.failures}")
        self.assertTrue(
            excluded_result.wasSuccessful(),
            f"{EXCLUDED_SIDE_METHOD} упал без подмены времени: "
            f"errors={excluded_result.errors}, "
            f"failures={excluded_result.failures}")


if __name__ == "__main__":
    unittest.main()
