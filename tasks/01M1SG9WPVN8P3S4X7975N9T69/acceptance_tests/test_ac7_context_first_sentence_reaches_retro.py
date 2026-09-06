"""Приёмочный тест AC-7 (tasks/01M1SG9WPVN8P3S4X7975N9T69/SPEC.md,
«Критерии приёмки»).

AC-7. Раздел «Контекст» настоящего SPEC называет раскатку в
`.artel/home/.claude/` операторским действием после мержа первым же
предложением — это предложение детерминированно попадает в «Суть»
`docs/retro/<id>.md` при закрытии задачи (`orchestrator/retro.py::
_first_context_sentence`), других действий по этому пункту не требуется.

Критерий — про сам текст SPEC этой задачи (не про код, который пишет
разработчик): SPEC.md разработчику трогать запрещено (скилы роли), а
`_first_context_sentence`/`section_body` — существующий, не меняемый
этой задачей код (SPEC, «Не входит» не называет этот пункт явно, но
требование 6/AC-7 прямо говорит «других действий не требуется»). Тест
здесь — регресс-гвардия на ДВА факта одновременно: (1) первое
предложение раздела «Контекст» уже сейчас называет раскатку операторским
действием после мержа, (2) существующая функция извлечения предложения
корректно достаёт именно его, а не обрывается раньше на одной из
множества точек внутри предложения (пути `.artel/home/.claude/`,
обратные кавычки, `orchestrator/catalog._deploy_role_home_reference`).

Зелёный с рождения: и текст SPEC.md, и `_first_context_sentence`
существуют на момент написания этой планки без правок этой задачи —
оба теста ниже проходят уже сейчас, до шага разработчика; красным этот
файл станет только при регрессии (правка SPEC.md, что запрещено, или
правка `_first_sentence`/`section_body`, ломающая разбор точек).
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TASK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import retro  # noqa: E402

SPEC_PATH = _TASK_DIR / "SPEC.md"


class ContextFirstSentenceNamesTheOperatorRolloutTest(unittest.TestCase):

    def setUp(self):
        self.spec_text = SPEC_PATH.read_text(encoding="utf-8")
        self.sentence = retro._first_context_sentence(self.spec_text)

    def test_ac7_first_context_sentence_names_operator_action_after_merge(self):
        """Первое предложение раздела «Контекст» называет раскатку в
        `.artel/home/.claude/` операторским действием после мержа.

        Ловит мутацию: переформулировка первого предложения «Контекста»
        так, что операторский характер действия ушёл в более позднее
        предложение (например, «Раскатка происходит через `init`.
        Оператор делает это после мержа.») — тогда `_first_sentence`
        вернула бы только первую часть, и `assertIn` ниже покраснеет.
        """
        self.assertIn("операторское действие", self.sentence)
        self.assertIn("после мержа", self.sentence)

    def test_ac7_extraction_does_not_truncate_on_an_inner_period(self):
        """Извлечённое предложение — ПОЛНОЕ первое предложение (не обрыв
        по первой попавшейся точке внутри `.artel/home/.claude/` или
        внутри обратных кавычек `orchestrator/catalog.
        _deploy_role_home_reference`).

        Ловит мутацию: правка `_first_sentence`, которая перестаёт
        отличать точку-разделитель предложений от точки внутри пути/имени
        модуля (регрессия ровно того класса, что чинил SPEC T063,
        требование 2) — извлечённая строка оборвалась бы на первом же
        `.artel` или `.claude`, и `assertIn` ниже не найдёт закрывающую
        скобку конца предложения.
        """
        self.assertIn("сама туда не попадает)", self.sentence,
                      f"предложение обрезано раньше конца: {self.sentence!r}")


if __name__ == "__main__":
    unittest.main()
