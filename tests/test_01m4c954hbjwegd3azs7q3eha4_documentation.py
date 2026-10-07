"""Правило об общей для чатов позиции подтверждения.

Группа: долгоживущий
Красен до реализации: в docs/operator-session.md ещё нет правила об общей позиции «разобрано».
"""

import unittest
from pathlib import Path


class DocumentationAcceptanceTest(unittest.TestCase):
    def test_ac16_reviewed_position_is_shared_by_chats(self):
        """Оператор читает правило о единой позиции подтверждений в одном абзаце.

        Ловит мутацию: указание об общей для чатов позиции «разобрано»
        удалено из документа, и ни один абзац больше не содержит правило.
        """
        document = (Path(__file__).resolve().parents[1]
                    / "docs" / "operator-session.md").read_text(encoding="utf-8")
        paragraphs = document.lower().split("\n\n")
        self.assertTrue(
            any("разобран" in paragraph and "общ" in paragraph
                and "чат" in paragraph for paragraph in paragraphs),
            "docs/operator-session.md не объясняет, что позиция «разобрано» "
            "общая для всех чатов",
        )
