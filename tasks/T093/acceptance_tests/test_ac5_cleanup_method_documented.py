"""Приёмочный тест T093 — AC-5 (tasks/T093/SPEC.md, «Критерии приёмки»).

AC-5: «Для каждого урока из AC-1 ровно один способ вычистки копилки
реализован и задокументирован в PLAN.md: либо соответствующая запись
«Предложения системе» удалена тем же MR (способ (а)), либо она внесена
в сводный реестр «дистиллировано → куда» в tasks/T093/ с адресом
исходной записи и адресом поглотившей её правки (способ (б)); выбор и
обоснование по каждому уроку названы в PLAN.md.»

Красен до реализации: как и AC-1, никакого перечня уроков в tasks/T093/
пока нет (`_lessons.lesson_items()` пуст) — первый тест падает явным
`fail`, а не тихим пропуском, потому что AC-5 неотделим от AC-1 по
формату: без перечня уроков нечего сверять со способом вычистки.

Маркер способа — литерально «способ (а)»/«способ (б)» (или латинские
a/b — визуально неотличимы от кириллицы на письме, тест принимает оба
написания): именно этими словами и скобками SPEC называет два способа в
требовании 7. Тест не оценивает текст обоснования (это редакторское
суждение, не синтаксис, — читает Оператор при приёмке PLAN.md) — только
что при каждом уроке назван РОВНО один из двух маркеров, и что для
уроков со способом (б) в каталоге tasks/T093/ есть хотя бы одна
реестровая запись — SPEC называет её формат дословно в требовании 7б:
«дистиллировано → куда» (строка со стрелкой '→').
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _lessons  # noqa: E402

METHOD_A_RE = re.compile(r"способ\s*\([аa]\)", re.IGNORECASE)
METHOD_B_RE = re.compile(r"способ\s*\([бb]\)", re.IGNORECASE)
ARROW_ENTRY_RE = re.compile(r"^.*→.*$", re.MULTILINE)


class Ac5CleanupMethodDocumentedTest(unittest.TestCase):

    def test_ac5_every_lesson_names_exactly_one_cleanup_method(self):
        items = _lessons.lesson_items()
        if not items:
            self.fail(
                "ни одного урока не найдено в tasks/T093/ (см. AC-1) — "
                "AC-5 требует, чтобы у каждого урока был назван ровно "
                "один способ вычистки копилки")

        bad = []
        for path, item in items:
            has_a = bool(METHOD_A_RE.search(item))
            has_b = bool(METHOD_B_RE.search(item))
            if has_a == has_b:  # ни одного маркера, либо оба сразу
                bad.append((path.name, item.strip()[:80],
                           "оба" if has_a else "ни одного"))

        self.assertEqual(
            bad, [],
            f"уроки без однозначно названного способа вычистки копилки "
            f"— нужно ровно одно из 'способ (а)'/'способ (б)' на урок, "
            f"(файл, урок, что_найдено): {bad}")

    def test_ac5_method_b_lessons_have_registry_entries_with_addresses(self):
        items = _lessons.lesson_items()
        b_count = sum(1 for _, item in items if METHOD_B_RE.search(item))
        if b_count == 0:
            self.skipTest("ни один урок не выбрал способ (б) — сводный "
                          "реестр требованием 7б не нужен")

        registry_lines = []
        for path in _lessons.artifact_files():
            text = path.read_text(encoding="utf-8")
            registry_lines.extend(ARROW_ENTRY_RE.findall(text))

        self.assertGreaterEqual(
            len(registry_lines), 1,
            f"{b_count} урок(ов) выбрали способ (б), но ни в одном "
            f".md-файле tasks/T093/ нет ни одной строки сводного "
            f"реестра «дистиллировано → куда» (SPEC, требование 7б — "
            f"формат со стрелкой '→', адрес исходной записи и адрес "
            f"поглотившей её правки)")


if __name__ == "__main__":
    unittest.main()
