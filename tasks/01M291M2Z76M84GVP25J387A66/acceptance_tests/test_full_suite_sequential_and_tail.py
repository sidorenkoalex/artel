"""Приёмочные тесты 01M291M2Z76M84GVP25J387A66 — AC-3, AC-4, AC-5.

Все три свойства ниже уже выполняются СЕГОДНЯШНИМ кодом
`orchestrator/acceptance.py` (до появления параллели требования 1) —
это не совпадение, а инвариант, который обязан пережить переход на
xdist: `run()` и без этой задачи не несёт `-n`/`-p xdist` (нечего
убирать), `run_full_suite()` и без этой задачи не подменяет отказ
subprocess тихим повторным прогоном (никакого повторного прогона в
коде нет вовсе), а срез хвоста `[-2000:]` и без этой задачи берёт
конец вывода, а не начало. Смысл этих тестов — не обнаружить
отсутствующую сегодня возможность, а зафиксировать три конкретных
свойства ПЛАНКОЙ до того, как их случайно сломает сама эта задача
(добавление `-n`/`-p xdist` в `_pytest_command`, а не только в
`run_full_suite`; добавление "умного" повтора без xdist при отказе;
смена среза хвоста на `[:2000]` из-за более длинного вывода воркеров).

Зелёный с рождения: все три теста проходят на сегодняшнем коде
`orchestrator/acceptance.py` без единой правки — они фиксируют
СУЩЕСТВУЮЩЕЕ поведение (планка последовательна, отказ pytest не
подменяется тихим повтором, срез хвоста берёт конец вывода), которое
требование 1 SPEC («Не входит») и требования 3/5 явно обязывают не
трогать/не сломать при добавлении параллели `run_full_suite`.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import acceptance  # noqa: E402


class MissingXdistPluginIsLoudNotSilentTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "tests").mkdir()

    def test_ac3_pytest_failure_from_a_missing_plugin_is_red_without_a_silent_retry(self):
        """Симулируем отказ, которым реально ответил бы pytest на явную
        загрузку `-p xdist` при физически отсутствующем в интерпретаторе
        пакете pytest-xdist (ненулевой код возврата, сообщение об
        отсутствующем модуле/плагине в stderr) — тем же приёмом громкого
        отказа, что уже несёт явная загрузка `-p timeout` в
        `_pytest_command` (докстрока `_pytest_command`). Проверяем: этот
        отказ доходит до вызывающего кода как красный результат с
        причиной в хвосте, а не тихо компенсируется повторным прогоном
        без параллели.

        Ловит мутацию: `run_full_suite` ловит ошибку загрузки плагина
        (например, по подстроке "xdist" в stderr) и молча повторяет
        `subprocess.run` без `-n`/`-p xdist` — полный набор снова тихо
        идёт последовательно вместо честного красного отказа.
        """
        fake_stderr = ("ERROR: usage error: unrecognized arguments: -p "
                       "xdist (no module named 'xdist')")
        with mock.patch.object(acceptance.stack, "pytest_python_executable",
                               return_value="python3"), \
             mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess(
                ["python3", "-m", "pytest"], 4, "", fake_stderr)
            green, tail = acceptance.run_full_suite(self.root)

        self.assertFalse(green)
        self.assertIn("xdist", tail)
        self.assertEqual(
            run_.call_count, 1,
            "run_full_suite вызвал subprocess.run больше одного раза — "
            "похоже на тихий повторный прогон без параллели")


class AcceptancePlankStaysSequentialTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_marker.py").write_text(
            "import unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_x(self):\n        self.assertTrue(True)\n",
            encoding="utf-8")

    def test_ac4_run_command_carries_no_parallel_flags(self):
        """Планка приёмочных тестов задачи (`acceptance.run`) остаётся
        последовательным прогоном pytest — без `-n` и без явной загрузки
        `-p xdist`, даже после того, как `run_full_suite` обзаведётся
        параллелью (требование 1 SPEC, раздел «Не входит»).

        Ловит мутацию: `-n`/`-p xdist` добавлены в общий помощник
        `_pytest_command`, которым пользуются и `run()`, и
        `run_full_suite()`, вместо того, чтобы остаться только в
        `run_full_suite()` — планка задачи начинает гоняться параллельно,
        хотя её короткий вывод читает Оператор последовательно.
        """
        with mock.patch.object(acceptance.stack, "pytest_python_executable",
                               return_value="python3"), \
             mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess([], 0, "1 passed", "")
            acceptance.run(self.tdir)

        command = run_.call_args.args[0]
        self.assertNotIn("-n", command, f"планка гонится с -n: {command}")
        p_values = [command[i + 1] for i, token in enumerate(command)
                   if token == "-p" and i + 1 < len(command)]
        self.assertNotIn("xdist", p_values,
                         f"планка явно загружает xdist: {command}")


class FullSuiteTailKeepsFinalPassedLineTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "tests").mkdir()

    def test_ac5_noisy_worker_output_does_not_push_out_the_passed_summary(self):
        """Хвост вывода `run_full_suite`, который автогейт приёмки пишет
        в журнал, режется С КОНЦА (`[-2000:]`), не с начала — итоговая
        строка "N passed" остаётся в хвосте, даже когда суммарный вывод
        перегружен построчными репортами воркеров xdist (сценарий
        требования 2/AC-5).

        Ловит мутацию: срез меняют на `[:2000]` (голова вместо хвоста)
        — при объёмном построчном выводе воркеров финальная строка
        "N passed" вылетает за пределы того, что попадает в журнал.
        """
        noisy = ("[gw0] PASSED tests/test_marker.py::test_one\n" * 200
                + "500 passed in 3.21s\n")
        self.assertGreater(
            len(noisy), 2000, "фикстура недостаточно длинная для проверки среза")

        with mock.patch.object(acceptance.stack, "pytest_python_executable",
                               return_value="python3"), \
             mock.patch.object(acceptance.subprocess, "run") as run_:
            run_.return_value = subprocess.CompletedProcess(
                ["python3", "-m", "pytest"], 0, noisy, "")
            green, tail = acceptance.run_full_suite(self.root)

        self.assertTrue(green)
        self.assertIn("500 passed", tail)


if __name__ == "__main__":
    unittest.main()
