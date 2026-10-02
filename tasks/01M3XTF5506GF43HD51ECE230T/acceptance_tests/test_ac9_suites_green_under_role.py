"""AC-9 — тесты, зовущие `artel.main()` с командами списка отказа, и
долгоживущий файл задачи зелёные из-под окружения роли.

Прогон — отдельным процессом pytest в корне чекаута планки, с
`ARTEL_ROLE=developer` и `HOME`, равным `config.ROLE_HOME` того же дерева
(именно его сравнивает признак в дочернем процессе), по одному файлу на
метод, чтобы уложиться в потолок pytest-timeout пульта. Пути относительные
(`tests/…`) — сторож `conftest.py` под ролью принимает только целевые пути.

«Проверки не ослаблены» держится числом тестовых методов каждого файла:
оно не меньше, чем в базе диффа задачи.

Группа: разовый
Красен до реализации: долгоживущий файл задачи в tests/ красен, пока нет единого признака и закрытого отказа; три файла под ролью пока зелёны — отказа ещё нет, и покраснеют, если отказ введут без снятия признака роли из окружения их вызова.
"""
import os
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plank  # noqa: E402
from orchestrator import config  # noqa: E402

CALLER_FILES = ("tests/test_analyst_role.py",
                "tests/test_approve_acceptance_full_suite.py",
                "tests/test_kill_live_cycle_refusal.py")

_TEST_DEF = re.compile(r"^\s*def (test_\w+)\s*\(", re.M)


def role_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in (config.ARTEL_ROLE_ENV, "HOME", "CLAUDE_CONFIG_DIR")}
    env[config.ARTEL_ROLE_ENV] = "developer"
    env["HOME"] = str(config.ROLE_HOME)
    return env


class SuitesUnderRoleTest(unittest.TestCase):
    def assert_green_under_role(self, rel: str):
        res = _plank.run_pytest([rel], env=role_env())
        self.assertEqual(0, res.returncode,
                         f"{rel} красный под ARTEL_ROLE=developer, "
                         f"HOME={config.ROLE_HOME}:\n{_plank.tail(res)}")
        self.assertRegex(res.stdout, r"\d+ passed", _plank.tail(res))

    def test_ac9_analyst_role_green_under_role(self):
        """`tests/test_analyst_role.py` проходит из-под окружения роли.

        Ловит мутацию: отказ диспетчера введён, а файл зовёт `artel.main()`
        с унаследованными `ARTEL_ROLE`/`HOME` роли — его тесты получают
        отказ роли, код возврата прогона ненулевой.
        """
        self.assert_green_under_role(CALLER_FILES[0])

    def test_ac9_approve_full_suite_green_under_role(self):
        """`tests/test_approve_acceptance_full_suite.py` проходит из-под окружения роли.

        Ловит мутацию: файл убирает из окружения вызова только `ARTEL_ROLE`,
        оставляя HOME роли, — признак по HOME отказывает `approve`, прогон
        красный.
        """
        self.assert_green_under_role(CALLER_FILES[1])

    def test_ac9_kill_refusal_green_under_role(self):
        """`tests/test_kill_live_cycle_refusal.py` проходит из-под окружения роли.

        Ловит мутацию: диспетчерные тесты `kill` зовут `artel.main()` без
        снятия признака роли — `cleanup.cmd_kill` не вызван, прогон красный.
        """
        self.assert_green_under_role(CALLER_FILES[2])

    def test_ac9_task_long_lived_file_green_under_role(self):
        """Долгоживущий файл задачи в `tests/` проходит из-под окружения роли.

        Ловит мутацию: тест файла задачи опирается на окружение процесса
        вместо собственного (например, сценарий «Оператор» без снятия
        унаследованного маркера) — под ролью он краснеет.
        """
        files = sorted(p.relative_to(_plank.REPO_ROOT).as_posix()
                       for p in (_plank.REPO_ROOT / "tests").glob(_plank.TASK_TESTS_GLOB))
        self.assertTrue(files, f"в tests/ нет файлов {_plank.TASK_TESTS_GLOB}")
        res = _plank.run_pytest(files, env=role_env())
        self.assertEqual(0, res.returncode, f"{files}:\n{_plank.tail(res)}")

    def test_ac9_caller_checks_not_weakened(self):
        """Число тестовых методов каждого из трёх файлов не меньше, чем в базе задачи.

        Ловит мутацию: тест, который краснел под ролью, удалили или
        переименовали в не-тест вместо снятия признака роли из окружения —
        число `def test_…` в файле меньше, чем в базе.
        """
        base = _plank.diff_base()
        self.assertIsNotNone(base, "git не ответил на базу диффа задачи")
        for rel in CALLER_FILES:
            with self.subTest(file=rel):
                before = _plank.show_at(base, rel)
                self.assertIsNotNone(before, f"{rel} нет в базе {base}")
                now = (_plank.REPO_ROOT / rel).read_text(encoding="utf-8")
                lost = set(_TEST_DEF.findall(before)) - set(_TEST_DEF.findall(now))
                self.assertGreaterEqual(len(_TEST_DEF.findall(now)),
                                        len(_TEST_DEF.findall(before)),
                                        f"{rel}: пропали методы {sorted(lost)}")


if __name__ == "__main__":
    unittest.main()
