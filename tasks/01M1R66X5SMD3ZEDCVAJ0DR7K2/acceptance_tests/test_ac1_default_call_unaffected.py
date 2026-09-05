"""Приёмочные тесты 01M1R66X5SMD3ZEDCVAJ0DR7K2 — AC-1 (вызов guard БЕЗ
включённого режима артефактной ветки не меняет поведение ни на бит,
включая существующий формат вывода `guard.py --all`).

Зелёный с рождения: этот файл целиком проверяет поведение БЕЗ флага
`--artifact-branch` — то есть поведение, которое уже существует СЕГОДНЯ,
до кода этой задачи. AC-1 требует именно неизменности этого пути, а
значит корректный тест обязан быть зелёным и ДО, и ПОСЛЕ реализации:
краснота здесь до кода задачи означала бы, что фикстуры сломаны (не то
поведение проверяют), а не что реализация ещё не готова.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import run_main, spec_zones_text  # noqa: E402


class NoFlagBehaviorIsStatusIndependentTest(unittest.TestCase):
    """Без флага `--artifact-branch` нарушение структуры отказывает
    ОДИНАКОВО для draft и ready SPEC — «независимо от status», буквально
    требование 1."""

    def test_ac1_missing_zones_fails_regardless_of_status_without_the_flag(self):
        """Прогоняет SPEC без `zones` дважды — со `status: draft` и
        `status: ready` — без флага `--artifact-branch` в обоих случаях.

        Ловит мутацию: разработчик по ошибке смещает условие черновика на
        путь БЕЗ флага (например читает status до проверки самого флага и
        применяет мягкий режим всегда для draft) — тогда прогон со
        `status: draft` без флага перестал бы отказывать (exit 0), хотя
        AC-1 требует ту же строгость независимо от status, пока флаг не
        включён явно.
        """
        for status in ("draft", "ready"):
            with self.subTest(status=status):
                code, out = run_main(
                    {"tasks/T1/SPEC.md": spec_zones_text(status=status, zones=None)},
                    artifact_branch=False)

                self.assertEqual(code, 1, out)
                self.assertIn("zones", out)


class NoFlagOutputFormatUnchangedTest(unittest.TestCase):
    """Требование 5, последнее предложение: «Без флага/переменной формат
    вывода не меняется» — без флага сводки «сдано N / черновиков M /
    нарушений K» быть не должно."""

    def test_ac1_clean_run_without_flag_prints_the_old_ok_line(self):
        """Валидный SPEC (со `zones`), без флага — вывод дословно совпадает
        с сегодняшним форматом «GUARD: ок (N файлов)», без новой сводки.

        Ловит мутацию: разработчик печатает новую строку сводки всегда
        (независимо от флага) — тест, ищущий строку «GUARD: ок», а не
        «сдано ... / черновиков ...», покраснеет на первой строке.
        """
        code, out = run_main(
            {"tasks/T1/SPEC.md": spec_zones_text(status="ready", zones="tests/")},
            artifact_branch=False)

        self.assertEqual(code, 0, out)
        self.assertIn("GUARD: ок", out)
        self.assertNotIn("черновиков", out)

    def test_ac1_broken_run_without_flag_prints_the_old_violations_header(self):
        code, out = run_main(
            {"tasks/T1/SPEC.md": spec_zones_text(status="draft", zones=None)},
            artifact_branch=False)

        self.assertEqual(code, 1, out)
        self.assertIn("GUARD: нарушения структуры артефактов:", out)
        self.assertNotIn("черновиков", out)


if __name__ == "__main__":
    unittest.main()
