"""AC-9 — соседние абзацы не переписаны: после применения обоих приложений
текст скилов совпадает с базой сравнения во всём, кроме добавленных строк.

Источник — SPEC.md, «Критерии приёмки»:

AC-9. Соседние абзацы не переписаны: после применения обоих приложений
текст `skills/test-authoring.md` и `skills/review-checklist.md` совпадает с
текстом базы сравнения дословно во всём, кроме строк, добавленных по
требованиям 1–7.

Проверяется опкодами `difflib.SequenceMatcher` по строкам: критерий
выполнен, когда КАЖДАЯ строка базы сравнения дословно осталась в тексте
после применения (в том же порядке), а всё расхождение — вставки. Замена
или удаление строки — и есть «переписанный соседний абзац»: правка
существующей формулировки читается как вставка + удаление, поэтому опкод
`replace` тоже отказ.

Красен до реализации: приложений на скилы ещё нет — текст после применения
равен базе сравнения, ни одной добавленной строки нет, и обе проверки
падают на «приложение ничего не добавило».
"""
import difflib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _appendix  # noqa: E402


class NeighbourParagraphsIntactTest(unittest.TestCase):

    def setUp(self):
        self.state = _appendix.state()

    def _opcodes(self, rel: str):
        base = _appendix.base_text(rel).splitlines()
        applied = _appendix.applied_text(rel).splitlines()
        return base, applied, difflib.SequenceMatcher(
            None, base, applied, autojunk=False).get_opcodes()

    def test_ac9_appendices_only_add_lines_to_test_authoring(self):
        """`skills/test-authoring.md` после применения приложений несёт
        добавленные строки и НИ ОДНОЙ изменённой или удалённой: все строки
        базы сравнения остались дословно и в прежнем порядке.

        Ловит мутацию: правка переформулировала существующий абзац раздела
        «Чувствительность» (вписала требование наблюдаемости внутрь уже
        написанной фразы вместо добавления строк) — в опкодах появится
        `replace`/`delete`, и проверка назовёт исчезнувшую строку базы.
        """
        self._assert_only_insertions(_appendix.TEST_AUTHORING)

    def test_ac9_appendices_only_add_lines_to_review_checklist(self):
        """То же для `skills/review-checklist.md`: только вставки, ни одной
        изменённой или удалённой строки базы сравнения.

        Ловит мутацию: правка переписала пункт 3 «Фазы B» целиком (вместо
        дописанной строки — новая редакция пункта) — опкод `replace`
        покажет исчезнувший текст базы, и проверка покраснеет.
        """
        self._assert_only_insertions(_appendix.REVIEW_CHECKLIST)

    def _assert_only_insertions(self, rel: str):
        base, applied, opcodes = self._opcodes(rel)
        self.assertTrue(
            base,
            f"текст `{rel}` базы сравнения не прочитан "
            f"({self.state.diagnosis()})")
        lost = [line for tag, i1, i2, _j1, _j2 in opcodes
                if tag in ("replace", "delete") for line in base[i1:i2]]
        self.assertEqual(
            [], lost,
            f"приложение переписало строки `{rel}`, а не только добавило "
            f"новые — из базы сравнения исчезли: {lost[:5]} "
            f"({self.state.diagnosis()})")
        added = [line for tag, _i1, _i2, j1, j2 in opcodes
                 if tag == "insert" for line in applied[j1:j2]]
        self.assertTrue(
            added,
            f"приложение не добавило в `{rel}` ни одной строки — текст после "
            f"применения совпадает с базой сравнения "
            f"({self.state.diagnosis()})")


if __name__ == "__main__":
    unittest.main()
