"""AC-7: раздел «Провайдер codex» в `docs/stack.md` несёт абзац о разборе
вывода и источнике стоимости.

Красен до реализации: раздел «Провайдер codex» ни одного вида событий `codex exec --json` сегодня не называет и о `cost_from_cli` не говорит — часть 1 линии писала его про команду, дом и изоляцию.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stream import REPO_ROOT  # noqa: E402

SECTION_TITLE = "Провайдер codex"

#: Пять видов событий образца 0.155.1 (SPEC требование 1): перечень,
#: который абзац обязан называть поимённо.
EVENT_KINDS = ("thread.started", "turn.started", "item.started",
               "item.completed", "turn.completed")

#: Формулировки «итог запуска цены не несёт» — любая из них считается:
#: критерий требует факта, а не конкретных слов. Сверяются с текстом,
#: сведённым к нижнему регистру, поэтому и записаны в нём.
NO_PRICE_WORDINGS = ("usd is none", "цены нет", "цены от cli нет",
                     "не несёт цены", "цены не несёт", "цены в итоге нет")


class StackDocSectionTest(unittest.TestCase):
    """Текст раздела о провайдере `codex` (требование 4)."""

    def section(self) -> str:
        """Текст раздела «Провайдер codex» ОДНОЙ строкой в нижнем
        регистре: перенос строки markdown внутри фразы («итог запуска
        цены не\\nнесёт») иначе ломал бы поиск фразы, которая в тексте
        есть — проверялась бы вёрстка абзаца, а не его содержание.

        Границы раздела — от его заголовка до следующего заголовка того
        же или более высокого уровня.
        """
        text = (REPO_ROOT / "docs" / "stack.md").read_text(encoding="utf-8")
        lines = text.splitlines()
        starts = [i for i, line in enumerate(lines)
                  if line.startswith("#") and SECTION_TITLE in line]
        self.assertTrue(starts,
                        f"в docs/stack.md нет раздела «{SECTION_TITLE}»")
        start = starts[0]
        level = len(lines[start]) - len(lines[start].lstrip("#"))
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if line.startswith("#") and \
                    len(line) - len(line.lstrip("#")) <= level:
                return " ".join(" ".join(lines[start:index]).lower().split())
        return " ".join(" ".join(lines[start:]).lower().split())

    def test_ac7_the_section_covers_the_parsing_and_the_cost_source(self):
        """Раздел называет виды событий поимённо, связку вызова с
        результатом по идентификатору элемента, отсутствие цены в итоге
        запуска и расчёт расхода шага по тарифу модели при
        `cost_from_cli: false`.

        Ловит мутацию: абзац написан только про разбор («какие события во
        что переводятся»), а про деньги умолчал — Оператор, увидев в
        журнале шага Codex `источник=расчёт по тарифу` вместо факта CLI,
        читает это как сбой извлечения стоимости и идёт искать
        потерянное поле потока, которого у этого CLI нет вовсе.
        """
        section = self.section()

        missing = [kind for kind in EVENT_KINDS if kind not in section]
        self.assertEqual(missing, [], "виды событий не перечислены поимённо")

        self.assertTrue("item.id" in section or "идентификатор" in section,
                        "связка вызова с результатом по идентификатору "
                        "не названа")

        self.assertTrue(any(wording in section for wording in NO_PRICE_WORDINGS),
                        "об отсутствии цены в итоге запуска не сказано")

        self.assertIn("cost_from_cli", section,
                      "признак каталога не назван по имени")
        self.assertIn("тариф", section, "расчёт по тарифу модели не назван")


if __name__ == "__main__":
    unittest.main()
