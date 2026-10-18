"""AC-9: `_tile_html` на строке без ключа `target` — терпимо, без элемента
проекта; строка внешнего проекта — с элементом проекта.

Группа: разовый
Красен до реализации: `_tile_html` пока не выводит элемент проекта у строки внешнего проекта; проверка строки без ключа `target` зелена и до правки — она держит сегодняшнюю терпимость.

Почему разовый: SPEC называет закрытую функцию `report._tile_html` и
строку без ключа `target` (как фикстуры `tests/test_report.py`);
публичный `cmd_report` читает строки из БД, где ключ есть всегда, а
долгоживущему файлу `tests/` закрытые имена недоступны. Публичная часть
AC-9 (плитки артели, NULL и внешнего проекта в `report.html`) — в
`tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`.
"""
import unittest
from html.parser import HTMLParser

from orchestrator import config, report


class _Elements(HTMLParser):
    """Собственный текст каждого элемента разметки (без потомков)."""

    def __init__(self):
        super().__init__()
        self.stack, self.texts = [], []

    def handle_starttag(self, tag, attrs):
        self.stack.append("")

    def handle_data(self, data):
        if self.stack:
            self.stack[-1] += data

    def handle_endtag(self, tag):
        if self.stack:
            self.texts.append(self.stack.pop().strip())


def _texts(html: str) -> list:
    parser = _Elements()
    parser.feed(html)
    return parser.texts


def _row(**extra):
    row = dict(id="T001", title="Плитка задачи", state="in_dev",
               escalated_from=None, budget_usd=10.0, spent_usd=1.0,
               review_iters=0)
    row.update(extra)
    return row


class TileWithoutTargetTest(unittest.TestCase):

    def test_ac9_row_without_target_key_has_no_project_element(self):
        """Строка плитки без ключа `target` рендерится без ошибки и без
        элемента проекта.

        Ловит мутацию: `_tile_html` читает `row["target"]` без терпимости
        — KeyError на строке без ключа; либо подставляет проект по
        умолчанию — элемент с текстом `artel` или `None`.
        """
        texts = _texts(report._tile_html(_row()))
        self.assertIn("T001", texts)
        for value in (config.DEFAULT_TARGET, "None"):
            self.assertNotIn(value, texts, texts)

    def test_ac9_external_row_dict_has_project_element(self):
        """Строка-словарь внешнего проекта даёт плитку с отдельным
        элементом, собственный текст которого — имя проекта.

        Ловит мутацию: терпимое чтение проекта сделано через
        `getattr(row, "target", None)` — на словаре всегда None, и плитка
        внешнего проекта из словаря теряет элемент проекта.
        """
        texts = _texts(report._tile_html(_row(target="kedr")))
        self.assertIn("kedr", texts, texts)


if __name__ == "__main__":
    unittest.main()
