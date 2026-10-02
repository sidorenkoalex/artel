"""AC-3 — удалённый на диске `test_*.py`, единственный покрывавший
критерий, даёт отказ `amend-tests` по трассируемости; лок не сдвинут.

Группа: разовый
Зелёный с рождения: трассируемость уже читает итоговую планку с диска worktree, где удалённого файла нет, — тест держит это поведение от регресса при переносе удалений (мутация «удалённые файлы исключены из проверок»).

Разовый: планка исполняется до мержа; после мержа это свойство держит
`tests/test_amend_remove.py` (SPEC, требование 6 и AC-5).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import ONLY_AC1, ONLY_AC2, PlainLockedSandbox  # noqa: E402


class RemovedSoleTestTraceabilityTest(PlainLockedSandbox):

    PLANK = {"test_ac1_only.py": ONLY_AC1, "test_ac2_only.py": ONLY_AC2}

    def test_ac3_removed_sole_test_refused_by_traceability(self):
        """Лок несёт два файла планки, AC-2 песочницы покрыт только
        `test_ac2_only.py`; Оператор удаляет его на диске worktree и
        вызывает `amend-tests`.

        Отказ по трассируемости, называющий AC-2; `tests_locked_sha`
        прежний, записи «правка планки» нет.

        Ловит мутацию: удалённые файлы исключены из проверок —
        трассируемость считается по планке артефактной ветки (с удалённым
        файлом) или удаление идёт мимо проверок, и лок сдвигается на
        планку без покрытия AC-2.
        """
        before = self.locked()
        self.delete_on_disk("test_ac2_only.py")

        out = self.run_amend()

        self.assertIn("SystemExit", out, f"удаление прошло мимо проверок: {out}")
        self.assertIn("трассируемость", out)
        self.assertIn("AC-2", out)
        self.assertEqual(self.locked(), before)
        self.assertEqual(self.amend_details(), [])


if __name__ == "__main__":
    unittest.main()
