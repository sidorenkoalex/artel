"""Приёмочные тесты AC-9: планка `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/
acceptance_tests/` зелёная на main; правка внесена отдельным коммитом с
пометкой в RETRO задачи 01M1NBWPKNBXP9ZXXQDJM7AXPJ (SPEC
01M1TKP45EM16ZMJGQKNZA5T7J, требование 4).

Красен до реализации: на момент написания планки (06.09, коммит
ea0bba68) прогон `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`
даёт 6 из 9 тестов красными (класс дефекта (а)/(б) из «Контекста» SPEC
этой задачи — проверено прогоном на диске), а RETRO задачи
01M1NBWPKNBXP9ZXXQDJM7AXPJ не несёт ни одного упоминания этой задачи.
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "01M1NBWPKNBXP9ZXXQDJM7AXPJ"
THIS_TASK_ID = "01M1TKP45EM16ZMJGQKNZA5T7J"


class TaskPlankGreenOnMainTest(unittest.TestCase):

    def test_ac9_plank_acceptance_tests_all_pass(self):
        """Полный набор приёмочных тестов планки задачи 01M1NBWP...
        проходит целиком (детерминированный прогон `unittest discover`),
        а не частично.

        Ловит мутацию: починка исправляет только часть красных тестов
        (например только класс (а) дефекта, не (б)) — `returncode`
        останется ненулевым, и `assertEqual` ниже поймает недоделанную
        починку.
        """
        res = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s",
            f"tasks/{TASK_ID}/acceptance_tests"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=180)
        self.assertEqual(res.returncode, 0, f"{res.stdout}\n{res.stderr}")

    def test_ac9_retro_carries_note_about_this_fix(self):
        """RETRO задачи 01M1NBWP... несёт пометку о правке, внесённой
        этой задачей (01M1TKP...) — «отдельным коммитом в main с
        пометкой в RETRO», требование 4 SPEC.

        Ловит мутацию: правка внесена без обязательной пометки в RETRO
        (голый коммит без документирования) — `assertIn` ниже не
        найдёт ссылку на текущую задачу в тексте RETRO.
        """
        retro_path = REPO_ROOT / "docs" / "retro" / f"{TASK_ID}.md"
        text = retro_path.read_text(encoding="utf-8")
        self.assertIn(
            THIS_TASK_ID, text,
            f"RETRO {retro_path} обязан упоминать задачу {THIS_TASK_ID} "
            f"как источник правки amend-tests")


if __name__ == "__main__":
    unittest.main()
