"""Итоговая строка pytest с категорией `deselected`: `acceptance.run_summary_line`
берёт строку целиком, `suite_run.parse` считает по ней прошло/упало/пропущено.

Группа: долгоживущий

Чистые функции разбора — без песочницы. Помимо строки из критерия
(«201 failed, 4309 passed, 1156 skipped, 4 deselected, 13 warnings in
52s») — случайные итоговые строки с `deselected` на случайном месте среди
прочих категорий; зерно печатается и входит в текст провала.

Красен до реализации: разбор итоговой строки не знает слова `deselected` — совпадение обрывается на нём, `run_summary_line` берёт хвост «13 warnings in 52s», и `suite_run.parse` считает прошло 0, упало 0, пропущено 0.
"""
import random
import unittest

from orchestrator import acceptance, suite_run

SLED_LINE = ("201 failed, 4309 passed, 1156 skipped, 4 deselected, "
             "13 warnings in 52s")


def pytest_output(summary: str, lines=()) -> str:
    """Вывод прогона pytest, заканчивающийся итоговой строкой `summary` в
    рамке из `=`, как её печатает pytest."""
    return "\n".join([
        "============================= test session starts "
        "==============================",
        "collected 5671 items / 4 deselected / 5667 selected",
        *lines,
        "=========================== short test summary info "
        "============================",
        "FAILED tests/test_probe.py::ProbeTest::test_probe - AssertionError",
        f"========== {summary} ==========",
        ""])


class SummaryDeselectedTest(unittest.TestCase):
    """Итоговая строка с `deselected` — строка критерия и случайные."""

    def setUp(self):
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def cases(self) -> list:
        """(итоговая строка, прошло, упало, пропущено): строка критерия и
        случайные строки с `deselected` в случайной позиции."""
        cases = [(SLED_LINE, 4309, 201, 1156)]
        for _ in range(5):
            passed, failed, skipped = (self.rng.randint(1, 9999)
                                       for _ in range(3))
            parts = [f"{failed} failed", f"{passed} passed",
                     f"{skipped} skipped"]
            parts.insert(self.rng.randint(0, len(parts)),
                         f"{self.rng.randint(1, 99)} deselected")
            if self.rng.random() < 0.5:
                parts.append(f"{self.rng.randint(1, 99)} warnings")
            seconds = f"{self.rng.randint(1, 999)}.{self.rng.randint(0, 99):02d}"
            cases.append((f"{', '.join(parts)} in {seconds}s",
                          passed, failed, skipped))
        return cases

    def test_ac4_summary_line_with_deselected_taken_whole(self):
        """`run_summary_line` возвращает всю итоговую строку с `deselected`.

        Вывод прогона заканчивается итоговой строкой в рамке `=`: строкой
        критерия и случайными строками, где `deselected` стоит на случайном
        месте среди `failed`/`passed`/`skipped`/`warnings`. Функция
        возвращает эту итоговую строку целиком — от первого числа до «in
        <секунды>s».

        Ловит мутацию: в перечне категорий итоговой строки нет `deselected`
        — совпадение обрывается на нём, и возвращается хвост «13 warnings
        in 52s» (или часть строки после `deselected`).
        """
        for summary, *_ in self.cases():
            with self.subTest(summary=summary, seed=self.seed):
                self.assertEqual(
                    acceptance.run_summary_line(pytest_output(summary)),
                    summary, f"зерно {self.seed}")

    def test_ac4_suite_run_parse_counts_line_with_deselected(self):
        """`suite_run.parse` по выводу с `deselected` считает прошло/упало/пропущено из итоговой строки.

        Красный прогон (`green=False`) с выводом, заканчивающимся строкой
        критерия, даёт прошло 4309, упало 201, пропущено 1156; случайные
        строки — свои числа.

        Ловит мутацию: `run_summary_line` берёт хвост строки после
        `deselected` — `parse` видит итог без `passed`/`failed`/`skipped` и
        считает нули.
        """
        for summary, passed, failed, skipped in self.cases():
            with self.subTest(summary=summary, seed=self.seed):
                parsed = suite_run.parse(False, pytest_output(summary))
                self.assertEqual((parsed.passed, parsed.failed, parsed.skipped),
                                 (passed, failed, skipped),
                                 f"зерно {self.seed}: {parsed!r}")


if __name__ == "__main__":
    unittest.main()
