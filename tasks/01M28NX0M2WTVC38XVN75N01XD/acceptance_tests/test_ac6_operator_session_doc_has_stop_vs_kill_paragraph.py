"""Приёмочный тест 01M28NX0M2WTVC38XVN75N01XD — AC-6 (SPEC.md).

Красен до реализации: `docs/operator-session.md` сегодня не несёт фразы
«stop против kill» вовсе (grep по файлу на момент написания теста —
пусто) — абзац с назначением каждой команды, последствиями и флагом
`--yes` разработчик добавляет только сейчас.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

_DOC = REPO_ROOT / "docs" / "operator-session.md"


class Ac6OperatorSessionDocHasStopVsKillParagraphTest(unittest.TestCase):
    """AC-6: `docs/operator-session.md` несёт абзац «stop против kill»
    — назначение каждой команды, последствия и флаг `--yes`."""

    def test_ac6_doc_names_stop_vs_kill_and_the_yes_flag(self):
        """Файл документации содержит буквальную фразу «stop против
        kill» (метка абзаца из формулировки критерия) и рядом с ней
        флаг `--yes`, называющий условие полной ликвидации.

        Ловит мутацию: абзац добавлен под другим заголовком (например,
        просто дополняет существующий раздел «Запуски и рабочие копии»
        без фразы «stop против kill») либо не называет флаг `--yes` —
        тест красен на отсутствии одной из двух подстрок.
        """
        text = _DOC.read_text(encoding="utf-8")

        self.assertIn("stop против kill", text,
                     f"{_DOC} не несёт абзац «stop против kill»")
        paragraph_start = text.index("stop против kill")
        # Флаг ищем в окне после метки абзаца, не по всему файлу — иначе
        # любое случайное упоминание `--yes` в другом, не связанном
        # месте документа ложно зачло бы критерий выполненным.
        window = text[paragraph_start:paragraph_start + 2000]
        self.assertIn("--yes", window,
                     "абзац «stop против kill» не называет флаг --yes")


if __name__ == "__main__":
    unittest.main()
