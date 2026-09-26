"""Юнит-тесты провайдера `codex` (SPEC 01M32NH6P053978AER66P0X4GN,
требования 1-5, 7, 12).

Постоянная регрессия поверх приёмочной планки задачи
(`tasks/01M32NH6P053978AER66P0X4GN/acceptance_tests/`): та планка уходит
вместе с каталогом задачи, а свойства «команда шага и курируемый дом
роли говорят одно и то же», «роль на Codex не наследует дом и секреты
Оператора» и «живой смок платного CLI не идёт в обычном `doctor`»
обязаны её пережить.

Песочницы — общие (`tests/sandbox.py`); настоящий `codex` на машине
прогона не нужен и не запускается ни разу: резолв инструментов манифеста
и ответы `codex --version` подменяются.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (catalog, config, doctor, keychain,  # noqa: E402
                          providers, runner, stack)
from orchestrator.providers import codex as codex_provider  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

STUB_BIN = "/artel-test-stub-bin"
KEYCHAIN_SECRET = "kluch-iz-slota"
AMBIENT_KEY = "kluch-operatora"
ALIEN_HOME = "/tmp/dom-operatora-ne-roli"
CLAUDE_SECRETS = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")
# Имена, которыми ключ API мог бы прийти к шагу: ни одного из них шаг на
# Codex не получает (SPEC 01M3EKCZJY9NGCW6VT878RX9JZ, требования 2, 3, 5).
FORBIDDEN_KEY_NAMES = codex_provider.FORBIDDEN_KEY_ENV_NAMES

# Вывод `codex login status` в трёх состояниях авторизации; маркер в каждой
# строке ловит эхо вывода CLI в текст строки `doctor`.
STATUS_MARKER = "VYVOD-CLI-STATUS"
NOISE_MARKER = "VYVOD-CLI-NOISE"
LOGGED_IN_CHATGPT = f"Logged in using ChatGPT {STATUS_MARKER}"
LOGGED_IN_API_KEY = f"Logged in using an API key {STATUS_MARKER}"
NOT_LOGGED_IN = f"Not logged in {STATUS_MARKER}"
CLI_NOISE = f"{NOISE_MARKER}: warning from cli"

# ЗАПИСАННЫЙ факт настоящего CLI 0.155.1 (живые пробы ревьювера, REVIEW.md
# итерации 1, R1-F1; отчёт `docs/research/codex-live-check-2026-09-22.md`):
# `codex login status` печатает результат в STDERR, оставляя stdout пустым,
# — `rc=0, stdout='', stderr='Logged in using ChatGPT\n'` при
# подтверждённом входе; `rc=0, stderr='Logged in using an API key - sk-***'`
# при входе ключом; `rc=1, stderr='Not logged in'`, если дом роли не вошёл.
# `codex --version`, наоборот, печатает в stdout (`codex-cli 0.155.1`):
# поток зависит от подкоманды, и обобщать его с соседней проверки нельзя.
#
# Заглушка калибруется этим фактом по умолчанию: до правки она клала строку
# входа в stdout, весь набор зеленел на CLI, которого нет, а вошедший дом
# роли получал `fail` с рецептом «войдите».
LOGIN_STATUS_STREAM = "stderr"


def _drop_ambient(test, *names) -> None:
    """Гасит ambient-переменные УДАЛЕНИЕМ, не пустым значением: белый
    список манифеста копирует и пустое значение, и «ключа нет» стало бы
    неотличимо от «ключ есть и пуст»."""
    patcher = mock.patch.dict(os.environ, {})
    patcher.start()
    test.addCleanup(patcher.stop)
    for name in names:
        os.environ.pop(name, None)


def _toml_pairs(text: str) -> dict:
    """{полный ключ: значение без кавычек и регистра} курируемого
    `config.toml`: ключ секции приписывается точкой, так что запись
    секцией и точечный ключ дают одну и ту же пару."""
    pairs, section = {}, ""
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip() if raw.lstrip().startswith("#") \
            else _strip_comment(raw).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        full = f"{section}.{key.strip()}" if section else key.strip()
        pairs[full] = value.strip().strip('"').strip("'").lower()
    return pairs


class _LoginStatusRuns:
    """Подмена `subprocess.run` пакета `doctor`: отвечает на `--version`
    обоих CLI и на `codex … login status`, запоминая ВСЕ вызовы и отдельно
    вызовы второго.

    Состояние авторизации (`status`) кладётся в тот поток, который назван
    `stream`; по умолчанию — `stderr`, как печатает настоящий 0.155.1 (см.
    `LOGIN_STATUS_STREAM`). Во второй поток идёт шум со своим маркером:
    эхо ЛЮБОГО из потоков в текст строки `doctor` обязано быть видно.

    Настоящий `codex` на машине прогона не нужен и не запускается ни разу.
    """

    def __init__(self, status=LOGGED_IN_CHATGPT, stream=LOGIN_STATUS_STREAM,
                 returncode=0, raises=None, codex_version="0.155.1",
                 noise=CLI_NOISE):
        self.status, self.stream, self.noise = status, stream, noise
        self.returncode, self.raises = returncode, raises
        self.codex_version = codex_version
        self.login_calls = []
        self.calls = []

    def streams(self) -> tuple:
        """(stdout, stderr) ответа `login status`: состояние — в своём
        потоке, шум — во втором."""
        text = f"{self.status}\n"
        if self.stream == "stdout":
            return text, f"{self.noise}\n"
        return f"{self.noise}\n", text

    def __call__(self, args, **kwargs):
        argv = [str(item) for item in args]
        self.calls.append(argv)
        if "login" in argv:
            self.login_calls.append((argv, kwargs))
            if self.raises is not None:
                raise self.raises
            stdout, stderr = self.streams()
            return subprocess.CompletedProcess(argv, self.returncode,
                                               stdout, stderr)
        name = Path(argv[0]).name
        text = self.codex_version if name == "codex" else config.CLI_VERSION_PIN
        return subprocess.CompletedProcess(argv, 0, f"{text}\n", "")


def _strip_comment(line: str) -> str:
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#":
            return line[:index]
    return line


class StepCommandTest(unittest.TestCase):
    """Argv шага роли — требования 2-3."""

    def setUp(self):
        self.asked = []
        patcher = mock.patch.object(runner, "declared_tool_path",
                                    self._stub_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.argv = providers.get("codex").command("gpt-5.6-terra")

    def _stub_path(self, name: str) -> str:
        self.asked.append(name)
        return f"{STUB_BIN}/{name}"

    def test_global_flags_stand_before_exec_and_subcommand_flags_after(self):
        """Ловит мутацию: флаги собраны одним списком после `exec` («так
        читается ровнее») — 0.155.1 разбирает глобальные флаги только ДО
        подкоманды, и шаг падал бы разбором аргументов либо, хуже, молча
        терял бы выключение функций."""
        at = self.argv.index("exec")

        for flag in ("--disable", "-c"):
            with self.subTest(flag=flag):
                positions = [i for i, a in enumerate(self.argv) if a == flag]
                self.assertTrue(positions, flag)
                self.assertLess(max(positions), at, self.argv)
        for flag in ("--json", "--sandbox", "--ephemeral", "--ignore-rules",
                     "-m"):
            with self.subTest(flag=flag):
                positions = [i for i, a in enumerate(self.argv) if a == flag]
                self.assertTrue(positions, flag)
                self.assertGreater(min(positions), at, self.argv)

    def test_argv_carries_the_resolved_tool_model_sandbox_and_stdin_prompt(self):
        """Ловит мутацию: argv[0] оставлен литералом `codex` (по PATH роли
        нашёлся бы одноимённый бинарник соседнего инструмента, инцидент
        06.09) либо спрошен на имя `claude`; либо промпт перестал идти со
        стандартного входа и текст задачи уехал в argv (а с ним — в
        вывод `ps` машины Оператора)."""
        self.assertEqual(self.asked, ["codex"])
        self.assertEqual(self.argv[0], f"{STUB_BIN}/codex")
        self.assertEqual(self.argv[-1], "-")
        self.assertIn("workspace-write", self.argv)
        self.assertEqual(
            self.argv[self.argv.index("-m") + 1], "gpt-5.6-terra")
        self.assertNotIn("-C", self.argv)
        self.assertNotIn("--ignore-user-config", self.argv)

    def test_every_disabled_feature_of_the_curated_home_is_in_the_command(self):
        """Ловит мутацию: список выключаемых функций набран частично
        («браузерные и так не нужны») — уцелевшая `computer_use` тем же
        путём, что и в живом запуске 0.155.1, позвала бы MCP-сервер и
        полезла открывать браузер на машине Оператора."""
        pairs = [(self.argv[i], self.argv[i + 1])
                 for i in range(len(self.argv) - 1)]

        missing = [f for f in codex_provider.DISABLED_FEATURES
                   if ("--disable", f) not in pairs]

        self.assertEqual(missing, [], self.argv)
        self.assertEqual(len(codex_provider.DISABLED_FEATURES), 11)

    def test_overrides_repeat_the_curated_config_pair_for_pair(self):
        """Ловит мутацию: `config.toml` поправили (переименовали ключ,
        сменили значение), а команду шага — нет; половинки изоляции
        разъезжаются молча, и роль идёт с сетью песочницы, включённой
        ровно там, где дом роли обещает её выключенной."""
        curated = _toml_pairs(
            (providers.get("codex").home_reference().reference
             / "config.toml").read_text(encoding="utf-8"))

        overrides = [self.argv[i + 1] for i, a in enumerate(self.argv)
                     if a == "-c"]

        self.assertEqual(len(overrides), len(codex_provider.CONFIG_OVERRIDES))
        for item in overrides:
            key, _, value = item.partition("=")
            with self.subTest(key=key):
                self.assertIn(key, curated)
                self.assertEqual(curated[key], value.lower())


class CuratedHomeTest(unittest.TestCase):
    """Курируемый дом роли — требование 5."""

    def reference(self) -> Path:
        return providers.get("codex").home_reference().reference

    def test_config_toml_carries_no_model_and_no_mcp_server(self):
        """Ловит мутацию: в дом роли переехал ключ выбора модели («чтобы
        не забыть») — модель шага задаёт ярус локального слоя и флаг
        `-m`, и файл начал бы молча перебивать выбор пульта; либо в дом
        роли вернулся MCP-сервер — ровно тот вектор, которым живой
        запуск 0.155.1 позвал `cua_repl`."""
        text = (self.reference() / "config.toml").read_text(encoding="utf-8")
        pairs = _toml_pairs(text)

        leaves = {key.rsplit(".", 1)[-1] for key in pairs}
        self.assertNotIn("model", leaves, pairs)
        self.assertEqual([k for k in pairs if "mcp_server" in k.lower()], [])
        self.assertEqual(
            [line for line in text.splitlines()
             if line.strip().startswith("[") and "mcp" in line.lower()], [])

    def test_every_disabled_feature_is_false_in_the_curated_config(self):
        """Ловит мутацию: из `config.toml` пропала (переименована,
        переключена в `true`) хотя бы одна из одиннадцати функций —
        курируемый дом роли перестаёт нести запрет, ради которого заведён,
        а шапка самого файла и `docs/stack.md` продолжают утверждать, что
        совпадение половин сверяет тест (REVIEW.md итерации 1, R1-F2:
        единственной проверкой этого свойства была приёмочная планка,
        уходящая вместе с каталогом задачи)."""
        pairs = _toml_pairs(
            (self.reference() / "config.toml").read_text(encoding="utf-8"))

        for feature in codex_provider.DISABLED_FEATURES:
            with self.subTest(feature=feature):
                self.assertEqual(pairs.get(f"features.{feature}"), "false",
                                 pairs)
        self.assertEqual([key for key, value in pairs.items()
                          if value == "true"], [], pairs)

    def test_curated_config_repeats_the_command_overrides_pair_for_pair(self):
        """Ловит мутацию: пара `-c`-переопределения переименована в
        команде шага, а дом роли остался прежним (или наоборот) — сверка
        AC-5 шла только со стороны команды, и правка одного лишь
        `config.toml` обеих половин не рассорила бы."""
        pairs = _toml_pairs(
            (self.reference() / "config.toml").read_text(encoding="utf-8"))

        for key, value in codex_provider.CONFIG_OVERRIDES:
            with self.subTest(key=key):
                self.assertEqual(pairs.get(key), value.lower(), pairs)

    def test_agents_md_explains_the_home_and_not_a_step_task(self):
        """Ловит мутацию: файл заведён заглушкой или скопирован у Claude
        без правки адресов — роль на Codex читает объяснение про чужой
        дом и чужой канал секрета."""
        text = (self.reference() / "AGENTS.md").read_text(encoding="utf-8")

        for marker in (".artel/home", "эфемер", "chatgpt", ".codex"):
            with self.subTest(marker=marker):
                self.assertIn(marker.lower(), text.lower())
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", text)
        # Канал ключа API убран из пульта (SPEC
        # 01M3EKCZJY9NGCW6VT878RX9JZ, требование 6): дом роли, который
        # продолжал бы обещать секрет переменной окружения, отправлял бы
        # роль искать причину отказа не там.
        self.assertNotIn("OPENAI_API_KEY", text)


class EnvironmentTest(TmpRootTest):
    """Окружение процесса роли — требование 4."""

    def setUp(self):
        super().setUp()
        self.slots = []
        patcher = mock.patch.object(keychain, "token", self._spy)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _spy(self, slot):
        self.slots.append(slot)
        return KEYCHAIN_SECRET

    def test_home_and_codex_home_overwrite_ambient_values(self):
        """Ловит мутацию: дом роли поставлен `setdefault`-ом «как токен»
        — роль наследует каталог конфига Оператора вместе с его
        MCP-серверами и правилами, то есть ровно ту конфиг-инъекцию, от
        которой дом роли и заводится."""
        _drop_ambient(self, *FORBIDDEN_KEY_NAMES)
        deployed = config.ROLE_HOME / ".codex"

        with mock.patch.dict(os.environ, {"CODEX_HOME": ALIEN_HOME,
                                          "HOME": ALIEN_HOME}):
            env = providers.get("codex").environment("developer", "T1")

        self.assertEqual(env["CODEX_HOME"], str(deployed))
        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertTrue(deployed.is_dir(), list(config.ROLE_HOME.rglob("*")))

    def test_environment_is_only_the_role_home_and_never_asks_the_keychain(self):
        """Ловит мутацию: ключ перестал попадать в окружение, но слот
        keychain по-прежнему читается «на всякий случай» — добытое значение
        либо кладётся под другим именем, либо добывается впустую, и шаг
        снова несёт секрет, которого требование 2 ему не даёт.

        Сверяется полный СОСТАВ окружения, а не отсутствие одного имени:
        роль на Codex авторизуется входом по подписке, и `HOME`/`CODEX_HOME`
        — единственное, что провайдер шагу передаёт.
        """
        _drop_ambient(self, *FORBIDDEN_KEY_NAMES, *CLAUDE_SECRETS)

        env = providers.get("codex").environment("developer", "T1")

        self.assertEqual(set(env), {"HOME", "CODEX_HOME"}, env)
        self.assertEqual(self.slots, [], "слот keychain спрошен провайдером")
        self.assertEqual(tuple(providers.get("codex").secret_env_names()), ())

    def test_no_api_key_name_reaches_the_step_whatever_the_ambient_value(self):
        """Ловит мутацию: канал ключа вернулся под другим именем —
        `CODEX_API_KEY` («тот, который `codex exec` и читает», факт живой
        проверки 22.09) или `CODEX_ACCESS_TOKEN`. Проверка на одно
        `OPENAI_API_KEY` пропустила бы ровно тот канал, которым ключ и
        подействовал бы на шаг.

        Ambient-значения заданы всем трём именам: провайдер обязан не
        пропускать их дальше НЕЗАВИСИМО от окружения Оператора.
        """
        _drop_ambient(self, *FORBIDDEN_KEY_NAMES)
        ambient = {name: AMBIENT_KEY for name in FORBIDDEN_KEY_NAMES}

        with mock.patch.dict(os.environ, ambient):
            env = providers.get("codex").environment("developer", "T1")

        self.assertEqual(self.slots, [], "keychain спрошен провайдером")
        for name in FORBIDDEN_KEY_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(name, env)
        self.assertNotIn(AMBIENT_KEY, set(env.values()), env)


class StepEnvironmentAllowlistTest(TmpRootTest):
    """Белый список манифеста и СОБРАННОЕ окружение шага — требование 3,
    AC-4 (REVIEW.md итерации 1, R1-F3).

    Свойство держится здесь, а не только приёмочной планкой задачи: CI
    гоняет `pytest tests` и каталогов `tasks/*/acceptance_tests` не
    трогает, так что планка закрытой задачи возврат имени в белый список
    уже не заметит.
    """

    def setUp(self):
        super().setUp()
        _drop_ambient(self, *FORBIDDEN_KEY_NAMES, *CLAUDE_SECRETS)
        patcher = mock.patch.object(keychain, "token", lambda slot: "tok-test")
        patcher.start()
        self.addCleanup(patcher.stop)

    def step_env(self, provider_name: str) -> dict:
        """Окружение шага, собранное РЕАЛЬНОЙ точкой пульта
        (`runner.role_env`), с исполнителем шага `provider_name`."""
        provider = providers.get(provider_name)
        with mock.patch.object(providers, "for_role", lambda role=None: provider):
            return runner.role_env("developer", "T1")

    def test_no_api_key_name_is_in_the_allowlist_or_in_either_step_env(self):
        """Ловит мутацию: `OPENAI_API_KEY` убран из белого списка, а взамен
        дописан `CODEX_API_KEY` — «тот, который `codex exec` и читает»
        (факт живой проверки 22.09). Список общий на пульт, поэтому такая
        замена возвращает ключ Оператора в окружение КАЖДОГО шага, включая
        шаг роли на Claude, — ровно та утечка, которую требование 3
        закрывает. Проверяются обе половины: сам список (с его префиксами)
        и собранное `runner.role_env` на обоих провайдерах при всех трёх
        заданных ambient-переменных.
        """
        prefixes = tuple(stack.ROLE_ENV_ALLOWLIST_PREFIXES)
        for name in FORBIDDEN_KEY_NAMES:
            with self.subTest(name=name, where="белый список"):
                self.assertNotIn(name, stack.ROLE_ENV_ALLOWLIST)
                self.assertFalse(name.startswith(prefixes), prefixes)

        ambient = {name: AMBIENT_KEY for name in FORBIDDEN_KEY_NAMES}
        for provider_name in ("codex", "claude"):
            with mock.patch.dict(os.environ, ambient):
                env = self.step_env(provider_name)

            for name in FORBIDDEN_KEY_NAMES:
                with self.subTest(provider=provider_name, name=name):
                    self.assertNotIn(name, env)
            self.assertNotIn(AMBIENT_KEY, set(env.values()), provider_name)


class RoleHomeDeploymentTest(TmpRootTest):
    """Развёртывание и сверка ДВУХ домов роли — требование 5."""

    def seed(self, provider_name: str, file_name: str) -> Path:
        reference = providers.get(provider_name).home_reference().reference
        reference.mkdir(parents=True, exist_ok=True)
        path = reference / file_name
        path.write_text("# курируемый слой\n", encoding="utf-8")
        return path

    def warns(self) -> list:
        checks = [doctor.check_role_home_reference()]
        checks += [p.check_home_reference()
                   for p in providers.PROVIDERS.values()]
        return [c for c in checks if c.status == "warn"]

    def test_both_homes_are_deployed_and_either_drift_is_noticed(self):
        """Ловит мутацию: развёртывание и сверка по-прежнему спрашивают
        только провайдера по умолчанию — второй дом либо не
        разворачивается, либо разворачивается, но его расхождение с
        референсом никто не замечает: Оператор правит
        `.artel/home/.codex/config.toml` руками, изоляция роли тихо
        разъезжается с обещанием репозитория, а `doctor` зелен."""
        self.seed("claude", "CLAUDE.md")
        self.seed("codex", "AGENTS.md")

        self.capture(catalog.cmd_init)

        deployed = config.ROLE_HOME / ".codex"
        self.assertTrue((config.ROLE_HOME / ".claude").is_dir())
        self.assertTrue(deployed.is_dir())
        self.assertEqual(self.warns(), [])

        (deployed / "AGENTS.md").write_text("# правка\n", encoding="utf-8")

        drifted = self.warns()
        self.assertTrue(drifted, "расхождение дома codex не замечено")
        self.assertTrue(any(".codex" in c.detail for c in drifted),
                        [c.detail for c in drifted])


class PreflightTest(TmpRootTest):
    """Предполётный набор провайдера — требование 12."""

    def setUp(self):
        super().setUp()
        _drop_ambient(self, *FORBIDDEN_KEY_NAMES, *CLAUDE_SECRETS)
        self.patch(keychain, "token", lambda slot: KEYCHAIN_SECRET)
        self.patch(doctor.shutil, "which", self._which)
        self.patch(runner, "declared_tool_path", lambda name: f"{STUB_BIN}/{name}")
        self.runs = _LoginStatusRuns(codex_version="0.150.0")
        self.patch(doctor.subprocess, "run", self.runs)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _which(self, name, *args, **kwargs):
        return f"{STUB_BIN}/{name}"

    def test_four_checks_with_own_names_hide_the_secret(self):
        """Ловит мутацию: набор собран переиспользованием проверок Claude
        — имена совпадают, склейка `provider_preflight_checks` схлопывает
        их как дубли, и отсутствие `codex` или невыполненный вход исчезает
        за зелёной строкой Claude; либо текст проверки авторизации несёт
        вывод `codex login status`, и состояние аутентификации уезжает в
        лог `doctor`."""
        checks = providers.get("codex").preflight("developer")

        self.assertEqual([c.name for c in checks],
                         ["codex-cli-found", "codex-cli-version",
                          doctor.CODEX_AUTH_CHECK, "codex-role-home"])
        claude_names = {c.name
                        for c in providers.default().preflight("developer")}
        self.assertEqual(set(c.name for c in checks) & claude_names, set())
        for check in checks:
            with self.subTest(check=check.name):
                self.assertNotIn(KEYCHAIN_SECRET, check.detail)
                self.assertNotIn(STATUS_MARKER, check.detail)
                self.assertNotIn(NOISE_MARKER, check.detail)

    def test_cli_version_below_the_minimum_warns_and_names_both_numbers(self):
        """Ловит мутацию: версия сверяется с пином Claude
        (`config.CLI_VERSION_PIN`) либо занижение отмечается `ok` —
        Оператор не узнаёт, что установленный Codex старше минимума, на
        котором держатся флаги команды шага."""
        check = providers.get("codex").check_cli_version()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("0.150.0", check.detail)
        self.assertIn("0.155.1", check.detail)

    def auth_check(self, **kwargs):
        """Строка авторизации на подменённом `codex login status`."""
        runs = _LoginStatusRuns(**kwargs)
        with mock.patch.object(doctor.subprocess, "run", runs):
            check = providers.get("codex").check_token("developer")
        return check, runs

    def test_login_status_is_called_with_the_role_home_and_the_step_overrides(self):
        """Ловит мутацию: вызов собран без окружения дома роли (CLI читает
        `~/.codex` Оператора и отвечает про ЛИЧНЫЙ вход) либо без пар
        авторизации — тогда `codex login status` отвечает про способ входа,
        отличный от того, каким пойдёт шаг, и зелёная строка `doctor`
        доказывает не то, что нужно. Вторая мутация: вызов без `timeout=` —
        висящий CLI держит предполёт шага бесконечно."""
        deployed = config.ROLE_HOME / ".codex"
        step_argv = providers.get("codex").command()

        check, runs = self.auth_check()

        self.assertEqual(check.status, "ok", check.detail)
        self.assertEqual(len(runs.login_calls), 1, runs.login_calls)
        argv, kwargs = runs.login_calls[0]
        self.assertEqual(Path(argv[0]).name, "codex", argv)
        self.assertLess(argv.index("login"), argv.index("status"), argv)
        for key, value in codex_provider.AUTH_OVERRIDES:
            with self.subTest(key=key):
                self.assertIn(f"{key}={value}", argv, argv)
                self.assertIn(f"{key}={value}", step_argv, step_argv)
                self.assertLess(argv.index(f"{key}={value}"),
                                argv.index("login"), argv)
        self.assertEqual(kwargs.get("env", {}).get("HOME"),
                         str(config.ROLE_HOME))
        self.assertEqual(kwargs.get("env", {}).get("CODEX_HOME"), str(deployed))
        self.assertGreater(kwargs.get("timeout") or 0, 0, kwargs)

    def test_ok_needs_both_a_zero_exit_code_and_a_confirmed_chatgpt_login(self):
        """Ловит мутацию: вердикт считается по одному коду выхода —
        `codex login status` отвечает нулём и на «Not logged in», и на вход
        ключом API (тот самый ключ без баланса, с которым живой запуск
        22.09 получил 401), и зелёная строка `doctor` доказывала бы
        авторизацию, которой у шага нет."""
        ok, _ = self.auth_check(status=LOGGED_IN_CHATGPT)
        self.assertEqual(ok.status, "ok", ok.detail)

        for title, kwargs in (
                ("ненулевой код выхода", {"returncode": 1}),
                ("код 0, вход не выполнен", {"status": NOT_LOGGED_IN}),
                ("код 0, вход ключом API", {"status": LOGGED_IN_API_KEY}),
                ("таймаут", {"raises": subprocess.TimeoutExpired(
                    cmd="codex", timeout=1)}),
                ("CLI не запустился", {"raises": OSError("нет такого файла")})):
            with self.subTest(scenario=title):
                check, _ = self.auth_check(**kwargs)

                self.assertEqual(check.status, "fail", check.detail)

    def test_the_confirmation_is_read_from_the_stream_the_cli_really_prints_to(self):
        """Ловит мутацию: подтверждение входа ищется в ОДНОМ потоке —
        именно это и было в итерации 1 (REVIEW.md, R1-F1): читался
        `stdout`, а настоящий 0.155.1 печатает результат `login status` в
        `stderr` (rc=0, stdout пуст, stderr='Logged in using ChatGPT'), и
        вошедший дом роли получал `fail` с рецептом «войдите» — то есть
        `ok` был недостижим, а предполёт блокировал КАЖДЫЙ шаг роли на
        Codex. Зеркальная мутация (читать только `stderr`) ловится тем же
        перебором: вендор вправе вернуть вывод в `stdout`, как уже делает
        `codex --version`.

        Вторая мутация: потоки склеиваются в один текст без границ строк —
        `Logged in using an API key` в одной строке и `ChatGPT` в другой
        начинают вместе давать `ok`, то есть вход ключом API засчитывается
        за подписочный.
        """
        for stream in ("stderr", "stdout"):
            with self.subTest(stream=stream):
                check, runs = self.auth_check(status=LOGGED_IN_CHATGPT,
                                              stream=stream)

                self.assertEqual(check.status, "ok", check.detail)
                self.assertEqual(len(runs.login_calls), 1)

        crossed = self.auth_check(
            status=LOGGED_IN_API_KEY, stream="stdout",
            noise=f"{NOISE_MARKER}: run `codex login` to use ChatGPT")[0]
        self.assertEqual(crossed.status, "fail", crossed.detail)

    def test_every_failure_hides_the_cli_output_and_names_both_operator_steps(self):
        """Ловит мутацию: причину отказа берут прямо из вывода CLI («так
        Оператору понятнее») — `codex login status` печатает адрес связки
        ключей и состояние авторизации, и строка `doctor` начинает выносить
        сведения об аутентификации в лог. Вторая мутация: рецепт приписан
        только к исходу «не вошёл», а таймаут и незапустившийся CLI
        отказывают без него — Оператор получает красную строку без того
        шага, которого не хватает (без указателя связки ключей вход не
        сохраняется вовсе, живая проверка 22.09)."""
        scenarios = ({}, {"returncode": 1}, {"status": NOT_LOGGED_IN},
                     {"status": LOGGED_IN_API_KEY},
                     {"raises": subprocess.TimeoutExpired(cmd="codex",
                                                          timeout=1)},
                     {"raises": OSError("нет такого файла")})

        for kwargs in scenarios:
            check, _ = self.auth_check(**kwargs)
            with self.subTest(status=check.status, detail=check.detail[:40]):
                self.assertNotIn(STATUS_MARKER, check.detail)
                self.assertNotIn(NOISE_MARKER, check.detail)
                if check.status == "fail":
                    self.assertIn("default-keychain", check.detail)
                    self.assertIn("codex login", check.detail)

    def test_the_auth_check_is_not_wired_into_the_general_doctor_set(self):
        """Ловит мутацию: проверка подключена к общему набору `doctor`
        (`all_checks`) вместо предполёта провайдера — КАЖДЫЙ прогон
        диагностики на пульте без Codex платит подпроцессом
        `codex login status` и печатает красную строку про авторизацию
        инструмента, которым никто не пользуется."""
        import inspect

        source = inspect.getsource(doctor.all_checks)

        self.assertNotIn("chatgpt", source.lower())
        self.assertNotIn(doctor.CODEX_AUTH_CHECK, source)

    def test_a_pult_without_a_codex_role_gets_neither_the_line_nor_the_call(self):
        """То же свойство ПОВЕДЕНИЕМ, а не текстом исходника (REVIEW.md
        итерации 1, R1-F3): сверка `inspect.getsource` выше слепа к
        подключению проверки через провайдера или переменную — имени в
        исходнике `all_checks` такая правка не оставит.

        Ловит мутацию: строка авторизации приходит не из
        `CodexProvider.preflight`, а из общего набора или из предполёта
        шага любой роли — пульт, где ни одна agent-роль не идёт на
        `codex`, начинает платить подпроцессом `codex login status` на
        каждый прогон и печатать красную строку про инструмент, которым
        никто не пользуется.

        Контроль вырожденности — вторая половина сценария: роль НА CODEX
        обе строки получает, и вызов CLI ровно один.
        """
        self.assertNotIn("codex", {providers.name_for_role(role)
                                   for role in doctor.agent_roles()})

        grouped = doctor.provider_preflight_checks()
        step = doctor.preflight_checks("developer", config.DEFAULT_TARGET)

        self.assertNotIn(doctor.CODEX_AUTH_CHECK, grouped, sorted(grouped))
        self.assertNotIn(doctor.CODEX_AUTH_CHECK, [c.name for c in step])
        self.assertEqual(self.runs.login_calls, [], self.runs.login_calls)
        self.assertEqual([argv for argv in self.runs.calls
                          if "codex" in " ".join(argv)], [], self.runs.calls)

        codex = providers.get("codex")
        with mock.patch.object(providers, "for_role", lambda role=None: codex):
            on_codex = doctor.preflight_checks("developer",
                                               config.DEFAULT_TARGET)

        self.assertIn(doctor.CODEX_AUTH_CHECK, [c.name for c in on_codex])
        self.assertEqual(len(self.runs.login_calls), 1, self.runs.login_calls)


class ModelVerdictTest(TmpRootTest):
    """Вердикт совместимости модели — требование 7."""

    CATALOG = """providers:
  claude:
    cli: claude
    min_cli_version: 1.0.0
    cost_from_cli: true
    models:
      claude-opus-5:
        min_cli_version: 1.0.0
        status: supported
        list_price_usd_per_mtok:
          input: 5.0
          output: 25.0
          cache_write: 6.25
          cache_read: 0.50
        price_date: 2026-09-21
  codex:
    cli: codex
    min_cli_version: 0.155.1
    cost_from_cli: false
    models:
      gpt-5.6-terra:
        min_cli_version: 0.155.1
        status: experimental
        list_price_usd_per_mtok:
          input: 2.0
          output: 12.0
          cache_write: 2.0
          cache_read: 0.20
        price_date: 2026-09-21
