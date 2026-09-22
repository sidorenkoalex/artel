"""AC-6..AC-8: окружение процесса роли на `codex` — `CODEX_HOME` на
курируемый дом, `OPENAI_API_KEY` из отдельного слота keychain, обе
переменные в белом списке манифеста и в собранном окружении шага.

Красен до реализации: `CodexProvider.environment(...)` ещё не существует,
а `stack.ROLE_ENV_ALLOWLIST` не несёт ни `CODEX_HOME`, ни
`OPENAI_API_KEY`.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import config, keychain, providers, runner, stack  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402
from tests.test_runner_role_model import _roles_yaml_text  # noqa: E402

from _codex import PROVIDER, TASK_ID, drop_ambient  # noqa: E402

KEYCHAIN_SECRET = "kluch-iz-slota-keychain"
AMBIENT_KEY = "kluch-zadannyy-operatorom"
ALIEN_CODEX_HOME = "/tmp/dom-operatora-ne-roli"
DEPLOYED_HOME_DIR = ".codex"

#: Секреты ДРУГОГО провайдера: окружение `codex` не отдаёт их ни в одном
#: сценарии (AC-7).
CLAUDE_SECRET_NAMES = ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY")


class CodexEnvironmentTest(TmpRootTest):
    """Провайдерская часть окружения — `CodexProvider.environment`."""

    def setUp(self):
        super().setUp()
        self.slots = []
        patcher = mock.patch.object(keychain, "token", self._spy_token)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _spy_token(self, slot):
        self.slots.append(slot)
        return KEYCHAIN_SECRET

    def test_ac6_codex_home_points_at_the_curated_dir_and_overrides_ambient(self):
        """Окружение роли несёт `CODEX_HOME`, равный
        `<корень пульта>/.artel/home/.codex`, каталог создаётся на диске, а
        ambient-значение, заданное до вызова, переписывается.

        Ловит мутацию: `CODEX_HOME` поставлен `setdefault`-ом «как
        токен» — роль наследует каталог конфига Оператора вместе с его
        MCP-серверами и правилами, то есть ровно ту конфиг-инъекцию, от
        которой дом роли и заводится; либо каталог не создаётся, и CLI
        заводит его сам там, где пульт о нём не знает.
        """
        drop_ambient(self, "OPENAI_API_KEY")
        expected = config.ROLE_HOME / DEPLOYED_HOME_DIR

        with mock.patch.dict(os.environ, {"CODEX_HOME": ALIEN_CODEX_HOME}):
            env = providers.get(PROVIDER).environment("developer", TASK_ID)

        self.assertEqual(env["CODEX_HOME"], str(expected))
        self.assertTrue(expected.is_dir(), list(config.ROLE_HOME.rglob("*")))

    def test_ac7_api_key_comes_from_a_named_slot_and_yields_to_ambient(self):
        """Ключ роли берётся из слота keychain, имя которого — именованная
        константа `orchestrator/config.py`; при заданной ambient-переменной
        `OPENAI_API_KEY` keychain не спрашивается вовсе и ambient-значение
        побеждает; секретов другого провайдера окружение не отдаёт ни в
        одном из двух случаев.

        Ловит мутацию: ключ берётся тем же вызовом, что подписочный токен
        Claude (`runner.role_token` по слотам `roles.yaml`) — оба
        провайдера начинают тянуть секрет из одного слота, и ключ OpenAI
        уходит в шаг под именем токена подписки; либо keychain
        спрашивается безусловно, и заданный Оператором ambient-ключ
        перестаёт быть сильнее слота.
        """
        drop_ambient(self, "OPENAI_API_KEY", *CLAUDE_SECRET_NAMES)

        from_slot = providers.get(PROVIDER).environment("developer", TASK_ID)

        self.assertEqual(from_slot["OPENAI_API_KEY"], KEYCHAIN_SECRET)
        self.assertTrue(self.slots, "keychain не спрошен вовсе")
        named = {value for name, value in vars(config).items()
                 if name.isupper() and isinstance(value, str)}
        self.assertIn(self.slots[-1], named,
                      f"слот {self.slots[-1]!r} не назван константой config")

        self.slots.clear()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": AMBIENT_KEY}):
            ambient = providers.get(PROVIDER).environment("developer", TASK_ID)

        self.assertEqual(self.slots, [], "keychain спрошен при ambient-ключе")
        self.assertIn(ambient.get("OPENAI_API_KEY"), (None, AMBIENT_KEY))
        for env in (from_slot, ambient):
            for name in CLAUDE_SECRET_NAMES:
                with self.subTest(name=name):
                    self.assertNotIn(name, env)


class StepEnvironmentAllowlistTest(TmpRootTest):
    """Собранное окружение шага (`runner.role_env`) — требование 4, AC-8."""

    CODEX_ROLE = "developer"
    CLAUDE_ROLE = "reviewer"

    def setUp(self):
        super().setUp()
        path = self.root / "roles-under-test.yaml"
        path.write_text(
            _roles_yaml_text(self.CODEX_ROLE, "strong").replace(
                f"  {self.CODEX_ROLE}:\n",
                f"  {self.CODEX_ROLE}:\n    provider: {PROVIDER}\n", 1),
            encoding="utf-8")
        self.patch(config, "ROLES", path)
        self.patch(keychain, "token", lambda slot: KEYCHAIN_SECRET)
        # Резолв инструментов манифеста подменён целиком: предмет
        # критерия — состав ПЕРЕМЕННЫХ собранного окружения, а не
        # присутствие бинарников на машине прогона (`codex` там по
        # условию задачи не установлен).
        self.patch(runner, "_resolve_declared_tools", self._stub_tools)
        # Ambient-каналы обоих провайдеров гасятся: на машине Оператора
        # токен подписки стоит в окружении по построению и был бы сильнее
        # слота — набор краснел бы без единого дефекта в коде.
        drop_ambient(self, "CODEX_HOME", "OPENAI_API_KEY",
                     *CLAUDE_SECRET_NAMES)

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _stub_tools(self) -> dict:
        names = set(stack.DECLARED_TOOLS) | {PROVIDER}
        return {name: f"/artel-test-stub-bin/{name}" for name in names}

    def test_ac8_both_variables_are_allowlisted_and_reach_the_codex_step(self):
        """`CODEX_HOME` и `OPENAI_API_KEY` входят в белый список манифеста,
        собранное окружение шага роли на `codex` несёт оба значения, а
        окружение роли на `claude` остаётся прежним по составу ключей —
        переменные второго провайдера в него не протекают.

        Ловит мутацию: провайдер кладёт обе переменные, а белый список
        манифеста о них не знает — `runner._allowlisted_env` не при чём
        (провайдерская часть ложится поверх), но ambient-канал
        `OPENAI_API_KEY` Оператора перестаёт доезжать до шага, и приоритет
        AC-7 ломается молча; либо провайдерская часть `codex` попадает в
        окружение КАЖДОЙ роли, и шаг на Claude получает чужой ключ.
        """
        for name in ("CODEX_HOME", "OPENAI_API_KEY"):
            with self.subTest(name=name):
                self.assertIn(name, stack.ROLE_ENV_ALLOWLIST)

        codex_env = runner.role_env(self.CODEX_ROLE, TASK_ID)

        self.assertEqual(codex_env["CODEX_HOME"],
                         str(config.ROLE_HOME / DEPLOYED_HOME_DIR))
        self.assertEqual(codex_env["OPENAI_API_KEY"], KEYCHAIN_SECRET)

        claude_env = runner.role_env(self.CLAUDE_ROLE, TASK_ID)

        self.assertEqual(claude_env["HOME"], str(config.ROLE_HOME))
        self.assertEqual(claude_env["CLAUDE_CONFIG_DIR"],
                         str(config.ROLE_CONFIG_DIR))
        self.assertEqual(claude_env["CLAUDE_CODE_OAUTH_TOKEN"],
                         KEYCHAIN_SECRET)
        for name in ("CODEX_HOME", "OPENAI_API_KEY"):
            with self.subTest(name=name):
                self.assertNotIn(name, claude_env)


if __name__ == "__main__":
    unittest.main()
