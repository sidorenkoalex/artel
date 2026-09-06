"""Приёмочный тест AC-11 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3:
`docs/operator-session.md` описывает правило «копилка сразу» как
исполняемое командой `note`; упоминания сценария со scratch-worktree в
тексте документа сняты.

Читает РЕАЛЬНЫЙ файл `docs/operator-session.md` репозитория (`config.
ROOT` не подменяется — это не git-песочница, а прямая проверка
содержимого документа на кодовой ветке задачи), поэтому не наследует
`tests.sandbox.TmpRootTest`.

Красен до реализации: сегодня (проверено на момент написания планки)
абзац «Копилка и бэклог пополняются В МОМЕНТ обнаружения аномалии...»
не упоминает команду `note` — правило описано как ручное действие
(«строка... пишется сразу, тем же ходом... и уходит изолированным
коммитом с push»).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config  # noqa: E402

RULE_MARKER = "Копилка и бэклог пополняются"


class OperatorSessionDocRuleTest(unittest.TestCase):

    def test_ac11_rule_paragraph_names_note_and_drops_scratch_worktree(self):
        """Абзац правила «копилка сразу» в `docs/operator-session.md`
        называет команду `note` исполняющей его и не содержит упоминаний
        сценария scratch-worktree.

        Ловит мутацию: абзац правила правится по любому другому поводу,
        но ссылку на команду `note` не добавляют (документ остаётся
        описывать ручной ход действий) — падает на `assertIn("note", ...)`.
        """
        text = (config.ROOT / "docs" / "operator-session.md").read_text(
            encoding="utf-8")

        idx = text.find(RULE_MARKER)
        self.assertNotEqual(idx, -1,
                            "абзац правила «копилка сразу» не найден в документе")
        paragraph = text[idx:idx + 800]

        self.assertIn("note", paragraph.lower(),
                     "абзац не называет команду note исполняющей правило")
        self.assertNotIn("scratch-worktree", text.lower(),
                         "документ всё ещё упоминает сценарий scratch-worktree")


if __name__ == "__main__":
    unittest.main()
