"""AC-10 — существующие тесты мьютекса merge-окна и цикла `merge_gate`
(часть 1: держание на весь цикл `approve`, включая ожидание CI) проходят
без ослабления и без изменения содержательных проверок (SPEC
01M291EPQ2VFGCHZTXXC81616V).

Прогоняет ДВЕ существующие планки целиком (`tests/test_merge_lock.py`,
`tests/test_merge_gate_ci_wait.py`) и требует полного успеха — прямая,
механическая часть критерия («существующие тесты проходят»). Часть
«без изменения содержательных проверок» — свойство ДИФФА (сравнение
файлов этих планок с версией до задачи), не поведения времени
исполнения; её проверяет ревьювер по факту, что зона задачи (`tests/`
входит в зоны SPEC) не тронула эти файлы, либо тронула без ослабления
ассертов — этот тест её не покрывает, но ловит главный практический
провал: реализация очереди случайно ломает существующий цикл ожидания
CI/мьютекса (например, меняет сигнатуру `_cmd_approve_merge_gate_cycle`
или порядок acquire/release).

Зелёный с рождения: обе планки уже проходят до кода этой задачи (часть 1
смержена) — красными их сделает именно РЕГРЕССИЯ реализации очереди, не
отсутствие кода; для этого критерия «зелёный сейчас» — ожидаемое и
корректное поведение, не признак тавтологии (сравни с докстрингами
остальных файлов планки: там красный ожидается ДО кода задачи, здесь
наоборот, зелёный СЕЙЧАС и ПОСЛЕ — самое прямое прочтение AC-10).
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests import test_merge_gate_ci_wait, test_merge_lock  # noqa: E402


class ExistingMergeLockAndCiWaitSuitesStillPassTest(unittest.TestCase):

    def test_ac10_existing_merge_lock_and_merge_gate_ci_wait_suites_pass(self):
        """Обе существующие планки (`tests/test_merge_lock.py`,
        `tests/test_merge_gate_ci_wait.py`) собираются в один
        `unittest.TestSuite` и прогоняются целиком — требуем `wasSuccessful()`.

        Ловит мутацию: реализация очереди меняет сигнатуру/поведение
        `merge_lock.acquire`/`release` или `_cmd_approve_merge_gate_cycle`
        так, что существующий вызов мьютекса на весь цикл `approve`
        (часть 1) перестаёт держаться/сниматься как раньше — любой из
        существующих тестов этих двух файлов покраснеет, `wasSuccessful()`
        станет `False`.
        """
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        suite.addTests(loader.loadTestsFromModule(test_merge_lock))
        suite.addTests(loader.loadTestsFromModule(test_merge_gate_ci_wait))

        result = unittest.TextTestRunner(
            verbosity=0, stream=io.StringIO()).run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            f"{len(result.failures)} провалов, {len(result.errors)} "
            f"ошибок в существующих планках merge_lock/merge_gate: "
            f"{[str(f[0]) for f in result.failures + result.errors]}")


if __name__ == "__main__":
    unittest.main()
