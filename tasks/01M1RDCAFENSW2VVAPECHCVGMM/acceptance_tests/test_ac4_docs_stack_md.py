"""AC-4 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md): `docs/stack.md`
человекочитаемо описывает стек и ссылается на `orchestrator/stack.py`
как на единственный источник значений.

Красен до реализации: `docs/stack.md` ещё не существует — `read_text`
падает `FileNotFoundError`.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STACK_MD = REPO_ROOT / "docs" / "stack.md"


class DocsStackMdTest(unittest.TestCase):

    def test_ac4_docs_names_the_module_as_the_source_and_explains_stdlib_only(self):
        """`docs/stack.md` называет `orchestrator/stack.py` источником
        значений и объясняет причину «только стандартная библиотека» —
        буквально требуемые требованием 2 три пункта («что входит,
        почему только стандартная библиотека, как проверить») и явная
        ссылка на модуль как единственный источник.

        Не проверяет отсутствие продублированных чисел версий (глубокий
        текстовый анализ прозы вне механической проверки) — эта грань
        AC-4 остаётся за ревью PLAN/диффа документа Оператором.

        Ловит мутацию: `docs/stack.md` заведён пустым или не упоминает
        `orchestrator/stack.py` (документ не ссылается на источник
        значений) — `assertIn` откажет на первой проверке; аналогично
        для отсутствия объяснения «только стандартная библиотека».
        """
        text = STACK_MD.read_text(encoding="utf-8")

        self.assertIn(
            "orchestrator/stack.py", text,
            "docs/stack.md не ссылается на orchestrator/stack.py как на "
            "источник значений (требование 2)")
        self.assertIn(
            "стандартн", text.lower(),
            "docs/stack.md не объясняет правило «только стандартная "
            "библиотека» (требование 2)")


if __name__ == "__main__":
    unittest.main()
