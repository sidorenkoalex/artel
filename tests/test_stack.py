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

from orchestrator import config, models, stack  # noqa: E402
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

        Строки моделей ролей (`model-<роль>`, SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ,
        требование 5) отсекаются по имени: их число — функция `roles.yaml`,
        не манифеста инструментов, а их статусы проверяет
        `CheckStackModelLinesTest` ниже.
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
                checks = [c for c in stack.check_stack()
                          if not c.name.startswith("model-")]

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


class PythonCheckProvenanceTest(unittest.TestCase):
    """Требование 7 (SPEC 01M1SHK3MD4ZF9NYXSCT67J8AP, AC-7): проверка
    `python` несёт дополнительную строку про фактический интерпретатор и
    `.artel/venv`, не меняя свой статус. Регрессия постоянная — переживает
    закрытие tasks/01M1SHK3MD4ZF9NYXSCT67J8AP/acceptance_tests/, которые
    проверяли то же самое подробнее, но живут только пока задача открыта.
    """

    def test_detail_names_executable_and_venv_presence(self):
        """Ловит мутацию: `sys.executable`/путь `.artel/venv` не попадают
        в `detail` — `assertIn` откажет."""
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = Path(tmp) / "venv"
            venv_dir.mkdir()
            with mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
                 mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
                check = stack._python_check()

        self.assertIn(sys.executable, check.detail)
        self.assertIn(str(venv_dir), check.detail)

    def test_status_unaffected_by_venv_presence(self):
        """Ловит мутацию: добавление сведений о venv заодно меняет статус
        проверки `python` — `assertEqual` статусов между прогонами
        (venv есть/нет) откажет."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys, "version_info", OK_PYTHON_VERSION_INFO):
                existing = Path(tmp) / "venv"
                existing.mkdir()
                with mock.patch.object(config, "VENV_DIR", existing, create=True):
                    with_venv = stack._python_check()
                missing = Path(tmp) / "missing"
                with mock.patch.object(config, "VENV_DIR", missing, create=True):
                    without_venv = stack._python_check()

        self.assertEqual("ok", with_venv.status)
        self.assertEqual(with_venv.status, without_venv.status)


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


TABLE_MODEL = "claude-fable-5-1"
UNKNOWN_MODEL = "claude-test-model-vne-kataloga"
CATALOG_MINIMUM = (2, 1, 251)

# Карта исполнителей под тестом: `developer` и `reviewer` — agent-роли с
# ярусами (строки моделей `check_stack()` получают только они),
# `orchestrator`/`verifier` — не agent-роли, `analyst` — agent-роль с
# ярусом, которого нет в локальном слое (строка отказа цепочки).
ROLES_YAML = """roles:
  orchestrator:
    executor: system
    token_slot: artel-orchestrator
  developer:
    executor: agent
    token_slot: artel-developer
    skills: [conventions-core]
    model_tier: strong
  reviewer:
    executor: agent
    token_slot: artel-reviewer
    skills: [conventions-core]
    model_tier: standard
  analyst:
    executor: agent
    token_slot: artel-analyst
    skills: [conventions-core]
    model_tier: cheap
  verifier:
    executor: none
    token_slot: artel-verifier
token_fallback: artel-token
"""

CATALOG_YAML = """providers:
  claude:
    cli: claude
    min_cli_version: 1.0.0
    cost_from_cli: true
    models:
      {table_model}:
        min_cli_version: 2.1.251
        status: supported
        list_price_usd_per_mtok:
          input: 5.0
          output: 25.0
          cache_write: 6.25
          cache_read: 0.50
        price_date: 2026-09-20
"""

LOCAL_YAML = """tiers:
  strong: {strong}
  standard: {standard}
