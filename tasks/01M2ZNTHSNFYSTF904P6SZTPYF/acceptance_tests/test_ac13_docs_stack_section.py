"""AC-13: `docs/stack.md` несёт раздел «Провайдер исполнителя роли» с
описанием состава интерфейса и того, что остаётся общим у runner.

Красен до реализации: такого раздела в `docs/stack.md` сегодня нет.
"""
import unittest

from orchestrator import config
from _providers import INTERFACE_METHODS

TITLE = "Провайдер исполнителя роли"


def heading_level(line: str) -> int:
    stripped = line.lstrip()
    return len(stripped) - len(stripped.lstrip("#"))


def section_body(text: str, title: str) -> str | None:
    """Тело раздела с заголовком `title` — до следующего заголовка того
    же или более высокого уровня; `None` — раздела нет."""
    lines = text.splitlines()
    start = None
    level = 0
    for index, line in enumerate(lines):
        if heading_level(line) and title in line:
            start, level = index, heading_level(line)
            break
    if start is None:
        return None
    body = []
    for line in lines[start + 1:]:
        current = heading_level(line)
        if current and current <= level:
            break
        body.append(line)
    return "\n".join(body)


class DocsStackSectionTest(unittest.TestCase):
    """Документация манифеста стека — текст репозитория, не артефакт задачи."""

    def setUp(self):
        self.text = (config.ROOT / "docs" / "stack.md").read_text(
            encoding="utf-8")

    def test_ac13_section_describes_the_interface_and_the_common_part(self):
        """Раздел есть, называет все методы интерфейса и говорит про то,
        что остаётся общим у runner.

        Ловит мутацию: раздел добавлен одной фразой «провайдеры есть» —
        состав интерфейса и граница «что у провайдера, что общее у
        runner» в документе не описаны, и следующий провайдер снова
        собирается чтением кода вместо документа.
        """
        body = section_body(self.text, TITLE)

        self.assertIsNotNone(body, f"в docs/stack.md нет раздела «{TITLE}»")
        for method in sorted(INTERFACE_METHODS):
            with self.subTest(method=method):
                self.assertIn(method, body)
        self.assertIn("runner", body.lower())


if __name__ == "__main__":
    unittest.main()
