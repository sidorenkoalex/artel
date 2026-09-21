"""AC-1: провайдер `codex` в реестре исполнителей роли, дефолт остаётся
`claude`, инструмент манифеста объявлен самим провайдером.

Красен до реализации: модуля `orchestrator/providers/codex.py` и записи
`codex` в `PROVIDERS` ещё нет — `providers.get("codex")` отказывает
`UnknownProviderError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import providers  # noqa: E402

from _codex import CLI_MINIMUM, PROVIDER  # noqa: E402


class ProviderRegistryTest(unittest.TestCase):
    """Реестр `orchestrator/providers/__init__.py` с двумя провайдерами."""

    def test_ac1_codex_is_registered_beside_claude_without_taking_the_default(self):
        """Реестр отдаёт `codex` экземпляром `CodexProvider` с именем
        `codex`, несёт обоих провайдеров, оставляет дефолтом `claude`, а
        сводка инструментов манифеста несёт запись `codex` с минимальной
        версией 0.155.1.

        Ловит мутацию: `DEFAULT_PROVIDER` переставлен на `codex` вместе с
        регистрацией (роль без поля `provider:` молча уехала бы на другой
        CLI); либо `cli_tool()` нового провайдера отдаёт имя/минимум
        claude (копипаста записи), и манифест стека спрашивает версию не
        у того инструмента.
        """
        provider = providers.get(PROVIDER)

        self.assertEqual(provider.name, PROVIDER)
        self.assertEqual(type(provider).__name__, "CodexProvider")
        self.assertIs(providers.PROVIDERS[PROVIDER], provider)
        self.assertIn(providers.DEFAULT_PROVIDER, providers.PROVIDERS)
        self.assertEqual(providers.DEFAULT_PROVIDER, "claude")

        tools = providers.cli_tools()
        self.assertIn(PROVIDER, tools)
        self.assertEqual(tools[PROVIDER].name, PROVIDER)
        self.assertEqual(tuple(tools[PROVIDER].minimum), CLI_MINIMUM)


if __name__ == "__main__":
    unittest.main()
