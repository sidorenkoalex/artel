"""AC-4 (SPEC 01M2B6K3EM7F2J72RC2F520Y2K) — `tests/test_conftest_role_guard.py`
существует как новый файл и сам зелёный: subprocess-прогон pytest с
ARTEL_ROLE=developer без путей/с `tests` даёт ненулевой код и текст
причины; с путём к файлу — сбор идёт; без ARTEL_ROLE — прежнее
поведение.

Красен до реализации: тест `test_ac4_new_test_file_exists` — файла
`tests/test_conftest_role_guard.py` ещё нет, проверка существования
падает сама по себе; `test_ac4_new_test_file_is_green` при этом не
красный, а `skipTest` (тот же факт отсутствия файла) — гонять
subprocess pytest по несуществующему пути бессмысленно, тест обязан
стать реальной (не вакуумной) проверкой только после появления файла.

Это НЕ повторная реализация той же проверки, что AC-2/AC-3 этой планки
(`test_ac2_.../test_ac3_...`, тот же субпроцессный приём) — это
самостоятельная проверка ОБЯЗАТЕЛЬНОГО файла, названного требованием
5(а) и критерием буквально по имени: сам этот новый юнит-тест
разработчика обязан существовать и проходить. Если бы этого теста не
было вовсе (только моя собственная планка проверяла бы поведение
`conftest.py`), критерий 4 остался бы неисполненным независимо от
правильности `conftest.py` самого по себе.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TARGET = REPO_ROOT / "tests" / "test_conftest_role_guard.py"


class ConftestRoleGuardTestFileTest(unittest.TestCase):

    def test_ac4_new_test_file_exists(self):
        """Файл `tests/test_conftest_role_guard.py` — новый файл, названный
        требованием буквально по имени.

        Ловит мутацию: разработчик кладёт эквивалентные проверки в уже
        существующий файл (например `tests/test_role_bash_guard.py`)
        вместо создания нового — критерий 4 называет ИМЕННО это имя
        файла.
        """
        self.assertTrue(TARGET.is_file(),
                        f"{TARGET.relative_to(REPO_ROOT)} должен существовать")

    def test_ac4_new_test_file_is_green(self):
        """Прогон самого нового файла (subprocess pytest, без ARTEL_ROLE —
        путь к конкретному файлу и так не заблокирован) завершается
        успешно: разработчик не просто завёл файл, тесты в нём проходят.

        Ловит мутацию: файл заведён, но его собственные проверки ломаются
        (например ссылаются на несуществующий REASON/конфтест до того, как
        тот появился, либо путают возвращаемый код) — subprocess вернёт
        ненулевой код, и этот тест покраснеет вместо AC-2/AC-3.
        """
        if not TARGET.is_file():
            self.skipTest("файл ещё не существует — см. test_ac4_new_test_file_exists")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
             str(TARGET.relative_to(REPO_ROOT))],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=100)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