"""

    def setUp(self):
        super().setUp()
        path = self.root / "models.yaml"
        path.write_text(self.CATALOG, encoding="utf-8")
        patcher = mock.patch.object(config, "MODELS", path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.asked = []

    def verdict(self, model: str, codex_version: str):
        def fake_run(args, **kwargs):
            name = Path(str(args[0])).name
            self.asked.append(name)
            text = codex_version if name == "codex" else "9.9.9"
            return subprocess.CompletedProcess(list(args), 0, f"{text}\n", "")

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run):
            return providers.get("codex").model_verdict(model)

    def test_version_is_asked_of_codex_and_the_minimum_comes_from_the_catalog(self):
        """Ловит мутацию: `model_verdict` унаследован у Claude как есть и
        зовёт зеро-арг `stack.installed_cli_version()` — тот спрашивает
        `claude --version`, и модель Codex получает вердикт по версии
        чужого CLI: свежий Claude при древнем Codex даёт зелёный
        предполёт и провал попытки за деньги."""
        fresh = self.verdict("gpt-5.6-terra", "0.156.0")

        self.assertEqual(fresh.status, "ok", fresh.detail)
        self.assertEqual(self.asked, ["codex"])

        stale = self.verdict("gpt-5.6-terra", "0.150.0")

        self.assertEqual(stale.status, "fail", stale.detail)
        self.assertIn(stack.MODEL_UNSUPPORTED_PREFIX, stale.detail)
        self.assertIn("codex ≥ 0.155.1", stale.detail)

    def test_model_outside_the_catalog_fails_without_probing_the_cli(self):
        """Ловит мутацию: модель вне каталога запускается «как есть» либо
        ради заведомого отказа всё равно заводится подпроцесс
        `codex --version`."""
        verdict = self.verdict("gpt-takoy-modeli-net", "0.156.0")

        self.assertEqual(verdict.status, "fail", verdict.detail)
        self.assertIn("gpt-takoy-modeli-net", verdict.detail)
        self.assertEqual(self.asked, [])


class LiveSmokeTest(TmpRootTest):
    """Живой смок — требование 12."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(runner, "declared_tool_path",
                                    lambda name: f"{STUB_BIN}/{name}")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_command_reuses_the_step_binary_and_passes_the_prompt_as_an_argument(self):
        """Ловит мутацию: смок собран на литерале `codex` вместо argv[0]
        команды шага — проверялась бы живость тёзки с PATH, а не того
        бинарника, который реально исполнит шаг (инцидент 06.09); либо
        промпт остался на стандартном входе, и смок висел бы, ожидая
        закрытия stdin."""
        provider = providers.get("codex")

        argv = provider.live_smoke_command("проверка")

        self.assertEqual(argv[0], provider.command()[0])
        self.assertIn("--json", argv)
        self.assertIn("--skip-git-repo-check", argv)
        self.assertEqual(argv[-1], "проверка")

    def test_doctor_skips_the_live_smoke_without_building_argv(self):
        """Ловит мутацию: живой смок второго провайдера попал в обычный
        `doctor` — каждый прогон диагностики начинает платить деньги за
        вызов платного CLI; либо `skip` заводит инцидент в `alerts`,
        и «проверка не выполнялась» становится неотличимой от провала."""
        calls = []
        self.assertFalse(providers.get("codex").live_smoke_in_doctor)
        self.assertTrue(providers.default().live_smoke_in_doctor)

        with mock.patch.object(type(providers.get("codex")),
                               "live_smoke_command",
                               lambda self, prompt: calls.append(prompt)), \
                mock.patch.object(providers, "for_role",
                                  lambda role: providers.get("codex")):
            check = doctor._live_smoke_run("developer")

        self.assertEqual(check.status, "skip", check.detail)
        self.assertEqual(calls, [])


