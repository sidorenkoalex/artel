"""AC-2 (tasks/T092/SPEC.md): сгенерированный HTML-файл самодостаточен —
не содержит ссылок на внешние скрипты/стили (CDN, JS-фреймворки) и не
требует шага сборки — открывается напрямую из файловой системы.

По образцу утверждённого макета `tasks/T080/mockup.html`: весь CSS —
единственный инлайновый `<style>` в `<head>`, никаких `<script src=...>`
и `<link ... href=...>` на внешний ресурс.

Красен до реализации: `orchestrator/report.py` не существует.
"""
import re
import unittest

from _sandbox import ReportSandboxTest  # noqa: E402

EXTERNAL_RESOURCE = re.compile(
    r'<(script|link)\b[^>]*\b(src|href)\s*=\s*["\']'
    r'(https?:)?//', re.IGNORECASE)


class ReportSelfContainedTest(ReportSandboxTest):

    def setUp(self):
        super().setUp()
        self.mk_task("T001", "Задача-фикстура для report", "in_dev")
        _, new_files, _, _ = self.run_report()
        self.assertEqual(len(new_files), 1, new_files)
        self.path = new_files[0]
        self.html = self.path.read_text(encoding="utf-8")

    def test_ac2_no_external_script_or_stylesheet_references(self):
        match = EXTERNAL_RESOURCE.search(self.html)
        self.assertIsNone(
            match,
            f"файл ссылается на внешний ресурс: {match.group(0) if match else ''}")

    def test_ac2_no_script_tag_with_src_attribute(self):
        """Внешние JS-фреймворки/CDN подключаются именно так — `<script
        src=...>`; инлайновый `<script>` (если он вообще есть) без `src`
        сюда не попадает."""
        self.assertNotRegex(
            self.html, r'<script\b[^>]*\bsrc\s*=',
            "файл подключает внешний скрипт через <script src=...>")

    def test_ac2_no_link_stylesheet_tag(self):
        """CSS обязан быть инлайновым `<style>` в самом файле — без
        `<link rel="stylesheet" href=...>`, как и в утверждённом макете
        tasks/T080/mockup.html."""
        self.assertNotRegex(
            self.html, r'<link\b[^>]*\bhref\s*=',
            "файл ссылается на внешнюю таблицу стилей через <link href=...>")

    def test_ac2_opens_as_plain_html_without_build_step(self):
        """«Не требует шага сборки»: файл — обычный текстовый HTML,
        читаемый как есть, без плейсхолдеров шаблонизатора/сборщика."""
        stripped = self.html.lstrip()
        self.assertTrue(
            stripped[:15].lower().startswith(("<!doctype html", "<html")),
            "файл не начинается с обычной HTML-разметки")

    def test_ac2_no_companion_asset_files_generated(self):
        """Самодостаточность — один файл, не файл-с-довеском (отдельный
        .css/.js рядом), иначе открыть «напрямую из файловой системы»
        было бы нельзя без остальных файлов."""
        before = self.all_files()
        self.mk_task("T002", "Вторая задача-фикстура", "review")
        out, new_files, _, after_html = self.run_report()
        after = self.all_files()
        new_non_html = {p for p in (after - before) if p.suffix != ".html"}
        self.assertEqual(
            new_non_html, set(),
            f"report создал файлы, кроме самого отчёта: {new_non_html}")


if __name__ == "__main__":
    unittest.main()
