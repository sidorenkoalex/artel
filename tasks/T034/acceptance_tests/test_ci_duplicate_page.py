"""Приёмочные тесты T034: AC-5 — дубли страницы пагинации в `ci.check_runs`.

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 3
(ревью T018, замечание 1 итерации 1): сверка `len(runs) != total`
может не заметить, что одна и та же страница API отдана дважды, если
число дублей случайно совпало с `total_count` — тогда часть настоящих
проверок (например, вторая страница с упавшим тестом) вообще не была
прочитана, а вердикт всё равно «полно».

Сценарий из самого замечания ревью: `total_count=60`, `per_page=30`,
API отдаёт одну и ту же страницу из 30 записей на `page=1` и `page=2`
— получается 60 записей, но только 30 уникальных по `id`.

SPEC допускает ровно один из двух вариантов исправления (цена решает
Оператор): дедупликация по `id` перед сверкой, либо снятие безусловной
формулировки из комментария у сверки без изменения поведения. Тест
проверяет то свойство, которое требует выбранный вариант: если
`check_runs` вернул `None` — сверка распознала дубли и не посчитала их
настоящими 60 проверками (вариант «дедупликация»); если вернул список
— комментарий у сверки `len(runs) != total` в `ci.py` не должен
называть её безусловной гарантией полноты (вариант «формулировка»).
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import ci, config  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SHA = "0123456789abcdef0123456789abcdef01234567"

# Фраза комментария ci.py:103-104 (docstring T034 SPEC, требование 3),
# описывающая сверку ниже как безоговорочно решающую, что из двух
# случилось — без оговорки про дубли по id, ровно то, что назвал
# review T018 «безусловной» гарантией.
UNCONDITIONAL_PHRASE = "решает сверка ниже"


def duplicate_page_of(count: int) -> list[dict]:
    """Страница из `count` записей с настоящими различающимися `id`."""
    return [{"id": i, "name": f"check-{i}", "status": "completed",
             "conclusion": "success"} for i in range(count)]


class Ac5DuplicatePageCompletenessTest(unittest.TestCase):
    """AC-5: сверка полноты не маскируется дублирующейся страницей API."""

    def setUp(self):
        patcher = mock.patch.object(config, "CI_CHECKS_PER_PAGE", 30)
        patcher.start()
        self.addCleanup(patcher.stop)

    def serve_duplicate_page(self, total: int, unique_per_page: int) -> None:
        """`gh` отдаёт одну и ту же страницу (30 уникальных id) на любой
        запрошенный `page=`, пока не набежит `total`."""
        page = duplicate_page_of(unique_per_page)

        def fake_gh(*args):
            body = {"check_runs": page, "total_count": total}
            return subprocess.CompletedProcess(list(args), 0,
                                               json.dumps(body), "")

        patcher = mock.patch.object(ci, "gh", fake_gh)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac5_duplicate_page_behavior_matches_the_one_chosen_fix(self):
        # total_count=60 — ровно вдвое больше уникальных записей одной
        # страницы (30): без дедупликации `len(runs)` дублей (60) случайно
        # совпадает с total, и сверка молча "проходит".
        self.serve_duplicate_page(total=60, unique_per_page=30)

        runs, why = ci.check_runs(SHA)

        if runs is None:
            # Вариант «дедупликация»: дубли не должны были сойти за 60
            # настоящих проверок — уникальных 30 из обещанных 60, это
            # неполнота, а не «полный» ответ.
            self.assertIn("неполон", why,
                         f"дедупликация распознала дубли, но причина отказа "
                         f"не про неполноту: {why!r}")
        else:
            # Вариант «формулировка»: дедупликации нет (поведение как до
            # T034 — 60 записей сошли за полный ответ), но комментарий у
            # сверки len(runs) != total больше не должен называть её
            # безусловной гарантией полноты.
            self.assertEqual(len(runs), 60)
            source = (REPO_ROOT / "orchestrator" / "ci.py").read_text(
                encoding="utf-8")
            self.assertNotIn(
                UNCONDITIONAL_PHRASE, source,
                "runs не дедуплицированы, но формулировка-гарантия у "
                "сверки len(runs) != total всё ещё на месте (SPEC "
                "требование 3, ревью T018)")

    def test_ac5_a_genuinely_short_response_is_still_caught(self):
        """Смежная гарантия: без дублей, короче обещанного — по-прежнему
        неполно, каким бы ни было решение про дедупликацию по id."""
        self.serve_duplicate_page(total=61, unique_per_page=30)

        runs, why = ci.check_runs(SHA)

        self.assertIsNone(runs)
        self.assertIn("неполон", why)


if __name__ == "__main__":
    unittest.main()
