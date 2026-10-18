"""AC-15: ветка задачи не меняет два существующих теста шагов внешнего
проекта.

Группа: разовый

Зелёный с рождения: до реализации ветка задачи этих файлов не меняет — тест держит, что правка задачи их и не тронет.

Пути задачи — `_pult.changed_paths()`: закоммиченный дифф ветки от её базы
(точка расхождения с `origin/main`, тот же `gitcmd.diff_base`, что гейт
зон) плюс неотслеживаемые файлы.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import changed_paths  # noqa: E402

UNTOUCHED = ("tests/test_multitarget_invariants.py",
             "tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py")


class ExistingTestsUntouchedTest(unittest.TestCase):

    def test_ac15_diff_does_not_touch_existing_external_step_tests(self):
        """Дифф ветки задачи относительно базы не содержит ни
        `tests/test_multitarget_invariants.py`, ни
        `tests/test_01m545eb0a9f191wtdspch36ga_project_role_step.py`.

        Ловит мутацию: разработчик «подгоняет» существующий тест шага
        внешнего проекта под новый бриф (например, правит ожидание о
        `CLAUDE.md` пульта в `test_multitarget_invariants.py:375-397`) —
        путь появляется в диффе ветки."""
        paths = set(changed_paths())
        for rel in UNTOUCHED:
            with self.subTest(path=rel):
                self.assertNotIn(rel, paths, f"ветка задачи меняет {rel}")


if __name__ == "__main__":
    unittest.main()
