"""Приёмочный тест T093 — AC-1 (tasks/T093/SPEC.md, «Критерии приёмки»).

AC-1: «В артефактах задачи (PLAN.md и/или отдельный реестр в
tasks/T093/) явно перечислены выделенные уроки; для каждого указаны
минимум два номера задач/инцидентов корпуса требования 1 (секции
«Предложения системе», docs/retro/, ANSWER-файлы), в которых наблюдение
встретилось. Уроков с фактурой из одного источника в этом перечне нет.»

Красен до реализации: tasks/T093/ несёт пока только SPEC.md (аналитик)
и TZ.md (Оператор), которые парсер `_lessons.py` намеренно исключает из
разбора (это не PLAN.md и не «отдельный реестр» разработчика) — ни в
одном другом .md файле каталога нет заголовка, содержащего «урок» или
«дистилл» (см. `_lessons.py`), поэтому `_lessons.lesson_items()`
возвращает пустой список и первый же тест падает на утверждении «список
не пуст». Как только PLAN.md (или отдельный реестр) разработчика внесёт
перечень уроков, тест разбирает его настоящим парсером — не заглушкой.

Формат заголовка и пункта не зафиксирован SPEC дословно (требование 3 —
выбор файла и формулировки за разработчиком); номер задачи/инцидента —
токен `T\\d{2,4}`, потому что весь корпус требования 1 адресуется
номерами задач (`docs/retro/T<n>.md`, `tasks/T<n>/ANSWER-*.md`, секции
«Предложения системе» в `tasks/T<n>/{PLAN,REVIEW}.md`).

Третий тест сверяет каждую упомянутую ссылку с реальным существованием
такого корпусного артефакта — не смысловую достоверность наблюдения
(это решает Оператор на приёмке PLAN.md), а сам факт, что номер
участвует в корпусе требования 1, а не является, например, номером
находки docs/audits/ (требование 1 явно исключает такие находки как
самостоятельный источник урока этой задачи).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _lessons  # noqa: E402


class Ac1LessonsListedWithTwoSourcesTest(unittest.TestCase):

    def test_ac1_at_least_one_lesson_is_explicitly_listed(self):
        items = _lessons.lesson_items()
        self.assertGreater(
            len(items), 0,
            "ни в PLAN.md, ни в отдельном реестре tasks/T093/ не найден "
            "раздел с явным перечнем уроков (заголовок, содержащий "
            "'урок' или 'дистилл', с пунктами списка) — AC-1 требует "
            "явного перечня выделенных уроков")

    def test_ac1_every_lesson_cites_at_least_two_corpus_numbers(self):
        items = _lessons.lesson_items()
        offenders = []
        for path, item in items:
            refs = _lessons.refs_in(item)
            if len(refs) < 2:
                offenders.append((path.name, item.strip()[:80], sorted(refs)))
        self.assertEqual(
            offenders, [],
            f"уроки с фактурой из одного (или нуля) источников — AC-1 "
            f"требует минимум два номера задач/инцидентов на урок, "
            f"(файл, урок, найденные_номера): {offenders}")

    def test_ac1_cited_numbers_belong_to_required_corpus(self):
        items = _lessons.lesson_items()
        bad = []
        for path, item in items:
            for ref in _lessons.refs_in(item):
                if not _lessons.is_corpus_task(ref):
                    bad.append((path.name, ref, item.strip()[:80]))
        self.assertEqual(
            bad, [],
            f"ссылки на номера задач, не входящие в корпус требования 1 "
            f"(нет docs/retro/<n>.md, нет tasks/<n>/ANSWER-*.md и нет "
            f"непустой секции 'Предложения системе' в tasks/<n>/"
            f"{{PLAN,REVIEW}}.md) — возможно, это номер находки "
            f"docs/audits/, которую требование 1 исключает как "
            f"самостоятельный источник урока, (файл, номер, урок): {bad}")


if __name__ == "__main__":
    unittest.main()
