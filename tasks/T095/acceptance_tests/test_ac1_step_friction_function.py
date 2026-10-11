"""AC-1 (tasks/T095/SPEC.md): существует детерминированная (без LLM)
функция, вычисляющая долю непродуктивных токенов/событий шага по логу
шага (`--output-format stream-json`), учитывающая как минимум три
сигнала, названные ТЗ/SPEC: повторные чтения одного файла, ошибки
инструментов и ретраи вызовов, перечитывания больших кусков.

Допущение об интерфейсе (`agent_log.step_friction(log_path: Path) ->
float`) и о формате фикстур — см. докстринг `_sandbox.py`. Точные пороги
и веса — решение разработчика (SPEC требование 1); эти тесты проверяют
только то, что верно при ЛЮБОМ разумном пороге: детерминизм, ноль на
шаге без единого поименованного сигнала, строгий рост при добавлении
КАЖДОГО из трёх сигналов относительно эквивалентного по числу вызовов
чистого шага.

Красен до реализации: `orchestrator.agent_log.step_friction` не
существует.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import (assistant_event, bash_call, edit_call,  # noqa: E402
                      read_call, tool_use_block, tool_result_line)
from orchestrator import agent_log  # noqa: E402 — красное до реализации


def clean_log(tmp_writer) -> Path:
    """4 разных, успешных, некрупных вызова — без единого поименованного
    в ТЗ сигнала непродуктивности."""
    return tmp_writer([
        read_call("t1", "a.py"),
        read_call("t2", "b.py"),
        bash_call("t3", "pytest tests/"),
        edit_call("t4", "c.py"),
    ])


class StepFrictionFunctionExistsTest(unittest.TestCase):

    def setUp(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp_dir = Path(tmp.name)
        self._n = 0

    def _write(self, lines: list) -> Path:
        self._n += 1
        path = self.tmp_dir / f"step-{self._n}.log"
        path.write_text("".join(lines), encoding="utf-8")
        return path

    def test_ac1_function_exists_and_is_callable(self):
        self.assertTrue(callable(agent_log.step_friction))

    def test_ac1_deterministic_same_log_same_result(self):
        path = clean_log(self._write)

        first = agent_log.step_friction(path)
        second = agent_log.step_friction(path)

        self.assertEqual(
            first, second,
            "step_friction обязана быть детерминированной: одинаковый "
            "лог дал разные значения на двух вызовах")

    def test_ac1_clean_step_has_zero_friction(self):
        path = clean_log(self._write)

        ratio = agent_log.step_friction(path)

        self.assertEqual(
            ratio, 0,
            "шаг без единого сигнала непродуктивности (ТЗ: повторные "
            "чтения файла, ошибки/ретраи инструментов, перечитывания "
            "больших кусков) обязан дать долю 0")

    def test_ac1_repeated_file_read_increases_friction(self):
        """Сигнал 1 ТЗ: повторные чтения одного и того же файла."""
        baseline = agent_log.step_friction(clean_log(self._write))

        noisy_path = self._write([
            read_call("t1", "a.py"),
            read_call("t2", "a.py"),  # повторное чтение того же файла
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        noisy = agent_log.step_friction(noisy_path)

        self.assertGreater(
            noisy, baseline,
            "повторное чтение одного файла обязано увеличивать долю "
            "непродуктивности относительно эквивалентного чистого шага")

    def test_ac1_tool_error_and_retry_increases_friction(self):
        """Сигнал 2 ТЗ: ошибки инструментов и ретраи вызовов."""
        baseline = agent_log.step_friction(clean_log(self._write))

        noisy_path = self._write([
            assistant_event(tool_use_block("t1", "Bash", command="pytest")),
            tool_result_line("t1", "ModuleNotFoundError", is_error=True),
            assistant_event(tool_use_block("t2", "Bash", command="pytest")),
            tool_result_line("t2", "готово", is_error=False),
            read_call("t3", "b.py"),
            edit_call("t4", "c.py"),
        ])
        noisy = agent_log.step_friction(noisy_path)

        self.assertGreater(
            noisy, baseline,
            "ошибка инструмента с последующим ретраем обязана "
            "увеличивать долю непродуктивности относительно "
            "эквивалентного чистого шага")

    def test_ac1_large_chunk_reread_increases_friction(self):
        """Сигнал 3 ТЗ: перечитывания больших кусков."""
        big_content = "x" * 50_000

        baseline_path = self._write([
            read_call("t1", "big.py"),
            tool_result_line("t1", big_content),
            bash_call("t2", "pytest tests/"),
            edit_call("t3", "c.py"),
            read_call("t4", "d.py"),
        ])
        baseline = agent_log.step_friction(baseline_path)

        noisy_path = self._write([
            read_call("t1", "big.py"),
            tool_result_line("t1", big_content),
            read_call("t2", "big.py"),  # перечитан тот же большой кусок
            tool_result_line("t2", big_content),
            bash_call("t3", "pytest tests/"),
            edit_call("t4", "c.py"),
        ])
        noisy = agent_log.step_friction(noisy_path)

        self.assertGreater(
            noisy, baseline,
            "повторное чтение большого куска обязано увеличивать долю "
            "непродуктивности относительно шага с тем же большим "
            "куском, прочитанным лишь один раз")


if __name__ == "__main__":
    unittest.main()
