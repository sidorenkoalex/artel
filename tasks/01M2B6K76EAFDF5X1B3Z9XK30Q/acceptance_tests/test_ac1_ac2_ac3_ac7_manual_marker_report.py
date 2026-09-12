"""Приёмочные тесты AC-1, AC-2, AC-3, AC-7 задачи 01M2B6K76EAFDF5X1B3Z9XK30Q.

Красен до реализации: `fsm_autogate._maybe_autogate_acceptance` сегодня
не журналирует и не печатает запись «приёмка: что проверит approve» —
`AcceptanceEntryReportSandbox.entry_report` падает на
`self.assertEqual(len(details), 1, ...)` (записей действия 0), ни один
тест этого файла не доходит до собственных assert'ов.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ACTION, AcceptanceEntryReportSandbox  # noqa: E402

_MANUAL_PLANKA = (
    '"""Маркер: планка с одним manual-критерием."""\n'
    "import unittest\n\n\n"
    "class MarkerTest(unittest.TestCase):\n"
    "    def test_ac1_marker_always_passes(self):\n"
    "        self.assertTrue(True)\n\n\n"
    "# AC-9: manual — печать флажков UI сверяется на приёмке визуально.\n"
)


def _group_slice(text: str, start_marker: str, end_markers: tuple) -> str:
    start = text.index(start_marker) + len(start_marker)
    end = len(text)
    for marker in end_markers:
        idx = text.find(marker, start)
        if idx != -1:
            end = min(end, idx)
    return text[start:end]


class ManualMarkerReportTest(AcceptanceEntryReportSandbox):
    """Планка с ровно одним manual-критерием; кодовая ветка несёт один
    настоящий merge main-а (история подтяжки, AC-3); REVIEW.md — итерация
    2 (передаётся параметром `iteration`, тем же путём, что и боевой
    вызов `fsm_advance._review_approved`)."""

    def setUp(self):
        super().setUp()
        self.seed_planka(_MANUAL_PLANKA)
        self.checkout_code_branch()
        self.commit_on_code_branch("dev.txt", "работа\n", "работа по задаче")
        self.commit_on_main("other.txt", "другая задача\n", "другая задача в main")
        self.merge_sha = self.merge_main_into_code_branch()

    def test_ac1_single_journal_entry_and_matching_stdout(self):
        """На входе в acceptance пульт журналирует ОДНОЙ записью действие
        «приёмка: что проверит approve» и печатает то же самое
        содержимое в stdout (SPEC требование 1, AC-1).

        Ловит мутацию: код, печатающий отчёт только в stdout без записи
        в журнал (или наоборот) — `entry_report()` либо не найдёт ровно
        одну запись `ACTION` (упадёт внутри самого хелпера песочницы),
        либо `assertIn` ниже, сверяющий печать с журналом, разойдётся.
        """
        out, detail = self.entry_report(iteration=2)

        self.assertIn(ACTION, out,
                     "печать обязана называть действие тем же текстом, "
                     "что и журнал")
        # «то же самое содержимое» (требование 1) — существенная часть
        # detail обязана быть видна и в напечатанном выводе, не только
        # в журнале.
        self.assertIn("автоматически при approve", out)
        self.assertIn("остаётся человеку", out)

    def test_ac2_automatic_group_lists_exactly_four_checks(self):
        """Группа «автоматически при approve» перечисляет ровно четыре
        пункта: прогон планки (с источником — веткой и sha), полный
        `tests/` в worktree, потолок бюджета, свежесть кодовой ветки
        против `origin/<main>` (SPEC требование 1а, AC-2).

        Ловит мутацию: пропущенный пункт (например, код, забывший
        свежесть против origin, — частый кандидат, так как
        `_autogate_conditions` её вообще не проверяет и пункт легко
        потерять при копировании остальных трёх из её `ok`-списка) —
        соответствующий `assertIn` ниже не найдёт ключевое слово.
        """
        out, detail = self.entry_report(iteration=1)

        group_a = _group_slice(detail, "автоматически при approve",
                               ("остаётся человеку", "автогейт пройдёт сам"))

        self.assertIn(self.artifact_branch, group_a,
                     "пункт 1 обязан называть источник планки — "
                     "артефактную ветку")
        self.assertIn("tests/", group_a,
                     "пункт 2 обязан называть полный tests/")
        self.assertIn("бюджет", group_a.lower(),
                     "пункт 3 обязан называть потолок бюджета")
        self.assertIn("origin", group_a.lower(),
                     "пункт 4 обязан называть свежесть против origin/<main>")
        self.assertNotIn("REVIEW.md", group_a,
                         "вердикт ревью — предмет группы «остаётся "
                         "человеку», не «автоматически при approve»")

    def test_ac3_human_group_names_marker_zones_merges_and_review(self):
        """Группа «остаётся человеку» перечисляет: manual-критерий
        (номер AC и первая строка пометки), факт «дифф сверен с зонами —
        уже сделано гейтом», родителей подтяжек (merge-коммиты main в
        ветку задачи) и вердикт ревью (файл REVIEW.md, номер итерации)
        (SPEC требование 1б, AC-3).

        Ловит мутацию: пропуск любого из четырёх элементов — например,
        код, не читающий историю кодовой ветки вовсе (родители подтяжек
        отсутствуют в выводе), либо не прокидывающий переданную
        `iteration` в текст (число итерации нигде не встречается).
        """
        out, detail = self.entry_report(iteration=3)

        group_b = _group_slice(detail, "остаётся человеку", ())

        self.assertIn("AC-9", group_b,
                     "обязан быть назван номер manual-критерия")
        self.assertIn("печать флажков UI сверяется на приёмке визуально",
                      group_b,
                     "обязана быть названа первая строка пометки")
        self.assertIn("дифф сверен с зонами — уже сделано гейтом", group_b)
        self.assertTrue(
            self.merge_sha in group_b or self.merge_sha[:8] in group_b,
            "обязан быть назван merge-коммит подтяжки main (родитель "
            f"подтяжки за жизнь ветки задачи), полным или коротким sha: "
            f"{self.merge_sha!r} не найден в {group_b!r}")
        self.assertIn("REVIEW.md", group_b)
        self.assertIn("3", group_b,
                     "обязан быть назван номер итерации REVIEW.md")

    def test_ac7_manual_marker_names_the_ac_and_the_full_suite(self):
        """Планка с одним manual-критерием: запись несёт номер этого AC
        в группе «остаётся человеку» и упоминание полного `tests/` в
        группе «автоматически при approve» (SPEC AC-7).

        Ловит мутацию: смешение групп — например, код, кладущий номер
        manual-критерия в группу «автоматически» (или упоминание
        `tests/` — в группу «остаётся человеку») пройдёт по «есть где-то
        в detail», но не по срезу СВОЕЙ группы, который проверяют
        отдельные assert'ы этого теста.
        """
        out, detail = self.entry_report(iteration=1)

        group_a = _group_slice(detail, "автоматически при approve",
                               ("остаётся человеку", "автогейт пройдёт сам"))
        group_b = _group_slice(detail, "остаётся человеку", ())

        self.assertIn("tests/", group_a)
        self.assertIn("AC-9", group_b)
        self.assertNotIn("AC-9", group_a,
                         "номер manual-критерия — предмет группы "
                         "«остаётся человеку», не «автоматически»")


if __name__ == "__main__":
    unittest.main()
