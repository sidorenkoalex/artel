"""AC-2 (tasks/01M1GJ3ZP1YGG5QRB6FQ44NN8D/SPEC.md): «Команда печатает все
AC-маркеры (manual/skip/escalate) с их причинами.»

Маркерные строки фикстуры ниже собраны конкатенацией, не одним куском
текста вида «решётка, AC, дефис, номер, двоеточие, manual» (та же
осторожность, что `tasks/T081/acceptance_tests/
test_ac1_non_test_files_excluded.py`, коммит 7cb7e25):
`guard.scan_acceptance_tests` читает сырой текст `.py`-файлов регуляркой
— сплошной литерал в исходнике ЭТОГО файла читался бы как настоящая
пометка задачи 01M1GJ3ZP1YGG5QRB6FQ44NN8D (класс дефекта ANSWER-1,
31.08). Конкатенация ломает регулярку в исходнике, а после вычисления
f-строки в СОДЕРЖИМОЕ фикстурного файла (которое реально уходит в
git-коммит ветки-фикстуры T900) попадает целая, корректная строка
пометки.

Красен до реализации: `_sandbox.discover_dry_run_command_name()` падает
`AssertionError` — новой команды в таблице диспетчера ещё нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import DryRunSandbox  # noqa: E402

REASON_MANUAL = "REASON-MANUAL-AC2-9f3d1"
REASON_SKIP = "REASON-SKIP-AC5-7ac20"

MARKER_LINE_AC2 = "# AC-" + "2: manual — " + REASON_MANUAL
MARKER_LINE_AC5 = "# AC-" + "5: skip — " + REASON_SKIP

TEST_FILE = f'''"""Фикстура маркеров.

Зелёный с рождения: файл-фикстура другой задачи, не код 01M1GJ3ZP1YGG5QRB6FQ44NN8D.
"""
import unittest

{MARKER_LINE_AC2}
{MARKER_LINE_AC5}


class MarkerFixtureTest(unittest.TestCase):

    def test_something_covered_by_real_test(self):
        """Фикстура — AC-1 покрыт тестом, не маркером."""
        pass
'''

AC_SECTION = (
    "AC-1. Критерий, покрытый тестом.\n"
    "AC-2. Критерий, помеченный manual.\n"
    "AC-5. Критерий, помеченный skip.\n"
)


class PrintsMarkersWithReasonsTest(DryRunSandbox):

    def test_ac2_output_contains_each_marker_kind_and_its_own_reason(self):
        """Ветка несёт один manual- и один skip-маркер с разными,
        уникальными причинами; вывод обязан назвать оба вместе с их
        собственными причинами, не перепутав, какая причина к какому
        AC и какому виду пометки относится.

        Ловит мутацию: реализация печатает номера/виды AC-маркеров без
        текста причины (например, только "AC-2: manual" без хвоста) —
        тест ищет литеральный текст причины (REASON-MANUAL-AC2-9f3d1 и
        REASON-SKIP-AC5-7ac20) в выводе и не находит его при пропущенной
        причине. Отдельно ловит перепутанное сопоставление AC<->вид:
        блок вокруг "AC-2" обязан нести "manual" и НЕ нести "skip"
        (и наоборот для AC-5) — если код печатает пометки, но с
        перепутанными видами, один из блоков нарушит это условие.
        """
        self.commit_fixture(AC_SECTION, {"test_markers.py": TEST_FILE})
        self.seed_task()

        out = self.run_dry_run()

        self.assertIn(REASON_MANUAL, out,
                     "причина manual-маркера AC-2 отсутствует в выводе")
        self.assertIn(REASON_SKIP, out,
                     "причина skip-маркера AC-5 отсутствует в выводе")

        block_ac2 = self._block_after(out, "AC-2")
        self.assertIn("manual", block_ac2,
                     "блок AC-2 не называет вид пометки manual")
        self.assertIn(REASON_MANUAL, block_ac2,
                     "блок AC-2 не несёт свою причину рядом с собой")
        self.assertNotIn(REASON_SKIP, block_ac2,
                         "блок AC-2 несёт чужую причину (AC-5) — "
                         "пометки перепутаны")

        block_ac5 = self._block_after(out, "AC-5")
        self.assertIn("skip", block_ac5,
                     "блок AC-5 не называет вид пометки skip")
        self.assertIn(REASON_SKIP, block_ac5,
                     "блок AC-5 не несёт свою причину рядом с собой")
        self.assertNotIn(REASON_MANUAL, block_ac5,
                         "блок AC-5 несёт чужую причину (AC-2) — "
                         "пометки перепутаны")

    @staticmethod
    def _block_after(text: str, label: str) -> str:
        """Текст от вхождения `label` до следующего вхождения "AC-" —
        допущение, что каждая пометка описывается в выводе как связный
        кусок (строка/абзац), не разбросана по всему выводу вперемешку
        с другими пометками (естественное свойство любой построчной
        распечатки списка пометок)."""
        idx = text.find(label)
        assert idx != -1, f"{label} не найден в выводе вовсе"
        rest = text[idx + len(label):]
        next_idx = rest.find("AC-")
        return rest if next_idx == -1 else rest[:next_idx]


if __name__ == "__main__":
    unittest.main()
