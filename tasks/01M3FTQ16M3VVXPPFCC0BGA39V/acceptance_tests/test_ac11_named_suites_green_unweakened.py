"""AC-11 — 01M3FTQ16M3VVXPPFCC0BGA39V: названные наборы тестов зелёные и
не ослаблены.

Источник — SPEC.md, «Критерии приёмки»:

AC-11. Зелёные без правок ожиданий и без ослабления:
`tests/test_notes.py`, `tests/test_codebase_map.py`, `tests/test_brief.py`,
`tests/test_capacity_gate_map.py`, `tests/test_fsm_map_regen.py`,
`tests/test_review_package_map.py`, `tests/test_acceptance_tests_flow.py`,
а также остальные тесты, читающие `config.CLI_VERSION_PIN`.

«Остальные тесты, читающие `config.CLI_VERSION_PIN`» перечисляются
`git grep` по `tests/` в момент прогона, а не списком имён: критерий
говорит о свойстве файлов, и новый файл с чтением константы обязан
попасть в сверку сам.

Зелёный с рождения: оба свойства критерия — сохранение. Названные наборы
зелены и до правок разработчика (проверено прогоном 27.09), диффа по ним
в ветке пока нет вовсе. Тест держит их такими на приёмке: подъём пина и
правка генератора — ровно те изменения, из-за которых ожидание в
существующем тесте проще поправить, чем сохранить.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

NAMED_SUITES = (
    "tests/test_notes.py",
    "tests/test_codebase_map.py",
    "tests/test_brief.py",
    "tests/test_capacity_gate_map.py",
    "tests/test_fsm_map_regen.py",
    "tests/test_review_package_map.py",
    "tests/test_acceptance_tests_flow.py",
)
PIN_CONSTANT = "CLI_VERSION_PIN"
# Удалённая строка диффа, несущая ожидание теста: ассерт, вызов
# `self.fail`, объявление тестового метода.
_EXPECTATION_RE = re.compile(r"assert|self\.fail\(|def\s+test_")


def _pin_reader_suites() -> list:
    """Файлы `tests/`, читающие `config.CLI_VERSION_PIN` — по
    отслеживаемым файлам рабочего дерева."""
    found = _util.git("grep", "-I", "-l", "-F", PIN_CONSTANT, "--", "tests/",
                      check=False)
    return [line for line in found.stdout.splitlines() if line]


class NamedSuitesTest(unittest.TestCase):

    def setUp(self):
        self.suites = sorted(set(NAMED_SUITES) | set(_pin_reader_suites()))
        for rel in NAMED_SUITES:
            self.assertTrue(
                (_util.REPO_ROOT / rel).is_file(),
                f"{rel} назван критерием AC-11, но его нет в дереве — "
                f"удаление файла тестов ослабляет планку")

    def test_ac11_named_suites_are_green(self):
        """Прогон pytest по названным критерием файлам и по всем файлам
        `tests/`, читающим `config.CLI_VERSION_PIN`, — зелёный.

        Ловит мутацию: подъём пина ломает ожидание теста, читающего
        константу (фикстура сверяет detail предупреждения `cli-version`
        с прежней строкой «пин 2.1.236»), либо правка генератора роняет
        юнит `tests/test_codebase_map.py` на изменившейся сигнатуре —
        прогон покраснеет здесь, а не в CI после приёмки.
        """
        result = _util.subprocess_pytest(self.suites)
        self.assertEqual(
            0, result.returncode,
            f"прогон {' '.join(self.suites)} обязан быть зелёным (AC-11):\n"
            f"{result.stdout[-4000:]}\n{result.stderr[-2000:]}")

    def test_ac11_named_suites_keep_their_expectations(self):
        """Диф ветки задачи по тем же файлам не удаляет и не переписывает
        ни одной строки с ожиданием (ассерт, `self.fail`, объявление
        тестового метода) — добавлять новые тесты требование 8 SPEC
        разрешает, править существующие ожидания AC-11 запрещает.

        Ловит мутацию: существующий юнит подогнан под новую сигнатуру
        `extract_imported_dotted_names` (ожидание переписано вместо
        совместимого параметра) или ассерт ослаблен до `assertIn` по
        части значения — в дифе появится удалённая строка с ассертом, и
        тест покраснеет, назвав файл и строку.
        """
        removed = []
        for rel in self.suites:
            for line in _util.diff_since_base(rel).splitlines():
                if not line.startswith("-") or line.startswith("---"):
                    continue
                if _EXPECTATION_RE.search(line):
                    removed.append(f"{rel}: {line}")
        self.assertEqual(
            [], removed,
            "ожидания существующих тестов не правятся этой задачей (AC-11); "
            "удалённые/переписанные строки:\n" + "\n".join(removed))


if __name__ == "__main__":
    unittest.main()
