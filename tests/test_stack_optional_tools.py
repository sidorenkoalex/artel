"""Юнит-тесты необязательной части манифеста стека (SPEC
01M32NH6P053978AER66P0X4GN, требование 6): CLI провайдера, кроме
провайдера по умолчанию, обязателен ровно тогда, когда ярус хотя бы
одной agent-роли разрешается в модель этого провайдера.

Постоянная регрессия поверх приёмочной планки задачи
(`tasks/01M32NH6P053978AER66P0X4GN/acceptance_tests/
test_ac12_ac13_ac19_optional_tool.py`): та планка уходит вместе с
каталогом задачи, а свойство «регистрация второго провайдера не ломает
работу первого» обязано её пережить — именно оно отделяет запись в
реестре от требования к машине Оператора.

Ни один настоящий CLI здесь не запускается: `subprocess.run` отвечает
заготовленными версиями, `shutil.which` — заготовленными путями.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, doctor, stack  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402
from tests.test_runner_role_model import _roles_yaml_text  # noqa: E402

CLAUDE_MODEL = "claude-opus-5"
CODEX_MODEL = "gpt-5.6-terra"
TIER = "strong"
ROLE = "developer"

CATALOG = """providers:
  claude:
    cli: claude
    min_cli_version: 1.0.0
    cost_from_cli: true
    models:
      {claude_model}:
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
      {codex_model}:
        min_cli_version: 0.155.1
        status: experimental
        list_price_usd_per_mtok:
          input: 2.0
          output: 12.0
          cache_write: 2.0
          cache_read: 0.20
        price_date: 2026-09-21
"""

LOCAL = """tiers:
  {tier}: {model}
allow_experimental:
  {model}: true