class IsolationSmokeTest(TmpRootTest):
    """Офлайн-смок изоляции — требование 12."""

    def setUp(self):
        super().setUp()
        _drop_ambient(self, "CODEX_HOME", *FORBIDDEN_KEY_NAMES, *CLAUDE_SECRETS)
        patcher = mock.patch.object(keychain, "token", lambda slot: "tok")
        patcher.start()
        self.addCleanup(patcher.stop)
        tools = mock.patch.object(runner, "declared_tool_path",
                                  lambda name: f"{STUB_BIN}/{name}")
        tools.start()
        self.addCleanup(tools.stop)
        self.healthy = providers.get("codex").command()
        self.provider_class = type(providers.get("codex"))

    def crippled(self, argv):
        with mock.patch.object(self.provider_class, "command",
                               lambda self, model=None: list(argv)):
            return doctor.codex_isolation_smoke("developer")

    def test_green_on_the_regular_command_and_red_on_each_missing_piece(self):
        """Ловит мутацию: смок сверяет изоляцию по СВОЕЙ копии списка
        флагов (константа рядом с проверкой), а не по реально собранной
        команде шага — выломанный из `command()` флаг смок не замечает, и
        Оператор читает зелёную строку про изоляцию, которой у шага уже
        нет."""
        healthy = doctor.codex_isolation_smoke("developer")
        self.assertEqual(healthy.status, "ok", healthy.detail)

        no_sandbox = self.crippled(
            [a for a in self.healthy if a != "workspace-write"])
        self.assertEqual(no_sandbox.status, "fail", no_sandbox.detail)
        self.assertIn("workspace-write", no_sandbox.detail)

        no_network = self.crippled(
            [a for a in self.healthy
             if codex_provider.NETWORK_ACCESS_KEY not in a])
        self.assertEqual(no_network.status, "fail", no_network.detail)
        self.assertIn("сет", no_network.detail.lower())

        no_feature = self.crippled(
            [a for a in self.healthy if a != "computer_use"])
        self.assertEqual(no_feature.status, "fail", no_feature.detail)
        self.assertIn("computer_use", no_feature.detail)

    def test_any_api_key_name_in_the_step_env_is_a_named_failure(self):
        """Ловит мутацию: проверка написана на одно имя (`OPENAI_API_KEY` —
        то, которое убрали из белого списка), а `CODEX_API_KEY`/
        `CODEX_ACCESS_TOKEN` не смотрит. Живая проверка 22.09 показала, что
        `codex exec` читает именно `CODEX_API_KEY`, — незамеченным остался
        бы ровно тот канал, которым ключ и подействовал бы на шаг. Вторая
        мутация: провал печатает ЗНАЧЕНИЕ найденной переменной, и ключ
        Оператора уезжает в лог `doctor`."""
        deployed = config.ROLE_HOME / ".codex"

        def leaky_with(extra):
            def environment(inner_self, role=None, task_id=None):
                env = {"HOME": str(config.ROLE_HOME),
                       "CODEX_HOME": str(deployed)}
                env.update(extra)
                return env
            return environment

        clean = doctor.codex_isolation_smoke("developer")
        self.assertNotEqual(clean.status, "fail", clean.detail)

        for name in FORBIDDEN_KEY_NAMES:
            with self.subTest(name=name):
                with mock.patch.object(self.provider_class, "environment",
                                       leaky_with({name: AMBIENT_KEY})):
                    check = doctor.codex_isolation_smoke("developer")

                self.assertEqual(check.status, "fail", check.detail)
                self.assertIn(name, check.detail)
                self.assertNotIn(AMBIENT_KEY, check.detail)

    def test_a_key_name_returned_to_the_allowlist_turns_the_smoke_red(self):
        """Ловит мутацию: пятый пункт смока смотрит НАКЛАДКУ провайдера
        (`provider.environment`), а не собранное окружение шага — ровно то,
        что было в итерации 1 (REVIEW.md, R1-F2). После требования 3
        единственный живой канал ключа — общий белый список манифеста:
        имя, дописанное в `stack.ROLE_ENV_ALLOWLIST` следующей задачей
        линии или правкой «по аналогии», едет в окружение КАЖДОГО шага,
        включая шаг Codex, а смок оставался бы зелёным — при том, что
        `docs/stack.md` и `AGENTS.md` дома роли обещают Оператору красную
        строку.

        Метод провайдера здесь НЕ подменяется намеренно: сценарий обязан
        ломаться от правки белого списка, иначе он проверяет заглушку, а
        не канал.
        """
        for name in FORBIDDEN_KEY_NAMES:
            with self.subTest(name=name):
                with mock.patch.dict(
                        stack.ROLE_ENV_ALLOWLIST,
                        {name: "ключ API, вернувшийся в белый список"}), \
                        mock.patch.dict(os.environ, {name: AMBIENT_KEY}):
                    check = doctor.codex_isolation_smoke("developer")

                self.assertEqual(check.status, "fail", check.detail)
                self.assertIn(name, check.detail)
                self.assertNotIn(AMBIENT_KEY, check.detail)

    def test_inherited_ambient_home_is_red(self):
        """Ловит мутацию: смок смотрит на окружение провайдера по
        умолчанию (или вовсе не смотрит) — ambient-дом, унаследованный
        шагом на Codex, остаётся невидимым, и роль исполняет конфиг
        Оператора."""
        def leaky(self, role=None, task_id=None):
            return {"HOME": os.environ.get("HOME", ""),
                    "CODEX_HOME": os.environ.get("CODEX_HOME", "")}

        with mock.patch.object(self.provider_class, "environment", leaky):
            check = doctor.codex_isolation_smoke("developer")

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("HOME", check.detail)

    def test_foreign_provider_secret_is_a_separate_yellow_line(self):
        """Ловит мутацию: чужой секрет в окружении шага под `codex`
        признан нормой («так задумано общим белым списком») и смок
        остаётся зелёным: сужение белого списка по провайдеру в эту
        задачу не входит, и молчание смока — единственное, чем факт
        утечки токена подписки в чужой CLI мог бы остаться
        незамеченным."""
        with mock.patch.dict(os.environ,
                             {"CLAUDE_CODE_OAUTH_TOKEN": "tok-chuzhoy"}):
            check = doctor.codex_isolation_smoke("developer")

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("CLAUDE_CODE_OAUTH_TOKEN", check.detail)
        self.assertNotIn("tok-chuzhoy", check.detail)

    def test_smoke_skips_when_the_tool_is_not_in_the_manifest(self):
        """Ловит мутацию: смок краснеет на пульте БЕЗ Codex — регистрация
        провайдера сама по себе начинает красить `doctor`, хотя ни один
        ярус на его модели не указывает (требование 6)."""
        def unresolved(name):
            raise KeyError(name)

        with mock.patch.object(runner, "declared_tool_path", unresolved):
            check = doctor.codex_isolation_smoke("developer")

        self.assertEqual(check.status, "skip", check.detail)

    def test_all_checks_carries_the_provider_smoke(self):
        """Ловит мутацию: смок написан, но не подключён к `all_checks` —
        `doctor` молчал бы о разъехавшейся изоляции Codex (тот же приём
        сверки подключения, что у `check_map_growth`/
        `check_pin_unpushed` в `tests/test_doctor.py`)."""
        import inspect

        source = inspect.getsource(doctor.all_checks)

        self.assertIn("provider_isolation_smokes", source)


