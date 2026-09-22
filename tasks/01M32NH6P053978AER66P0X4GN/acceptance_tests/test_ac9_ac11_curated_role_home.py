"""AC-9..AC-11: курируемый дом роли `codex` — содержимое `config.toml`,
объяснение механики в `AGENTS.md`, пара «референс -> развёрнутый каталог»
и сверка развёрнутого слоя, замечающая расхождение ЛЮБОГО из двух домов.

Красен до реализации: каталога `docs/reference/role-home/codex/` в
репозитории ещё нет, `CodexProvider.home_reference()` не существует, а
сверка развёрнутого слоя смотрит только на провайдера по умолчанию.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import catalog, config, doctor, providers  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

from _codex import (DISABLED_FEATURES, PROVIDER,  # noqa: E402
                    normalized, role_home_reference_dir, toml_pairs,
                    toml_sections)

DEPLOYED_HOME_DIR = ".codex"
CLAUDE_DEPLOYED_HOME_DIR = ".claude"

#: Механика курируемого дома, которую `AGENTS.md` обязан объяснить роли
#: (AC-10): чей это HOME, что он эфемерен, откуда приходит ключ.
AGENTS_MARKERS = (".artel/home", "эфемер", "OPENAI_API_KEY")


class CuratedConfigTest(unittest.TestCase):
    """Референс `docs/reference/role-home/codex/` — читается из
    репозитория, песочница временного корня здесь не нужна и мешала бы:
    предмет критерия — файл, который лежит в git."""

    def curated_text(self, name: str) -> str:
        path = role_home_reference_dir() / name
        self.assertTrue(path.is_file(), f"{path} не заведён")
        return path.read_text(encoding="utf-8")

    def test_ac9_config_toml_disables_network_approvals_features_and_mcp(self):
        """`config.toml` курируемого дома несёт выключенную сеть
        песочницы, политику подтверждений «никогда», `false` на каждую из
        одиннадцати функций, ни одного MCP-сервера и ни одного ключа
        выбора модели.

        Ловит мутацию: в дом роли переехал ключ выбора модели («чтобы не
        забыть») — модель шага задаёт ярус локального слоя и флаг `-m`, и
        файл начал бы молча перебивать выбор пульта; либо в перечне
        функций выключена не вся одиннадцатка, и оставшаяся
        `computer_use`/`browser_use` доступна роли ровно тем путём,
        который нашёлся живым запуском 0.155.1.
        """
        text = self.curated_text("config.toml")
        pairs = toml_pairs(text)
        values = {key: normalized(value) for key, value in pairs}
        by_leaf = {}
        for key, value in pairs:
            by_leaf.setdefault(key.rsplit(".", 1)[-1], []).append(
                normalized(value))

        network = [k for k, v in values.items()
                   if "network" in k and v == "false"]
        self.assertTrue(network, f"сеть песочницы не выключена: {values}")
        self.assertIn("never", values.values(),
                      f"политика подтверждений не «никогда»: {values}")

        for feature in DISABLED_FEATURES:
            with self.subTest(feature=feature):
                self.assertIn("false", by_leaf.get(feature, []),
                              f"функция {feature} не выключена")

        mcp = [name for name in toml_sections(text) if "mcp" in name.lower()]
        mcp += [key for key in values if "mcp_server" in key.lower()]
        self.assertEqual(mcp, [], "в доме роли описан MCP-сервер")

        self.assertNotIn("model", by_leaf,
                         "в доме роли задан ключ выбора модели")

    def test_ac10_agents_md_explains_the_curated_home_mechanics(self):
        """`AGENTS.md` курируемого дома существует и объясняет роли
        механику дома: чей это HOME (адрес курируемого слоя), что он
        эфемерен, откуда приходит ключ.

        Ловит мутацию: файл заведён заглушкой («правила роли») или
        скопирован у Claude без правки адресов — роль на Codex читает
        объяснение про чужой дом и чужой канал секрета, а курируемый слой
        остаётся необъяснённым ровно там, где ANSWER-1 нашёл попытку
        вызвать MCP-сервер Оператора.
        """
        text = self.curated_text("AGENTS.md")

        for marker in AGENTS_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker.lower(), text.lower(),
                              f"AGENTS.md не объясняет: {marker}")


class RoleHomeDeploymentTest(TmpRootTest):
    """Развёртывание и сверка двух домов роли — требование 5, AC-11."""

    def seed_reference(self, provider_name: str, file_name: str) -> Path:
        """Референс дома провайдера во ВРЕМЕННОМ корне песочницы: предмет
        критерия — развёртывание и сверка, а не содержимое файла."""
        reference = providers.get(provider_name).home_reference().reference
        reference.mkdir(parents=True, exist_ok=True)
        path = reference / file_name
        path.write_text("# курируемый слой\n", encoding="utf-8")
        return path

    def test_ac11_both_homes_are_deployed_and_either_drift_turns_it_yellow(self):
        """`home_reference()` провайдера `codex` отдаёт каталог
        `docs/reference/role-home/codex` и имя развёрнутого каталога
        `.codex`; развёртывание на пустом `.artel/home` создаёт И
        `.artel/home/.claude/`, И `.artel/home/.codex/`; сверка
        развёрнутого слоя с референсом жёлтая, когда расходится дом
        `codex`.

        Ловит мутацию: развёртывание и сверка по-прежнему спрашивают
        только провайдера по умолчанию (`providers.default()`) — второй
        дом либо не разворачивается вовсе, либо разворачивается, но его
        расхождение с референсом никто не замечает: Оператор правит
        `.artel/home/.codex/config.toml` руками, изоляция роли тихо
        разъезжается с обещанием репозитория, и `doctor` остаётся
        зелёным.
        """
        home = providers.get(PROVIDER).home_reference()

        self.assertEqual(home.deployed_name, DEPLOYED_HOME_DIR)
        self.assertEqual(home.reference, config.ROOT / "docs" / "reference"
                         / "role-home" / PROVIDER)

        self.seed_reference("claude", "CLAUDE.md")
        self.seed_reference(PROVIDER, "AGENTS.md")

        self.capture(catalog.cmd_init)

        deployed_claude = config.ROLE_HOME / CLAUDE_DEPLOYED_HOME_DIR
        deployed_codex = config.ROLE_HOME / DEPLOYED_HOME_DIR
        self.assertTrue(deployed_claude.is_dir(),
                        list(config.ROLE_HOME.rglob("*")))
        self.assertTrue(deployed_codex.is_dir(),
                        list(config.ROLE_HOME.rglob("*")))

        self.assertEqual(self.drift_checks(), [], "сверка не сошлась до правки")

        (deployed_codex / "AGENTS.md").write_text("# правка Оператора\n",
                                                  encoding="utf-8")

        drifted = self.drift_checks()
        self.assertTrue(drifted, "расхождение дома codex осталось незамеченным")
        self.assertTrue(any(DEPLOYED_HOME_DIR in c.detail for c in drifted),
                        [c.detail for c in drifted])

    def drift_checks(self) -> list:
        """Жёлтые строки сверки дома роли — общей зеро-арг сверкой
        `doctor` И проверкой дома каждого провайдера реестра: критерий
        говорит про СВЕРКУ, не про имя её носителя, а провайдеры вправе
        называть свои строки по-своему (AC-16)."""
        checks = [doctor.check_role_home_reference()]
        for provider in providers.PROVIDERS.values():
            checks.append(provider.check_home_reference())
        return [c for c in checks if c.status == "warn"]


if __name__ == "__main__":
    unittest.main()
