"""AC-3, AC-4, AC-5: у шага роли на Codex больше нет канала ключа API —
ни в окружении провайдера, ни в белом списке манифеста, ни именем слота
в коде пульта.

Красен до реализации: `CodexProvider.environment` сегодня добывает ключ
из слота `config.OPENAI_API_KEY_SLOT` и кладёт его в окружение шага,
`secret_env_names()` называет `OPENAI_API_KEY` секретом провайдера,
`stack.ROLE_ENV_ALLOWLIST` несёт то же имя, а сама константа слота живёт
в `orchestrator/config.py` и читается двумя модулями — каждый из трёх
тестов ниже падает на действующем канале ключа.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from orchestrator import config, keychain, providers, runner, stack  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

KEYCHAIN_SECRET = "kluch-iz-slota-operatora"
AMBIENT_VALUE = "kluch-iz-okruzheniya-operatora"


class CodexEnvironmentTest(TmpRootTest):
    """Окружение процесса роли на Codex — требование 2."""

    def setUp(self):
        super().setUp()
        self.slots = []
        _util.patch(self, keychain, "token", self._spy)

    def _spy(self, slot):
        self.slots.append(slot)
        return KEYCHAIN_SECRET

    def test_ac3_environment_is_only_the_role_home_and_never_asks_the_keychain(self):
        """Окружение провайдера состоит РОВНО из `HOME` и `CODEX_HOME`
        курируемого дома роли — и при заданных Оператором ambient-именах
        ключей, и при непустом слоте keychain; сам слот при этом не
        спрашивается ни разу, а `secret_env_names()` пуст.

        Ловит мутацию: ключ перестал попадать в окружение, но слот
        по-прежнему читается «на всякий случай» (значение добывается и
        кладётся под другим именем либо просто добывается впустую) — шаг
        снова несёт секрет, которого требование 2 ему не даёт, а пустой
        `secret_env_names()` при этом врёт смоку изоляции, что у
        провайдера секрета в окружении нет.
        """
        _util.drop_ambient(self, *_util.FORBIDDEN_ENV_NAMES)
        provider = providers.get("codex")
        deployed = config.ROLE_HOME / ".codex"
        ambient = {name: AMBIENT_VALUE for name in _util.FORBIDDEN_ENV_NAMES}

        for title, overrides in (("без ambient-ключей", {}),
                                 ("с ambient-ключами", ambient)):
            with self.subTest(scenario=title):
                with mock.patch.dict(os.environ, overrides):
                    env = provider.environment("developer", "T1")

                self.assertEqual(set(env), {"HOME", "CODEX_HOME"}, env)
                self.assertEqual(env["HOME"], str(config.ROLE_HOME))
                self.assertEqual(env["CODEX_HOME"], str(deployed))
                self.assertEqual(self.slots, [],
                                 "слот keychain спрошен провайдером")

        self.assertEqual(tuple(provider.secret_env_names()), ())


class RoleEnvAllowlistTest(TmpRootTest):
    """Белый список манифеста и собранное окружение шага — требование 3."""

    def setUp(self):
        super().setUp()
        _util.drop_ambient(self, *_util.CLAUDE_SECRETS,
                           *_util.FORBIDDEN_ENV_NAMES)
        _util.patch(self, keychain, "token", lambda slot: "tok-podpiski")

    def step_env(self, provider_name: str) -> dict:
        """Окружение шага роли, собранное РЕАЛЬНОЙ точкой пульта
        (`runner.role_env`), с исполнителем шага `provider_name`."""
        provider = providers.get(provider_name)
        with mock.patch.object(providers, "for_role", lambda role=None: provider):
            return runner.role_env("developer", "T1")

    def test_ac4_no_openai_key_name_in_the_allowlist_or_in_either_step_env(self):
        """Ни `OPENAI_API_KEY`, ни `CODEX_API_KEY`, ни
        `CODEX_ACCESS_TOKEN` не входят в белый список манифеста (с учётом
        его префиксов), и собранное окружение шага не несёт ни одной из
        них ни на `codex`, ни на `claude` при всех трёх заданных
        ambient-переменных.

        Ловит мутацию: `OPENAI_API_KEY` убран из белого списка, а взамен
        дописан `CODEX_API_KEY` — «тот, который `codex exec` и читает»
        (факт живой проверки 22.09). Белый список общий на пульт, поэтому
        такая замена вернула бы ключ Оператора в окружение КАЖДОГО шага,
        включая шаг роли на Claude, — ровно та утечка, которую требование
        3 закрывает.
        """
        prefixes = tuple(stack.ROLE_ENV_ALLOWLIST_PREFIXES)
        for name in _util.FORBIDDEN_ENV_NAMES:
            with self.subTest(name=name, where="белый список"):
                self.assertNotIn(name, stack.ROLE_ENV_ALLOWLIST)
                self.assertFalse(name.startswith(prefixes), prefixes)

        ambient = {name: AMBIENT_VALUE for name in _util.FORBIDDEN_ENV_NAMES}
        for provider_name in ("codex", "claude"):
            with mock.patch.dict(os.environ, ambient):
                env = self.step_env(provider_name)
            for name in _util.FORBIDDEN_ENV_NAMES:
                with self.subTest(provider=provider_name, name=name):
                    self.assertNotIn(name, env)
            self.assertNotIn(AMBIENT_VALUE, set(env.values()), provider_name)


class SlotNameGoneTest(unittest.TestCase):
    """Имя слота и сама запись keychain — требование 2, вторая половина."""

    def test_ac5_the_slot_name_is_absent_from_pult_code_and_the_role_home_reference(self):
        """Ни имя `OPENAI_API_KEY_SLOT`, ни строка `artel-openai-api-key`
        не встречаются ни в одном файле кода пульта и ни в одном файле
        `docs/reference/role-home/codex/`; читать или удалять запись
        keychain с этим именем стало нечем — адреса в коде нет.

        Ловит мутацию: константа оставлена в `orchestrator/config.py` «с
        пометкой не используется» — именованный адрес слота остаётся
        внутри пульта, и ближайшая задача линии возвращает ключ в
        окружение «по аналогии» (обоснование требования 2 в SPEC). Та же
        мутация в мягкой форме: читателей убрали из провайдера и
        предполёта, но `stack.ROLE_ENV_ALLOWLIST` продолжает называть
        слот в описании переменной.
        """
        for path in _util.pult_code_files():
            text = path.read_text(encoding="utf-8")
            label = str(path.relative_to(_util.REPO_ROOT))
            with self.subTest(file=label):
                self.assertNotIn(_util.SLOT_CONST_NAME, text, label)
                self.assertNotIn(_util.SLOT_RECORD_NAME, text, label)

        for path in sorted(_util.CODEX_REFERENCE_DIR.rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            label = str(path.relative_to(_util.REPO_ROOT))
            with self.subTest(file=label):
                self.assertNotIn(_util.SLOT_CONST_NAME, text, label)
                self.assertNotIn(_util.SLOT_RECORD_NAME, text, label)

        self.assertFalse(hasattr(config, _util.SLOT_CONST_NAME))


if __name__ == "__main__":
    unittest.main()