class ForeignSecretCheckTest(TmpRootTest):
    """Секрет чужого провайдера в окружении шага — симметрия обеих
    сторон белого списка манифеста (REVIEW.md итерации 1, R1-F4)."""

    def setUp(self):
        super().setUp()
        _drop_ambient(self, *FORBIDDEN_KEY_NAMES, *CLAUDE_SECRETS)

    def test_the_openai_key_is_no_longer_named_for_a_claude_step(self):
        """Ловит мутацию: ключ убран из белого списка, но остался в
        `CodexProvider.secret_env_names()` — проверка чужих секретов
        перебирает имена секретов ДРУГИХ провайдеров, и жёлтая строка про
        утечку горела бы на пульте, где утечки уже нет: `doctor` просит
        Оператора чинить починенное. Ни одно из трёх имён ключа при этом не
        должно называться ни при каком ambient-значении, включая пустое."""
        ambient = {name: AMBIENT_KEY for name in FORBIDDEN_KEY_NAMES}

        for title, values in (("ключи заданы", ambient),
                              ("ключи пусты",
                               {n: "" for n in FORBIDDEN_KEY_NAMES})):
            with self.subTest(scenario=title):
                with mock.patch.dict(os.environ, values):
                    check = doctor.check_foreign_provider_secrets()

                self.assertEqual(check.status, "ok", check.detail)
                for name in FORBIDDEN_KEY_NAMES:
                    self.assertNotIn(name, check.detail)
                self.assertNotIn(AMBIENT_KEY, check.detail)

    def test_a_registered_secret_of_a_foreign_provider_is_still_a_yellow_line(self):
        """Ловит мутацию: механика жёлтой строки осиротела вместе с ключом
        OpenAI — «раз называть больше нечего, уберём и проверку». Реестр
        провайдеров открыт, и следующий исполнитель со своим секретом в
        общем белом списке обязан попадать в строку записью в реестр, а не
        правкой проверки.

        Секрет синтетический (имя и запись белого списка подменяются на
        время сценария): после требования 3 у сегодняшних двух провайдеров
        подходящей пары «имя Codex, стоящее в белом списке» не осталось, и
        сверять механику на фактическом состоянии реестра было бы нечем.
        """
        foreign = "ARTEL_TEST_FOREIGN_SECRET"
        codex_class = type(providers.get("codex"))

        with mock.patch.object(codex_class, "secret_env_names",
                               lambda inner: (foreign,)), \
                mock.patch.dict(stack.ROLE_ENV_ALLOWLIST,
                                {foreign: "синтетический секрет теста"}), \
                mock.patch.dict(os.environ, {foreign: AMBIENT_KEY}):
            check = doctor.check_foreign_provider_secrets()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn(foreign, check.detail)
        self.assertNotIn(AMBIENT_KEY, check.detail)

    def test_the_check_is_wired_into_all_checks(self):
        """Ловит мутацию: проверка написана, но не подключена к
        `all_checks` — про чужой секрет в шаге не сказал бы никто (тот же
        приём сверки подключения, что у `check_map_growth`)."""
        import inspect

        self.assertIn("check_foreign_provider_secrets",
                      inspect.getsource(doctor.all_checks))


if __name__ == "__main__":
    unittest.main()