"""


class ModelCliVerdictTest(unittest.TestCase):
    """Чистый вердикт `model_cli_verdict` (SPEC
    01M2XJKV84SQ9VEVR0VNVKDNGJ, AC-5), с минимумом версии ПАРАМЕТРОМ из
    каталога моделей: таблица `MODEL_MIN_CLI_VERSION` удалена задачей
    01M3009Y9AGGY6ZCFA7H1HJ1TD (требование 10, AC-13)."""

    def test_catalog_carries_the_incident_entry(self):
        """Ловит мутацию: запись инцидента 19.09 не пережила переезд из
        таблицы в каталог — минимум `claude-fable-5-1` стал другим."""
        self.assertEqual(
            models.load_catalog().models[TABLE_MODEL].min_cli_version,
            CATALOG_MINIMUM)

    def test_verdict_reads_the_parameter_not_a_literal(self):
        """Ловит мутацию: минимум повторён литералом по месту сравнения —
        переданное число не меняет ни вердикт, ни названную версию."""
        low = stack.model_cli_verdict(TABLE_MODEL, (7, 7, 6), (7, 7, 7))
        high = stack.model_cli_verdict(TABLE_MODEL, (7, 7, 8), (7, 7, 7))
        equal = stack.model_cli_verdict(TABLE_MODEL, (7, 7, 7), (7, 7, 7))

        self.assertEqual(low.status, "fail")
        self.assertIn("7.7.7", low.detail)
        self.assertIn("7.7.6", low.detail)
        self.assertEqual(high.status, "ok")
        self.assertEqual(equal.status, "ok")

    def test_fail_detail_names_the_refusal_and_the_hint(self):
        """Ловит мутацию: текст отказа расходится с требованием 3 SPEC
        (префикс, «требует claude ≥ X, установлен Y», подсказка)."""
        verdict = stack.model_cli_verdict(TABLE_MODEL, (2, 1, 236),
                                          CATALOG_MINIMUM)

        self.assertEqual(verdict.status, "fail")
        self.assertTrue(verdict.detail.startswith(
            f"{stack.MODEL_UNSUPPORTED_PREFIX}: {TABLE_MODEL} требует claude ≥ "
            f"2.1.251, установлен 2.1.236"), verdict.detail)
        self.assertIn(stack.CLI_UPGRADE_HINT, verdict.detail)

    def test_unknown_minimum_is_a_refusal_regardless_of_version(self):
        """Ловит мутацию: неизвестный минимум (модели нет в каталоге)
        снова трактуется как `warn` с запуском «как есть» — ровно то
        поведение, которое требование 10 заменяет отказом."""
        for installed in ((0, 0, 1), (999, 0, 0), None):
            with self.subTest(installed=installed):
                verdict = stack.model_cli_verdict(UNKNOWN_MODEL, installed,
                                                  None)
                self.assertEqual(verdict.status, "fail")
                self.assertIn(UNKNOWN_MODEL, verdict.detail)

    def test_the_removed_table_is_not_back(self):
        """Ловит мутацию: таблица совместимости вернулась в манифест —
        два источника минимума версии (код и каталог) разошлись бы
        молча (AC-13)."""
        self.assertFalse(hasattr(stack, "MODEL_MIN_CLI_VERSION"))
        self.assertFalse(hasattr(stack, "MODEL_NOT_IN_TABLE_WARNING"))

    def test_undetermined_cli_version_is_a_warning_not_a_refusal(self):
        """Ловит мутацию: `installed=None` сравнивается с кортежем
        (`TypeError`) либо трактуется как «ниже минимума» — отказ по
        причине вне предмета сверки."""
        verdict = stack.model_cli_verdict(TABLE_MODEL, None, CATALOG_MINIMUM)

        self.assertEqual(verdict.status, "warn")
        self.assertIn("не определилась", verdict.detail)

    def test_ok_detail_matches_the_spec_wording(self):
        """Ловит мутацию: строка `ok` теряет обе версии или знак `≥`
        (текст требования 5: «CLI 2.1.267 ≥ 2.1.251 — ok»)."""
        verdict = stack.model_cli_verdict(TABLE_MODEL, (2, 1, 267),
                                          CATALOG_MINIMUM)

        self.assertEqual(verdict.status, "ok")
        self.assertEqual(verdict.detail, "CLI 2.1.267 ≥ 2.1.251 — ok")


class InstalledCliVersionTest(unittest.TestCase):
    """Требование 3: `installed_cli_version()` — тот же вызов и разбор
    `claude --version`, что у проверки инструмента манифеста."""

    def test_parses_the_version_tuple_from_claude_version(self):
        """Ловит мутацию: версия читается не из `claude --version` или
        возвращается строкой, не кортежем."""
        recorded = []

        def fake_run(args, **kwargs):
            recorded.append(list(args))
            return subprocess.CompletedProcess(args, 0, "2.1.267 (Claude Code)\n", "")

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run):
            version = stack.installed_cli_version()

        self.assertEqual(version, (2, 1, 267))
        self.assertEqual(recorded, [list(stack.REQUIRED_TOOLS["claude"].command)])

    def test_missing_or_unparsable_cli_gives_none(self):
        """Ловит мутацию: отсутствие CLI роняет вызывающий код исключением
        либо нераспознанный вывод отдаётся пустым кортежем."""
        def missing(args, **kwargs):
            raise FileNotFoundError("claude")

        with mock.patch.object(stack.subprocess, "run", side_effect=missing):
            self.assertIsNone(stack.installed_cli_version())
        with mock.patch.object(stack.subprocess, "run",
                               side_effect=_all_ok_run_with_freeze("")):
            with mock.patch.object(stack, "VERSION_RE", stack.re.compile("nope")):
                self.assertIsNone(stack.installed_cli_version())


class CheckStackModelLinesTest(unittest.TestCase):
    """Требование 5 (AC-10): строки моделей agent-ролей в `check_stack()`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tdir = Path(tmp.name)
        self.roles_path = self.tdir / "roles.yaml"
        self.roles_path.write_text(ROLES_YAML, encoding="utf-8")
        self.catalog_path = self.tdir / "models.yaml"
        self.catalog_path.write_text(CATALOG_YAML.format(table_model=TABLE_MODEL),
                                     encoding="utf-8")
        self.local_path = self.tdir / "local-models.yaml"
        self.set_tiers(strong=TABLE_MODEL, standard=TABLE_MODEL)
        self.patch(config, "ROLES", self.roles_path)
        self.patch(config, "MODELS", self.catalog_path)
        self.patch(config, "MODELS_LOCAL", self.local_path)
        self.patch(sys, "version_info", OK_PYTHON_VERSION_INFO)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_tiers(self, strong, standard) -> None:
        self.local_path.write_text(
            LOCAL_YAML.format(strong=strong, standard=standard),
            encoding="utf-8")

    def checks_with_cli(self, version_text: str) -> list:
        self.runs = []

        def fake_run(args, **kwargs):
            self.runs.append(list(args))
            if args[0] == "claude":
                return subprocess.CompletedProcess(args, 0, f"{version_text}\n", "")
            return _all_ok_run(args, **kwargs)

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run):
            return stack.check_stack()

    def model_lines(self, checks) -> dict:
        return {c.name: c for c in checks if c.name.startswith("model-")}

    def test_one_line_per_agent_role_resolved_through_the_tier(self):
        """Ловит мутацию: строка печатается на каждую роль подряд (включая
        не-agent `orchestrator`/`verifier`), модель читается не через
        разрешение цепочки, либо неразрешимая цепочка (`analyst`: ярус
        `cheap` в локальном слое не назван) молча пропускает строку
        вместо `fail`."""
        lines = self.model_lines(self.checks_with_cli("2.1.267"))

        self.assertEqual(sorted(lines),
                         ["model-analyst", "model-developer", "model-reviewer"])
        ok = lines["model-developer"]
        self.assertEqual(ok.status, "ok", ok.detail)
        self.assertEqual(
            ok.detail,
            f"модель роли developer {TABLE_MODEL}: CLI 2.1.267 ≥ 2.1.251 — ok")
        unresolved = lines["model-analyst"]
        self.assertEqual(unresolved.status, "fail", unresolved.detail)
        self.assertIn("cheap", unresolved.detail)

    def test_model_outside_the_catalog_fails_the_line(self):
        """Ловит мутацию: модель яруса, которой нет в каталоге, даёт
        `warn` (поведение до 20.09) — `doctor` зеленел бы при модели без
        минимума версии CLI и без тарифа."""
        self.set_tiers(strong=UNKNOWN_MODEL, standard=TABLE_MODEL)

        line = self.model_lines(self.checks_with_cli("2.1.267"))["model-developer"]

        self.assertEqual(line.status, "fail", line.detail)
        self.assertIn(UNKNOWN_MODEL, line.detail)

    def test_line_fails_when_the_installed_cli_is_below_the_minimum(self):
        """Ловит мутацию: заниженная версия отмечается `warn` (как минимум
        инструмента в `_tool_check`) — `doctor` остаётся зелёным при
        заведомо нерабочей модели роли."""
        lines = self.model_lines(self.checks_with_cli("2.1.236"))

        check = lines["model-developer"]
        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("2.1.251", check.detail)
        self.assertIn("2.1.236", check.detail)
        self.assertIn(stack.CLI_UPGRADE_HINT, check.detail)

    def test_model_lines_reuse_the_tool_probe_without_extra_subprocesses(self):
        """Ловит мутацию: версия для строк моделей добывается отдельным
        `claude --version` на роль — `check_stack()` (а с ним и
        `runner._venv_interpreter_bin` на каждом шаге) заводит лишние
        подпроцессы."""
        self.checks_with_cli("2.1.267")

        claude_runs = [r for r in self.runs if r[0] == "claude"]
        self.assertEqual(len(claude_runs), 1, self.runs)

    def test_model_line_names_do_not_match_the_venv_filter(self):
        """Ловит мутацию: имя строки содержит «venv» — фильтр `runner.
        _venv_interpreter_bin` (`"venv" in c.name`) примет WARN модели за
        неготовый venv и остановит шаг."""
        lines = self.model_lines(self.checks_with_cli("1.0.0"))

        self.assertTrue(lines)
        for name in lines:
            self.assertNotIn("venv", name.lower())

    def test_unreadable_roles_yaml_is_a_warning_line_not_an_exception(self):
        """Ловит мутацию: нечитаемый `roles.yaml` роняет `check_stack()`
        необработанным `RolesError` вместо строки диагностики."""
        self.roles_path.unlink()

        checks = self.checks_with_cli("2.1.267")

        warn = [c for c in checks if c.name == "model-roles"]
        self.assertEqual(len(warn), 1)
        self.assertEqual(warn[0].status, "warn")

    def test_undetermined_cli_version_gives_warn_lines(self):
        """Ловит мутацию: `claude` не найден — строка модели из таблицы
        падает исключением или даёт `fail` по неизвестному числу."""
        def missing_claude(args, **kwargs):
            if args[0] == "claude":
                raise FileNotFoundError("claude")
            return _all_ok_run(args, **kwargs)

        with mock.patch.object(stack.subprocess, "run", side_effect=missing_claude):
            lines = self.model_lines(stack.check_stack())

        self.assertEqual(lines["model-developer"].status, "warn")
        self.assertIn("не определилась", lines["model-developer"].detail)


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
