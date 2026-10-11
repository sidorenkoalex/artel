"""AC-8 (tasks/T073/SPEC.md): `docs/retention.md` существует и описывает
политику для каждого вида данных из требования 1: `.artel/logs/` (90
дней И N=20 последних задач, со ссылкой на константу конфига), ветки
task/* (удаление при done, merge без squash), alerts (архив старше 90
дней), worktree задачи (уборка при done/killed), report-страница
(перегенерация на месте, без истории отчётов), журнал БД и артефакты
гейтов (вечны).

Не проверяет качество прозы (это решает Оператор при чтении документа)
— только структурное покрытие: по каждому виду данных документ несёт
узнаваемый набор ключевых слов из самого текста критерия. Слабая с виду
проверка (по ключевым словам) — тем не менее не тавтология: документа
сегодня не существует, и произвольный текст (даже подробный) не обязан
случайно упомянуть каждый из шести видов данных, 90/20 и имя константы.

Красен до реализации: `docs/retention.md` не существует —
`FileNotFoundError`.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


def _read_retention_doc() -> str:
    return (REPO_ROOT / "docs" / "retention.md").read_text(encoding="utf-8")


class RetentionDocCoversDataKindsTest(unittest.TestCase):

    def test_ac8_doc_exists(self):
        self.assertTrue((REPO_ROOT / "docs" / "retention.md").is_file(),
                        "docs/retention.md обязан существовать")

    def test_ac8_logs_policy_mentions_90_days_and_n20_constant_reference(self):
        text = _read_retention_doc()
        self.assertIn(".artel/logs", text)
        self.assertIn("90", text)
        self.assertIn("20", text)
        # «Со ссылкой на константу конфига» — не просто число 20 самим
        # текстом, а указание на то, что оно ЖИВЁТ константой (имя
        # константы или явное слово «константа»/«config»).
        self.assertTrue(
            "config." in text or "константа" in text.lower(),
            "политика логов обязана ссылаться на именованную константу "
            "конфига (SPEC AC-8/AC-5), а не только называть число 20")

    def test_ac8_branch_policy_mentions_done_deletion_and_no_squash(self):
        text = _read_retention_doc()
        self.assertIn("task/", text)
        self.assertIn("done", text)
        self.assertIn("squash", text.lower())

    def test_ac8_alerts_policy_mentions_90_day_archive_not_deletion(self):
        text = _read_retention_doc()
        self.assertIn("alert", text.lower())
        self.assertTrue("архив" in text.lower(),
                        "alerts старше 90 дней — архивация, не удаление")

    def test_ac8_worktree_policy_mentions_done_and_killed_cleanup(self):
        text = _read_retention_doc()
        self.assertIn("worktree", text.lower())
        self.assertIn("done", text)
        self.assertIn("killed", text.lower())

    def test_ac8_report_page_policy_mentions_regeneration_without_history(self):
        text = _read_retention_doc()
        self.assertTrue(
            "report" in text.lower() or "отчёт" in text.lower(),
            "политика обязана упомянуть report-страницу (П2')")
        self.assertTrue(
            "перегенер" in text.lower() or "на месте" in text.lower(),
            "report-страница перегенерируется на месте")

    def test_ac8_db_journal_and_gate_artifacts_are_marked_eternal(self):
        text = _read_retention_doc()
        self.assertTrue("журнал" in text.lower())
        self.assertTrue(
            "вечн" in text.lower(),
            "журнал БД и артефакты гейтов обязаны быть отмечены как "
            "вечные (retention их не касается)")


if __name__ == "__main__":
    unittest.main()
