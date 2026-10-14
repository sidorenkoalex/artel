"""Матрица и результаты регрессии, относящиеся к этой задаче.

Группа: разовый
Красен до реализации: PLAN с матрицей и результатами AC-1 на базе и исправлении ещё не подготовлен.

Проверяется наличие предметных свидетельств в PLAN и его текстовых
приложениях; достоверность результатов дополняется исполняемой AC-1.
Проверен временный стаб чтения PLAN через плагин pytest: полный отчёт
проходит, удаление зелёного результата AC-1 даёт отказ. Стаб удалён.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import artifact_text


class EvidenceTest(unittest.TestCase):
    def test_ac8_matrix_and_red_green_regression_results(self):
        """Результат задачи содержит матрицу и оба исхода продуктовой регрессии.

        PLAN либо его приложения называют базу, AC-1, ложный spec_gate
        вместо spec_audit и успешный прогон после исправления.
        Ловит мутацию: из результата удалены матрица, база или красный/
        зелёный исход AC-1 — документ больше не подтверждает критерий.
        """
        plan = artifact_text("PLAN.md")
        self.assertTrue(plan, "нет PLAN.md с результатами работы")
        texts = [plan]
        # Приложения из ссылки документов: допускается обычная markdown-
        # ссылка или имя в backticks; записки ролей не являются отчётом.
        names = set(re.findall(r"[A-Za-zА-Яа-яЁё0-9_./-]+\.(?:md|txt|log)", plan))
        for name in sorted(names):
            if name.startswith(("/", "../", "NOTE-")) or name in ("SPEC.md", "PLAN.md"):
                continue
            text = artifact_text(name)
            if text:
                texts.append(text)
        report = "\n".join(texts)
        self.assertRegex(report.lower(), r"матриц[аы] неослабления")
        rows = [line for line in report.splitlines()
                if line.strip().startswith("|") and "test_" in line]
        self.assertTrue(rows, "в матрице нет проверок прежних свойств")
        self.assertTrue(any(len([c for c in row.split("|") if c.strip()]) >= 3
                            for row in rows), "матрица не связывает свойство и покрытие")
        self.assertIn("daec84553c0951b8ddb9c46573c0e308d7319057", report)
        self.assertRegex(report, r"AC-1|test_ac1_")
        self.assertIn("spec_gate", report)
        self.assertIn("spec_audit", report)
        self.assertRegex(report.lower(), r"failed|assertionerror|красн|ложн[а-я]* проход")
        # В красном pytest-логе тоже бывает «1 passed» (родитель метода
        # с упавшими subTest). Успех обязан относиться именно к AC-1 на
        # исправлении, а не к соседним зелёным тестам/подслучаям базы.
        paragraphs = re.split(r"\n\s*\n", report)
        # Абзац либо подпись с соседним блоком вывода — перенос строки и
        # markdown-ограждения не задают отдельного формата свидетельства.
        blocks = paragraphs + [a + "\n" + b
                               for a, b in zip(paragraphs, paragraphs[1:])]
        green_blocks = [block for block in blocks
                        if re.search(r"AC-1|test_ac1_", block)
                        and re.search(r"исправ|HEAD", block, re.I)
                        and re.search(r"[1-9][0-9]* passed|зел[её]н|успе[хш]", block, re.I)
                        and not re.search(r"[1-9][0-9]* failed|AssertionError", block)]
        self.assertTrue(green_blocks,
                        "нет явно связанного результата: AC-1 на исправлении — успех")
