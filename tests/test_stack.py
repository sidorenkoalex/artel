"""Юнит-тесты orchestrator/stack.py (SPEC 01M1RDCAFENSW2VVAPECHCVGMM,
требования 1, 4; SPEC 01M1REVEZ1HESMJ7AFD5A9MEJ8, требования 1-2:
исключения манифеста для pytest/pytest-timeout/pytest-xdist и сверка
`.artel/venv` с файлом закреплённых версий): манифест стека и
`check_stack()`.

Постоянная регрессия (AC-15/AC-16) — переживает закрытие
`tasks/01M1RDCAFENSW2VVAPECHCVGMM/acceptance_tests/` и
`tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests/`, которые проверяли
то же самое подробнее, но живут только пока задача открыта.
"""
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, stack  # noqa: E402
from tests.sandbox import resilient_tmp_cleanup  # noqa: E402

HIGH_VERSION = "999.999.999"
LOW_VERSION = "0.0.1"
OK_PYTHON_VERSION_INFO = (3, 99, 0, "final", 0)
LOCK_CONTENT = "pytest==7.4.4\npytest-timeout==2.3.1\npytest-xdist==3.5.0\n"


def _all_ok_run(args, **kwargs):
    if "freeze" in args:
        return subprocess.CompletedProcess(args, 0, LOCK_CONTENT, "")
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

    def test_third_party_exceptions_list_carries_the_pytest_family(self):
        """AC-2 (tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md, требование 1):
        переход на pytest несёт три записи исключений манифеста
        (`pytest`, `pytest_timeout`, `xdist` — ИМПОРТИРУЕМЫЕ имена, не
        написание PyPI), каждая с непустой причиной.

        Ловит мутацию: одна из трёх записей отсутствует, либо у какой-то
        из них причина — пустая строка — `assertIn`/`assertTrue` откажут.
        """
        by_name = dict(stack.THIRD_PARTY_EXCEPTIONS)
        for name in ("pytest", "pytest_timeout", "xdist"):
            self.assertIn(name, by_name)
            self.assertTrue(by_name[name].strip())

    def test_per_test_timeout_matches_pyproject_toml(self):
        """R1-F1 (REVIEW.md 01M1TKP6AAY4W8GDGZNA9R0JZT итерация 1):
        `pyproject.toml` (`[tool.pytest.ini_options] timeout`) несёт
        таймаут отдельного теста тем же числом, что
        `stack.PER_TEST_TIMEOUT_SEC` — TOML не умеет читать константу
        оттуда, оба места синхронизированы руками; без этого теста
        комментарии рядом с обоими числами ссылались на защиту, которой
        не существовало.

        Ловит мутацию: `PER_TEST_TIMEOUT_SEC` меняется без правки
        `timeout` в `pyproject.toml` (или наоборот) — `assertEqual`
        откажет.
        """
        pyproject = Path(config.ROOT) / "pyproject.toml"
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
        configured_timeout = data["tool"]["pytest"]["ini_options"]["timeout"]
        self.assertEqual(stack.PER_TEST_TIMEOUT_SEC, configured_timeout)


class CheckStackTest(unittest.TestCase):

    def test_ok_scenario_reports_ok_for_every_tool(self):
        """AC-7: по одной проверке на каждый инструмент манифеста
        (python, git, gh, claude) плюс venv/venv-packages (SPEC
        01M1REVEZ1HESMJ7AFD5A9MEJ8, требование 2) — 6 проверок, все `ok`,
        когда все версии заведомо проходят порог и venv согласован с
        файлом закреплённых версий.

        Ловит мутацию: `check_stack()` пропускает проверку или
        задваивает проверку одной и той же — счётчик проверок
        отклонится от 6, `assertEqual` откажет; либо какой-то из
        заведомо согласованных проверок присвоен не `ok` — `assertEqual`
        на множестве статусов откажет.
        """
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / "venv"
            venv_dir.mkdir()
            lock_file = Path(tmp) / "requirements.lock"
            lock_file.write_text(LOCK_CONTENT, encoding="utf-8")

            with mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
                 mock.patch.object(config, "REQUIREMENTS_LOCK", lock_file,
                                   create=True), \
                 mock.patch.object(stack.subprocess, "run",
                                   side_effect=_all_ok_run), \
                 mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
                checks = stack.check_stack()

        self.assertEqual(6, len(checks))
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


