"""Приёмочный тест AC-1 (SPEC 01M28NX43ERJGHCJN29HVKMCC3): маркер `# AC-n:
manual|skip|escalate|ci`, поставленный с отступом внутри `acceptance_tests/`,
обязан отказать транзишну `tests_writing -> in_dev` именованной ошибкой, а
не молча пройти как раньше (инцидент 11.09, `# AC-7: manual` с отступом
вместо снятого метода — ADR-0014 ч.2, 01M1THKWFX).

Красен до реализации: `scripts/guard.py` сегодня не несёт детекции
отступа у маркера (`AC_MARKER` заякорена на `^#`, индентированная строка
просто не матчится вовсе) — транзишн вложенной песочницы блокируется
ОБЩЕЙ ошибкой «нет теста и нет пометки», которая не называет ни файл,
ни строку (просто «AC-1: нет теста и нет пометки manual/skip/escalate —
добавь тестовый метод...»); текста «с отступом»/«вынеси в начало строки
либо убери» и имени файла с номером строки, которых требует AC-1 SPEC
этой задачи, в выводе нет и быть не может — код задачи ещё не написан.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm  # noqa: E402
from _sandbox import AcMarkerIndentSandbox  # noqa: E402


SPEC_ONE_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: песочница одного критерия

## Критерии приёмки

AC-1. Единственный критерий вложенной песочницы.
"""

# Маркер `# AC-1: manual` стоит с ЧЕТЫРЬМЯ пробелами отступа внутри тела
# класса, а не в начале строки — ровно сценарий инцидента 11.09 (маркер
# поставлен вместо снятого метода, отступ унаследован от места метода).
INDENTED_MARKER_TEST = '''"""Красен до реализации: фикстура вложенной песочницы — маркер AC-1
поставлен с отступом вместо метода, guard ещё не должен его засчитывать
ни как валидную пометку, ни как повод молчать.
"""
import unittest


class PlaceholderTest(unittest.TestCase):

    def test_placeholder(self):
        pass

    # AC-1: manual — Оператор проверяет глазами на приёмке
'''


class Ac1IndentedMarkerBlocksTransitionTest(AcMarkerIndentSandbox):

    def test_ac1_indented_marker_blocks_transition_with_named_error(self):
        """Маркер `# AC-1: manual` с отступом внутри `acceptance_tests/`
        вложенной задачи блокирует переход `tests_writing -> in_dev`
        именованной ошибкой, называющей файл, строку и требующей убрать
        отступ.

        Ловит мутацию: реализация детектирует отступ, но не включает в
        текст ошибки требуемую формулировку «с отступом» / «вынеси в
        начало строки либо убери» (например, использует другую
        формулировку или молча пропускает индентированный маркер как
        валидный) — тест покраснеет и на составе текста ошибки, и (если
        мутация вовсе снимает отказ) на состоянии задачи.
        """
        self.enter_tests_writing(SPEC_ONE_AC)
        self.write_acceptance_tests(INDENTED_MARKER_TEST,
                                    name="test_placeholder.py")

        out = self.capture_advance()

        self.assertEqual(
            self.state(), "tests_writing",
            "маркер AC-1 стоит с отступом — переход обязан остаться "
            "заблокированным")
        self.assertIn("test_placeholder.py", out)
        # Строка 13 фикстуры — та самая `    # AC-1: manual — ...`.
        self.assertIn("test_placeholder.py:13", out)
        self.assertIn("с отступом", out)
        self.assertIn("вынеси в начало строки либо убери", out)
        self.assertIn("AC-1", out)

    def capture_advance(self) -> str:
        return self.capture(fsm.cmd_advance, self.TASK)
