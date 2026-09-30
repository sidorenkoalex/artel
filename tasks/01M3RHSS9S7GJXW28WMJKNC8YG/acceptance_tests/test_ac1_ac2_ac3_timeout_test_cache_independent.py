"""AC-1, AC-2, AC-3 — тест таймаута прогона приёмочных тестов
(`tests/test_acceptance_tests_flow.py`) не зависит от кэша
`environment_fingerprint` и по-прежнему ловит свои мутации.

Группа: разовый

Предмет планки — сам исправленный тест `tests/`: он запускается в
ОТДЕЛЬНОМ интерпретаторе (`_runner.py`) в одиночку — только тесты
таймаута файла (`-k timeout`), без соседей — при пустом и при заранее
заполненном кэше `agent_log.environment_fingerprint`, а также против
мутаций `orchestrator/acceptance.py::run`, внесённых в памяти (файл
кода не правится). Прогон полного `tests/` (вторая половина AC-3) —
работа CI и автогейта приёмки, планка его не повторяет (решение
Оператора 05.09: полный набор в шаге не гоняется); заполненный кэш —
ровно то состояние, в котором тест оказывается после соседей в полном
наборе.

Красен до реализации: текущий тест сверяет `timeout` ПОСЛЕДНЕГО вызова подменённого `subprocess.run`, а при пустом кэше последним идёт `git/claude --version` из `environment_fingerprint` с `timeout=5` — прогон при пустом кэше красный (AC-1, AC-3); прогоны с заполненным кэшем и мутационные уже сейчас ведут себя как требуется.
"""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import _runner  # noqa: E402

TEST_FILE = "tests/test_acceptance_tests_flow.py"
SELECT = ["-k", "timeout"]
RUN_TIMEOUT_SEC = 100


def run_timeout_tests(cache: str, mutation: str = "none"):
    """Код возврата и вывод прогона тестов таймаута в отдельном процессе."""
    res = subprocess.run(
        [sys.executable, str(HERE / "_runner.py"), cache, mutation,
         TEST_FILE, *SELECT],
        cwd=REPO_ROOT, capture_output=True, text=True,
        timeout=RUN_TIMEOUT_SEC)
    return res.returncode, (res.stdout + res.stderr)[-4000:]


class TimeoutTestCacheIndependentTest(unittest.TestCase):

    def test_ac1_timeout_test_green_alone_with_empty_fingerprint_cache(self):
        """Тесты таймаута файла запускаются одни, кэш fingerprint пуст.

        Сценарий одиночного запуска: после `acceptance.run` переход зовёт
        `environment_fingerprint()`, и тот при пустом кэше делает свои
        вызовы подменённого `subprocess.run` с `timeout=5`. Тест, который
        сверяет вызов pytest, опознанный по команде, остаётся зелёным;
        сверка последнего вызова — красна. Прогон собирает хотя бы один
        тест (код 5 «ничего не собрано» — провал).

        Ловит мутацию: тест по-прежнему берёт `run_mock.call_args`
        (последний вызов) вместо вызова pytest — при пустом кэше он
        видит `timeout=5` вместо `config.ACCEPTANCE_TIMEOUT_SEC`, прогон
        падает с кодом 1.
        """
        code, out = run_timeout_tests("empty")
        self.assertEqual(code, 0, f"тест таймаута красен при пустом кэше "
                                  f"environment_fingerprint:\n{out}")

    def test_ac3_timeout_test_green_with_prefilled_fingerprint_cache(self):
        """Тот же одиночный прогон, но кэш fingerprint заполнен заранее.

        Сценарий — тест идёт в полном `tests/` после соседа, уже
        заполнившего кэш: `environment_fingerprint()` не делает вызовов
        процесса вовсе. Тест обязан быть зелёным и здесь.

        Ловит мутацию: исправление завязано на пустой кэш (например,
        сверяется вызов по индексу «предпоследний», рассчитанный на два
        вызова `--version` после pytest) — при заполненном кэше таких
        вызовов нет, сверяется не тот вызов, прогон падает с кодом 1.
        """
        code, out = run_timeout_tests("prefilled")
        self.assertEqual(code, 0, f"тест таймаута красен при заполненном "
                                  f"кэше environment_fingerprint:\n{out}")

    def test_ac2_removed_timeout_in_acceptance_run_turns_test_red(self):
        """Из вызова pytest в `acceptance.run` убран `timeout=`.

        Мутация вносится в памяти отдельного процесса, при обоих
        состояниях кэша: тесты таймаута обязаны упасть (код 1 — провал
        тестов, не ошибка сбора и не «мутация не применилась»).

        Ловит мутацию: тест перестал проверять `timeout` вызова pytest
        (сверка удалена или заменена на «любой вызов с каким-нибудь
        timeout», которому удовлетворяет вызов `--version` из
        fingerprint) — после удаления `timeout=` прогон остаётся с кодом 0.
        """
        for cache in ("empty", "prefilled"):
            with self.subTest(cache=cache):
                code, out = run_timeout_tests(cache, "no_timeout")
                self.assertNotEqual(code, _runner.MUTATION_NOT_APPLIED,
                                    f"мутация не применилась:\n{out}")
                self.assertEqual(code, 1, f"удаление timeout= из "
                                          f"acceptance.run не ловится "
                                          f"(кэш {cache}):\n{out}")

    def test_ac1_timeout_test_checks_limit_named_in_output_and_journal(self):
        """Текст отказа по таймауту в `acceptance.run` больше не называет
        «превысил».

        Тест из AC-1 обязан требовать `превысил {ACCEPTANCE_TIMEOUT_SEC}с`
        в выводе `cmd_advance` и «превысил» в записи журнала — при такой
        мутации он падает (код 1) при обоих состояниях кэша.

        Ловит мутацию: из исправленного теста выпали проверки вывода и
        журнала (осталась только сверка `timeout` вызова pytest) — после
        смены текста отказа прогон остаётся с кодом 0.
        """
        for cache in ("empty", "prefilled"):
            with self.subTest(cache=cache):
                code, out = run_timeout_tests(cache, "no_word")
                self.assertNotEqual(code, _runner.MUTATION_NOT_APPLIED,
                                    f"мутация не применилась:\n{out}")
                self.assertEqual(code, 1, f"смена текста «превысил» не "
                                          f"ловится (кэш {cache}):\n{out}")


if __name__ == "__main__":
    unittest.main()
