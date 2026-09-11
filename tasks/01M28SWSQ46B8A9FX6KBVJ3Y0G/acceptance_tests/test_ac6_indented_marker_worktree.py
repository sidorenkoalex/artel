"""Приёмочный тест AC-6 задачи 01M28SWSQ46B8A9FX6KBVJ3Y0G: правка
worktree, ставящая пометку `# AC-n: manual` с ОТСТУПОМ (инцидент 11.09,
`# AC-7: manual` вместо снятого тестового метода), отказывает ТЕМ ЖЕ
путём детекции, что гейт `tests_writing -> in_dev` — маркер `guard.
scan_indented_ac_markers`, задача 01M28NX43E.

Красен до реализации: тест зависит от ДВУХ независимых правок. (1) Эта
задача (01M28SWSQ46B8A9FX6KBVJ3Y0G) сама ещё не научила `_cmd_amend_
tests` звать `guard.acceptance_traceability_errors` вовсе (см. другие
файлы этой планки) — без этого правка проходит без единого отказа. (2)
Даже после этой правки — задача 01M28NX43E (детекция маркера с отступом
в `guard.acceptance_traceability_errors`, зона `scripts/guard.py`, вне
зон ЭТОЙ задачи) на момент написания SPEC не смержена в main (SPEC,
раздел «Контекст»): до её мержа `AC_MARKER` в `guard.py` молча не видит
метку с отступом, критерий читается как «нет теста и нет пометки» БЕЗ
упоминания слова «отступ» в тексте отказа — assertIn("отступ", ...) ниже
падает по причине вне зоны этой задачи, не по дефекту её реализации.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AC_TEST_INDENTED_AC2_MARKER, WorktreeGateSandbox, amend  # noqa: E402


class IndentedMarkerWorktreeTest(WorktreeGateSandbox):

    def test_ac6_indented_manual_marker_refuses_via_the_same_detection_as_the_gate(self):
        """Правка worktree переносит метку `# AC-2: manual` на строку с
        отступом (AC-1 остаётся честно протестирован) — `amend-tests`
        отказывает, и текст отказа называет именно отступ как причину
        (тот же путь детекции `guard.scan_indented_ac_markers`, что
        использует гейт `tests_writing -> in_dev`), `tests_locked_sha`
        не сдвигается.

        Ловит мутацию: `_cmd_amend_tests` вызывает `guard.
        acceptance_traceability_errors`, но эта функция (после мержа
        01M28NX43E) перестаёт агрегировать `scan_indented_ac_markers` —
        метка с отступом снова тихо принимается за валидную, либо отказ
        происходит, но текстом, не называющим отступ (регресс к общему
        «нет теста и нет пометки», неотличимому от AC-5 по смыслу
        ошибки).
        """
        self.edit_tests(AC_TEST_INDENTED_AC2_MARKER)
        old_locked = self.row()["tests_locked_sha"]

        with self.assertRaises(SystemExit) as ctx:
            amend.cmd_amend_tests(self.TASK, "метка AC-2 с отступом")

        message = str(ctx.exception)
        self.assertIn("отступ", message,
                      f"отказ обязан называть отступ как причину: {message}")
        self.assertEqual(
            self.row()["tests_locked_sha"], old_locked,
            "tests_locked_sha не должен сдвигаться при отказе трассируемости")


if __name__ == "__main__":
    unittest.main()