class CheckStackVenvTest(unittest.TestCase):
    """AC-7/AC-8 (tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md, требование 2):
    `check_stack()` сверяет `.artel/venv` с файлом закреплённых версий."""

    def setUp(self):
        self.version_patcher = mock.patch.object(
            sys, "version_info", OK_PYTHON_VERSION_INFO)
        self.version_patcher.start()
        self.addCleanup(self.version_patcher.stop)

    def _check_with(self, venv_dir, lock_file, freeze_output):
        with mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
             mock.patch.object(config, "REQUIREMENTS_LOCK", lock_file,
                               create=True), \
             mock.patch.object(stack.subprocess, "run",
                               side_effect=_all_ok_run_with_freeze(freeze_output)):
            return stack.check_stack()

    def test_missing_venv_gives_warn_naming_the_creation_command(self):
        """AC-8: `.artel/venv` отсутствует — WARN называет `venv-sync`.

        Ловит мутацию: отсутствие venv трактуется как `ok` (проверка не
        смотрит на существование каталога) — `assertTrue`/`assertIn`
        откажут.
        """
        with tempfile.TemporaryDirectory() as tmp:
            lock_file = Path(tmp) / "requirements.lock"
            lock_file.write_text(LOCK_CONTENT, encoding="utf-8")
            missing_venv = Path(tmp) / "no-such-venv"

            checks = self._check_with(missing_venv, lock_file, "")

        venv_checks = [c for c in checks if "venv" in c.name.lower()]
        self.assertTrue(venv_checks)
        warn = [c for c in venv_checks if c.status == "warn"]
        self.assertTrue(warn)
        self.assertIn("venv-sync", " ".join(c.detail for c in warn))

    def test_version_mismatch_gives_warn_naming_the_package(self):
        """AC-7: одна из версий venv расходится с файлом закреплённых
        версий — WARN называет РАСХОДЯЩИЙСЯ пакет по имени.

        Ловит мутацию: сверка версий не реализована (venv считается
        согласованным всегда, пока каталог существует) — WARN не
        появится; либо WARN не называет расходящийся пакет —
        `assertIn` откажет.
        """
        freeze_output = ("pytest==7.0.0\npytest-timeout==2.3.1\n"
                         "pytest-xdist==3.5.0\n")
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / "venv"
            venv_dir.mkdir()
            lock_file = Path(tmp) / "requirements.lock"
            lock_file.write_text(LOCK_CONTENT, encoding="utf-8")

            checks = self._check_with(venv_dir, lock_file, freeze_output)

        warn = [c for c in checks
               if "venv" in c.name.lower() and c.status == "warn"]
        self.assertTrue(warn)
        self.assertIn("pytest", " ".join(c.detail.lower() for c in warn))

    def test_matching_versions_produce_no_venv_warn(self):
        """AC-7 (контроль): все версии venv совпадают с файлом
        закреплённых версий — ни одна venv-проверка не WARN.

        Ловит мутацию: реализация безусловно даёт WARN для venv-пакетов
        независимо от факта совпадения — `assertFalse` откажет.
        """
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / "venv"
            venv_dir.mkdir()
            lock_file = Path(tmp) / "requirements.lock"
            lock_file.write_text(LOCK_CONTENT, encoding="utf-8")

            checks = self._check_with(venv_dir, lock_file, LOCK_CONTENT)

        warn = [c for c in checks
               if "venv" in c.name.lower() and c.status == "warn"]
        self.assertFalse(warn)


def _all_ok_run_with_freeze(freeze_output: str):
    def fake_run(args, **kwargs):
        args = list(args)
        if "freeze" in args:
            return subprocess.CompletedProcess(args, 0, freeze_output, "")
        return _all_ok_run(args, **kwargs)
    return fake_run


