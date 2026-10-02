"""Абзац «Допуск набора» в `docs/stack.md` говорит о ролях вне набора.

Группа: разовый

Красен до реализации: абзац «**Допуск набора**» сегодня требует лишь совпадения сводки с набором «по всем его ролям» и о ролях сводки вне набора не говорит ни слова.

Файл читается из дерева кода, которое проверяется (каталог над пакетом
`orchestrator`, — `cwd` прогона планки), не из артефактов задачи.
Планка провалидирована временной правкой абзаца (тест зелёный, правка
снята).

Критерии AC-1…AC-5 покрыты долгоживущим файлом
`tests/test_01m3z5s8tqxpnh133xq8k1978x_set_admission.py`.
"""
import re
import unittest
from pathlib import Path

from orchestrator import models

STACK_DOC = Path(models.__file__).resolve().parents[1] / "docs" / "stack.md"
HEAD = "**Допуск набора**"

#: Упоминание ролей, не входящих в набор, — в любой из естественных форм.
OUTSIDE_RE = re.compile(
    r"вне\s+набора|не\s+вход\w*\s+в\s+(?:\w+\s+)?набор|не\s+из\s+набора",
    re.IGNORECASE)
COMBAT_RE = re.compile(r"боев\w*", re.IGNORECASE)

#: Окно вокруг упоминания ролей вне набора, в котором ищется «боевая».
WINDOW = 200


def admission_paragraph(text: str) -> str:
    """Абзац, начинающийся с `HEAD`, до первой пустой строки."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(HEAD):
            block = []
            for item in lines[i:]:
                if not item.strip():
                    break
                block.append(item)
            return " ".join(block)
    return ""


class StackDocTest(unittest.TestCase):

    def test_ac6_admission_paragraph_requires_combat_models_outside_set(self):
        """Абзац допуска набора требует боевых моделей у ролей вне набора.

        Сценарий: из `docs/stack.md` берётся абзац, начинающийся с
        «**Допуск набора**»; в нём должно быть упоминание ролей сводки
        прогона, не входящих в набор, и рядом с ним (в пределах окна) —
        слово «боевая»/«боевых».

        Ловит мутацию: код задачи поправлен, а абзац `docs/stack.md` нет —
        или фраза о ролях вне набора дописана в другой раздел, — упоминания
        ролей вне набора в абзаце «Допуск набора» нет."""
        text = STACK_DOC.read_text(encoding="utf-8")
        paragraph = admission_paragraph(text)
        self.assertTrue(paragraph, f"абзаца {HEAD} в {STACK_DOC} нет")
        hits = list(OUTSIDE_RE.finditer(paragraph))
        self.assertTrue(hits, f"абзац не говорит о ролях вне набора:\n"
                              f"{paragraph}")
        near = [m for m in hits if COMBAT_RE.search(
            paragraph[max(0, m.start() - WINDOW):m.end() + WINDOW])]
        self.assertTrue(near, f"рядом с ролями вне набора нет боевых "
                              f"моделей:\n{paragraph}")


if __name__ == "__main__":
    unittest.main()
