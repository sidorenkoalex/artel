"""AC-14: пять названных критерием файлов `tests/` остаются зелёными.

Зелёный с рождения: все пять зелены до задачи (замер 20.09 — 18 с на
весь набор из пяти) и обязаны остаться такими после переезда сборки
команды, окружения и предполётных проверок к провайдеру.

Известное место натяжения, найденное валидацией планки временным стабом:
`tests/test_doctor.py::LiveSmokeTest::test_cli_not_found_fails` опознаёт
процесс живого смоука сравнением `cmd[0] == "claude"`, а argv
провайдера несёт АБСОЛЮТНЫЙ путь резолва манифеста (AC-5) — мок фикстуры
придётся согласовать с новой формой вызова (например по базовому имени,
как это уже делает `tests/sandbox.py::is_claude_call`). Это правка
фикстуры, не ослабление проверки: сам ассерт про «claude CLI не найден»
остаётся.
"""
import subprocess
import sys
import unittest

from orchestrator import config, stack

NAMED_FILES = (
    "tests/test_runner_role_model.py",
    "tests/test_runner_model_preflight.py",
    "tests/test_stack.py",
    "tests/test_doctor.py",
    "tests/test_doctor_canary_pool.py",
)

# Запас под таймаутом ОДНОГО теста планки (`stack.PER_TEST_TIMEOUT_SEC`,
# тем же числом её гоняет гейт приёмки): прогон обязан упасть своим
# отказом с хвостом вывода, а не быть срезанным таймаутом снаружи.
TIMEOUT_SEC = max(30, stack.PER_TEST_TIMEOUT_SEC - 30)


class NamedTestsStayGreenTest(unittest.TestCase):
    """Прогон отдельным процессом: тесты пульта гоняются тем же
    интерпретатором, которым идёт сама планка."""

    def test_ac14_named_test_files_stay_green(self):
        """Пять файлов, названных критерием, проходят все до одного.

        Ловит мутацию: переезд `role_cmd`/`role_env`/предполётных
        проверок к провайдеру расходится с тем, как эти файлы подменяют
        коллаборантов (например, провайдер зовёт `stack.check_stack`
        мимо подменённого песочницей атрибута, или `doctor` получает
        вторую копию проверки CLI) — прогон возвращает ненулевой код,
        тест печатает хвост вывода pytest.
        """
        command = [sys.executable, "-m", "pytest", *NAMED_FILES,
                   "-p", "no:cacheprovider", "-q"]

        result = subprocess.run(command, cwd=config.ROOT, capture_output=True,
                                text=True, timeout=TIMEOUT_SEC)

        tail = (result.stdout + result.stderr)[-2000:]
        self.assertEqual(result.returncode, 0,
                         f"прогон {' '.join(NAMED_FILES)} не зелёный:\n{tail}")


if __name__ == "__main__":
    unittest.main()
