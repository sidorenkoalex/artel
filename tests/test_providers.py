"""Юнит-тесты пакета `orchestrator/providers/` — интерфейса исполнителя
роли (SPEC 01M2ZNTHSNFYSTF904P6SZTPYF, требования 1-7).

Постоянная регрессия поверх приёмочной планки задачи
(`tasks/01M2ZNTHSNFYSTF904P6SZTPYF/acceptance_tests/`): та планка уходит
вместе с каталогом задачи, а свойство «один источник истины о том, что
нужно исполнителю роли» обязано пережить её. Здесь — реестр и дефолт
провайдера роли, неизменность argv/окружения шага, отказ по
незарегистрированному имени, инструмент манифеста, дом роли и строки
`doctor`.

Песочницы — общие (`tests/sandbox.py`), шаг роли — готовый
`_StepSandbox` из `tests/test_runner_model_preflight.py` (настоящий путь
`runner.cmd_run` с подменённым процессом агента), полный прогон
`doctor.all_checks` — готовая песочница `tests/test_doctor.py`, тем же
приёмом, каким тот файл переиспользует `tests/test_runner_role_model.py`.
"""
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (catalog, config, doctor, keychain, providers,  # noqa: E402
                          roles, runner, stack, store)
from orchestrator.providers import claude as claude_provider  # noqa: E402
from tests.sandbox import (TmpDirTest, TmpRootTest, claude_only_popen,  # noqa: E402
                           claude_only_run)
from tests.test_doctor import (FakeLiveSmokeProc,  # noqa: E402
                               TmpRootTest as DoctorSandbox, result_event)
from tests.test_runner_model_preflight import _StepSandbox  # noqa: E402
from tests.test_runner_role_model import _roles_yaml_text  # noqa: E402

UNKNOWN_PROVIDER = "provider-kotorogo-net"

# Ambient-канал токена: обе переменные входят в белый список манифеста
# (`stack.ROLE_ENV_ALLOWLIST`) и сильнее слота keychain, а в окружении
# прогона стоят по построению — внутри шага роли их кладёт туда сам
# пульт (`runner.role_env`). Тесты, чей предмет — слот, гасят их пустым
# значением, тем же приёмом, что `tests/test_doctor.py::
# _DoctorTmpRootTest`: иначе набор краснел бы на машине Оператора с
# заданным токеном без единого дефекта в коде (REVIEW.md итерации 1,
# R1-F1).
NO_AMBIENT_TOKEN = {"CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_API_KEY": ""}

# Хвост argv шага роли, зафиксированный ДО задачи (`runner.role_cmd()` на
# 20.09): значение `--setting-sources` — от крутилки Оператора, не
# литералом.
EXPECTED_ARGV_TAIL = [
    "-p", "--permission-mode", "acceptEdits",
    "--output-format", "stream-json", "--verbose",
    "--allowedTools", "Bash(git:*),Bash(python3:*)",
    "--setting-sources", config.AGENT_SETTING_SOURCES,
    "--strict-mcp-config",
]

ROLES_YAML = """roles:
  alfa:
    executor: agent
    token_slot: artel-alfa
    skills: [conventions-core]
    provider: {unknown}
  beta:
    executor: agent
    token_slot: artel-beta
    skills: [conventions-core]
  gamma:
    executor: agent
    token_slot: artel-gamma
    skills: [conventions-core]
    provider: 17

token_fallback: artel-token
""".format(unknown=UNKNOWN_PROVIDER)


