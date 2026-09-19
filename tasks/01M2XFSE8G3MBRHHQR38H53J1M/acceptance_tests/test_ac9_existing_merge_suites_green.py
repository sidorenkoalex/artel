"""AC-9 — существующие наборы тестов мьютекса, очереди и цикла ожидания CI
остаются зелёными вместе с новыми тестами задачи (задача
01M2XFSE8G3MBRHHQR38H53J1M).

Зелёный с рождения: все три файла (`tests/test_merge_lock.py`,
`tests/test_merge_queue.py`, `tests/test_merge_gate_ci_wait.py`) проходят и
до кода задачи — критерий требует, чтобы они прошли и ПОСЛЕ смены ключа
владения мьютексом/записью очереди с сессии на процесс. Красным его делает
именно регрессия реализации (например `release`, переставший снимать свой
же мьютекс, или изменённая сигнатура `acquire`), не отсутствие кода. Новые
тесты задачи в этих же файлах подхватываются автоматически: прогоняются
модули целиком, а не перечисленные классы.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests import (test_merge_gate_ci_wait, test_merge_lock,  # noqa: E402
                   test_merge_queue)


class ExistingMergeSuitesStillGreenTest(unittest.TestCase):

    def test_ac9_three_existing_merge_suites_pass_as_whole_modules(self):
        """Три существующих набора собираются в один `unittest.TestSuite` и
        прогоняются целиком — требуется `wasSuccessful()`.

        Ловит мутацию: реализация владения по процессу ломает соседнее
        существующее свойство — например `store.release_merge_lock` с
        обязательным pid вызывается из `merge_lock.release` без него
        (TypeError в `RunWindowTest`), либо `acquire` перестаёт брать
        свободный мьютекс. Любой такой случай делает `wasSuccessful()`
        ложным, и тест покраснеет с перечнем упавших имён.
        """
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for module in (test_merge_lock, test_merge_queue,
                       test_merge_gate_ci_wait):
            suite.addTests(loader.loadTestsFromModule(module))

        result = unittest.TextTestRunner(verbosity=0,
                                        stream=io.StringIO()).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            f"{len(result.failures)} провалов, {len(result.errors)} ошибок "
            f"в существующих наборах merge_lock/merge_queue/merge_gate: "
            f"{[str(case) for case, _ in result.failures + result.errors]}")


if __name__ == "__main__":
    unittest.main()
