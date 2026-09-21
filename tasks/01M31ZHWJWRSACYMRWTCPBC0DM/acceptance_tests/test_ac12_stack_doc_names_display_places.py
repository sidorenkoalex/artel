"""AC-12 — 01M31ZHWJWRSACYMRWTCPBC0DM: абзац «Вывод и стоимость у
провайдера» в `docs/stack.md` называет места, где показаны токены.

Источник — SPEC.md, «Критерии приёмки»:

AC-12. Абзац «Вывод и стоимость у провайдера» в `docs/stack.md` назван
местами, где показаны токены (`status`, RETRO, `report`).

Красен до реализации: абзац, написанный частью 1 нарезки
(`docs/stack.md`, раздел «Вывод и стоимость у провайдера»), говорит о
разборе события провайдера и о ветках учёта денег и не называет ни
`status`, ни RETRO, ни `report` — слов `status`/`RETRO`/`report` в его
теле сегодня нет вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _tokens  # noqa: E402

TITLE = "Вывод и стоимость у провайдера"

#: Места показа, названные критерием дословно.
PLACES = ("status", "RETRO", "report")


def heading_level(line: str) -> int:
    stripped = line.lstrip()
    return len(stripped) - len(stripped.lstrip("#"))


def section_body(text: str, title: str):
    """Тело раздела с заголовком `title` — до следующего заголовка того же
    или более высокого уровня; `None` — раздела нет."""
    lines = text.splitlines()
    start, level = None, 0
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


class StackDocNamesDisplayPlacesTest(unittest.TestCase):

    def setUp(self):
        self.text = (_tokens.REPO_ROOT / "docs" / "stack.md").read_text(
            encoding="utf-8")

    def test_ac12_paragraph_names_status_retro_and_report_as_token_places(self):
        """Абзац «Вывод и стоимость у провайдера» существует и называет
        все три места показа токенов — `status`, RETRO и `report` — при
        этом говоря именно о токенах, а не только о деньгах.

        Ловит мутацию: абзац дополнен общей фразой «токены теперь видно в
        выводе пульта» без перечисления мест — читатель, которому нужно
        понять, где искать разбивку по видам, снова пойдёт читать код
        трёх модулей; `missing` назовёт непроизнесённые места поимённо.
        """
        body = section_body(self.text, TITLE)
        self.assertIsNotNone(
            body, f"в docs/stack.md нет раздела «{TITLE}»")

        self.assertIn("токен", body.lower(),
                      f"абзац «{TITLE}» не говорит о токенах вовсе")
        missing = [place for place in PLACES if place not in body]
        self.assertEqual(
            [], missing,
            f"абзац «{TITLE}» не называет места показа токенов: {missing}")


if __name__ == "__main__":
    unittest.main()
