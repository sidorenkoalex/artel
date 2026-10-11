"""AC-1 (tasks/T080/SPEC.md): в артефактах задачи присутствует один
самодостаточный HTML-файл или набор HTML-файлов-скетчей, каждый
открывается локально (`file://`) без сервера, демона или сборки.

Красен до реализации: разработчик ещё не положил ни одного HTML-файла в
tasks/T080/ (SPEC — единственный существующий артефакт задачи на момент
написания этих тестов) — `_html_utils.html_files()` возвращает пустой
список, и первый же тест падает с понятным сообщением. Как только
появится хотя бы один самодостаточный *.html/*.htm файл, тест позеленеет.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import unittest  # noqa: E402

import _html_utils as h  # noqa: E402


class HtmlFilesOpenStandaloneTest(unittest.TestCase):

    def test_ac1_at_least_one_html_file_present(self):
        files = h.html_files()
        self.assertTrue(
            files,
            "в tasks/T080/ нет ни одного *.html/*.htm файла макета "
            "(AC-1) — искали рекурсивно, исключая acceptance_tests/")

    def test_ac1_every_html_file_is_self_contained_document(self):
        files = h.html_files()
        if not files:
            self.skipTest("нет HTML-файлов — см. test_ac1_at_least_one_html_file_present")
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertTrue(
                text.strip(),
                f"{path.relative_to(h.TASK_DIR)} пуст — не может "
                f"открыться как самостоятельный документ (AC-1)")
            root = h.parse(text)
            visible = h.full_text(root)
            self.assertTrue(
                len(visible.strip()) > 20,
                f"{path.relative_to(h.TASK_DIR)}: после разбора HTML "
                f"почти нет видимого текста — не похоже на "
                f"самодостаточный макет, который можно открыть и "
                f"увидеть (AC-1)")

    def test_ac1_no_files_require_a_build_step_to_produce_html(self):
        # «Открывается локально без ... шагов сборки» (AC-1) — сами файлы
        # макета обязаны БЫТЬ HTML, а не источником, который сборка
        # превращает в HTML (.jsx/.vue/.pug/.ejs и т.п.).
        build_source_exts = {".jsx", ".tsx", ".vue", ".pug", ".ejs",
                             ".hbs", ".mustache", ".njk"}
        found = [p for p in h.TASK_DIR.rglob("*")
                 if p.is_file() and p.suffix.lower() in build_source_exts
                 and h.ACCEPTANCE_DIR not in p.parents]
        self.assertFalse(
            found,
            "найдены файлы-источники, требующие шага сборки в HTML "
            "(AC-1): " + ", ".join(str(p.relative_to(h.TASK_DIR)) for p in found))


if __name__ == "__main__":
    unittest.main()
