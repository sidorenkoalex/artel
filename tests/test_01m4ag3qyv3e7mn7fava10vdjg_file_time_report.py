"""Замер времени долгоживущих файлов и вывод результата в двух текстах.

Группа: долгоживущий
Красен до реализации: публичные функции отчёта и вывода результата ещё не добавлены.

Публичный контракт для разработчика: `acceptance.long_lived_file_report`
принимает пары (путь, секунды) и порог, возвращает текст с временем каждого
файла и предупреждениями; `fsm_autogate.acceptance_checklist_measurement` и
`review.review_package_measurement` принимают отчёты последовательных
прогонов и вставляют последний в свои тексты.
"""

import random
import re
import unittest

from orchestrator import acceptance, config, fsm_autogate, review


class FileTimeReportTest(unittest.TestCase):
    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.paths = [f"tests/test_{self.rng.randrange(1 << 40):010x}.py"
                      for _ in range(3)]

    def context(self, value):
        return f"зерно: {self.seed}; {value}"

    def test_ac5_over_limit_names_file_time_and_limit(self):
        """Два разных файла сверх порога дают предупреждения со всеми числами.

        Ловит мутацию: сравнение перевёрнуто или из предупреждения выпало
        время файла — строка для превышения отсутствует либо неполна.
        """
        limit = config.LONG_LIVED_FILE_WARN_SEC
        for excess in (0.25, 2.75):
            with self.subTest(excess=excess):
                path = self.rng.choice(self.paths)
                elapsed = limit + excess
                report = acceptance.long_lived_file_report([(path, elapsed)], limit)
                self.assertIn(path, report, self.context(report))
                self.assertIn(str(elapsed), report, self.context(report))
                self.assertIn(str(limit), report, self.context(report))
                self.assertRegex(report.lower(), r"предупрежд|превыш|сверх",
                                 self.context(report))

    def test_ac6_at_or_below_limit_has_no_warning(self):
        """На границе и ниже неё время записывается без предупреждения.

        Ловит мутацию: условие `>=` вместо `>` предупреждает о файле,
        время которого равно порогу.
        """
        limit = config.LONG_LIVED_FILE_WARN_SEC
        for elapsed in (0.125, limit / 2, limit):
            with self.subTest(elapsed=elapsed):
                path = self.rng.choice(self.paths)
                report = acceptance.long_lived_file_report([(path, elapsed)], limit)
                self.assertIn(path, report, self.context(report))
                self.assertIn(str(elapsed), report, self.context(report))
                self.assertNotRegex(report.lower(), r"предупрежд|превыш|сверх",
                                    self.context(report))

    def test_ac8_named_limit_controls_warning_boundary(self):
        """Константа равна 60 секундам; смена порога меняет предупреждение.

        Ловит мутацию: отчёт сравнивает время с зашитыми 60 секундами —
        при другом пороге исход предупреждения не меняется.
        """
        self.assertEqual(config.LONG_LIVED_FILE_WARN_SEC, 60)
        elapsed = config.LONG_LIVED_FILE_WARN_SEC + 0.5
        path = self.paths[0]
        for limit, warning in ((elapsed - 0.25, True), (elapsed, False),
                               (elapsed + 0.25, False)):
            with self.subTest(limit=limit):
                report = acceptance.long_lived_file_report([(path, elapsed)], limit)
                self.assertIn(path, report, self.context(report))
                self.assertEqual(bool(re.search(
                    r"предупрежд|превыш|сверх", report.lower())), warning,
                    self.context(report))

    def test_ac9_checklist_contains_latest_file_times_and_warnings(self):
        """Карточка приёмки показывает время файлов и превышение последнего прогона.

        Ловит мутацию: карточка пропускает итог замера — пути и предупреждение
        исчезают из её текста.
        """
        limit = config.LONG_LIVED_FILE_WARN_SEC
        previous = acceptance.long_lived_file_report(
            [(self.paths[2], limit + 9)], limit)
        report = acceptance.long_lived_file_report(
            [(self.paths[0], limit + 1.5), (self.paths[1], limit / 2)], limit)
        card = fsm_autogate.acceptance_checklist_measurement([previous, report])
        for value in (self.paths[0], self.paths[1], str(limit + 1.5),
                      str(limit / 2)):
            self.assertIn(value, card, self.context(card))
        self.assertRegex(card.lower(), r"предупрежд|превыш|сверх",
                         self.context(card))
        self.assertNotIn(self.paths[2], card, self.context(card))

    def test_ac10_review_package_contains_latest_file_times_and_warnings(self):
        """Ревью-пакет показывает тот же замер, включая предупреждение.

        Ловит мутацию: сборщик пакета выбрасывает итог замера — путь
        превышающего файла и его время исчезают из текста ревьювера.
        """
        limit = config.LONG_LIVED_FILE_WARN_SEC
        previous = acceptance.long_lived_file_report(
            [(self.paths[1], limit + 11)], limit)
        report = acceptance.long_lived_file_report(
            [(self.paths[0], limit + 3.25), (self.paths[2], limit / 4)], limit)
        package = review.review_package_measurement([previous, report])
        for value in (self.paths[0], self.paths[2], str(limit + 3.25),
                      str(limit / 4)):
            self.assertIn(value, package, self.context(package))
        self.assertRegex(package.lower(), r"предупрежд|превыш|сверх",
                         self.context(package))
        self.assertNotIn(self.paths[1], package, self.context(package))
