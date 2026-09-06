"""Приёмочный тест AC-1 (tasks/01M1SG9WPVN8P3S4X7975N9T69/SPEC.md,
«Критерии приёмки»).

AC-1. `docs/reference/role-home/claude/hooks/bash_guard.py` существует, и
его функция `verdict()` даёт тот же результат, что редакция коммита
80c38245: голый `python3 -m unittest` (без имён модулей/файлов) —
отклонён; `discover` без `-s`/с `-s tests`/`-s .` — отклонён; `discover`
с `-s <каталог планки задачи>` — разрешён; `pytest`/`python3 -m pytest`
без аргументов-путей или с путём `tests`/`tests/`/`.` — отклонён; по
конкретному модулю/файлу — разрешён. Список отклоняемых форм не шире и
не уже, чем в редакции 80c38245.

Красен до реализации: `docs/reference/role-home/claude/hooks/bash_guard.py`
снят коммитом dea8016b (стек ч.3, 01M1RDCEF0JZ4AVQRE43JFH8TN) — файла нет
на диске, `_load()` падает `FileNotFoundError` при первом же обращении к
`HOOK` в `setUp` каждого теста ниже.

Списки команд ниже — дословный перенос `test_blocks_full_suite_forms`/
`test_allows_targeted_runs_and_other_commands` из `tests/
test_role_bash_guard.py` редакции коммита 80c38245 (`git show
80c38245:tests/test_role_bash_guard.py`): AC-1 требует ТОТ ЖЕ результат,
что и та редакция, поэтому проверочный набор команд — тот же самый, не
переизобретённый заново.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

HOOK = (_REPO_ROOT / "docs" / "reference" / "role-home" / "claude" / "hooks"
        / "bash_guard.py")


def _load():
    if not HOOK.is_file():
        raise FileNotFoundError(f"хук не найден: {HOOK}")
    spec = importlib.util.spec_from_file_location("bash_guard_ac1", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BlocksFullSuiteFormsTest(unittest.TestCase):
    """Формы команды, отклоняющие полный прогон набора тестов."""

    def setUp(self):
        self.g = _load()

    def test_ac1_blocks_full_suite_forms(self):
        """Полный набор форм голого/дерево-широкого прогона `unittest`/
        `pytest` (перенос из редакции 80c38245) отклоняется — `verdict()`
        возвращает непустую причину для каждой формы.

        Ловит мутацию: сужение проверки только до `discover` без `-s`
        (например, пропуск ветки «голый `python3 -m unittest` без
        `discover`») — форма `"python3 -m unittest"` без `discover`
        перестала бы отклоняться и тест покраснеет на первом же элементе
        списка.
        """
        for cmd in [
            "python3 -m unittest",
            "python3 -m unittest -v",
            "python3 -m unittest -v 2>&1 | tail -30",
            "python3 -m unittest > /dev/null 2>&1",
            "python3 -m unittest -v >log.txt",
            "python3 -m unittest discover -s tests -v",
            "python3 -m unittest discover",
            "python3 -m unittest discover -p 'test_*.py'",
            "python3 -m unittest discover -s . -p 'test_*.py'",
            "python3 -m unittest discover --start-directory=tests",
            "python3 -m unittest discover tests",
            "cd .artel/worktrees/X && python3 -m unittest",
            "python -m unittest",
            "python3.11 -m unittest -k lease",
            "pytest",
            "pytest -q",
            "python3 -m pytest tests/ -q",
            "python3 -m pytest tests",
            "pytest . -x",
            "PYTHONPATH=. python3 -m unittest",
            "git status; python3 -m unittest discover",
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(self.g.verdict(cmd),
                                     f"должно быть отклонено: {cmd!r}")


class AllowsTargetedRunsTest(unittest.TestCase):
    """Формы адресного прогона и прочих команд — пропускаются."""

    def setUp(self):
        self.g = _load()

    def test_ac1_allows_targeted_runs_and_other_commands(self):
        """Адресный прогон по модулю/файлу, `discover` по каталогу планки
        задачи и прочие (не тестовые) команды не отклоняются — `verdict()`
        возвращает `None`.

        Ловит мутацию: расширение правила «дерева целиком» до ЛЮБОГО
        `discover` (без учёта каталога планки задачи) — форма
        `"python3 -m unittest discover -s tasks/X/acceptance_tests"`
        перестала бы проходить, и тест покраснеет.
        """
        for cmd in [
            "python3 -m unittest tests.test_liveness -v 2>&1 | tail -30",
            "python3 -m unittest tests.test_a tests.test_b",
            "python3 -m unittest tasks/X/acceptance_tests/test_ac1.py",
            "python3 -m unittest discover -s tasks/X/acceptance_tests -p 'test_*.py' -t .",
            "python3 -m unittest discover -s tasks/X/acceptance_tests",
            "python3 -m unittest discover tasks/X/acceptance_tests -v",
            "python3 -m unittest -k lease tests.test_store",
            "python3 -m pytest tests/test_multitarget.py -q",
            "pytest tests/test_x.py::Case::test_y -q",
            "python3 -c 'print(1)'",
            "python3 scripts/guard.py tasks/X/SPEC.md",
            "git status && git diff --stat",
            "",
        ]:
            with self.subTest(cmd=cmd):
                self.assertIsNone(self.g.verdict(cmd),
                                  f"не должно быть отклонено: {cmd!r}")


if __name__ == "__main__":
    unittest.main()
