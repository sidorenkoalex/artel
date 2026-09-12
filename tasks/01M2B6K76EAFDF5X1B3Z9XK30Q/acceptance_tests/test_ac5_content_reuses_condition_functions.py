"""Приёмочные тесты AC-5 задачи 01M2B6K76EAFDF5X1B3Z9XK30Q.

Красен до реализации: `fsm_autogate._maybe_autogate_acceptance` сегодня
не журналирует запись «приёмка: что проверит approve» вовсе —
`entry_report()` падает внутри песочницы (записей действия 0), тест не
доходит до собственных assert'ов.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import artifact_source, gitcmd, store  # noqa: E402
from scripts import guard  # noqa: E402

from _sandbox import AcceptanceEntryReportSandbox  # noqa: E402

_CLEAN_PLANKA = '''"""Маркер: заведомо чистая планка (без manual/skip/escalate)."""
import unittest


class MarkerTest(unittest.TestCase):
    def test_ac1_marker_always_passes(self):
        self.assertTrue(True)
'''


class GroupContentReusesRealFunctionsTest(AcceptanceEntryReportSandbox):
    """Планка заведомо чистая (без единой пометки) — если бы группа
    «остаётся человеку» вычислялась НЕ через `guard.scan_ac_content`, а
    отдельным разбором планки, подмена этой функции ничего не изменила
    бы в выводе; ниже этой посылке даётся возможность себя опровергнуть."""

    def setUp(self):
        super().setUp()
        self.seed_planka(_CLEAN_PLANKA)
        self.checkout_code_branch()
        self.commit_on_code_branch("dev.txt", "работа\n", "работа по задаче")

    def test_ac5_human_group_is_computed_via_scan_ac_content(self):
        """Группа «остаётся человеку» вычислена через функцию
        `scan_ac_content` guard'а — не отдельным разбором планки,
        дублирующим её по смыслу (SPEC требование 2, AC-5): планка на
        диске/в ветке заведомо чистая, но подмена `scan_ac_content`
        фиктивным manual-критерием обязана попасть в вывод — список в
        печати не может разойтись с тем, что реально просканировал
        guard.

        Ловит мутацию: реализация читает планку и ищет пометки СВОИМ
        регэкспом вместо вызова `guard.scan_ac_content` — подмена ниже
        останется без эффекта, планка (реально чистая) даст «автогейт
        пройдёт сам», и `assertIn` на фиктивный маркер провалится.
        """
        fake_reason = "ФИКТИВНЫЙ-МАРКЕР-Q7F2: инъекция теста AC-5"

        def fake_scan(sources):
            return set(), {77: ("manual", fake_reason)}

        with mock.patch.object(guard, "scan_ac_content", side_effect=fake_scan):
            out, detail = self.entry_report(iteration=1)

        self.assertIn("AC-77", detail,
                     "номер фиктивного критерия обязан попасть в отчёт — "
                     "значит, отчёт реально зовёт guard.scan_ac_content, "
                     "а не свою копию разбора")
        self.assertIn(fake_reason, detail)
        self.assertNotIn("автогейт пройдёт сам", detail,
                         "с фиктивным manual-критерием фраза «нет "
                         "критериев» не имеет права остаться в выводе")

    def test_ac5_automatic_group_names_the_real_source_branch_and_sha(self):
        """Группа «автоматически при approve» называет источник планки
        (ветка + sha) ровно теми значениями, что вернули бы
        `artifact_source.resolve`/`gitcmd.branch_head_sha` для этой
        задачи — те же примитивы, которыми пользуется
        `_autogate_conditions` (SPEC требование 2, AC-5), не отдельно
        зашитая строка.

        Ловит мутацию: код, печатающий имя артефактной ветки без sha
        (или устаревший/чужой sha) — `assertIn` на точный текущий sha
        головы артефактной ветки провалится, хотя имя ветки само по
        себе могло бы случайно совпасть.
        """
        branch, _ = artifact_source.resolve(store.db(), self.TASK)
        expected_sha = gitcmd.branch_head_sha(branch)

        out, detail = self.entry_report(iteration=1)

        self.assertIn(branch, detail)
        self.assertIn(expected_sha, detail,
                     "обязан быть назван РЕАЛЬНЫЙ sha головы артефактной "
                     "ветки, тот же, что видит _autogate_conditions")


if __name__ == "__main__":
    unittest.main()
