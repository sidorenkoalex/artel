"""Сторож дерева: литерал признака 1а с префиксом `~/`, `$HOME/`,
`${HOME}/` в отслеживаемых файлах каталогов кода пульта (AC-9).

Группа: разовый
Зелёный с рождения: на ветке-основе `git grep` по образцу признака 1а пуст (сверено на старте шага); тест держит, что правка задачи не внесла такого литерала в код, скилы, шаблоны и тесты.

Критерии AC-1..AC-8 покрыты долгоживущим файлом
`tests/test_01m5knxgembac1qrnhy3kc14jr_pool_leak_signs.py`.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT  # noqa: E402

POOL_DIRNAME = ".artel-" + "canary"
GUARDED_DIRS = ("orchestrator", "scripts", "skills", "templates", "tests")


def sign_1a_pattern() -> str:
    """Образец признака 1а с префиксами `~/`, `$HOME/`, `${HOME}/` —
    расширенное регулярное выражение `git grep -E`."""
    return (r"(~|\$HOME|\$\{HOME\})/" + re.escape(POOL_DIRNAME)
            + r"/[A-Za-z0-9_]")


class TreeGuardTest(unittest.TestCase):

    def test_ac9_no_tracked_file_carries_sign_1a_literal(self):
        """`git grep -E` по образцу признака 1а в отслеживаемых файлах
        каталогов `orchestrator`, `scripts`, `skills`, `templates`, `tests`
        рабочей копии задачи ничего не находит.

        Ловит мутацию: разработчик пишет образец утечки в новом тесте или
        докстринге литералом (`~/.artel-canary/x.md`) вместо сборки из
        `config.CANARY_POOL_DIRNAME` — `git grep` находит строку, тест
        краснеет с её адресом.
        """
        res = subprocess.run(
            ["git", "-C", str(CODE_ROOT), "grep", "-nE", sign_1a_pattern(),
             "--", *GUARDED_DIRS],
            capture_output=True, text=True, timeout=60)
        self.assertNotEqual(res.returncode, 0,
                            f"литерал признака 1а в дереве:\n{res.stdout}")
        self.assertEqual(res.returncode, 1,
                         f"git grep не ответил: {res.stderr}")


if __name__ == "__main__":
    unittest.main()