"""


# Настоящий `check_stack` снимается ДО песочницы: `tests/sandbox.py::
# TmpRootTest` подменяет его заглушкой, а предмет этого файла — именно
# состав его строк.
_REAL_CHECK_STACK = stack.check_stack


class _ManifestSandbox(TmpRootTest):
    """Каталог с двумя провайдерами и управляемым ярусом роли; какой
    моделью разрешается ярус — выбирает тест."""

    def setUp(self):
        super().setUp()
        self.catalog_path = self.root / "models-catalog" / "models.yaml"
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(
            CATALOG.format(claude_model=CLAUDE_MODEL, codex_model=CODEX_MODEL),
            encoding="utf-8")
        self.patch(config, "MODELS", self.catalog_path)
        self.roles_path = self.root / "roles-under-test.yaml"
        self.use_tier(CLAUDE_MODEL)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def use_tier(self, model: str, provider: str = None) -> None:
        """Ярус роли -> `model`; `provider` — необязательное поле роли,
        которое НЕ должно решать обязательность инструмента."""
        text = _roles_yaml_text(ROLE, TIER)
        if provider is not None:
            text = text.replace(f"  {ROLE}:\n",
                                f"  {ROLE}:\n    provider: {provider}\n", 1)
        self.roles_path.write_text(text, encoding="utf-8")
        # Патч, а не присваивание: `tests/sandbox.py` уводит `config.ROLES`
        # на свой файл при импорте, и невосстановленное значение утекло бы
        # в соседние тесты процесса.
        self.patch(config, "ROLES", self.roles_path)
        config.MODELS_LOCAL.write_text(LOCAL.format(tier=TIER, model=model),
                                       encoding="utf-8")

    def stack_checks(self, codex_found: bool) -> list:
        def fake_run(args, **kwargs):
            name = Path(str(args[0])).name
            if name == "codex" and not codex_found:
                raise FileNotFoundError("codex")
            if "freeze" in list(args):
                return subprocess.CompletedProcess(list(args), 0, "", "")
            return subprocess.CompletedProcess(list(args), 0, "9.9.9\n", "")

        with mock.patch.object(stack.subprocess, "run", side_effect=fake_run):
            return _REAL_CHECK_STACK()


class OptionalToolManifestTest(_ManifestSandbox):
    """Состав манифеста при разных ярусах — требование 6."""

    def test_unused_provider_tool_stays_out_of_the_manifest(self):
        """Ловит мутацию: запись `codex` внесена в манифест безусловно
        (`REQUIRED_TOOLS`/`DECLARED_TOOLS` собираются по всему реестру
        провайдеров, как до задачи) — пульт БЕЗ Codex перестаёт
        запускать шаги вовсе: резолв объявленных инструментов отказывает
        `OSError` на каждом `role_env`, то есть регистрация второго
        провайдера ломает работу первого."""
        self.assertNotIn("codex", stack.REQUIRED_TOOLS)
        self.assertEqual(list(stack.REQUIRED_TOOLS)[:2], ["git", "gh"])
        self.assertIn("claude", stack.REQUIRED_TOOLS)

        self.assertNotIn("codex", stack.required_tools())
        self.assertNotIn("codex", stack.DECLARED_TOOLS)
        self.assertEqual(stack.DECLARED_TOOLS[0], "python3")

    def test_tier_resolving_to_a_codex_model_makes_the_tool_required(self):
        """Ловит мутацию: инструмент второго провайдера остался
        необязательным ВСЕГДА — шаг стартует, платит токенами и падает на
        отсутствующем CLI внутри попытки вместо бесплатного отказа до
        старта агента."""
        self.use_tier(CODEX_MODEL)

        self.assertIn("codex", stack.model_providers())
        self.assertIn("codex", stack.required_tools())
        self.assertIn("codex", stack.DECLARED_TOOLS)
        self.assertEqual(list(stack.DECLARED_TOOLS)[-1], "codex",
                         "необязательный инструмент встаёт после обязательных")

    def test_requirement_follows_the_model_not_the_provider_field_of_the_role(self):
        """Ловит мутацию: условие обязательности смотрит на поле
        `provider:` роли из `roles.yaml`, а не на разрешение яруса в
        модель — роль с `provider: claude` и ярусом на модель Codex
        уходила бы в шаг без объявленного CLI, а роль с `provider: codex`
        и ярусом на модель Claude требовала бы установки Codex зря."""
        self.use_tier(CODEX_MODEL, provider="claude")
        self.assertIn("codex", stack.model_providers())

        self.use_tier(CLAUDE_MODEL, provider="codex")
        self.assertNotIn("codex", stack.model_providers())

    def test_unreadable_layers_demand_nothing_instead_of_raising(self):
        """Ловит мутацию: неразрешимая цепочка или нечитаемая карта
        исполнителей пробрасывает исключение из сборки манифеста — тогда
        `role_env`/`check_stack`/`doctor` падали бы трейсбеком там, где
        про ту же поломку уже говорит собственный именованный отказ."""
        config.MODELS_LOCAL.write_text("tiers:\n  cheap: nothing\n",
                                       encoding="utf-8")
        self.assertEqual(stack.model_providers(), set())

        self.roles_path.write_text("roles:\n  - developer\n", encoding="utf-8")
        self.assertEqual(stack.model_providers(), set())
        self.assertNotIn("codex", stack.DECLARED_TOOLS)


class CheckStackLinesTest(_ManifestSandbox):
    """Строки `check_stack()` — требования 6-7."""

    def test_missing_unused_tool_gives_no_line_at_all(self):
        """Ловит мутацию: строка инструмента печатается по реестру
        провайдеров — пульт без Codex краснеет `doctor` из-за CLI,
        которым не пользуется ни одна роль."""
        checks = self.stack_checks(codex_found=False)

        self.assertEqual([c for c in checks if c.name == "codex"], [])
        self.assertEqual(
            [c.name for c in checks if c.status == "fail"], [])

    def test_missing_demanded_tool_is_a_red_line_naming_it(self):
        """Ловит мутацию: востребованный инструмент отмечается `warn`
        вместо `fail` либо строка не называет его по имени — `doctor`
        зеленел бы при заведомо нерабочей цепочке роли."""
        self.use_tier(CODEX_MODEL)

        checks = self.stack_checks(codex_found=False)

        line = [c for c in checks if c.name == "codex"]
        self.assertEqual(len(line), 1, [c.name for c in checks])
        self.assertEqual(line[0].status, "fail", line[0].detail)
        self.assertIn("не найден", line[0].detail)

    def test_model_line_is_verdicted_by_the_version_of_its_own_cli(self):
        """Ловит мутацию: строка модели роли сверяется с версией
        `claude` для ЛЮБОГО провайдера — модель Codex получает вердикт по
        версии чужого CLI: свежий Claude при отсутствующем Codex дал бы
        зелёную строку там, где запускать нечем."""
        self.use_tier(CODEX_MODEL)

        checks = self.stack_checks(codex_found=False)

        line = [c for c in checks if c.name == f"model-{ROLE}"]
        self.assertEqual(len(line), 1, [c.name for c in checks])
        self.assertEqual(line[0].status, "warn", line[0].detail)
        self.assertIn("codex --version", line[0].detail)


class PreflightGateTest(_ManifestSandbox):
    """Блокирующая проверка предполёта — требование 6."""

    def which(self, codex_found: bool):
        def fake(name, *args, **kwargs):
            if name == "codex":
                return "/artel-test-stub-bin/codex" if codex_found else None
            return f"/artel-test-stub-bin/{name}"
        return fake

    def check(self, codex_found: bool):
        with mock.patch.object(doctor.shutil, "which",
                               self.which(codex_found)):
            return doctor.check_model_provider_cli()

    def test_check_is_silent_and_green_while_no_tier_needs_a_foreign_cli(self):
        """Ловит мутацию: проверка спрашивает `shutil.which` по всему
        реестру провайдеров — на сегодняшнем пульте (все ярусы на модели
        Claude) она начала бы блокировать каждый шаг отсутствием CLI,
        которым никто не пользуется."""
        calls = []

        def spy(name, *args, **kwargs):
            calls.append(name)
            return None

        with mock.patch.object(doctor.shutil, "which", spy):
            check = doctor.check_model_provider_cli()

        self.assertEqual(check.status, "ok", check.detail)
        self.assertEqual(calls, [], "лишние вопросы к PATH")

    def test_missing_demanded_cli_blocks_the_step_by_name(self):
        """Ловит мутацию: отсутствие востребованного CLI всплывает только
        `OSError`'ом внутри `check_git_identity` — исход шага назван
        жёлтой строкой «окружение роли не подготовлено» вместо отказа, и
        Оператор чинит не то."""
        self.use_tier(CODEX_MODEL)

        check = self.check(codex_found=False)

        self.assertEqual(check.status, "fail", check.detail)
        self.assertIn("codex", check.detail)
        self.assertIn("не найден", check.detail)

        self.assertEqual(self.check(codex_found=True).status, "ok")

    def test_the_check_is_part_of_the_blocking_group_of_preflight(self):
        """Ловит мутацию: проверка написана, но не подключена к
        `preflight_checks` (или подключена ПОСЛЕ раннего возврата по
        блокирующим) — шаг стартовал бы, несмотря на ненайденный CLI
        модели."""
        import inspect

        source = inspect.getsource(doctor.preflight_checks)
        head, _, tail = source.partition("if any(c.status ==")

        self.assertIn("check_model_provider_cli", head, source)
        self.assertNotIn("check_model_provider_cli", tail)


class DeclaredToolsSequenceTest(unittest.TestCase):
    """`stack.DECLARED_TOOLS` — ленивая последовательность вместо
    кортежа: `orchestrator/runner.py` перебирает именно это имя."""

    def test_object_behaves_like_the_tuple_it_replaced(self):
        """Ловит мутацию: объект потерял одну из операций, которыми им
        пользуются (`for`, `len`, индекс, `in`, сравнение с кортежем) —
        `runner._resolve_declared_tools`/`_role_path_dirs` или тесты
        манифеста падали бы `TypeError` на ровном месте."""
        names = list(stack.DECLARED_TOOLS)

        self.assertEqual(len(stack.DECLARED_TOOLS), len(names))
        self.assertEqual(stack.DECLARED_TOOLS[0], names[0])
        self.assertEqual(stack.DECLARED_TOOLS[-1], names[-1])
        self.assertIn(names[0], stack.DECLARED_TOOLS)
        self.assertEqual(stack.DECLARED_TOOLS, tuple(names))
        self.assertEqual(stack.DECLARED_TOOLS, names)

    def test_composition_is_recomputed_at_every_access(self):
        """Ловит мутацию: состав посчитан один раз (кортеж при импорте
        или кэш) — перевод яруса на модель другого провайдера не доезжает
        до резолва инструментов до перезапуска процесса, и шаг идёт без
        объявленного CLI."""
        with mock.patch.object(stack, "demanded_optional_tools",
                               lambda: {"vymyshlennyy-cli": None}):
            self.assertIn("vymyshlennyy-cli", stack.DECLARED_TOOLS)

        self.assertNotIn("vymyshlennyy-cli", stack.DECLARED_TOOLS)


if __name__ == "__main__":
    unittest.main()