class RegistryTest(unittest.TestCase):
    """Реестр `orchestrator/providers/__init__.py`."""

    def test_claude_is_registered_and_carries_the_interface(self):
        """Ловит мутацию: имя `claude` пропало из реестра либо под ним
        зарегистрирован объект без методов интерфейса — пульт остался бы
        без исполнителя, а подмена провайдера снова требовала бы правки
        ветвления вместо записи в словарь."""
        entry = providers.PROVIDERS[providers.DEFAULT_PROVIDER]

        self.assertIsInstance(entry, claude_provider.ClaudeProvider)
        self.assertIs(providers.get("claude"), entry)
        self.assertIs(providers.default(), entry)
        for method in ("command", "environment", "home_reference", "preflight",
                       "cli_tool", "model_verdict"):
            self.assertTrue(callable(getattr(entry, method, None)), method)

    def test_unknown_name_refuses_and_names_the_provider(self):
        """Ловит мутацию: неизвестное имя резолвится дефолтом
        (`PROVIDERS.get(name, claude)`) — шаг молча ушёл бы на `claude`
        вместо отказа; либо отказ безымянный, и Оператор не видит, какое
        имя чинить."""
        with self.assertRaises(providers.UnknownProviderError) as ctx:
            providers.get(UNKNOWN_PROVIDER)

        self.assertIn(UNKNOWN_PROVIDER, str(ctx.exception))

    def test_cli_tools_and_home_references_cover_the_registry(self):
        """Ловит мутацию: сводки для манифеста стека и развёртывания дома
        роли собираются по одному провайдеру (жёстко `claude`), а не по
        всему реестру — второй провайдер не попал бы ни в
        `REQUIRED_TOOLS`, ни в холодный старт."""
        self.assertEqual(sorted(providers.cli_tools()),
                         sorted(p.cli_tool().name
                                for p in providers.PROVIDERS.values()))
        self.assertEqual(len(providers.home_references()),
                         len(providers.PROVIDERS))