class MainCopyRootTest(unittest.TestCase):
    """ANSWER-7 (01M1TKP6AAY4W8GDGZNA9R0JZT, возврат «venv по расположению
    кода»): `tests/sandbox.py::RealGitSandbox` подменяет `config.ROOT` на
    временный git-репозиторий, никак не связанный с настоящей копией
    пульта — `_main_copy_root()` обязана искать `--git-common-dir` от
    расположения кода (`stack._MODULE_ROOT`), не от `config.ROOT`,
    иначе поиск venv уходит в несуществующий временный репозиторий
    вместо настоящей главной копии.
    """

    def test_uses_module_root_not_config_root(self):
        """Ловит мутацию: отправная точка снова `config.ROOT` —
        записанный `cwd` совпал бы с подменённым (фейковым) путём вместо
        `_MODULE_ROOT`, `assertEqual`/`assertNotEqual` откажут."""
        recorded = {}

        def fake_run(args, **kwargs):
            recorded["cwd"] = kwargs.get("cwd")
            return subprocess.CompletedProcess(args, 1, "", "")

        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            with mock.patch.object(config, "ROOT", fake_root), \
                 mock.patch.object(stack.subprocess, "run",
                                   side_effect=fake_run):
                stack._main_copy_root()

        self.assertEqual(recorded["cwd"], stack._MODULE_ROOT)
        self.assertNotEqual(Path(recorded["cwd"]), fake_root)


class PytestPythonExecutableWorktreeTest(unittest.TestCase):
    """ANSWER-6 (01M1TKP6AAY4W8GDGZNA9R0JZT, возврат «интерпретатор venv
    из worktree»): планку пульт гоняет против worktree'а задачи, где
    `.artel/venv` рядом с `config.ROOT` не существует — только ГЛАВНАЯ
    копия несёт venv пульта. Git настоящий (по образцу
    tests/test_workspace.py): суть проверки — реальный `git rev-parse
    --git-common-dir` из worktree'а, заглушкой не проверить.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.main_root = Path(tmp.name).resolve()
        self._git(self.main_root, "init", "-q", "-b", "main")
        self._git(self.main_root, "config", "user.email",
                 "artel-tests@example.invalid")
        self._git(self.main_root, "config", "user.name", "artel tests")
        (self.main_root / "README.md").write_text("x", encoding="utf-8")
        self._git(self.main_root, "add", "-A")
        self._git(self.main_root, "commit", "-q", "-m", "init")

        self.worktree_root = self.main_root / "worktree"
        self._git(self.main_root, "worktree", "add", "-b", "task/x",
                 str(self.worktree_root))
        self.missing_venv = self.worktree_root / ".artel" / "venv"

    def _git(self, cwd, *args):
        res = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                             text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res

    def test_falls_back_to_main_copy_venv_when_worktree_has_none(self):
        """Ловит мутацию: шаг 2 (поиск venv главной копии через
        `_main_copy_root()`) убран — функция ушла бы прямиком на
        `sys.executable`, `assertEqual` откажет.

        Отправная точка `_main_copy_root()` — `stack._MODULE_ROOT`, не
        `config.ROOT` (ANSWER-7): подменяем именно `_MODULE_ROOT` на
        сконструированный worktree — тем же приёмом, что и раньше
        `config.ROOT`, только через актуальный якорь."""
        main_venv_python = self.main_root / ".artel" / "venv" / "bin" / "python3"
        main_venv_python.parent.mkdir(parents=True)
        main_venv_python.touch()

        with mock.patch.object(stack, "_MODULE_ROOT", self.worktree_root), \
             mock.patch.object(config, "VENV_DIR", self.missing_venv,
                               create=True):
            executable = stack.pytest_python_executable()

        self.assertEqual(executable, str(main_venv_python))

    def test_falls_back_to_sys_executable_when_main_copy_has_no_venv_either(self):
        """Контроль: главная копия тоже не несёт venv — шаг 3, не пустой
        путь и не исключение."""
        with mock.patch.object(stack, "_MODULE_ROOT", self.worktree_root), \
             mock.patch.object(config, "VENV_DIR", self.missing_venv,
                               create=True):
            executable = stack.pytest_python_executable()

        self.assertEqual(executable, sys.executable)


if __name__ == "__main__":
    unittest.main()
