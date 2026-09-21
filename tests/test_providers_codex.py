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

    def test_agents_md_explains_the_home_and_not_a_step_task(self):
        """Ловит мутацию: файл заведён заглушкой или скопирован у Claude
        без правки адресов — роль на Codex читает объяснение про чужой
        дом и чужой канал секрета."""
        text = (self.reference() / "AGENTS.md").read_text(encoding="utf-8")

        for marker in (".artel/home", "эфемер", "OPENAI_API_KEY", ".codex"):
            with self.subTest(marker=marker):
                self.assertIn(marker.lower(), text.lower())
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", text)


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
        _drop_ambient(self, "OPENAI_API_KEY")
        deployed = config.ROLE_HOME / ".codex"

        with mock.patch.dict(os.environ, {"CODEX_HOME": ALIEN_HOME,
                                          "HOME": ALIEN_HOME}):
            env = providers.get("codex").environment("developer", "T1")

        self.assertEqual(env["CODEX_HOME"], str(deployed))
        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertTrue(deployed.is_dir(), list(config.ROLE_HOME.rglob("*")))

    def test_key_comes_from_its_own_slot_and_never_carries_a_foreign_secret(self):
        """Ловит мутацию: ключ берётся тем же вызовом, что подписочный
        токен Claude (`runner.role_token` по слотам `roles.yaml`) — оба
        провайдера начинают тянуть секрет из одного слота, и ключ OpenAI
        уходит в шаг под именем токена подписки."""
        _drop_ambient(self, "OPENAI_API_KEY", *CLAUDE_SECRETS)

        env = providers.get("codex").environment("developer", "T1")

        self.assertEqual(env["OPENAI_API_KEY"], KEYCHAIN_SECRET)
        self.assertEqual(self.slots, [config.OPENAI_API_KEY_SLOT])
        for name in CLAUDE_SECRETS:
            with self.subTest(name=name):
                self.assertNotIn(name, env)

    def test_ambient_key_is_stronger_than_the_slot(self):
        """Ловит мутацию: keychain спрашивается безусловно — заданный
        Оператором ambient-ключ перестаёт быть сильнее слота, и шаг идёт
        не под тем счётом, под которым Оператор его запускал."""
        _drop_ambient(self, "OPENAI_API_KEY")

        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": AMBIENT_KEY}):
            env = providers.get("codex").environment("developer", "T1")

        self.assertEqual(self.slots, [], "keychain спрошен при ambient-ключе")
        self.assertNotIn("OPENAI_API_KEY", env)


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
        _drop_ambient(self, "OPENAI_API_KEY", *CLAUDE_SECRETS)
        self.patch(keychain, "token", lambda slot: KEYCHAIN_SECRET)
        self.patch(doctor.shutil, "which", self._which)
        self.patch(doctor.subprocess, "run", self._run)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _which(self, name, *args, **kwargs):
        return f"{STUB_BIN}/{name}"

    def _run(self, args, **kwargs):
        name = Path(str(args[0])).name
        text = "0.150.0" if name == "codex" else config.CLI_VERSION_PIN
        return subprocess.CompletedProcess(list(args), 0, f"{text}\n", "")

    def test_four_checks_with_own_names_hide_the_secret(self):
        """Ловит мутацию: набор собран переиспользованием проверок Claude
        — имена совпадают, склейка `provider_preflight_checks` схлопывает
        их как дубли, и отсутствие `codex` или его ключа исчезает за
        зелёной строкой Claude; либо текст проверки ключа печатает сам
        секрет, и он уезжает в лог `doctor`."""
        checks = providers.get("codex").preflight("developer")

        self.assertEqual(len(checks), 4, [c.name for c in checks])
        claude_names = {c.name
                        for c in providers.default().preflight("developer")}
        self.assertEqual(set(c.name for c in checks) & claude_names, set())
        for check in checks:
            with self.subTest(check=check.name):
                self.assertNotIn(KEYCHAIN_SECRET, check.detail)
        key_line = [c for c in checks if c.name == "codex-api-key"]
        self.assertTrue(key_line)
        self.assertIn(config.OPENAI_API_KEY_SLOT, key_line[0].detail)

    def test_cli_version_below_the_minimum_warns_and_names_both_numbers(self):
        """Ловит мутацию: версия сверяется с пином Claude
        (`config.CLI_VERSION_PIN`) либо занижение отмечается `ok` —
        Оператор не узнаёт, что установленный Codex старше минимума, на
        котором держатся флаги команды шага."""
        check = providers.get("codex").check_cli_version()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("0.150.0", check.detail)
        self.assertIn("0.155.1", check.detail)

    def test_missing_key_is_a_blocking_check_naming_only_the_slot(self):
        """Ловит мутацию: отсутствие ключа трактуется предупреждением —
        шаг стартует, платит попыткой и падает на авторизации вместо
        бесплатного отказа до старта агента."""
        with mock.patch.object(keychain, "token", lambda slot: None):
            check = providers.get("codex").check_token("developer")

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(config.OPENAI_API_KEY_SLOT, check.detail)


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
        _drop_ambient(self, "CODEX_HOME", "OPENAI_API_KEY", *CLAUDE_SECRETS)
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


if __name__ == "__main__":
    unittest.main()