class RolesProviderTest(TmpDirTest):
    """`roles.provider(role)` на временной карте исполнителей."""

    def setUp(self):
        super().setUp()
        self.use_roles_text(ROLES_YAML)

    def use_roles_text(self, text: str) -> None:
        """Карта исполнителей под тестом: `config.ROLES` — файл с этим
        содержимым (патч снимается штатным cleanup, поэтому повторный
        вызов внутри теста подменяет карту поверх setUp)."""
        path = self.tdir / "roles-under-test.yaml"
        path.write_text(text, encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_field_value_wins_and_absent_field_defaults_to_claude(self):
        """Ловит мутацию: поле `provider:` не читается вовсе (всегда
        дефолт) — роль на другом CLI молча ушла бы на `claude`; либо
        отсутствие поля оформлено отказом/`None`, как у `roles.model`, —
        сегодняшний `roles.yaml` без поля останавливал бы каждый шаг."""
        self.assertEqual(roles.provider("alfa"), UNKNOWN_PROVIDER)
        self.assertEqual(roles.provider("beta"), providers.DEFAULT_PROVIDER)

    def test_unreadable_value_and_unknown_role_are_named_failures(self):
        """Ловит мутацию: значение не-строкой (число, bool) принимается
        как имя провайдера — отказ уехал бы в `KeyError` реестра вместо
        причины, называющей поле и роль."""
        for role in ("gamma", "delta"):
            with self.subTest(role=role):
                with self.assertRaises(roles.RolesError):
                    roles.provider(role)

    def test_for_role_degrades_to_the_default_for_an_unknown_role(self):
        """Ловит мутацию: `providers.for_role` роняет трейсбек на роли,
        которой в карте исполнителей нет, — сборка окружения (`role_env`,
        её зовёт и `doctor`) падала бы вместо своей, названной причины,
        которую шаг и так печатает раньше."""
        self.assertIs(providers.for_role("delta"), providers.default())
        self.assertIs(providers.for_role(None), providers.default())

    def test_for_role_degrades_to_the_default_on_an_unreadable_map(self):
        """Ловит мутацию: та же деградация, но на карте, которая НЕ
        РАЗОБРАНА или которой нет на диске (`RolesError` из `_document`,
        не из «роль не описана») — ветка, которой до REVIEW.md итерации 1
        (R1-F3) не касался ни один тест: `role_env()` падал бы трейсбеком
        разбора YAML там, где обязан отдать окружение провайдера по
        умолчанию.
        """
        # Блочный список — конструкция, которую `yamlmini` не разбирает.
        self.use_roles_text("roles:\n  - developer\n")
        with self.assertRaises(roles.RolesError):
            roles.provider("developer")
        self.assertIs(providers.for_role("developer"), providers.default())

        with mock.patch.object(config, "ROLES",
                               self.tdir / "net-takogo-fayla.yaml"):
            self.assertIs(providers.for_role("developer"), providers.default())

    def test_role_providers_does_not_degrade_on_an_unreadable_map(self):
        """Ловит мутацию: сводка «кто на чём идёт» собирается через
        `name_for_role` (с деградацией к дефолту) — `doctor` утверждал бы
        зелёной строкой «роль → claude» по карте, которую не смог
        прочитать (REVIEW.md итерации 1, R1-F2).
        """
        self.assertEqual(providers.role_providers(["beta"]),
                         [("beta", providers.DEFAULT_PROVIDER)])

        self.use_roles_text("roles:\n  - developer\n")
        with self.assertRaises(roles.RolesError):
            providers.role_providers(["developer"])


class StepCommandTest(TmpRootTest):
    """Argv шага роли — требования 5, 9 (байт-в-байт как до задачи)."""

    def test_role_cmd_matches_the_pre_task_argv(self):
        """Ловит мутацию: провайдер собрал команду заново и потерял или
        переставил флаг (`--strict-mcp-config`, `--verbose`,
        `--setting-sources`), либо argv[0] снова литерал `claude`, а не
        абсолютный путь резолва манифеста (затенение тёзкой, инцидент
        06.09)."""
        argv = runner.role_cmd()

        self.assertEqual(argv[1:], EXPECTED_ARGV_TAIL)
        self.assertEqual(argv[0], shutil.which("claude"))
        self.assertTrue(Path(argv[0]).is_absolute(), argv[0])

    def test_model_is_appended_by_the_provider_at_the_end(self):
        """Ловит мутацию: флаг модели вставлен в середину списка или
        подставляется в argv всегда (в том числе для роли без `model:`) —
        порядок флагов шага меняется, а роль без модели перестаёт идти
        на дефолт CLI."""
        provider = providers.default()

        self.assertEqual(provider.command("model-x")[-2:], ["--model", "model-x"])
        self.assertEqual(provider.command("model-x")[:-2], provider.command())
        self.assertNotIn("--model", provider.command())

    def test_role_cmd_is_the_command_of_the_registered_provider(self):
        """Ловит мутацию: `role_cmd()` снова собирает список литералами
        мимо реестра — подмена сборки у провайдера её не трогает, и
        офлайн-смок изоляции сверяет не ту команду, которой пойдёт
        шаг."""
        stub = ["/stub/cli", "-p"]
        with mock.patch.object(claude_provider.ClaudeProvider, "command",
                               lambda self, model=None: list(stub)):
            self.assertEqual(runner.role_cmd(), stub)


class StepEnvironmentTest(TmpRootTest):
    """Окружение шага роли — требования 5, 9 (AC-6)."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(keychain, "token", lambda slot: "tok-test")
        patcher.start()
        self.addCleanup(patcher.stop)
        env_patcher = mock.patch.dict(os.environ, NO_AMBIENT_TOKEN)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    def test_provider_part_sits_on_top_of_the_manifest_allowlist(self):
        """Ловит мутацию: провайдерская часть окружения собирается копией
        `os.environ` (весь мир Оператора течёт в шаг) либо теряет
        HOME/CLAUDE_CONFIG_DIR — роль исполнялась бы в user-слое
        Оператора (конфиг-инъекция, ADR-0003 п.14)."""
        leak = "ARTEL_TEST_MARKER_VNE_SPISKA"
        with mock.patch.dict(os.environ, {leak: "znachenie-Operatora"}):
            env = runner.role_env("developer", "01TESTTASK")

        self.assertEqual(env["HOME"], str(config.ROLE_HOME))
        self.assertEqual(env["CLAUDE_CONFIG_DIR"], str(config.ROLE_CONFIG_DIR))
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "tok-test")
        self.assertNotIn(leak, env)
        self.assertEqual(env[config.ARTEL_ROLE_ENV], "developer")
        self.assertEqual(env[config.ARTEL_TASK_ENV], "01TESTTASK")
        self.assertEqual(env["PATH"].split(os.pathsep)[0],
                         str(config.VENV_DIR / "bin"))

    def test_ambient_token_stays_stronger_than_the_keychain_slot(self):
        """Ловит мутацию: провайдер кладёт токен из keychain безусловно —
        заданный Оператором ambient-токен перестаёт быть сильнее слота, и
        шаг уходит не под тем аккаунтом, под которым Оператор его
        запускал."""
        with mock.patch.dict(os.environ,
                             {"CLAUDE_CODE_OAUTH_TOKEN": "tok-ambient"}):
            env = runner.role_env("developer")

        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "tok-ambient")

    def test_environment_comes_from_the_registered_provider(self):
        """Ловит мутацию: `role_env` снова кладёт дом роли и токен сама,
        мимо реестра — провайдер на другом CLI не смог бы подставить ни
        своего каталога конфига, ни своего секрета."""
        with mock.patch.object(claude_provider.ClaudeProvider, "environment",
                               lambda self, role=None, task_id=None:
                               {"PROVIDER_MARKER": "1"}):
            env = runner.role_env("developer")

        self.assertEqual(env["PROVIDER_MARKER"], "1")
        # Курируемый слой ПЕСОЧНИЦЫ в окружение не попал: значения
        # HOME/CLAUDE_CONFIG_DIR кладёт только провайдер (ambient-копия
        # белого списка манифеста несёт значения процесса прогона — они
        # другие, и это ровно то, что проверяется).
        self.assertNotEqual(env.get("CLAUDE_CONFIG_DIR"),
                            str(config.ROLE_CONFIG_DIR))
        self.assertNotEqual(env.get("HOME"), str(config.ROLE_HOME))


class ManifestToolTest(unittest.TestCase):
    """Инструмент манифеста от провайдера — требование 6 (AC-8)."""

    def test_required_tools_entry_equals_the_provider_cli_tool(self):
        """Ловит мутацию: `stack.REQUIRED_TOOLS` снова несёт запись
        `claude` своим литералом — два источника истины о минимальной
        версии CLI разъезжаются молча; либо запись перестала быть
        обязательной, и отсутствие CLI больше не красит `doctor`."""
        tool = providers.default().cli_tool()

        self.assertIn(tool.name, stack.REQUIRED_TOOLS)
        self.assertIn(tool.name, stack.DECLARED_TOOLS)
        requirement = stack.REQUIRED_TOOLS[tool.name]
        self.assertEqual(requirement.minimum, tool.minimum)
        self.assertEqual(tuple(requirement.command), tuple(tool.command))

    def test_common_tools_keep_their_place_before_the_provider_tool(self):
        """Ловит мутацию: инструменты провайдеров затирают общие записи
        манифеста (или встают перед ними) — порядок каталогов PATH роли
        и порядок строк `check_stack()` меняются на ровном месте."""
        self.assertEqual(list(stack.REQUIRED_TOOLS)[:2], ["git", "gh"])
        self.assertEqual(stack.DECLARED_TOOLS[0], "python3")


class RoleHomeTest(TmpRootTest):
    """Дом роли по `home_reference()` — требование 7 (AC-12)."""

    def seed_reference(self) -> Path:
        reference = providers.default().home_reference().reference
        reference.mkdir(parents=True, exist_ok=True)
        (reference / "CLAUDE.md").write_text("# слой\n", encoding="utf-8")
        return reference

    def test_reference_points_at_the_repository_directory_and_dotted_name(self):
        """Ловит мутацию: имя развёрнутого каталога отдано без ведущей
        точки (`claude`, как в самом репозитории) или референс указывает
        на уже развёрнутый слой `.artel/home` — холодный старт
        разворачивает дом роли не туда, а CLI шага не находит своих
        настроек."""
        home = providers.default().home_reference()

        self.assertEqual(home.deployed_name, ".claude")
        self.assertEqual(
            home.reference,
            config.ROOT / "docs" / "reference" / "role-home" / "claude")

    def test_init_deploys_the_provider_reference_byte_for_byte(self):
        """Ловит мутацию: развёртывание берёт каталог мимо провайдера
        (собственный литерал пути) или копирует не то дерево — холодный
        старт оставляет роль без курируемого слоя."""
        reference = self.seed_reference()

        self.capture(catalog.cmd_init)

        deployed = config.ROLE_HOME / ".claude" / "CLAUDE.md"
        self.assertTrue(deployed.is_file(), list(config.ROLE_HOME.rglob("*")))
        self.assertEqual(deployed.read_bytes(),
                         (reference / "CLAUDE.md").read_bytes())

    def test_existing_home_is_not_overwritten_by_init(self):
        """Ловит мутацию: развёртывание перестало быть идемпотентным и
        затирает курирование Оператора (`.artel/home` он правит по ходу
        работы, docs/reference/role-home.md) на каждом `init`."""
        self.seed_reference()
        config.ROLE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        (config.ROLE_CONFIG_DIR / "CLAUDE.md").write_text("# моё\n",
                                                          encoding="utf-8")

        self.capture(catalog.cmd_init)

        self.assertEqual(
            (config.ROLE_CONFIG_DIR / "CLAUDE.md").read_text(encoding="utf-8"),
            "# моё\n")

    def test_missing_reference_leaves_no_half_deployed_home(self):
        """Ловит мутацию: `init` создаёт пустой `.artel/home` на дереве
        без референса — следующий `init` с настоящим референсом уже
        ничего не развернёт (каталог существует), и роль остаётся без
        курируемого слоя навсегда."""
        self.capture(catalog.cmd_init)

        self.assertFalse(config.ROLE_HOME.exists())


class DoctorProviderLinesTest(TmpRootTest):
    """Строки `doctor` — требования 4, 6 (AC-9, AC-11)."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(keychain, "token", lambda slot: "tok-test")
        patcher.start()
        self.addCleanup(patcher.stop)
        env_patcher = mock.patch.dict(os.environ, NO_AMBIENT_TOKEN)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

    def use_roles_yaml(self, text: str) -> None:
        path = self.root / "roles-under-test.yaml"
        path.write_text(text, encoding="utf-8")
        patcher = mock.patch.object(config, "ROLES", path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_role_providers_line_names_every_agent_role(self):
        """Ловит мутацию: строка печатается пустой (реестр опрошен, а
        карта исполнителей — нет) либо перечисляет провайдеров без ролей
        — Оператор видит «claude, claude, claude» и не может сказать,
        какая роль на каком CLI пойдёт."""
        check = doctor.check_role_providers()

        self.assertEqual(check.status, "ok", check.detail)
        self.assertIn("провайдеры ролей:", check.detail)
        for role in doctor.agent_roles():
            self.assertIn(f"{role} → claude", check.detail)

    def test_unknown_provider_of_a_role_is_a_red_line(self):
        """Ловит мутацию: `doctor` печатает провайдеров ролей строкой, но
        не проверяет их регистрацию (статус всегда `ok`) — пульт узнаёт о
        незнакомом имени только в момент отказа шага."""
        self.use_roles_yaml(
            _roles_yaml_text("developer", "claude-opus-5").replace(
                "  developer:\n",
                f"  developer:\n    provider: {UNKNOWN_PROVIDER}\n", 1))

        check = doctor.check_role_providers()

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn(
            f"провайдер {UNKNOWN_PROVIDER} роли developer не зарегистрирован",
            check.detail)

    def test_provider_preflight_is_collected_without_duplicates(self):
        """Ловит мутацию: `preflight()` провайдера склеивается по ролям
        без дедупликации — «CLI найден»/«версия CLI»/«дом роли»
        печатаются по разу на роль, и Оператор ищет настоящий провал в
        учетверённом списке; либо проверка секрета схлопнута в одну на
        все роли, и отсутствие токена у одной из них исчезает из вывода.
        """
        with mock.patch.object(doctor.subprocess, "run",
                               lambda *a, **kw: subprocess.CompletedProcess(
                                   a[0], 0, f"{config.CLI_VERSION_PIN}\n", "")):
            grouped = doctor.provider_preflight_checks()

        for name in ("cli-found", "cli-version", "role-home-reference"):
            with self.subTest(check=name):
                self.assertEqual(len(grouped.get(name, [])), 1, grouped)
        self.assertEqual(len(grouped.get("token", [])),
                         len(doctor.agent_roles()), grouped)

    def test_unreadable_roles_map_is_a_warn_line_not_a_green_one(self):
        """Ловит мутацию: карта исполнителей не прочитана, а строка
        «провайдеры ролей» всё равно зелёная с перечнем ролей на
        `claude` — `doctor` утверждает прочитанным файл, которого не
        читал, и поломка `roles.yaml` (опечатка, файл не на месте)
        остаётся невидимой до отказа шага (REVIEW.md итерации 1, R1-F2).
        """
        self.use_roles_yaml("roles:\n  - developer\n")

        check = doctor.check_role_providers()

        self.assertEqual(check.status, "warn", check.detail)
        self.assertIn("не разобран", check.detail)


class AllChecksProviderNamesTest(DoctorSandbox):
    """Склейка провайдерских проверок в выводе `doctor` — требование 6.

    Песочница — готовая `tests/test_doctor.py` (временный корень с
    `skills/`/`templates/`, подменённый keychain, погашенный
    ambient-токен): `all_checks` проходит весь прогон целиком, и своих
    копий этой обвязки здесь не заводится.
    """

    def test_all_checks_prints_provider_checks_with_unexpected_names(self):
        """Ловит мутацию: `all_checks` разбирает набор провайдера по
        четырём сегодняшним именам и молча теряет остальные — проверка
        секрета второго провайдера под своим именем (`api-key` у
        `codex`) исчезает из вывода `doctor`, и Оператор видит зелёный
        прогон при отсутствующем ключе (REVIEW.md итерации 1, R1-F4).
        """
        own = doctor.Check("api-key", "fail", "ключ провайдера не найден")
        self.touch_backup()

        with mock.patch.object(claude_provider.ClaudeProvider, "preflight",
                               lambda self, role: [own]), \
                mock.patch.object(doctor.subprocess, "run", claude_only_run(
                    f"{config.CLI_VERSION_PIN} (Claude Code)\n")), \
                mock.patch.object(doctor.subprocess, "Popen", claude_only_popen(
                    FakeLiveSmokeProc(result_event(0.01)))):
            checks = doctor.all_checks(store.db())

        self.assertIn(own, checks, [c.name for c in checks])


class UnknownProviderStepTest(_StepSandbox):
    """Шаг роли с незарегистрированным провайдером — требование 4 (AC-4)."""

    def setUp(self):
        super().setUp()
        path = self.root / "roles-under-test.yaml"
        path.write_text(
            _roles_yaml_text(self.ROLE, "claude-opus-5").replace(
                f"  {self.ROLE}:\n",
                f"  {self.ROLE}:\n    provider: {UNKNOWN_PROVIDER}\n", 1),
            encoding="utf-8")
        self.patch(config, "ROLES", path)

    def test_run_refuses_by_name_before_the_agent_starts(self):
        """Ловит мутацию: неизвестное имя провайдера резолвится дефолтом
        — шаг молча уходит на `claude` и запускает агента вместо отказа;
        либо отказ есть, но безымянный (`KeyError`/трейсбек), и Оператор
        не видит, какое имя и у какой роли чинить."""
        out = self.run_step()

        self.spawn.assert_not_called()
        refusal = f"провайдер {UNKNOWN_PROVIDER} роли {self.ROLE} не зарегистрирован"
        self.assertIn(refusal, f"{out}\n{self.exit_message or ''}")
        self.assertIn(runner.PROVIDER_REFUSAL_ACTION, self.actions())
        self.assertEqual(self.state(), "in_dev")


if __name__ == "__main__":
    unittest.main()
