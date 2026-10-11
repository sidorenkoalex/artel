"""AC-11 (tasks/T092/SPEC.md): повторный запуск `report` перезаписывает
файл по тому же пути — без сохранения прежних версий отчёта.

Красен до реализации: `orchestrator/report.py` не существует.
"""
import unittest

from _sandbox import ReportSandboxTest  # noqa: E402


class RerunOverwritesSamePathTest(ReportSandboxTest):

    def test_ac11_second_run_reuses_same_path(self):
        self.mk_task("T001", "Задача-фикстура для report", "in_dev")
        _, first_files, _, _ = self.run_report()
        self.assertEqual(len(first_files), 1, first_files)
        first_path = first_files[0]

        _, second_new_files, before2, after2 = self.run_report()

        self.assertEqual(
            second_new_files, [],
            "повторный запуск создал НОВЫЙ файл вместо перезаписи "
            f"прежнего: {second_new_files}")
        self.assertTrue(first_path.exists())
        self.assertEqual(
            after2, before2,
            "после повторного запуска набор *.html-файлов изменился — "
            "похоже, прежняя версия отчёта не была перезаписана/удалена")

    def test_ac11_no_history_of_previous_reports_kept(self):
        self.mk_task("T001", "Задача-фикстура для report", "in_dev")
        self.run_report()
        self.mk_task("T002", "Вторая задача-фикстура", "review")
        self.run_report()

        html_files = self.html_files()
        self.assertEqual(
            len(html_files), 1,
            f"после двух прогонов report на диске больше одного "
            f"HTML-файла — похоже, прежние версии сохраняются: {html_files}")

    def test_ac11_content_actually_regenerated(self):
        """Перезапись — не no-op по неизменному пути: содержимое обязано
        отражать фактическое состояние БД на момент повторного запуска."""
        self.mk_task("T001", "Первая задача-фикстура", "in_dev")
        _, first_files, _, _ = self.run_report()
        first_content = first_files[0].read_text(encoding="utf-8")

        self.mk_task("T999", "Новая задача добавлена перед вторым прогоном",
                    "review")
        _, second_new_files, before2, after2 = self.run_report()

        second_content = first_files[0].read_text(encoding="utf-8")
        self.assertIn(
            "T999", second_content,
            "повторный запуск не отразил новую задачу в перезаписанном "
            "файле")
        self.assertNotEqual(first_content, second_content)


if __name__ == "__main__":
    unittest.main()
