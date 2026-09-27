"""AC-8 — скил ревьювера требует двух проверок: долгоживущие свойства
закрыты тестами `tests/`, а не только планкой, и заявка мутации проверена
на наблюдаемость расхождения.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. После применения приложения `skills/review-checklist.md` требует от
ревьювера двух проверок: долгоживущие свойства задачи закрыты тестами
`tests/`, а не только планкой (со ссылкой на ADR-0018, п. 3), и заявка
мутации проверена на наблюдаемость расхождения.

Проверяется текст скила ревьювера после применения приложений PLAN к базе
сравнения (см. `_appendix`).

Красен до реализации: приложения на `skills/review-checklist.md` ещё нет —
в базе сравнения нет ни ссылки на ADR-0018, ни требования сверять заявку
мутации на наблюдаемость расхождения.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix  # noqa: E402

ADR = "ADR-0018"


class ReviewChecklistChecksTest(unittest.TestCase):

    def setUp(self):
        self.state = _appendix.state()
        self.text = _appendix.applied_text(_appendix.REVIEW_CHECKLIST)

    def test_ac8_requires_long_lived_properties_in_tests_dir(self):
        """Скил ревьювера требует проверять, что долгоживущие свойства
        задачи закрыты тестами `tests/`, а не только планкой, и ссылается на
        ADR-0018.

        Ловит мутацию: правка требует «проверь, что тесты есть», не
        противопоставляя `tests/` планке приёмки (и без ссылки на решение) —
        ревьювер зачтёт долгоживущее свойство, закрытое одной планкой,
        которая уедет вместе с задачей: абзаца, где рядом стоят `tests/`,
        планка и ADR-0018, не появится.
        """
        self.assertTrue(
            self.text,
            f"текст `{_appendix.REVIEW_CHECKLIST}` после применения "
            f"приложений пуст ({self.state.diagnosis()})")
        needles = ("tests/", "планк", "долгоживущ", ADR)
        blocks = [p for p in _appendix.paragraphs(self.text)
                  if not _appendix.missing(p, needles)]
        self.assertTrue(
            blocks,
            f"в `{_appendix.REVIEW_CHECKLIST}` нет требования сверять, что "
            f"долгоживущие свойства закрыты тестами `tests/`, а не только "
            f"планкой (ищется абзац со словами {list(needles)}) "
            f"({self.state.diagnosis()})")

    def test_ac8_requires_mutation_claim_observability_check(self):
        """Скил ревьювера требует проверять заявку мутации на наблюдаемость
        расхождения.

        Ловит мутацию: правка коснулась только тестов `tests/` и не добавила
        второй проверки — заявку мутации ревьювер по-прежнему сверяет лишь
        на правдоподобие, а поведенчески нейтральную заявку (повод волны
        27.09) пропускает: абзаца, где рядом стоят мутация, наблюдаемость и
        расхождение, не появится.
        """
        self.assertTrue(
            self.text,
            f"текст `{_appendix.REVIEW_CHECKLIST}` после применения "
            f"приложений пуст ({self.state.diagnosis()})")
        needles = ("мутаци", "наблюдаем", "расхожден")
        blocks = [p for p in _appendix.paragraphs(self.text)
                  if not _appendix.missing(p, needles)]
        self.assertTrue(
            blocks,
            f"в `{_appendix.REVIEW_CHECKLIST}` нет требования проверять "
            f"заявку мутации на наблюдаемость расхождения (ищется абзац со "
            f"словами {list(needles)}) ({self.state.diagnosis()})")


if __name__ == "__main__":
    unittest.main()
