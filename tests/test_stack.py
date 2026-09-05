"""Юнит-тесты orchestrator/stack.py (SPEC 01M1RDCAFENSW2VVAPECHCVGMM,
требования 1, 4): манифест стека и `check_stack()`.

Постоянная регрессия (AC-15) — переживает закрытие
`tasks/01M1RDCAFENSW2VVAPECHCVGMM/acceptance_tests/`, которая
проверяла то же самое подробнее, но живёт только пока задача открыта.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import stack  # noqa: E402

HIGH_VERSION = "999.999.999"
LOW_VERSION = "0.0.1"
OK_PYTHON_VERSION_INFO = (3, 99, 0, "final", 0)


def _all_ok_run(args, **kwargs):
    return subprocess.CompletedProcess(args, 0, f"{HIGH_VERSION}\n", "")


class ManifestConstantsTest(unittest.TestCase):

    def test_required_python_is_a_tuple(self):
        """Требование 1: минимальная версия Python объявлена константой
        `REQUIRED_PYTHON` — кортеж как минимум из двух чисел (major,
        minor), не строка и не одиночное число.

        Ловит мутацию: `REQUIRED_PYTHON` переименована, удалена, либо
        заменена на нечто, что не является кортежем нужной длины
        (например строка `"3.11"` или число `3`) — `assertIsInstance`/
        `assertGreaterEqual` откажут.
        """
        self.assertIsInstance(stack.REQUIRED_PYTHON, tuple)
        self.assertGreaterEqual(len(stack.REQUIRED_PYTHON), 2)

    def test_each_tool_has_minimum_and_command(self):
        """Требование 1/2: манифест несёт для каждого из `git`/`gh`/
        `claude` минимальную версию (кортеж) и способ проверки версии
        — команду, начинающуюся с имени инструмента и содержащую
        `--version`.

        Ловит мутацию: один из трёх инструментов отсутствует в
        `REQUIRED_TOOLS`, либо его `minimum` — не кортеж, либо
        `command` не начинается с имени инструмента или не содержит
        `--version` (например собран без флага) — соответствующий
        `assertIn`/`assertIsInstance`/`assertEqual` откажет.
        """
        for tool in ("git", "gh", "claude"):
            self.assertIn(tool, stack.REQUIRED_TOOLS)
            requirement = stack.REQUIRED_TOOLS[tool]
            self.assertIsInstance(requirement.minimum, tuple)
            self.assertEqual(requirement.command[0], tool)
            self.assertIn("--version", requirement.command)

    def test_third_party_exceptions_list_is_empty(self):
        """AC-3: список допустимых исключений правила «сторонних
        пакетов нет» объявлен и пуст на момент этой задачи.

        Ловит мутацию: `THIRD_PARTY_EXCEPTIONS` не заведён вовсе
        (`AttributeError` до сравнения) либо заведён уже с записью
        (не пуст) — `assertEqual` откажет в обоих случаях.
        """
        self.assertEqual((), stack.THIRD_PARTY_EXCEPTIONS)


class CheckStackTest(unittest.TestCase):

    def test_ok_scenario_reports_ok_for_every_tool(self):
        """AC-7: по одной проверке на каждый инструмент манифеста
        (python, git, gh, claude) — ровно 4 проверки, и все `ok`, когда
        все версии заведомо проходят порог.

        Ловит мутацию: `check_stack()` пропускает инструмент или
        задваивает проверку одного и того же — счётчик проверок
        отклонится от 4, `assertEqual` откажет; либо какой-то из
        заведомо высоких версий присвоен не `ok` — `assertEqual` на
        множестве статусов откажет.
        """
        with mock.patch.object(stack.subprocess, "run", side_effect=_all_ok_run), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
            checks = stack.check_stack()

        self.assertEqual(4, len(checks))
        statuses = {c.status for c in checks}
        self.assertEqual({"ok"}, statuses)

    def test_warn_scenario_for_underversioned_tool(self):
        """AC-8: инструмент с версией ниже минимально требуемой —
        статус WARN, текст в одну строку с именем инструмента и его
        фактической версией (`git` занижен, `gh`/`claude` заведомо
        завышены).

        Ловит мутацию: расхождение версии трактуется как `ok` (порог
        не сравнивается) или строка WARN не содержит имя инструмента
        либо его фактическую версию — `assertEqual`/`assertIn` откажут.
        """
        def fake_run(args, **kwargs):
            version = LOW_VERSION if args[0] == "git" else HIGH_VERSION
            return subprocess.CompletedProcess(args, 0, f"{version}\n", "")

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
            checks = stack.check_stack()

        by_name = {c.name: c for c in checks}
        self.assertEqual("warn", by_name["git"].status)
        self.assertIn("git", by_name["git"].detail.lower())
        self.assertIn(LOW_VERSION, by_name["git"].detail)

    def test_fail_scenario_for_missing_tool(self):
        """AC-9: инструмент отсутствует в PATH/системе
        (`FileNotFoundError` на попытке его вызвать) — статус FAIL
        именно для этого инструмента (`claude`), а не для остальных.

        Ловит мутацию: отсутствие инструмента трактуется как `warn`
        (не `fail`), либо роняет весь `check_stack()` необработанным
        исключением вместо структурированного FAIL — `assertEqual`
        откажет, либо сам вызов упадёт вместо возврата результата.
        """
        def fake_run(args, **kwargs):
            if args[0] == "claude":
                raise FileNotFoundError("claude: команда не найдена")
            return _all_ok_run(args, **kwargs)

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
            checks = stack.check_stack()

        by_name = {c.name: c for c in checks}
        self.assertEqual("fail", by_name["claude"].status)

    def test_no_network_calls(self):
        """AC-10/инвариант 35 (docs/invariants.md): `check_stack()` не
        обращается к сети — подмена `socket.socket` на взрыв доказывает
        отсутствие попытки сетевого соединения при полностью успешном
        прогоне.

        Ловит мутацию: реализация проверки версии инструмента вместо
        `subprocess`+CLI использует сетевой запрос (например, к API
        релизов инструмента) — подмена `socket.socket` поднимет
        `AssertionError`, и вызов `check_stack()` внутри `with`
        завершится этим исключением вместо штатного результата.
        """
        def explode(*args, **kwargs):
            raise AssertionError("check_stack() обратился к сети")

        with mock.patch.object(stack.subprocess, "run", side_effect=_all_ok_run), \
             mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO), \
             mock.patch("socket.socket", side_effect=explode):
            checks = stack.check_stack()

        self.assertTrue(checks)


if __name__ == "__main__":
    unittest.main()
