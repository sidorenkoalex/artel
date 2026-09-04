"""Приёмочные тесты 01M1KS8K9RXWHX2PW3ZKB0P903 — AC-6 (guard принимает
SPEC без сработавших сигналов независимо от секции «Оценка объёма и
деление»).

Фикстура-«чистый» SPEC (`_sandbox.spec_text` без `extra_requirement_
sentence`) намеренно нейтральна по всем шести сигналам требования 1: без
фраз-триггеров AC-2, без упоминаний docs/invariants.md (AC-3), с
`budget_usd: 15` (< $30), с двумя критериями приёмки (< 10) и без единого
упомянутого пути файла (не может дать «≥5 затронутых модулей» ни при
каком разумном способе счёта) — единственная переменная в тестах ниже
это состояние секции «Оценка объёма и деление».

Зелёный с рождения: сегодняшний guard.py вообще не знает об этой секции
и потому принимает любую из фикстур ниже без единой ошибки — то же самое
верно и ПОСЛЕ реализации требования 3 SPEC, раз ни один сигнал не
сработал. Тест — защита от регрессии («слишком жадная» проверка начинает
требовать секцию даже без сигналов), не проверка новой логики.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import check  # noqa: E402


class NoSignalAcceptsRegardlessOfSectionTest(unittest.TestCase):
    """Без единого сработавшего сигнала guard принимает SPEC независимо от
    того, отсутствует ли секция «Оценка объёма и деление», пуста она или
    заполнена содержимым.

    Ловит мутацию: реализация требует секцию безусловно (забыли обернуть
    проверку условием «хотя бы один сигнал сработал») — соответствующий
    subTest покраснеет отказом там, где ожидается пустой список ошибок.
    """

    def test_ac6_absent_empty_and_filled_section_all_pass_without_signals(self):
        cases = {
            "отсутствует": None,
            "пустая": "",
            "заполненная": "Деление не требуется, задача мала.",
        }
        for label, volume_section in cases.items():
            with self.subTest(section=label):
                errors = check(volume_section=volume_section)

                self.assertEqual(
                    errors, [],
                    f"guard отклонил SPEC без сработавших сигналов "
                    f"(секция «Оценка объёма и деление» {label}): {errors}")


if __name__ == "__main__":
    unittest.main()
