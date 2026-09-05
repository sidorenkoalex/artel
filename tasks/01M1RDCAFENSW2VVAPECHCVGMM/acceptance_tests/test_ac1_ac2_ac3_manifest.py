"""AC-1, AC-2, AC-3 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md, требование 1).

Красен до реализации: `orchestrator/stack.py` ещё не существует — импорт
модуля падает `ModuleNotFoundError` для всех трёх тестов ниже.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import stack  # noqa: E402


class ManifestConstantsTest(unittest.TestCase):

    def test_ac1_required_python_is_3_11_tuple(self):
        """`REQUIRED_PYTHON` — константа-кортеж `(3, 11)`, буквально из
        требования 1 (обоснование в TZ.md: без неё синтаксис `X | None`
        в аннотациях кода пульта не работает без `__future__`).

        Ловит мутацию: константа переименована, отсутствует, либо несёт
        другое значение (например `(3, 10)` или строку `"3.11"` вместо
        кортежа) — `assertEqual` в это не поверит.
        """
        self.assertEqual(stack.REQUIRED_PYTHON, (3, 11))

    def test_ac2_check_stack_queries_each_tool_by_its_named_version_command(self):
        """Требование 1/4 буквально называют команду каждого инструмента:
        `git --version`, `gh --version`, `claude --version`. Манифест
        обязан знать способ проверки версии — единственный наблюдаемый
        (не зависящий от того, как разработчик назовёт внутренние
        структуры манифеста) след этого факта — реальные argv, которыми
        `check_stack()` зовёт `subprocess.run` для каждого из трёх
        инструментов.

        Подмена всех вызовов одним и тем же «успешным» ответом с высокой
        версией ("999.999.999") — не предмет этого теста (это WARN/FAIL/ok
        сценарии AC-7..AC-9/AC-17), только фиксация ТРЁХ ожидаемых
        команд.

        Ловит мутацию: `check_stack()` не зовёт `git --version`/
        `gh --version`/`claude --version` (например, забыт один из трёх
        инструментов, или команда собрана с опечаткой типа `["git",
        "version"]` без `--`) — недостающая или неверная команда не
        попадёт в список зафиксированных вызовов, `assertIn` откажет.
        """
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0, "999.999.999\n", "")

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run):
            stack.check_stack()

        for tool in ("git", "gh", "claude"):
            self.assertIn(
                [tool, "--version"], calls,
                f"check_stack() не вызвал `{tool} --version` "
                f"(зафиксированные вызовы: {calls})")

    def test_ac3_stdlib_exceptions_list_is_empty(self):
        """Список допустимых исключений правила «сторонних пакетов нет»
        объявлен и пуст на момент этой задачи (требование 1/AC-3).

        Имя атрибута манифеста не зафиксировано SPEC буквально — ищем по
        смыслу (единственный публичный атрибут модуля, чьё имя содержит
        «except», независимо от регистра), не гадаем точное имя.

        Ловит мутацию: список исключений не заведён вовсе, либо заведён
        уже с записью (не пуст) — обе мутации `assertEqual(value, ...)`
        поймает как через отсутствие кандидата, так и через непустое
        значение.
        """
        candidates = {
            name: value for name, value in vars(stack).items()
            if not name.startswith("_") and "except" in name.lower()
        }
        self.assertTrue(
            candidates,
            "в orchestrator/stack.py не найден публичный атрибут со "
            "словом 'except' в имени — список допустимых исключений "
            "правила «сторонних пакетов нет» (требование 1) не найден")
        name, value = next(iter(candidates.items()))
        self.assertIn(
            value, ([], (), set(), frozenset()),
            f"{name} обязан быть пуст на момент этой задачи (AC-3: "
            f"«список пуст»), получено: {value!r}")


if __name__ == "__main__":
    unittest.main()
